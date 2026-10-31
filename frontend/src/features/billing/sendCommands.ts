import { useSyncExternalStore } from 'react';
export interface SendScope { actor: string; invoice: string }
export type EmailStatus = 'PENDING' | 'SENDING' | 'SENT' | 'FAILED';
export interface SendReceipt { outbox_id: string; email_status: EmailStatus }
interface Entry { phase: 'idle' | 'pending' | 'uncertain' | 'acknowledged' | 'storage_error'; requestKey: string | null; receipt?: SendReceipt; error?: unknown }
export function sendStorageKey(scope: SendScope) { return `cadentra.billing.send.${encodeURIComponent(JSON.stringify([scope.actor, scope.invoice]))}`; }
function validKey(value: unknown): value is string { return typeof value === 'string' && value.length > 0 && value.length <= 128; }
export function createSendCommands(storage: () => Storage = () => sessionStorage) {
  const entries = new Map<string, Entry>();
  const listeners = new Set<() => void>();
  function publish(scope: SendScope, entry: Entry) { entries.set(sendStorageKey(scope), entry); listeners.forEach(listener => listener()); }
  function load(scope: SendScope): Entry {
    const key = sendStorageKey(scope);
    if (entries.has(key)) return entries.get(key)!;
    let entry: Entry = { phase: 'idle', requestKey: null };
    try {
      const raw = storage().getItem(key);
      if (raw !== null) {
        const record = JSON.parse(raw);
        if (record.actor !== scope.actor || record.invoice !== scope.invoice || !validKey(record.requestKey)) throw new Error('Invalid retained invoice send');
        entry = { phase: 'uncertain', requestKey: record.requestKey };
      }
    } catch { entry = { phase: 'storage_error', requestKey: null }; }
    entries.set(key, entry); return entry;
  }
  return {
    get: load,
    subscribe(listener: () => void) { listeners.add(listener); return () => { listeners.delete(listener); }; },
    begin(scope: SendScope, proposed: string): string | null {
      const current = load(scope);
      if (!['idle', 'uncertain', 'acknowledged'].includes(current.phase)) return null;
      const requestKey = current.requestKey ?? proposed;
      if (!validKey(requestKey)) return null;
      try {
        const raw = JSON.stringify({ ...scope, requestKey });
        storage().setItem(sendStorageKey(scope), raw);
        if (storage().getItem(sendStorageKey(scope)) !== raw) throw new Error('Send retention failed');
      } catch {
        publish(scope, { phase: 'storage_error', requestKey: current.requestKey, error: new Error('Cannot safely retain this email request. No request was sent. Restore session storage and reload.') }); return null;
      }
      publish(scope, { phase: 'pending', requestKey }); return requestKey;
    },
    uncertain(scope: SendScope, requestKey: string, error: unknown) {
      const current = load(scope);
      if (current.phase === 'pending' && current.requestKey === requestKey) publish(scope, { ...current, phase: 'uncertain', error });
    },
    acknowledge(scope: SendScope, requestKey: string, value: unknown): boolean {
      const current = load(scope);
      if (current.phase !== 'pending' || current.requestKey !== requestKey) return false;
      const response = value as Partial<SendReceipt> & { status?: string } | null;
      const status = response?.email_status ?? response?.status;
      if (!response || typeof response.outbox_id !== 'string' || !response.outbox_id || !['PENDING', 'SENDING', 'SENT', 'FAILED'].includes(status ?? '')) {
        publish(scope, { ...current, phase: 'uncertain', error: new Error('The send acknowledgement was invalid. Retry the retained request key.') }); return false;
      }
      const receipt = { outbox_id: response.outbox_id, email_status: status as EmailStatus };
      try {
        storage().removeItem(sendStorageKey(scope));
        if (storage().getItem(sendStorageKey(scope)) !== null) throw new Error('Send retention could not be cleared');
      } catch { publish(scope, { ...current, phase: 'storage_error', receipt }); return false; }
      publish(scope, { phase: 'acknowledged', requestKey: null, receipt }); return true;
    },
  };
}
export const sendCommands = createSendCommands();
export function useSendCommand(scope: SendScope) { return useSyncExternalStore(sendCommands.subscribe, () => sendCommands.get(scope)); }
export function describeEmailStatus(status: EmailStatus): string {
  return { PENDING: 'PENDING — email is queued.', SENDING: 'SENDING — email submission is in progress.', SENT: 'SENT — accepted by SMTP; external delivery is unverified.', FAILED: 'FAILED — the server recorded an email submission failure.' }[status];
}
