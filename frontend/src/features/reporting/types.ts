export interface DashboardSummary {
  as_of: string; range_from: string; range_to: string; currency: string;
  active_subscriptions: number; invoiced_gross_in_range: string; cash_received_in_range: string;
  outstanding_now: string; overdue_now: string; overdue_invoice_count: number;
  metric_basis: Record<string, string>;
}
export interface RevenueBucket { period_start: string; period_end: string; invoiced_gross: string; cash_received: string }
export interface RevenueSeries { range_from: string; range_to: string; currency: string; cadence: 'DAILY' | 'MONTHLY'; buckets: RevenueBucket[] }
export interface InvoiceRow { id: string; number: string; customer_id: string; customer_name?: string; customer_snapshot?: { display_name?: string }; due_date: string; total: string; balance_due: string; currency: string; collection_status?: string }
export interface Customer { id: string; display_name: string; email: string }
export interface ReportFilter { from: string; to: string; customerId: string; customerName: string }

/** Service dates are calendar dates; never interpret them in browser local time. */
export function shiftDate(value: string, days: number): string {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return ''
  const date = new Date(`${value}T00:00:00Z`)
  if (!Number.isFinite(date.getTime()) || date.toISOString().slice(0, 10) !== value) return ''
  date.setUTCDate(date.getUTCDate() + days)
  return date.toISOString().slice(0, 10)
}
export function reportQuery(filter: ReportFilter, cadence?: string): string {
  const params = new URLSearchParams()
  if (filter.from) params.set('from', filter.from)
  if (filter.to) params.set('to', filter.to)
  if (filter.customerId) params.set('customer_id', filter.customerId)
  if (cadence) params.set('cadence', cadence)
  return params.size ? `?${params}` : ''
}
