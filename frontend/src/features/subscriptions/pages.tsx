import { useState, type FormEvent } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router';
import { apiClient, ApiError, getErrorMessage, type ListResponse, type ResourceResponse } from '../../lib';
import { Button, DataTable, DateLabel, EmptyState, ErrorPanel, FormField, LoadingSkeleton, Money, PageHeader, StatusBadge, SubscriptionStepper } from '../../components/ui';
import { fieldError, SubscriptionForm } from './forms';
import type { Subscription, TaxRuleReference, Template } from './types';
import { useResource } from './useResource';

const states = ['DRAFT', 'QUOTATION', 'CONFIRMED', 'ACTIVE', 'CLOSED'];
function OptionalDate({ value }: { value?: string | null }) { return value ? <DateLabel value={value} /> : <span>—</span>; }
function TaxReferences({ taxes }: { taxes?: TaxRuleReference[] }) {
  return <span>{taxes === undefined ? 'Resolved on invoice' : taxes.length === 0 ? 'No applicable tax rules' : taxes.map(tax => `${tax.name} (${tax.rate_percent}%)`).join(', ')}</span>;
}

export function SubscriptionList() {
  const [params, setParams] = useSearchParams();
  const page = Math.max(1, Number(params.get('page')) || 1);
  const query = params.get('q') ?? ''; const state = params.get('state') ?? '';
  const [search, setSearch] = useState(query);
  const [filterState, setFilterState] = useState(state);
  const request = new URLSearchParams({ page: String(page), page_size: '25' });
  if (query) request.set('q', query); if (state) request.set('state', state);
  const [retry, setRetry] = useState(0);
  const resource = useResource<ListResponse<Subscription>>(`/subscriptions?${request}`, retry);
  function filter(event: FormEvent) { event.preventDefault(); setParams({ ...(search ? { q: search } : {}), ...(filterState ? { state: filterState } : {}), page: '1' }); }
  return <div className="subscription-stack"><PageHeader title="Subscriptions" description="Track agreed service, scheduled changes and the next billing cycle." actions={<div className="ui-actions"><Link to="/subscriptions/templates" className="ui-button ui-button--secondary">Templates</Link><Link to="/subscriptions/new" className="ui-button ui-button--primary">New subscription</Link></div>} />
    <form className="subscription-filter" onSubmit={filter}><FormField id="subscription-search" label="Search subscriptions"><input type="search" value={search} onChange={event => setSearch(event.target.value)} placeholder="Reference or customer" /></FormField><FormField id="subscription-state" label="State"><select value={filterState} onChange={event => setFilterState(event.target.value)}><option value="">All states</option>{states.map(item => <option key={item}>{item}</option>)}</select></FormField><Button type="submit" variant="secondary">Apply filters</Button></form>
    {resource.loading && <LoadingSkeleton label="Loading subscriptions" />}
    {resource.error !== undefined && <ErrorPanel message={getErrorMessage(resource.error)} onRetry={() => setRetry(value => value + 1)} />}
    {resource.data && <DataTable caption="Subscriptions" rows={resource.data.items} getRowKey={row => row.id} page={page} pageSize={25} total={resource.data.total} onPageChange={next => { const updated = new URLSearchParams(params); updated.set('page', String(next)); setParams(updated); }} emptyTitle="No subscriptions match these filters" columns={[
      { key: 'reference', header: 'Subscription', render: row => <Link className="subscription-link" to={`/subscriptions/${row.id}`}>{row.number}</Link> },
      { key: 'customer', header: 'Customer', render: row => row.customer_name ?? row.customer_id },
      { key: 'plan', header: 'Plan', render: row => row.plan_snapshot?.name ?? row.plan_id },
      { key: 'state', header: 'State', render: row => <div><StatusBadge status={row.state} />{row.paused && <p>Paused</p>}{row.expired && row.state !== 'CLOSED' && <p>Expired, closure pending</p>}</div> },
      { key: 'next', header: 'Next scheduled cycle', render: row => <OptionalDate value={row.next_billing_date} /> },
      { key: 'amount', header: 'Per-cycle subtotal · before tax and discounts', render: row => row.recurring_subtotal !== undefined ? <Money amount={row.recurring_subtotal} currency={row.currency} /> : '—' },
    ]} />}
  </div>;
}

