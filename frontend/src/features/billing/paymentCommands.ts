import { useSyncExternalStore } from 'react';
import type { Invoice } from './types';
export interface PaymentCommand { method: string; amount: string; paid_on: string; note: string; external_reference: string | null; request_key: string }
export interface PaymentScope { actor: string; invoice: string }
type Phase = 'idle' | 'pending' | 'uncertain' | 'refresh' | 'rejected' | 'storage_error';
interface Entry { phase: Phase; command: PaymentCommand | null; version: number; error?: unknown }
const methods = ['MANUAL', 'BANK_TRANSFER', 'UPI', 'CASH', 'CARD_EXTERNAL', 'OTHER'];
export function paymentStorageKey(scope: PaymentScope) { return `cadentra.billing.payment.${encodeURIComponent(JSON.stringify([scope.actor, scope.invoice]))}`; }
function validCommand(value: unknown): value is PaymentCommand {
  if (!value || typeof value !== 'object') return false;
  const c = value as Partial<PaymentCommand>;
  return typeof c.method === 'string' && methods.includes(c.method) && typeof c.amount === 'string' && /^\d+(?:\.\d{1,2})?$/.test(c.amount) && typeof c.paid_on === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(c.paid_on) && typeof c.note === 'string' && c.note.length <= 10000 && (c.external_reference === null || typeof c.external_reference === 'string') && typeof c.request_key === 'string' && c.request_key.length > 0 && c.request_key.length <= 128;
}
function canonicalMoney(value: string) { const [whole, fraction = ''] = value.split('.'); return `${whole.replace(/^0+(?=\d)/, '')}.${fraction.padEnd(2, '0')}`; }
export function createPaymentCommands(storage: () => Storage = () => sessionStorage) {
  const entries = new Map<string, Entry>();
  const listeners = new Set<() => void>();
  const publish = (scope: PaymentScope, next: Omit<Entry, 'version'>) => {
    const key = paymentStorageKey(scope);
    entries.set(key, { ...next, version: (entries.get(key)?.version ?? 0) + 1 });
    listeners.forEach(listener => listener());
  };
  function load(scope: PaymentScope): Entry {
    const key = paymentStorageKey(scope);
    if (entries.has(key)) return entries.get(key)!;
    let entry: Entry = { phase: 'idle', command: null, version: 0 };
    try {
      const raw = storage().getItem(key);
      if (raw !== null) {
        const record = JSON.parse(raw);
        if (record.actor !== scope.actor || record.invoice !== scope.invoice || !validCommand(record.command)) throw new Error('Invalid retained payment');
        entry = { phase: 'uncertain', command: Object.freeze({ ...record.command }), version: 0 };
      }
    } catch { entry = { phase: 'storage_error', command: null, version: 0 }; }
    entries.set(key, entry); return entry;
  }
  function persist(scope: PaymentScope, command: PaymentCommand) {
    const key = paymentStorageKey(scope);
    const raw = JSON.stringify({ ...scope, command });
    storage().setItem(key, raw);
    if (storage().getItem(key) !== raw) throw new Error('Payment retention failed');
  }
  function clear(scope: PaymentScope) {
    const key = paymentStorageKey(scope);
    storage().removeItem(key);
    if (storage().getItem(key) !== null) throw new Error('Payment retention could not be cleared');
  }
  return {
    get: load,
    subscribe(listener: () => void) { listeners.add(listener); return () => { listeners.delete(listener); }; },
    begin(scope: PaymentScope, proposed?: PaymentCommand): PaymentCommand | null {
      const current = load(scope);
      if (!['idle', 'uncertain'].includes(current.phase)) return null;
      const command = current.command ?? proposed;
      if (!validCommand(command)) return null;
      const retained = Object.freeze({ ...command });
      try { persist(scope, retained); }
      catch { publish(scope, { phase: 'storage_error', command: current.command, error: new Error('Cannot safely retain this payment. No request was sent. Restore session storage and reload.') }); return null; }
      publish(scope, { phase: 'pending', command: retained }); return retained;
    },
    settle(scope: PaymentScope, phase: 'refresh' | 'uncertain' | 'rejected', error?: unknown) {
      const current = load(scope);
      if (current.phase !== 'pending' || !current.command) return;
      // The original durable command is intentionally retained through settlement.
      publish(scope, { phase, command: current.command, error });
    },
    rejectedEdit(scope: PaymentScope) {
      const current = load(scope);
      if (current.phase !== 'rejected') return false;
      try { clear(scope); } catch { publish(scope, { ...current, phase: 'storage_error' }); return false; }
      publish(scope, { phase: 'idle', command: null }); return true;
    },
    reconcile(scope: PaymentScope, version: number, invoice: Invoice): boolean {
      const current = load(scope); const c = current.command;
      if (current.version !== version || current.phase === 'pending' || !c || invoice.id !== scope.invoice || !Array.isArray(invoice.payments)) return false;
      const match = invoice.payments.some(p => p.request_key === c.request_key && p.invoice_id === scope.invoice && p.method === c.method && canonicalMoney(p.amount) === canonicalMoney(c.amount) && p.paid_on === c.paid_on && p.note === c.note && (p.external_reference ?? null) === c.external_reference);
      if (!match) return false;
      try { clear(scope); } catch { publish(scope, { ...current, phase: 'storage_error' }); return false; }
      publish(scope, { phase: 'idle', command: null }); return true;
    },
  };
}
export const paymentCommands = createPaymentCommands();
export function usePaymentCommand(scope: PaymentScope) { return useSyncExternalStore(paymentCommands.subscribe, () => paymentCommands.get(scope)); }
