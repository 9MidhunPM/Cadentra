import { useEffect, useRef, useState, type FormEvent } from 'react';
import { apiClient, ApiError, getErrorMessage, useSession, type ListResponse, type ResourceResponse } from '../../lib';
import { Button, DataTable, DateLabel, ErrorPanel, FormField, LoadingSkeleton, Money, PageHeader, StatusBadge } from '../../components/ui';
import { fieldError, useResource } from './resource';
import type { Rule } from './types';
import { beginRuleWrite, completeRuleRead, getRuleWrite, setRuleWrite, useRuleWriteState } from './ruleWrites';

type Kind = 'tax' | 'discount';
interface Product { id: string; name: string }
export function RulePage({ kind }: { kind: Kind }) {
  const { actor } = useSession();
  const admin = actor?.role === 'ADMIN';
  const [page, setPage] = useState(1);
  const [editing, setEditing] = useState<Rule | null | undefined>(undefined);
  const [message, setMessage] = useState('');
  const writeState = useRuleWriteState(kind);
  const blocked = writeState !== 'idle';
  const [reconciling, setReconciling] = useState(false);
  const [reconcileError, setReconcileError] = useState<unknown>(null);
  const reconcileLock = useRef(false);
  const path = kind === 'tax' ? '/tax-rules' : '/discount-rules';
  const resource = useResource<ListResponse<Rule>>(`${path}?page=${page}&page_size=25`);
  const replaceRules = resource.replace;
  useEffect(() => {
    if (writeState !== 'refresh') return;
    const abort = new AbortController();
    const version = getRuleWrite(kind).version;
    void apiClient.request<ListResponse<Rule>>(`${path}?page=1&page_size=25`, { signal: abort.signal }).then(result => {
      if (!Array.isArray(result.items)) throw new ApiError(200, 'INVALID_RESPONSE', 'The rule list could not be verified.');
      if (abort.signal.aborted || !completeRuleRead(kind, version)) return;
      replaceRules(result); setEditing(undefined); setPage(1); setReconcileError(null);
    }).catch(failure => { if (!abort.signal.aborted) setReconcileError(failure); });
    return () => abort.abort();
  }, [writeState, kind, path, replaceRules]);
  async function reconcile() {
    if (reconcileLock.current || getRuleWrite(kind).state === 'pending') return;
    const version = getRuleWrite(kind).version;
    reconcileLock.current = true; setReconciling(true); setReconcileError(null);
    try {
      const result = await apiClient.request<ListResponse<Rule>>(`${path}?page=1&page_size=25`);
      if (!Array.isArray(result.items)) throw new ApiError(200, 'INVALID_RESPONSE', 'The rule list could not be verified.');
      if (!completeRuleRead(kind, version)) return;
      replaceRules(result); setEditing(undefined); setPage(1);
      setMessage('Rule list reloaded. Check whether the previous rule was created before starting another request.');
    } catch (failure) { setReconcileError(failure); }
    finally { reconcileLock.current = false; setReconciling(false); }
  }
  return <section><PageHeader eyebrow="Billing configuration" title={kind === 'tax' ? 'Tax rules' : 'Discount rules'} description={admin ? 'Changes create retained revisions. Existing invoice snapshots are preserved.' : 'Read-only configuration. Administrators maintain these rules.'} actions={admin && <Button disabled={blocked || resource.loading || resource.error != null} onClick={() => setEditing(null)}>Create {kind} rule</Button>} />
    {writeState === 'pending' && <p role="status">A rule request is still in progress. New writes and reconciliation are unavailable until it settles.</p>}
    {writeState === 'refresh' && <div className="billing-card"><p role="status">Rule saved. Refreshing the list before another request is allowed.</p>{reconcileError != null && <ErrorPanel message={getErrorMessage(reconcileError)} onRetry={() => void reconcile()} />}</div>}
    {writeState === 'uncertain' && <div className="billing-card"><p role="alert">The previous rule request may have succeeded. Creating or revising again is blocked until you reload the rule list and reconcile the result.</p><Button variant="secondary" pending={reconciling} onClick={() => void reconcile()}>Reload rule list to reconcile</Button>{reconcileError != null && <ErrorPanel message={getErrorMessage(reconcileError)} />}</div>}
    {message && <p role="status">{message}</p>}{resource.loading && <LoadingSkeleton label="Loading rules" />}{resource.error != null && <ErrorPanel message={getErrorMessage(resource.error)} onRetry={resource.reload} />}
    {admin && editing !== undefined && <RuleForm key={`${kind}-${editing?.id ?? 'new'}`} kind={kind} rule={editing} blocked={blocked} onCancel={() => setEditing(undefined)} onSaved={rule => { setEditing(undefined); setMessage(editing ? `Revision scheduled from ${rule.effective_from}. The list shows currently effective rules.` : 'Rule created.'); }} />}
    {resource.data && <DataTable rows={resource.data.items} getRowKey={row => row.id} page={page} pageSize={resource.data.page_size} total={resource.data.total} onPageChange={setPage} caption={kind === 'tax' ? 'Tax rules' : 'Discount rules'} emptyTitle={`No ${kind} rules configured`} columns={[
      { key: 'name', header: 'Rule', render: row => <><strong>{row.name}</strong><small className="billing-tax">Effective <DateLabel value={row.effective_from} /></small></> },
      { key: 'value', header: kind === 'tax' ? 'Rate' : 'Benefit', render: row => kind === 'tax' ? `${row.rate_percent}%` : row.kind === 'PERCENT' ? `${row.value}%` : <Money amount={row.value ?? '0.00'} /> },
      { key: 'scope', header: 'Scope', render: row => kind === 'tax' ? `${row.product_ids?.length ?? 0} product selections` : row.scope },
      { key: 'status', header: 'Status', render: row => <StatusBadge status={row.active ? 'ACTIVE' : 'INACTIVE'} /> },
      ...(kind === 'discount' ? [{ key: 'uses', header: 'Global uses', render: (row: Rule) => `${row.uses_count ?? 0} / ${row.usage_limit ?? 'unlimited'}` }] : []),
      ...(admin ? [{ key: 'edit', header: 'Actions', render: (row: Rule) => <Button variant="secondary" disabled={blocked} onClick={() => setEditing(row)}>Schedule revision</Button> }] : []),
    ]} />}
  </section>;
}