export function TemplateList() {
  const [page, setPage] = useState(1); const [retry, setRetry] = useState(0);
  const resource = useResource<ListResponse<Template>>(`/quotation-templates?page=${page}&page_size=25`, retry);
  return <div className="subscription-stack"><PageHeader title="Quotation templates" description="Reusable plans and product selections. Editing a template never changes an existing quotation." actions={<div className="ui-actions"><Link className="subscription-link" to="/subscriptions">Subscriptions</Link><Link className="ui-button ui-button--primary" to="/subscriptions/templates/new">New template</Link></div>} />
    {resource.loading && <LoadingSkeleton label="Loading templates" />}{resource.error !== undefined && <ErrorPanel message={getErrorMessage(resource.error)} onRetry={() => setRetry(value => value + 1)} />}
    {resource.data && <DataTable caption="Quotation templates" rows={resource.data.items} getRowKey={row => row.id} page={page} pageSize={25} total={resource.data.total} onPageChange={setPage} emptyTitle="Create your first quotation template" columns={[
      { key: 'name', header: 'Template', render: row => <Link className="subscription-link" to={`/subscriptions/templates/${row.id}/edit`}>{row.name}</Link> },
      { key: 'plan', header: 'Plan', render: row => row.plan_id },
      { key: 'validity', header: 'Validity', render: row => `${row.valid_days} days` },
      { key: 'lines', header: 'Product lines', render: row => row.lines.length },
    ]} />}
  </div>;
}

const actionLabels: Record<string, string> = { 'issue-quotation': 'Issue quotation', revise: 'Revise to draft', confirm: 'Confirm quotation', activate: 'Activate subscription', pause: 'Schedule pause', resume: 'Resume service', close: 'Close subscription', renew: 'Create renewal draft' };
export function ActionForm({ action, record, onSaved }: { action: string; record: Subscription; onSaved: (result: Subscription) => void }) {
  const [days, setDays] = useState(record.quotation_valid_days ?? 7); const [start, setStart] = useState(record.end_date); const [end, setEnd] = useState(''); const [reason, setReason] = useState('');
  const [acknowledged, setAcknowledged] = useState(false); const [pending, setPending] = useState(false); const [error, setError] = useState<unknown>();
  async function submit(event: FormEvent) {
    event.preventDefault(); if (pending) return;
    setPending(true); setError(undefined);
    const json = action === 'issue-quotation' ? { valid_days: days } : action === 'renew' ? { start_date: start, end_date: end } : (reason ? { reason } : {});
    try { const result = await apiClient.request<ResourceResponse<Subscription>>(`/subscriptions/${record.id}/${action}`, { method: 'POST', json }); onSaved(result.data); }
    catch (caught) { setError(caught); } finally { setPending(false); }
  }
  return <form className="subscription-panel subscription-stack" onSubmit={event => void submit(event)}>
    <h2>{actionLabels[action]}</h2>{error !== undefined && <ErrorPanel message={getErrorMessage(error)} />}{error instanceof ApiError && error.code === 'QUOTATION_PLAN_CHANGED' && <p className="subscription-note">Revise this quotation to a draft, review the updated plan terms, and issue a new quotation before confirming.</p>}
    <fieldset disabled={pending}><div className="subscription-grid">
      {action === 'issue-quotation' && <FormField id="quote-validity" label="Validity in days" error={fieldError(error, 'valid_days')} hint="Confirmation must happen before the exclusive deadline."><input required type="number" min="1" step="1" value={days} onChange={event => setDays(Number(event.target.value))} /></FormField>}
      {action === 'renew' && <><FormField id="renew-start" label="Renewal start" error={fieldError(error, 'start_date')} hint="An active term cannot overlap; an expired term cannot be backdated."><input required type="date" value={start} onChange={event => setStart(event.target.value)} /></FormField><FormField id="renew-end" label="Renewal end (excluded)" error={fieldError(error, 'end_date')}><input required type="date" min={start || undefined} value={end} onChange={event => setEnd(event.target.value)} /></FormField></>}
      {['pause', 'resume', 'close'].includes(action) && <FormField id="lifecycle-reason" label="Reason (optional)"><textarea value={reason} maxLength={2000} onChange={event => setReason(event.target.value)} /></FormField>}
    </div></fieldset>
    {action === 'confirm' && <><p className="subscription-note">Billing is in advance. Each cycle includes the plan base fee plus product lines. A shortened final period is charged at the full-cycle price. There is no automatic proration or refund.</p><label><input required type="checkbox" checked={acknowledged} disabled={pending} onChange={event => setAcknowledged(event.target.checked)} />I have reviewed the service dates, prices and full-cycle policy.</label></>}
    {action === 'activate' && <p className="ui-muted">Activation does not issue an invoice directly. The due-billing worker or operator billing run processes the first eligible cycle.</p>}
    {['pause', 'resume', 'close'].includes(action) && <p className="ui-muted">The server determines the effective schedule boundary. Previously processed periods and invoices remain unchanged; process any due backlog before changing the schedule.</p>}
    {action === 'renew' && <p className="ui-muted">Renewal creates a linked draft for a new quotation and confirmation. It does not reopen or bill the original subscription.</p>}
    <div><Button type="submit" variant={action === 'close' ? 'danger' : 'primary'} pending={pending} disabled={action === 'confirm' && !acknowledged}>{actionLabels[action]}</Button></div>
  </form>;
}

