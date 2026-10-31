import { useCallback, useEffect, useState, type FormEvent } from 'react';
import { Link, useNavigate, useParams } from 'react-router';
import { apiClient, ApiError, getErrorMessage, isAbortError, type ResourceResponse } from '../../lib';
import { Button, ErrorPanel, FormField, LoadingSkeleton, PageHeader } from '../../components/ui';
import { allRecords } from './api';
import type { Customer, LineInput, Plan, Product, Subscription, Template, Variant } from './types';

interface Catalog { customers: Customer[]; plans: Plan[]; products: Product[]; templates: Template[] }
export function useCatalog() {
  const [data, setData] = useState<Catalog>();
  const [error, setError] = useState<unknown>();
  const [revision, setRevision] = useState(0);
  const reload = useCallback(() => { setError(undefined); setRevision(current => current + 1); }, []);
  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      allRecords<Customer>('/customers', controller.signal), allRecords<Plan>('/plans', controller.signal),
      allRecords<Product>('/products', controller.signal), allRecords<Template>('/quotation-templates', controller.signal),
    ]).then(([customers, plans, products, templates]) => {
      if (!controller.signal.aborted) setData({ customers, plans, products, templates });
    }).catch((caught: unknown) => { if (!controller.signal.aborted && !isAbortError(caught)) setError(caught); });
    return () => controller.abort();
  }, [revision]);
  return { data, error, reload };
}

export function fieldError(error: unknown, field: string): string | undefined {
  if (!(error instanceof ApiError)) return undefined;
  for (const key of [field, `body.${field}`]) {
    const value = error.fields[key];
    if (typeof value === 'string') return value;
    if (Array.isArray(value)) {
      const messages = value.filter(item => typeof item === 'string');
      if (messages.length) return messages.join(', ');
    }
  }
  return undefined;
}

export function LineEditor({ lines, onChange, products, disabled = false, validationError }: { lines: LineInput[]; onChange: (lines: LineInput[]) => void; products: Product[]; disabled?: boolean; validationError?: unknown }) {
  const [variants, setVariants] = useState<Record<string, Variant[]>>({});
  const [error, setError] = useState<unknown>();
  const selected = [...new Set(lines.map(line => line.product_id).filter(Boolean))].sort().join(',');
  useEffect(() => {
    const controller = new AbortController();
    setError(undefined);
    Promise.all(selected.split(',').filter(Boolean).map(async id => {
      const result = await apiClient.request<ResourceResponse<Product>>(`/products/${id}`, { signal: controller.signal });
      return [id, result.data.variants ?? []] as const;
    })).then(entries => { if (!controller.signal.aborted) setVariants(Object.fromEntries(entries)); })
      .catch((caught: unknown) => { if (!controller.signal.aborted && !isAbortError(caught)) setError(caught); });
    return () => controller.abort();
  }, [selected]);
  function change(index: number, value: LineInput) { onChange(lines.map((line, position) => position === index ? value : line)); }
  return <fieldset disabled={disabled}><legend>Product lines</legend><div className="subscription-lines">
    {error !== undefined && <ErrorPanel title="Cannot load variants" message={getErrorMessage(error)} />}
    {lines.map((line, index) => <div className="subscription-line" key={index}>
      <FormField id={`line-product-${index}`} label={`Product ${index + 1}`} error={fieldError(validationError, `lines.${index}.product_id`)}><select required value={line.product_id} onChange={event => change(index, { product_id: event.target.value, quantity: line.quantity })}><option value="">Select a product</option>{products.filter(product => product.active || product.id === line.product_id).map(product => <option key={product.id} value={product.id}>{product.name}{!product.active ? ' (archived)' : ''}</option>)}</select></FormField>
      <FormField id={`line-variant-${index}`} label={`Variant ${index + 1}`} error={fieldError(validationError, `lines.${index}.variant_id`)}><select value={line.variant_id ?? ''} onChange={event => change(index, { ...line, variant_id: event.target.value || undefined })}><option value="">No variant</option>{(variants[line.product_id] ?? []).filter(variant => variant.active || variant.id === line.variant_id).map(variant => <option key={variant.id} value={variant.id}>{variant.attribute_name}: {variant.attribute_value}{!variant.active ? ' (archived)' : ''}</option>)}</select></FormField>
      <FormField id={`line-quantity-${index}`} label={`Quantity ${index + 1}`} error={fieldError(validationError, `lines.${index}.quantity`)}><input required type="number" min="1" step="1" value={line.quantity} onChange={event => change(index, { ...line, quantity: Number(event.target.value) })} /></FormField>
      <Button variant="secondary" onClick={() => onChange(lines.filter((_, position) => position !== index))} aria-label={`Remove line ${index + 1}`}>Remove</Button>
    </div>)}
    <div><Button variant="secondary" onClick={() => onChange([...lines, { product_id: '', quantity: 1 }])}>Add product line</Button></div>
  </div></fieldset>;
}