function RuleForm({ kind, rule, onSaved, onCancel, blocked }: { kind: Kind; rule: Rule | null; blocked: boolean; onSaved: (rule: Rule) => void; onCancel: () => void }) {
  const [name, setName] = useState(rule?.name ?? '');
  const [value, setValue] = useState(rule?.rate_percent ?? rule?.value ?? '');
  const [discountKind, setDiscountKind] = useState(rule?.kind ?? 'PERCENT');
  const [scope, setScope] = useState(rule?.scope ?? 'SUBSCRIPTION');
  const [start, setStart] = useState(rule?.valid_from ?? rule?.starts_on ?? '');
  const [end, setEnd] = useState(rule?.valid_until ?? rule?.ends_on ?? '');
  const [effective, setEffective] = useState('');
  const [minimum, setMinimum] = useState(rule?.min_purchase ?? '0.00');
  const [quantity, setQuantity] = useState(String(rule?.min_quantity ?? 0));
  const [limit, setLimit] = useState(rule?.usage_limit == null ? '' : String(rule.usage_limit));
  const [active, setActive] = useState(rule?.active ?? true);
  const [selected, setSelected] = useState<{ id: string; name?: string }[]>(() => (rule?.product_ids ?? []).map(id => ({ id })));
  const [search, setSearch] = useState('');
  const [productPage, setProductPage] = useState(1);
  const products = useResource<ListResponse<Product>>(`/products?page=${productPage}&page_size=100&q=${encodeURIComponent(search)}`);
  const productRows = products.data?.items;
  useEffect(() => {
    if (!productRows) return;
    // Retain names of selected products when their page or search is no longer visible.
    setSelected(current => {
      let changed = false;
      const next = current.map(product => {
        const match = productRows.find(row => row.id === product.id);
        if (!match || match.name === product.name) return product;
        changed = true;
        return { id: product.id, name: match.name };
      });
      return changed ? next : current;
    });
  }, [productRows]);
  const [error, setError] = useState<unknown>(null);
  const [pending, setPending] = useState(false);
  const lock = useRef(false);
  const uncertainAttempt = useRef(false);
  function selectProduct(product: Product, checked: boolean) {
    setSelected(current => {
      if (!checked) return current.filter(item => item.id !== product.id);
      return current.some(item => item.id === product.id) ? current : [...current, product];
    });
  }
  async function submit(event: FormEvent) {
    event.preventDefault(); if (lock.current || blocked || uncertainAttempt.current || !beginRuleWrite(kind)) return;
    lock.current = true; setPending(true); setError(null);
    const common = { name, active, product_ids: kind === 'discount' && scope === 'SUBSCRIPTION' ? [] : selected.map(product => product.id) };
    const payload = kind === 'tax' ? { ...common, rate_percent: value, valid_from: start, valid_until: end || null } : { ...common, kind: discountKind, value, scope, min_purchase: minimum, min_quantity: Number(quantity), starts_on: start, ends_on: end || null, usage_limit: limit === '' ? null : Number(limit) };
    try {
      const path = `${kind === 'tax' ? '/tax-rules' : '/discount-rules'}${rule ? `/${rule.id}` : ''}`;
      const result = await apiClient.request<ResourceResponse<Rule>>(path, { method: rule ? 'PATCH' : 'POST', json: rule ? { ...payload, effective_from: effective } : payload });
      if (!result.data || typeof result.data.id !== 'string' || typeof result.data.effective_from !== 'string') throw new ApiError(200, 'INVALID_RESPONSE', 'The rule result could not be verified. Reload the rule list before retrying.');
      setRuleWrite(kind, 'refresh');
      onSaved(result.data);
    } catch (failure) {
      setError(failure);
      const rejected = failure instanceof ApiError && failure.status >= 400 && failure.status < 500 && failure.status !== 408 && !['INVALID_RESPONSE', 'NETWORK_ERROR'].includes(failure.code);
      if (rejected) setRuleWrite(kind, 'idle');
      else { uncertainAttempt.current = true; setRuleWrite(kind, 'uncertain'); }
    }
    finally { lock.current = false; setPending(false); }
  }
  return <form className="billing-card" onSubmit={event => void submit(event)}><h2>{rule ? 'Schedule a retained revision' : `New ${kind} rule`}</h2><fieldset disabled={pending || blocked} className="billing-form-grid">
    <FormField error={fieldError(error, 'name')} id="rule-name" label="Rule name"><input required maxLength={200} value={name} onChange={event => setName(event.target.value)} /></FormField>
    {kind === 'discount' && <FormField error={fieldError(error, 'kind')} id="rule-kind" label="Discount kind"><select value={discountKind} onChange={event => setDiscountKind(event.target.value)}><option value="PERCENT">Percentage</option><option value="FIXED">Fixed amount (INR)</option></select></FormField>}
    <FormField error={fieldError(error, kind === 'tax' ? 'rate_percent' : 'value')} id="rule-value" label={kind === 'tax' ? 'Tax rate (%)' : discountKind === 'PERCENT' ? 'Discount percentage' : 'Fixed discount (INR)'} hint={kind === 'tax' || discountKind === 'PERCENT' ? 'Up to four fractional digits; maximum 100%.' : 'Up to two fractional digits.'}><input inputMode="decimal" required pattern={kind === 'tax' || discountKind === 'PERCENT' ? '[0-9]+([.][0-9]{1,4})?' : '[0-9]+([.][0-9]{1,2})?'} value={value} onChange={event => setValue(event.target.value)} /></FormField>
    <FormField error={fieldError(error, kind === 'tax' ? 'valid_from' : 'starts_on')} id="rule-start" label="Eligibility starts on"><input type="date" required value={start} onChange={event => setStart(event.target.value)} /></FormField>
    <FormField error={fieldError(error, kind === 'tax' ? 'valid_until' : 'ends_on')} id="rule-end" label="Eligibility ends before (optional)"><input type="date" value={end} onChange={event => setEnd(event.target.value)} /></FormField>
    {rule && <FormField error={fieldError(error, 'effective_from')} id="rule-effective" label="Revision effective from" hint="Must be at least the next business day. Existing history cannot be rewritten."><input type="date" required value={effective} onChange={event => setEffective(event.target.value)} /></FormField>}
    {kind === 'discount' && <><FormField error={fieldError(error, 'scope')} id="rule-scope" label="Discount scope"><select value={scope} onChange={event => setScope(event.target.value)}><option value="SUBSCRIPTION">Whole subscription (including base fee)</option><option value="PRODUCTS">Selected products</option></select></FormField>
    <FormField error={fieldError(error, 'min_purchase')} id="rule-minimum" label="Minimum eligible purchase (INR)"><input required inputMode="decimal" pattern="[0-9]+([.][0-9]{1,2})?" value={minimum} onChange={event => setMinimum(event.target.value)} /></FormField>
    <FormField error={fieldError(error, 'min_quantity')} id="rule-quantity" label="Minimum eligible product quantity"><input type="number" min={0} step={1} required value={quantity} onChange={event => setQuantity(event.target.value)} /></FormField>
    <FormField error={fieldError(error, 'usage_limit')} id="rule-limit" label="Global usage limit (optional)"><input type="number" min={0} step={1} value={limit} onChange={event => setLimit(event.target.value)} /></FormField></>}
    <label className="billing-check"><input type="checkbox" checked={active} onChange={event => setActive(event.target.checked)} /> Rule active</label>
    {(kind === 'tax' || scope === 'PRODUCTS') && <div className="billing-product-picker"><FormField id="product-search" label="Search eligible products"><input maxLength={200} value={search} onChange={event => { setSearch(event.target.value); setProductPage(1); }} /></FormField>{products.loading && <LoadingSkeleton label="Loading products" />}{products.error != null && <ErrorPanel message={getErrorMessage(products.error)} onRetry={products.reload} />}
    {products.data?.items.map(product => <label className="billing-check" key={product.id}><input type="checkbox" checked={selected.some(item => item.id === product.id)} onChange={event => selectProduct(product, event.target.checked)} />{product.name}</label>)}
    {products.data?.total === 0 && <p>No matching products. Search another name.</p>}
    <nav className="ui-pagination" aria-label="Eligible products pagination"><span className="ui-muted">{products.data ? `${products.data.total} matching ${products.data.total === 1 ? 'product' : 'products'} · Page ${productPage} of ${Math.max(1, Math.ceil(products.data.total / products.data.page_size))}` : 'Product pages unavailable until the list loads.'}</span><div className="ui-actions"><Button variant="secondary" disabled={products.loading || products.error != null || productPage <= 1} onClick={() => setProductPage(page => page - 1)}>Previous products</Button><Button variant="secondary" disabled={products.loading || products.error != null || !products.data || productPage >= Math.ceil(products.data.total / products.data.page_size)} onClick={() => setProductPage(page => page + 1)}>Next products</Button></div></nav>
    <p className="ui-muted">{selected.length} products selected. Search and page changes retain selections.</p>{selected.map(product => <Button key={product.id} variant="secondary" onClick={() => setSelected(current => current.filter(item => item.id !== product.id))}>Remove selected product {product.name ?? product.id}</Button>)}</div>}
  </fieldset>{error != null && <ErrorPanel message={getErrorMessage(error)} />}<div className="ui-actions"><Button type="submit" pending={pending} disabled={blocked}>{rule ? 'Schedule revision' : 'Create rule'}</Button><Button variant="secondary" disabled={pending} onClick={onCancel}>Close form</Button></div></form>;
}