export function SubscriptionDetail() {
  const { id = '' } = useParams(); const navigate = useNavigate();
  const [revision, setRevision] = useState(0); const [action, setAction] = useState(''); const [editing, setEditing] = useState(false);
  const resource = useResource<ResourceResponse<Subscription>>(`/subscriptions/${id}`, revision);
  const record = resource.data?.data;
  function saved(result: Subscription) { setAction(''); setEditing(false); if (result.id !== id) navigate(`/subscriptions/${result.id}`); else setRevision(value => value + 1); }
  return <div className="subscription-stack"><PageHeader title={record?.number ?? 'Subscription details'} description="Review the service agreement and its server-authorized next steps." actions={<Link className="subscription-link" to="/subscriptions">All subscriptions</Link>} />
    {resource.loading && <LoadingSkeleton label="Loading subscription details" />}
    {resource.error !== undefined && <ErrorPanel message={getErrorMessage(resource.error)} onRetry={() => setRevision(value => value + 1)} />}
    {record && <><SubscriptionStepper state={record.state} /><section className="subscription-panel subscription-stack"><div className="ui-actions"><StatusBadge status={record.state} />{record.paused && <StatusBadge status="PAUSED" />}{record.expired && record.state !== 'CLOSED' && <span>Expired, closure pending</span>}</div>
      <dl className="subscription-facts"><div><dt>Customer</dt><dd>{record.customer_name ?? record.customer_id}</dd></div><div><dt>Plan</dt><dd>{record.plan_snapshot?.name ?? record.plan_id}</dd></div><div><dt>Service start</dt><dd><DateLabel value={record.start_date} /></dd></div><div><dt>Service end (excluded)</dt><dd><DateLabel value={record.end_date} /></dd></div><div><dt>Next scheduled cycle</dt><dd><OptionalDate value={record.next_billing_date} /></dd></div><div><dt>Payment terms</dt><dd>{record.payment_terms_days} days</dd></div>{record.quotation_valid_until && <div><dt>Quotation deadline (excluded)</dt><dd><DateLabel value={record.quotation_valid_until} /></dd></div>}{record.recurring_subtotal !== undefined && <div><dt>Per-cycle subtotal before tax and discounts</dt><dd><Money amount={record.recurring_subtotal} currency={record.currency} /></dd></div>}</dl>
      {record.pause_interval && <p className="subscription-note">Pause begins <DateLabel value={record.pause_interval.starts_on} />; {record.pause_interval.ends_on ? <>resume effective <DateLabel value={record.pause_interval.ends_on} /></> : 'resume has not been scheduled'}.</p>}
      {record.close_effective_on && <p className="subscription-note">Closure effective <DateLabel value={record.close_effective_on} />. Existing invoices remain payable.</p>}
      <p className="ui-muted">Plan policies: pause {record.plan_snapshot?.allow_pause ? 'permitted' : 'disabled'}; early close {record.plan_snapshot?.allow_early_close ? 'permitted' : 'disabled'}; renewal {record.plan_snapshot?.allow_renew ? 'permitted' : 'disabled'}; expiry auto-close {record.plan_snapshot?.auto_close ? 'enabled' : 'disabled'}.</p>
    </section>
    <section className="subscription-panel"><h2>Agreed product lines</h2>{record.lines.length ? <div className="ui-table-scroll"><table className="ui-table"><thead><tr><th>Product</th><th>Quantity</th><th>Agreed unit price</th><th>Tax rules</th><th>Line amount · before tax and discounts</th></tr></thead><tbody>{record.lines.map((line, index) => <tr key={line.id ?? index}><td>{line.description ?? line.product_id}</td><td>{line.quantity}</td><td>{line.unit_price !== undefined ? <Money amount={line.unit_price} currency={record.currency} /> : '—'}</td><td><TaxReferences taxes={line.taxes} /></td><td>{line.line_total !== undefined ? <Money amount={line.line_total} currency={record.currency} /> : '—'}</td></tr>)}</tbody></table></div> : <EmptyState title="No product lines" />}<p className="ui-muted">Plan base fee: <Money amount={record.plan_snapshot?.base_fee ?? '0.00'} currency={record.currency} /> per cycle, additional to product lines. Taxes and discounts are resolved by billing.</p><p className="ui-muted">Base-fee tax rules: <TaxReferences taxes={record.base_fee_taxes} /></p>{record.tax_preview_on && <p className="subscription-note">Tax rule preview for <DateLabel value={record.tax_preview_on} />. {record.tax_preview_basis ?? 'Invoice amounts are authoritative.'}</p>}</section>
    <div className="subscription-actions">{(record.allowed_actions ?? []).filter(item => item in actionLabels).map(item => <Button key={item} variant="secondary" onClick={() => { setEditing(false); setAction(item); }}>{actionLabels[item]}</Button>)}{(record.state === 'DRAFT' || (record.state === 'ACTIVE' && record.next_billing_date != null)) && <Button variant="secondary" onClick={() => { setAction(''); setEditing(true); }}>{record.state === 'ACTIVE' ? 'Change next-cycle lines' : 'Edit draft'}</Button>}</div>
    {action && (record.allowed_actions ?? []).includes(action) && <ActionForm key={`${record.id}-${action}`} action={action} record={record} onSaved={saved} />}
    {editing && <SubscriptionForm key={record.id} initial={record} onSaved={saved} onCancel={() => setEditing(false)} />}
    <section className="subscription-panel"><h2>Invoice history</h2>{record.invoice_references?.length ? <ul>{record.invoice_references.map(invoice => <li key={invoice.id}><Link className="subscription-link" to={`/billing/invoices/${invoice.id}`}>{invoice.number}</Link> · {invoice.status}</li>)}</ul> : <EmptyState title="No invoices issued yet" description="Activation does not create invoices directly. Billing processes eligible due cycles." />}</section>
    </>}
  </div>;
}
