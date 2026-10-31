import { afterEach, expect, it } from 'vitest';
import { createPaymentCommands, paymentStorageKey, type PaymentCommand } from './paymentCommands';
import type { Invoice } from './types';
const scope = { actor: 'store-actor', invoice: 'store-invoice' };
const command: PaymentCommand = { method: 'BANK_TRANSFER', amount: '2000.00', paid_on: '2026-10-31', note: 'Recorded transfer', external_reference: null, request_key: 'stable-request' };
const detail: Invoice = { id: scope.invoice, number: 'INV', customer_id: 'customer', status: 'CONFIRMED', collection_status: 'PARTIALLY_PAID', currency: 'INR', invoice_date: '2026-10-31', due_date: '2026-11-07', period_start: '2026-10-31', period_end: '2026-11-30', subtotal: '4970.16', discount_total: '0.00', tax_total: '0.00', total: '4970.16', paid_amount: '2000.00', balance_due: '2970.16', payments: [{ id: 'payment', invoice_id: scope.invoice, ...command }] };
afterEach(() => sessionStorage.clear());
it('hydrates a pending command as uncertain after a reload and preserves its same key and payload', () => {
  const original = createPaymentCommands();
  expect(original.begin(scope, command)).toEqual(command);
  const reloaded = createPaymentCommands();
  expect(reloaded.get(scope).phase).toBe('uncertain');
  expect(reloaded.begin(scope, { ...command, amount: '1.00', request_key: 'different' })).toEqual(command);
});
it('does not clear a pending or newer command using an older history read', () => {
  const store = createPaymentCommands(); store.begin(scope, command); store.settle(scope, 'uncertain');
  const oldVersion = store.get(scope).version;
  store.begin(scope);
  expect(store.reconcile(scope, oldVersion, detail)).toBe(false);
  expect(store.get(scope).phase).toBe('pending');
  store.settle(scope, 'refresh');
  expect(store.reconcile(scope, store.get(scope).version, { ...detail, payments: [] })).toBe(false);
  expect(store.reconcile(scope, store.get(scope).version, detail)).toBe(true);
  expect(sessionStorage.getItem(paymentStorageKey(scope))).toBeNull();
});
it('requires matching request key, invoice and normalized payload before clearing retention', () => {
  const store = createPaymentCommands(); store.begin(scope, command); store.settle(scope, 'refresh');
  expect(store.reconcile(scope, store.get(scope).version, { ...detail, payments: [{ ...detail.payments![0], amount: '1.00' }] })).toBe(false);
  expect(store.get(scope).command).toEqual(command);
});
it('does not load another actor command and fails closed on corrupt retained storage', () => {
  const store = createPaymentCommands(); store.begin(scope, command);
  expect(store.get({ ...scope, actor: 'other' }).command).toBeNull();
  sessionStorage.setItem(paymentStorageKey({ actor: 'corrupt', invoice: scope.invoice }), '{broken');
  const reloaded = createPaymentCommands();
  expect(reloaded.get({ actor: 'corrupt', invoice: scope.invoice }).phase).toBe('storage_error');
  expect(reloaded.begin({ actor: 'corrupt', invoice: scope.invoice }, command)).toBeNull();
});
