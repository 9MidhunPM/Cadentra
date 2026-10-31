import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Link } from 'react-router'
import { ArrowRight, CalendarDays, CircleAlert, CreditCard, FileText, Plus, RefreshCw, Users } from 'lucide-react'
import { apiClient, getErrorMessage, isAbortError } from '../../lib'
import type { ListResponse, ResourceResponse } from '../../lib'
import { Button, DataTable, DateLabel, ErrorPanel, LoadingSkeleton, Money, PageHeader, StatusBadge } from '../../components/ui'
import { CustomerFilter } from './CustomerFilter'
import { RevenueChart } from './RevenueChart'
import { reportQuery, shiftDate, type DashboardSummary, type InvoiceRow, type ReportFilter, type RevenueSeries } from './types'
import './reporting.css'

type Resource<T> = { loading: boolean; data: T | null; error: string | null }
function useResource<T>(path: string, revision: number): Resource<T> {
  const [state, setState] = useState<Resource<T>>({ loading: true, data: null, error: null })
  useEffect(() => {
    const controller = new AbortController()
    setState({ loading: true, data: null, error: null })
    apiClient.request<T>(path, { signal: controller.signal }).then(data => {
      if (!controller.signal.aborted) setState({ loading: false, data, error: null })
    }).catch(error => { if (!controller.signal.aborted && !isAbortError(error)) setState({ loading: false, data: null, error: getErrorMessage(error) }) })
    return () => controller.abort()
  }, [path, revision])
  return state
}
const emptyFilter: ReportFilter = { from: '', to: '', customerId: '', customerName: '' }
interface BillingRun { invoices_created: number; processed_periods: number; failed_subscription_count: number; has_more_due: boolean }

