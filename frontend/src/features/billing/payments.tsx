import { useEffect, useRef, useState, type FormEvent } from 'react';
import { apiClient, ApiError, getErrorMessage, useSession, type ResourceResponse } from '../../lib';
import { Button, ErrorPanel, FormField, Money } from '../../components/ui';
import { paymentCommands, usePaymentCommand, type PaymentCommand, type PaymentScope } from './paymentCommands';
import { paymentMethods } from './paymentMethods';
import { fieldError } from './resource';
import type { Invoice } from './types';
interface Draft { method: string; amount: string; paid_on: string; note: string; external_reference: string }
export function PaymentForm({ invoice, onSaved }: { invoice: Invoice; onSaved: (invoice: Invoice) => void }) {
  const { actor } = useSession();
  if (!actor || !['ADMIN', 'STAFF'].includes(actor.role)) return null;
  return <ScopedPaymentForm key={`${actor.id}:${invoice.id}`} scope={{ actor: actor.id, invoice: invoice.id }} invoice={invoice} onSaved={onSaved} />;
}
function ScopedPaymentForm({ scope, invoice, onSaved }: { scope: PaymentScope; invoice: Invoice; onSaved: (invoice: Invoice) => void }) {
  const command = usePaymentCommand(scope);
  const [draft, setDraft] = useState<Draft>({ method: 'BANK_TRANSFER', amount: '', paid_on: '', note: '', external_reference: '' });
  const [readError, setReadError] = useState<unknown>(null);
  const [reading, setReading] = useState(false);
  const readLock = useRef(false);
  const retained = command.command;
  const shown = retained ? { ...retained, external_reference: retained.external_reference ?? '' } : draft;
  const blocked = command.phase !== 'idle';
  const pending = command.phase === 'pending';
  const actorId = scope.actor; const invoiceId = scope.invoice;
  useEffect(() => {
    if (command.phase !== 'refresh') return;
    const abort = new AbortController(); const version = command.version;
    const original = { actor: actorId, invoice: invoiceId };
    void apiClient.request<ResourceResponse<Invoice>>(`/invoices/${invoiceId}`, { signal: abort.signal }).then(({ data }) => {
      if (abort.signal.aborted) return;
      if (!paymentCommands.reconcile(original, version, data)) { setReadError(new ApiError(0, 'PAYMENT_UNVERIFIED', 'The retained payment is not yet verified in fresh payment history. Check again or retry the same request.')); return; }
      setDraft(value => ({ ...value, amount: '', note: '', external_reference: '' })); onSaved(data);
    }).catch(error => { if (!abort.signal.aborted) setReadError(error); });
    return () => abort.abort();
  }, [command.phase, command.version, actorId, invoiceId, onSaved]);
  async function checkHistory() {
    if (readLock.current || paymentCommands.get(scope).phase === 'pending') return;
    const version = paymentCommands.get(scope).version;
    readLock.current = true; setReading(true); setReadError(null);
    try {
      const { data } = await apiClient.request<ResourceResponse<Invoice>>(`/invoices/${invoice.id}`);
      if (paymentCommands.reconcile(scope, version, data)) { setDraft({ ...draft, amount: '', note: '', external_reference: '' }); onSaved(data); }
      else setReadError(new ApiError(0, 'PAYMENT_UNVERIFIED', 'No matching retained payment was verified. Keep this command and retry its same request key.'));
    } catch (error) { setReadError(error); }
    finally { readLock.current = false; setReading(false); }
  }
  async function submit(event: FormEvent) {
    event.preventDefault();
    const current = paymentCommands.get(scope);
    if (!['idle', 'uncertain'].includes(current.phase) || (current.phase === 'idle' && invoice.status !== 'CONFIRMED')) return;
    const proposed: PaymentCommand = { ...draft, external_reference: draft.external_reference || null, request_key: current.command?.request_key ?? crypto.randomUUID() };
    const body = paymentCommands.begin(scope, proposed);
    if (!body) return;
    setReadError(null);
    try {
      await apiClient.request(`/invoices/${invoice.id}/payments`, { method: 'POST', json: body });
      paymentCommands.settle(scope, 'refresh');
    } catch (error) {
      const rejected = current.phase === 'idle' && error instanceof ApiError && error.status >= 400 && error.status < 500 && error.status !== 408 && !['INVALID_RESPONSE', 'NETWORK_ERROR'].includes(error.code);
      paymentCommands.settle(scope, rejected ? 'rejected' : 'uncertain', error);
    }
  }
  if (invoice.status !== 'CONFIRMED' && command.phase === 'idle') return null;
  return <form className="billing-card" onSubmit={event => void submit(event)}><h2>{invoice.status === 'CONFIRMED' ? 'Record a manual payment' : 'Recover a retained payment'}</h2><p className="ui-muted">Remaining balance: <Money amount={invoice.balance_due} currency={invoice.currency} />. This records a payment already received.</p>
    <fieldset disabled={blocked} className="billing-form-grid">
      <FormField error={fieldError(command.error, 'method')} id="payment-method" label="Payment method"><select value={shown.method} onChange={event => setDraft({ ...draft, method: event.target.value })}>{paymentMethods.map(({ code, label }) => <option key={code} value={code}>{label}</option>)}</select></FormField>
      <FormField error={fieldError(command.error, 'amount')} id="payment-amount" label="Amount" hint={`Enter ${invoice.currency} as a decimal amount.`}><input inputMode="decimal" pattern="[0-9]+([.][0-9]{1,2})?" required value={shown.amount} onChange={event => setDraft({ ...draft, amount: event.target.value })} /></FormField>
      <FormField error={fieldError(command.error, 'paid_on')} id="payment-date" label="Payment date"><input type="date" required value={shown.paid_on} onChange={event => setDraft({ ...draft, paid_on: event.target.value })} /></FormField>
      <FormField error={fieldError(command.error, 'external_reference')} id="payment-reference" label="External reference (optional)"><input value={shown.external_reference} onChange={event => setDraft({ ...draft, external_reference: event.target.value })} /></FormField>
      <FormField error={fieldError(command.error, 'note')} id="payment-note" label="Payment note" hint="Do not enter card data or bank credentials."><textarea required value={shown.note} onChange={event => setDraft({ ...draft, note: event.target.value })} /></FormField>
    </fieldset>
    {command.error != null && <ErrorPanel message={getErrorMessage(command.error)} />}{readError != null && <ErrorPanel message={getErrorMessage(readError)} />}
    {pending && <p role="status">This retained payment is still in progress. New payments and reconciliation are blocked until it settles.</p>}
    {command.phase === 'uncertain' && <p role="status">The result is uncertain. Its amount and request key are retained across navigation and reload. Check payment history or retry this same request.</p>}
    {command.phase === 'refresh' && <p role="status">Payment accepted. A fresh payment-history read must verify it before another payment is allowed.</p>}
    {command.phase === 'storage_error' && <p role="alert">Payment storage is unavailable or invalid. No new payment can be sent. Restore session storage and reload; do not re-enter a potentially recorded payment.</p>}
    <div className="ui-actions"><Button type="submit" pending={pending} disabled={!['idle', 'uncertain'].includes(command.phase)}>{retained ? 'Retry same payment' : 'Record payment'}</Button>
    {retained && !pending && <Button variant="secondary" pending={reading} onClick={() => void checkHistory()}>Check retained payment history</Button>}
    {command.phase === 'rejected' && <Button variant="secondary" onClick={() => { if (paymentCommands.rejectedEdit(scope)) { setDraft({ ...shown }); setReadError(null); } }}>Edit rejected payment</Button>}</div>
  </form>;
}
