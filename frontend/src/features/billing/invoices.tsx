import { useRef, useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router';
import { apiClient, getErrorMessage, useSession, type ListResponse, type ResourceResponse } from '../../lib';
import { Button, ConfirmDialog, DataTable, DateLabel, ErrorPanel, FormField, LoadingSkeleton, Money, PageHeader, StatusBadge } from '../../components/ui';
import { fieldError, useResource } from './resource';
import type { BillingRun, Invoice } from './types';
import { PaymentForm } from './payments';
import { sendCommands, useSendCommand, describeEmailStatus } from './sendCommands';
export { PaymentForm };

export function InvoiceList() {
  const [searchParams, setSearchParams] = useSearchParams();
  const rawPage = searchParams.get('page') ?? '1';
  const parsedPage = Number(rawPage);
  const page = /^\d+$/.test(rawPage) && Number.isSafeInteger(parsedPage) && parsedPage >= 1 ? parsedPage : 1;
  const [customerSearch, setCustomerSearch] = useState('');
  const customers = useResource<ListResponse<{ id: string; display_name: string }>>(`/customers?page_size=100&q=${encodeURIComponent(customerSearch)}`);
  const filterKeys = ['customer_id', 'status', 'overdue', 'from', 'to'] as const;
  type FilterKey = typeof filterKeys[number];
  const filters = Object.fromEntries(filterKeys.map(key => [key, searchParams.get(key) ?? ''])) as Record<FilterKey, string>;
  function updateQuery(changes: Partial<Record<FilterKey, string>>, nextPage = 1) {
    setSearchParams(previous => {
      const next = new URLSearchParams();
      for (const key of filterKeys) {
        const value = changes[key] ?? previous.get(key) ?? '';
        if (value) next.set(key, value);
      }
      next.set('page', String(nextPage));
      return next;
    });
  }
  const setPage = (nextPage: number) => updateQuery({}, nextPage);
  const query = new URLSearchParams({ page: String(page), page_size: '25' });
  Object.entries(filters).forEach(([key, value]) => { if (value) query.set(key, value); });
  const resource = useResource<ListResponse<Invoice>>(`/invoices?${query}`);
  const [pending, setPending] = useState(false);
  const lock = useRef(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState<unknown>(null);
  async function runDue() {
    if (lock.current) return;
    lock.current = true; setPending(true); setError(null); setMessage('');
    try {
      const { data } = await apiClient.request<ResourceResponse<BillingRun>>('/billing/run-due', { method: 'POST' });
      setMessage(`${data.invoices_created} invoices created; ${data.paused_periods} paused periods; ${data.failed_subscription_count} subscriptions failed.${data.has_more_due ? ' More periods remain: run billing again to continue.' : ''}`);
      resource.reload();
    } catch (failure) { setError(failure); }
    finally { lock.current = false; setPending(false); }
  }
  return <section><PageHeader eyebrow="Billing" title="Invoices" description="Stored charges, payments and outstanding balances." actions={<Button pending={pending} onClick={() => void runDue()}>Run due billing</Button>} />
    <form className="billing-filters" onSubmit={event => event.preventDefault()}>
      <FormField id="invoice-customer-search" label="Find customer"><input value={customerSearch} onChange={event => setCustomerSearch(event.target.value)} /></FormField>
      <FormField id="invoice-customer" label="Customer"><select value={filters.customer_id} onChange={event => updateQuery({ customer_id: event.target.value })}><option value="">All customers</option>{filters.customer_id && !customers.data?.items.some(customer => customer.id === filters.customer_id) && <option value={filters.customer_id}>Selected customer</option>}{customers.data?.items.map(customer => <option key={customer.id} value={customer.id}>{customer.display_name}</option>)}</select></FormField>
      <FormField id="invoice-status" label="Invoice status"><select value={filters.status} onChange={event => updateQuery({ status: event.target.value })}><option value="">All statuses</option>{['DRAFT', 'CONFIRMED', 'PAID', 'CANCELLED'].map(status => <option key={status}>{status}</option>)}</select></FormField>
      <FormField id="invoice-overdue" label="Collection"><select value={filters.overdue} onChange={event => updateQuery({ overdue: event.target.value })}><option value="">All invoices</option><option value="true">Overdue only</option><option value="false">Not overdue</option></select></FormField>
      <FormField id="invoice-from" label="Invoice date from"><input type="date" value={filters.from} onChange={event => updateQuery({ from: event.target.value })} /></FormField>
      <FormField id="invoice-to" label="Invoice date before"><input type="date" value={filters.to} onChange={event => updateQuery({ to: event.target.value })} /></FormField>
    </form>
    {customers.error != null && <ErrorPanel title="Customer search unavailable" message={getErrorMessage(customers.error)} onRetry={customers.reload} />}
    {message && <p role="status">{message}</p>}{error != null && <ErrorPanel message={getErrorMessage(error)} />}
    {resource.loading && <LoadingSkeleton label="Loading invoices" />}{resource.error != null && <ErrorPanel message={getErrorMessage(resource.error)} onRetry={resource.reload} />}
    {resource.data && <DataTable rows={resource.data.items} getRowKey={row => row.id} page={page} pageSize={resource.data.page_size} total={resource.data.total} onPageChange={setPage} caption="Invoices" emptyTitle="No invoices match these filters" columns={[
      { key: 'number', header: 'Invoice', render: row => <Link to={`/billing/invoices/${row.id}`}>{row.number}</Link> },
      { key: 'customer', header: 'Customer', render: row => row.customer_snapshot?.display_name ?? row.customer_id },
      { key: 'status', header: 'Status', render: row => <><StatusBadge status={row.collection_status || row.status} />{row.overdue && <StatusBadge status="OVERDUE" />}</> },
      { key: 'due', header: 'Due', render: row => <DateLabel value={row.due_date} /> },
      { key: 'total', header: 'Total', render: row => <Money amount={row.total} currency={row.currency} /> },
      { key: 'balance', header: 'Balance', render: row => <Money amount={row.balance_due} currency={row.currency} /> },
    ]} />}
  </section>;
}

export function InvoiceDetail() {
  const { id = '' } = useParams();
  const { actor } = useSession();
  if (!actor) return <p>Sign in to view this invoice.</p>;
  return <InvoiceRecord key={`${actor.id}:${id}`} id={id} actorId={actor.id} />;
}

function InvoiceRecord({ id, actorId }: { id: string; actorId: string }) {
  const resource = useResource<ResourceResponse<Invoice>>(`/invoices/${encodeURIComponent(id)}`);
  const [pending, setPending] = useState(false);
  const lock = useRef(false);
  const sendScope = { actor: actorId, invoice: id };
  const send = useSendCommand(sendScope);
  const [message, setMessage] = useState('');
  const [error, setError] = useState<unknown>(null);
  const [reason, setReason] = useState('');
  async function action(name: 'confirm' | 'cancel') {
    if (lock.current) return;
    lock.current = true; setPending(true); setError(null); setMessage('');
    try {
      await apiClient.request(`/invoices/${id}/${name}`, { method: 'POST', json: name === 'cancel' ? { reason } : undefined });
      setMessage(`Invoice ${name === 'confirm' ? 'confirmed' : 'cancelled'}.`);
      resource.reload();
    } catch (failure) { setError(failure); throw failure; }
    finally { lock.current = false; setPending(false); }
  }
  async function sendInvoice() {
    if (lock.current) return;
    const requestKey = sendCommands.begin(sendScope, crypto.randomUUID());
    if (!requestKey) return;
    lock.current = true; setPending(true);
    try {
      const { data } = await apiClient.request<ResourceResponse<unknown>>(`/invoices/${encodeURIComponent(id)}/send`, { method: 'POST', json: { request_key: requestKey } });
      if (sendCommands.acknowledge(sendScope, requestKey, data)) resource.reload();
    } catch (failure) { sendCommands.uncertain(sendScope, requestKey, failure); }
    finally { lock.current = false; setPending(false); }
  }
  const invoice = resource.data?.data;
  return <section><PageHeader eyebrow="Billing" title={invoice?.number ?? 'Invoice details'} description="Immutable charges and recorded payments." actions={<Link to="/billing/invoices">All invoices</Link>} />
    {resource.loading && <LoadingSkeleton label="Loading invoice" />}{resource.error != null && <ErrorPanel message={getErrorMessage(resource.error)} onRetry={resource.reload} />}{message && <p role="status">{message}</p>}{error != null && <ErrorPanel message={getErrorMessage(error)} />}
    {invoice && <>
      <div className="billing-card"><div className="ui-actions"><StatusBadge status={invoice.status} />{invoice.collection_status !== invoice.status && <StatusBadge status={invoice.collection_status} />}{invoice.overdue && <StatusBadge status="OVERDUE" />}</div><p>{invoice.customer_snapshot?.display_name ?? invoice.customer_id}</p><p>Service: <DateLabel value={invoice.period_start} /> to <DateLabel value={invoice.period_end} /> (end excluded)</p><p>Issued <DateLabel value={invoice.invoice_date} /> · Due <DateLabel value={invoice.due_date} /></p><p>Email: {invoice.email_status === 'SENT' ? <span>Accepted by SMTP (external delivery unverified)</span> : <StatusBadge status={invoice.email_status ?? 'NOT_REQUESTED'} />}</p>
      <div className="ui-actions">{invoice.status === 'DRAFT' && <ConfirmDialog title="Confirm this invoice?" description="Confirming makes this stored invoice payable." trigger={<Button disabled={pending}>Confirm invoice</Button>} onConfirm={() => action('confirm')} />}
      {(['CONFIRMED', 'PAID'].includes(invoice.status) || send.requestKey) && <Button variant="secondary" pending={pending} disabled={send.phase === 'storage_error' || send.phase === 'pending'} onClick={() => void sendInvoice()}>{send.requestKey ? 'Retry same invoice email request' : send.phase === 'acknowledged' ? 'Queue another invoice email' : 'Queue invoice email'}</Button>}
      <a className="ui-button ui-button--secondary" href={`/api/v1/invoices/${encodeURIComponent(invoice.id)}/print`} target="_blank" rel="noopener noreferrer">Print invoice</a></div></div>
      {send.phase === 'pending' && <p role="status">This retained email request is in progress.</p>}
      {send.phase === 'uncertain' && <p role="status">The email request result is uncertain. Its request key is retained across reload. Retry the same request to check its recorded status; no email is sent automatically.</p>}
      {send.receipt && <p role="status">Last send acknowledgement: {describeEmailStatus(send.receipt.email_status)}</p>}
      {send.error != null && <ErrorPanel message={getErrorMessage(send.error)} />}
      {send.phase === 'storage_error' && <p role="alert">Invoice email recovery storage is unavailable or invalid. Sending is blocked. Restore session storage and reload before retrying.</p>}
      <h2>Stored invoice lines</h2><p className="ui-muted billing-scroll-hint">Scroll the line table horizontally to view every charge.</p><div className="ui-table-panel"><div className="ui-table-scroll" role="region" aria-label="Stored invoice lines" tabIndex={0}><table className="ui-table billing-invoice-lines"><caption className="ui-sr-only">Stored invoice lines</caption><thead><tr><th>Description</th><th>Quantity</th><th>Unit price</th><th>Discount</th><th>Tax</th><th>Total</th></tr></thead><tbody>{invoice.lines?.map(line => <tr key={line.id}><td>{line.description}{line.taxes?.map((tax, index) => <small className="billing-tax" key={index}>{tax.name} ({tax.rate_percent}%): <Money amount={tax.amount} currency={invoice.currency} /></small>)}</td><td>{line.quantity}</td><td><Money amount={line.unit_price} currency={invoice.currency} /></td><td><Money amount={line.discount} currency={invoice.currency} /></td><td><Money amount={line.tax_total} currency={invoice.currency} /></td><td><Money amount={line.total} currency={invoice.currency} /></td></tr>)}</tbody></table></div></div>
      <dl className="billing-totals">{([['Subtotal', invoice.subtotal], ['Discount', invoice.discount_total], ['Tax', invoice.tax_total], ['Total', invoice.total], ['Paid', invoice.paid_amount], ['Balance due', invoice.balance_due]] as const).map(([label, amount]) => <div key={label}><dt>{label}</dt><dd><Money amount={amount} currency={invoice.currency} /></dd></div>)}</dl>
      <h2>Payment history</h2><DataTable rows={invoice.payments ?? []} columns={[{ key: 'date', header: 'Paid on', render: row => <DateLabel value={row.paid_on} /> }, { key: 'method', header: 'Method', render: row => row.method }, { key: 'amount', header: 'Amount', render: row => <Money amount={row.amount} currency={invoice.currency} /> }]} getRowKey={row => row.id} page={1} pageSize={Math.max(1, invoice.payments?.length ?? 0)} total={invoice.payments?.length ?? 0} onPageChange={() => undefined} caption="Payments" emptyTitle="No payments recorded" />
      {['CONFIRMED', 'PAID'].includes(invoice.status) && <PaymentForm invoice={invoice} onSaved={detail => resource.replace({ data: detail })} />}
      {['DRAFT', 'CONFIRMED'].includes(invoice.status) && (invoice.payments?.length ?? 0) === 0 && <div className="billing-card"><h2>Cancel invoice</h2><FormField error={fieldError(error, 'reason')} id="cancel-reason" label="Cancellation reason"><textarea value={reason} onChange={event => setReason(event.target.value)} /></FormField><ConfirmDialog title="Cancel this invoice?" description="This preserves the period and discount history. It cannot be automatically invoiced again." trigger={<Button variant="danger" disabled={pending || !reason.trim()}>Cancel invoice</Button>} onConfirm={() => action('cancel')} /></div>}
    </>}
  </section>;
}