export function OverviewPage() {
  const [applied, setApplied] = useState<ReportFilter>(emptyFilter)
  const [draft, setDraft] = useState<ReportFilter>(emptyFilter)
  const [cadence, setCadence] = useState<'DAILY' | 'MONTHLY'>('DAILY')
  const [revision, setRevision] = useState(0)
  const [page, setPage] = useState(1)
  const [filterError, setFilterError] = useState<string | null>(null)
  const [running, setRunning] = useState(false)
  const [runError, setRunError] = useState<string | null>(null)
  const [runMessage, setRunMessage] = useState<string | null>(null)
  const inFlight = useRef(false)
  const summary = useResource<ResourceResponse<DashboardSummary>>(`/reports/summary${reportQuery(applied)}`, revision)
  const series = useResource<ResourceResponse<RevenueSeries>>(`/reports/revenue-series${reportQuery(applied, cadence)}`, revision)
  const invoiceParams = new URLSearchParams({ overdue: 'true', page: String(page), page_size: '5' })
  if (applied.customerId) invoiceParams.set('customer_id', applied.customerId)
  const invoices = useResource<ListResponse<InvoiceRow>>(`/invoices?${invoiceParams}`, revision)
  const data = summary.data?.data
  useEffect(() => {
    if (!data) return
    setDraft(current => current.from || current.to ? current : { ...current, from: data.range_from, to: data.range_to })
  }, [data])

  function applyFilters(event: FormEvent) {
    event.preventDefault()
    if (!draft.from || !draft.to || draft.from >= draft.to) { setFilterError('Choose a start date on or before the final day.'); return }
    setFilterError(null); setApplied({ ...draft }); setPage(1)
  }
  async function runBilling() {
    if (inFlight.current) return
    inFlight.current = true; setRunning(true); setRunError(null); setRunMessage(null)
    try {
      const result = await apiClient.request<ResourceResponse<BillingRun>>('/billing/run-due', { method: 'POST', json: {} })
      const run = result.data
      setRunMessage(`${run.invoices_created} invoices created from ${run.processed_periods} processed periods.${run.has_more_due ? ' More periods remain; run billing again to continue.' : ''}${run.failed_subscription_count ? ` ${run.failed_subscription_count} subscriptions need review.` : ''}`)
      setRevision(value => value + 1)
    } catch (error) { setRunError(getErrorMessage(error)) }
    finally { inFlight.current = false; setRunning(false) }
  }
  return <section className="report-overview">
    <PageHeader title="Overview" description="Your subscription business at a glance." actions={<><Button variant="secondary" pending={running} onClick={() => void runBilling()}><RefreshCw size={15} aria-hidden="true" />Run due billing</Button><Link className="ui-button ui-button--primary" to="/subscriptions/new"><Plus size={16} aria-hidden="true" />New subscription</Link></>} />
    <form className="report-filters" onSubmit={applyFilters}>
      <div className="report-date-range"><CalendarDays size={16} aria-hidden="true" /><label>From<input type="date" aria-label="Report start date" value={draft.from} onChange={event => setDraft(current => ({ ...current, from: event.target.value }))} /></label><span aria-hidden="true">–</span><label>Through<input type="date" aria-label="Report final day" value={shiftDate(draft.to, -1)} onChange={event => setDraft(current => ({ ...current, to: shiftDate(event.target.value, 1) }))} /></label></div>
      <CustomerFilter selectedId={draft.customerId} selectedName={draft.customerName} onChange={(customerId, customerName) => setDraft(current => ({ ...current, customerId, customerName }))} />
      <Button variant="secondary" type="submit">Apply filters</Button><Button variant="secondary" onClick={() => setRevision(value => value + 1)} aria-label="Refresh reports"><RefreshCw size={16} aria-hidden="true" /></Button>
    </form>
    {filterError ? <p className="report-inline-error" role="alert">{filterError}</p> : null}
    {runError ? <ErrorPanel title="Billing run failed" message={runError} /> : null}{runMessage ? <p className="report-run-message" role="status">{runMessage}</p> : null}
    {summary.loading ? <LoadingSkeleton label="Loading report summary" /> : summary.error ? <ErrorPanel title="Summary unavailable" message={summary.error} onRetry={() => setRevision(value => value + 1)} /> : data ? <>
      <div className="report-metrics" aria-label="Subscription business summary">
        <div className="report-metric"><span className="report-metric-icon"><Users size={20} /></span><div><h2>Active subscriptions</h2><strong>{data.active_subscriptions}</strong><small>As of <DateLabel value={data.as_of} /></small></div></div>
        <div className="report-metric"><span className="report-metric-icon"><FileText size={20} /></span><div><h2>Invoiced</h2><strong><Money amount={data.invoiced_gross_in_range} currency={data.currency} /></strong><small>Selected range, tax inclusive</small></div></div>
        <div className="report-metric"><span className="report-metric-icon"><CreditCard size={20} /></span><div><h2>Payments received</h2><strong><Money amount={data.cash_received_in_range} currency={data.currency} /></strong><small>Selected range</small></div></div>
        <div className="report-metric"><span className="report-metric-icon report-icon-warning"><CalendarDays size={20} /></span><div><h2>Outstanding</h2><strong><Money amount={data.outstanding_now} currency={data.currency} /></strong><small>As of <DateLabel value={data.as_of} /></small></div></div>
        <div className="report-metric"><span className="report-metric-icon report-icon-warning"><CircleAlert size={20} /></span><div><h2>Overdue</h2><strong><Money amount={data.overdue_now} currency={data.currency} /></strong><small>{data.overdue_invoice_count} invoices · as of today</small></div></div>
      </div>
      <p className="report-range-note">Range: <DateLabel value={data.range_from} /> through <DateLabel value={shiftDate(data.range_to, -1)} />. Active subscriptions and balances show the current state.</p>
    </> : null}
    <div className="report-chart-layout"><section className="report-panel"><header className="report-panel-heading"><h2>Invoiced &amp; received</h2><label className="report-cadence">Group by<select value={cadence} onChange={event => setCadence(event.target.value as 'DAILY' | 'MONTHLY')}><option value="DAILY">Daily</option><option value="MONTHLY">Monthly</option></select></label></header>{series.loading ? <LoadingSkeleton label="Loading reporting series" /> : series.error ? <ErrorPanel title="Chart unavailable" message={series.error} onRetry={() => setRevision(value => value + 1)} /> : series.data ? <RevenueChart series={series.data.data} /> : null}</section>
      {data ? <aside className="report-panel report-balances"><h2>Balances</h2><dl><div><dt>Outstanding</dt><dd><Money amount={data.outstanding_now} currency={data.currency} /></dd></div><div><dt>Overdue</dt><dd><Money amount={data.overdue_now} currency={data.currency} /></dd></div></dl><small>As of <DateLabel value={data.as_of} /></small><Link to="/billing/invoices?overdue=true">View overdue invoices <ArrowRight size={14} aria-hidden="true" /></Link></aside> : null}</div>
    <section className="report-panel report-invoices"><header className="report-panel-heading"><div><h2>Overdue invoices</h2><p>Current unpaid invoices past their due date.</p></div><Link to="/billing/invoices?overdue=true">View all invoices <ArrowRight size={14} aria-hidden="true" /></Link></header>
    {invoices.loading ? <LoadingSkeleton label="Loading overdue invoices" /> : invoices.error ? <ErrorPanel title="Overdue invoices unavailable" message={invoices.error} onRetry={() => setRevision(value => value + 1)} /> : invoices.data ? <DataTable caption="Overdue invoices" columns={[
      { key: 'number', header: 'Invoice', render: row => <Link to={`/billing/invoices/${row.id}`}>{row.number}</Link> },
      { key: 'customer', header: 'Customer', render: row => row.customer_name || row.customer_snapshot?.display_name || 'Customer record' },
      { key: 'due', header: 'Due', render: row => <DateLabel value={row.due_date} /> },
      { key: 'balance', header: 'Balance', render: row => <Money amount={row.balance_due} currency={row.currency} /> },
      { key: 'status', header: 'Status', render: () => <StatusBadge status="OVERDUE" /> },
    ]} rows={invoices.data.items} getRowKey={row => row.id} page={page} pageSize={5} total={invoices.data.total} onPageChange={setPage} emptyTitle="No overdue invoices" /> : null}</section>
  </section>
}