export function SubscriptionForm({ initial, onSaved, onCancel }: { initial?: Subscription; onSaved?: (record: Subscription) => void; onCancel?: () => void }) {
  const catalog = useCatalog();
  const navigate = useNavigate();
  const [customer, setCustomer] = useState(initial?.customer_id ?? '');
  const [plan, setPlan] = useState(initial?.plan_id ?? '');
  const [template, setTemplate] = useState('');
  const [start, setStart] = useState(initial?.start_date ?? '');
  const [end, setEnd] = useState(initial?.end_date ?? '');
  const [terms, setTerms] = useState(initial?.payment_terms_days ?? 0);
  const [lines, setLines] = useState<LineInput[]>(initial?.lines.map(({ product_id, variant_id, quantity }) => ({ product_id, variant_id: variant_id ?? undefined, quantity })) ?? [{ product_id: '', quantity: 1 }]);
  const [error, setError] = useState<unknown>();
  const [pending, setPending] = useState(false);
  const active = initial?.state === 'ACTIVE';
  function selectTemplate(id: string) {
    setTemplate(id);
    const record = catalog.data?.templates.find(item => item.id === id);
    if (record) { setPlan(record.plan_id); setLines(record.lines.map(({ product_id, variant_id, quantity }) => ({ product_id, variant_id: variant_id ?? undefined, quantity }))); }
  }
  async function submit(event: FormEvent) {
    event.preventDefault(); if (pending) return;
    setPending(true); setError(undefined);
    const json = initial ? (active ? { lines } : { start_date: start, end_date: end, payment_terms_days: terms, lines }) : { customer_id: customer, plan_id: plan, ...(template ? { template_id: template } : {}), start_date: start, end_date: end, payment_terms_days: terms, lines };
    try {
      const result = await apiClient.request<ResourceResponse<Subscription>>(initial ? `/subscriptions/${initial.id}` : '/subscriptions', { method: initial ? 'PATCH' : 'POST', json });
      if (onSaved) onSaved(result.data); else navigate(`/subscriptions/${result.data.id}`);
    } catch (caught) { setError(caught); } finally { setPending(false); }
  }
  return <form className="subscription-stack subscription-panel" onSubmit={event => void submit(event)}>
    {catalog.error !== undefined && <ErrorPanel message={getErrorMessage(catalog.error)} onRetry={catalog.reload} />}
    {!catalog.data && catalog.error === undefined && <LoadingSkeleton label="Loading subscription options" />}
    {error !== undefined && <ErrorPanel message={getErrorMessage(error)} />}
    {catalog.data && <><fieldset disabled={pending}><div className="subscription-grid">
      {!initial && <><FormField id="subscription-customer" label="Customer" error={fieldError(error, 'customer_id')}><select required value={customer} onChange={event => setCustomer(event.target.value)}><option value="">Select customer</option>{catalog.data.customers.map(item => <option key={item.id} value={item.id}>{item.display_name}</option>)}</select></FormField>
      <FormField id="subscription-template" label="Quotation template (optional)"><select value={template} onChange={event => selectTemplate(event.target.value)}><option value="">Start without a template</option>{catalog.data.templates.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></FormField>
      <FormField id="subscription-plan" label="Plan" error={fieldError(error, 'plan_id')} hint="Plan availability is checked against the requested start date."><select required value={plan} onChange={event => { setPlan(event.target.value); setTemplate(''); }}><option value="">Select plan</option>{catalog.data.plans.map(item => <option key={item.id} value={item.id}>{item.name} · {item.cadence.toLowerCase()} · minimum {item.min_quantity} products</option>)}</select></FormField></>}
      {!active && <><FormField id="subscription-start" label="Service start (included)" error={fieldError(error, 'start_date')}><input required type="date" value={start} onChange={event => setStart(event.target.value)} /></FormField>
      <FormField id="subscription-end" label="Service end (excluded)" hint="Service stops before this date." error={fieldError(error, 'end_date')}><input required type="date" min={start || undefined} value={end} onChange={event => setEnd(event.target.value)} /></FormField>
      <FormField id="subscription-terms" label="Payment terms (days)" error={fieldError(error, 'payment_terms_days')}><input required type="number" min="0" step="1" value={terms} onChange={event => setTerms(Number(event.target.value))} /></FormField></>}
    </div></fieldset>
    {active && <p className="subscription-note">Changes apply to the next unprocessed cycle. Process any due billing backlog first; existing invoices remain unchanged.</p>}
    <LineEditor lines={lines} onChange={setLines} products={catalog.data.products} disabled={pending} validationError={error} />
    {fieldError(error, 'lines') && <p role="alert" className="subscription-inline-error">{fieldError(error, 'lines')}</p>}
    <p className="ui-muted">The plan base fee is charged once per cycle in addition to product lines. Minimum quantity counts products only. Prices and eligibility are validated by the server.</p>
    <div className="ui-actions"><Button type="submit" pending={pending}>{initial ? 'Save changes' : 'Create draft'}</Button>{onCancel && <Button variant="secondary" disabled={pending} onClick={onCancel}>Cancel</Button>}</div></>}
  </form>;
}

export function NewSubscription() { return <div className="subscription-stack"><PageHeader title="New subscription" description="Prepare a draft, review the quotation, then confirm the agreed service." actions={<Link className="subscription-link" to="/subscriptions">All subscriptions</Link>} /><SubscriptionForm /></div>; }

export function TemplateEditor() {
  const { id } = useParams();
  const catalog = useCatalog();
  const [loadedId, setLoadedId] = useState<string>();
  const [name, setName] = useState(''); const [plan, setPlan] = useState('');
  const [days, setDays] = useState(7); const [lines, setLines] = useState<LineInput[]>([{ product_id: '', quantity: 1 }]);
  const [error, setError] = useState<unknown>(); const [pending, setPending] = useState(false);
  const navigate = useNavigate();
  useEffect(() => {
    const existing = catalog.data?.templates.find(item => item.id === id);
    if (existing && loadedId !== id) { setName(existing.name); setPlan(existing.plan_id); setDays(existing.valid_days); setLines(existing.lines.map(({ product_id, variant_id, quantity }) => ({ product_id, variant_id: variant_id ?? undefined, quantity }))); setLoadedId(id); }
  }, [catalog.data, id, loadedId]);
  async function submit(event: FormEvent) {
    event.preventDefault(); if (pending) return;
    setPending(true); setError(undefined);
    try { await apiClient.request(id ? `/quotation-templates/${id}` : '/quotation-templates', { method: id ? 'PATCH' : 'POST', json: { name, plan_id: plan, valid_days: days, lines } }); navigate('/subscriptions/templates'); }
    catch (caught) { setError(caught); } finally { setPending(false); }
  }
  const unavailable = id && catalog.data && !catalog.data.templates.some(item => item.id === id);
  return <div className="subscription-stack"><PageHeader title={id ? 'Edit quotation template' : 'New quotation template'} description="Templates copy a plan and product selections into a draft. Existing quotations remain unchanged." actions={<Link className="subscription-link" to="/subscriptions/templates">All templates</Link>} />
    {catalog.error !== undefined && <ErrorPanel message={getErrorMessage(catalog.error)} onRetry={catalog.reload} />}{!catalog.data && catalog.error === undefined && <LoadingSkeleton label="Loading template options" />}
    {unavailable && <ErrorPanel message="This template is unavailable." />}
    {catalog.data && !unavailable && <form onSubmit={event => void submit(event)} className="subscription-panel subscription-stack">
      {error !== undefined && <ErrorPanel message={getErrorMessage(error)} />}
      <fieldset disabled={pending}><div className="subscription-grid"><FormField id="template-name" label="Template name" error={fieldError(error, 'name')}><input required value={name} onChange={event => setName(event.target.value)} /></FormField>
      <FormField id="template-plan" label="Plan" error={fieldError(error, 'plan_id')}><select required value={plan} onChange={event => setPlan(event.target.value)}><option value="">Select plan</option>{catalog.data.plans.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></FormField>
      <FormField id="template-days" label="Quotation validity (days)" error={fieldError(error, 'valid_days')} hint="The deadline is exclusive; confirmation must happen before that date."><input required type="number" min="1" step="1" value={days} onChange={event => setDays(Number(event.target.value))} /></FormField></div></fieldset>
      <LineEditor lines={lines} onChange={setLines} products={catalog.data.products} disabled={pending} validationError={error} />
      {fieldError(error, 'lines') && <p role="alert" className="subscription-inline-error">{fieldError(error, 'lines')}</p>}
      <Button type="submit" pending={pending}>{id ? 'Save template' : 'Create template'}</Button>
    </form>}
  </div>;
}
