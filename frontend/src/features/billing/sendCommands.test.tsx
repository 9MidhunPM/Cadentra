/** Recovery fixtures verify client behavior, not actual SMTP delivery. */
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router';
import { afterEach, expect, it, vi } from 'vitest';
import { apiClient } from '../../lib';
import { InvoiceDetail } from './invoices';
import { createSendCommands, describeEmailStatus, sendStorageKey } from './sendCommands';
import type { Invoice } from './types';
vi.mock('../../lib', async importOriginal => ({
  ...await importOriginal<typeof import('../../lib')>(),
  useSession: () => ({ actor: { id: 'send-ui-actor', role: 'STAFF', name: 'Staff', customer_id: null } }),
}));
const scope = { actor: 'send-store-actor', invoice: 'send-invoice' };
afterEach(() => { vi.restoreAllMocks(); sessionStorage.clear(); });
it('retains the same send key through a lost response, remount and reload without sending automatically', () => {
  const store = createSendCommands();
  expect(store.begin(scope, 'original-key')).toBe('original-key');
  store.uncertain(scope, 'original-key', new Error('Response lost'));
  const reloaded = createSendCommands();
  expect(reloaded.get(scope).phase).toBe('uncertain');
  expect(reloaded.begin(scope, 'replacement-key')).toBe('original-key');
  expect(reloaded.begin(scope, 'duplicate-key')).toBeNull();
  expect(JSON.parse(sessionStorage.getItem(sendStorageKey(scope))!)).toEqual({ ...scope, requestKey: 'original-key' });
});
it.each(['PENDING', 'SENDING', 'SENT', 'FAILED'] as const)('replays actual %s acknowledgement before allowing an explicit new request', status => {
  const store = createSendCommands(); store.begin(scope, 'same-key');
  expect(store.acknowledge(scope, 'same-key', { outbox_id: 'outbox', email_status: status })).toBe(true);
  expect(store.get(scope).receipt?.email_status).toBe(status);
  expect(sessionStorage.getItem(sendStorageKey(scope))).toBeNull();
  expect(store.begin(scope, 'explicit-new-key')).toBe('explicit-new-key');
  if (status === 'SENT') expect(describeEmailStatus(status)).toMatch(/accepted by SMTP; external delivery is unverified/);
});
it('retains an uncertain key for malformed responses or a stale acknowledgement', () => {
  const store = createSendCommands(); store.begin(scope, 'retained');
  expect(store.acknowledge(scope, 'different', { outbox_id: 'outbox', email_status: 'SENT' })).toBe(false);
  expect(store.acknowledge(scope, 'retained', { outbox_id: 'outbox', email_status: 'DELIVERED' })).toBe(false);
  expect(store.get(scope).phase).toBe('uncertain');
  expect(createSendCommands().get(scope).requestKey).toBe('retained');
});
it('isolates actor/invoice scopes and fails closed when persistence is unavailable', () => {
  const store = createSendCommands(); store.begin(scope, 'original');
  expect(store.get({ ...scope, actor: 'another-actor' }).requestKey).toBeNull();
  expect(store.get({ ...scope, invoice: 'another-invoice' }).requestKey).toBeNull();
  expect(createSendCommands().get(scope).requestKey).toBe('original');
  const broken = createSendCommands(() => { throw new Error('Storage blocked'); });
  expect(broken.begin(scope, 'never-sent')).toBeNull();
  expect(broken.get(scope).phase).toBe('storage_error');
});
it('blocks sending if writes fail and blocks new keys if acknowledged retention cannot be cleared', () => {
  const writeBlocked: Storage = { length: 0, key: () => null, clear: () => undefined, getItem: () => null, removeItem: () => undefined, setItem: () => { throw new Error('Quota exceeded'); } };
  const blocked = createSendCommands(() => writeBlocked);
  expect(blocked.begin(scope, 'not-sent')).toBeNull();
  expect(blocked.get(scope).phase).toBe('storage_error');
  let retained: string | null = null;
  const clearBlocked: Storage = { length: 1, key: () => 'retained', clear: () => undefined, getItem: () => retained, setItem: (_key, value) => { retained = value; }, removeItem: () => { throw new Error('Storage blocked'); } };
  const store = createSendCommands(() => clearBlocked);
  store.begin(scope, 'acknowledged-key');
  expect(store.acknowledge(scope, 'acknowledged-key', { outbox_id: 'existing', email_status: 'SENT' })).toBe(false);
  expect(store.get(scope).receipt?.email_status).toBe('SENT');
  expect(store.begin(scope, 'must-not-replace')).toBeNull();
  expect(retained).toContain('acknowledged-key');
});
it('keeps uncertain UI sends across remount and shows replay status instead of claiming a new email was queued', async () => {
  const invoice: Invoice = { id: 'ui-invoice', number: 'INV-SEND', customer_id: 'customer', status: 'CONFIRMED', collection_status: 'UNPAID', currency: 'INR', invoice_date: '2026-10-31', due_date: '2026-11-07', period_start: '2026-10-31', period_end: '2026-11-30', subtotal: '100.00', discount_total: '0.00', tax_total: '0.00', total: '100.00', paid_amount: '0.00', balance_due: '100.00', payments: [] };
  const sent: unknown[] = [];
  vi.spyOn(apiClient, 'request').mockImplementation(async (path, options) => {
    if (path.endsWith('/send')) {
      sent.push(options?.json);
      if (sent.length === 1) throw new Error('Response lost after acceptance');
      return { data: { outbox_id: 'existing-outbox', email_status: sent.length === 2 ? 'FAILED' : 'SENT' } };
    }
    return { data: invoice };
  });
  const mount = () => render(<MemoryRouter initialEntries={['/billing/invoices/ui-invoice']}><Routes><Route path="/billing/invoices/:id" element={<InvoiceDetail />} /></Routes></MemoryRouter>);
  const user = userEvent.setup(); const first = mount();
  await user.click(await screen.findByRole('button', { name: 'Queue invoice email' }));
  expect(await screen.findByText(/request result is uncertain/)).toBeInTheDocument();
  first.unmount(); mount();
  await screen.findByRole('button', { name: 'Retry same invoice email request' });
  expect(sent).toHaveLength(1);
  await user.click(screen.getByRole('button', { name: 'Retry same invoice email request' }));
  expect(await screen.findByText(/Last send acknowledgement: FAILED/)).toBeInTheDocument();
  expect(sent[1]).toEqual(sent[0]);
  await user.click(screen.getByRole('button', { name: 'Queue another invoice email' }));
  await waitFor(() => expect(sent).toHaveLength(3));
  expect(sent[2]).not.toEqual(sent[0]);
  expect(await screen.findByText(/Last send acknowledgement: SENT/)).toHaveTextContent('external delivery is unverified');
});
