import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router'
import { afterAll, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'
import { apiClient, ApiError } from '../../lib'
import { OverviewPage } from './OverviewPage'
import { CustomerFilter } from './CustomerFilter'
import { reportQuery, shiftDate } from './types'

const summary = { data: { as_of: '2026-11-02', range_from: '2026-10-01', range_to: '2026-11-01', currency: 'INR', active_subscriptions: 2, invoiced_gross_in_range: '5870.16', cash_received_in_range: '3050.00', outstanding_now: '3570.16', overdue_now: '3170.16', overdue_invoice_count: 2, metric_basis: {} } }
const series = { data: { range_from: '2026-10-01', range_to: '2026-11-01', currency: 'INR', cadence: 'DAILY', buckets: [{ period_start: '2026-10-01', period_end: '2026-10-02', invoiced_gross: '200.00', cash_received: '750.00' }] } }
const empty = { items: [], total: 0, page: 1, page_size: 5 }
function setup() { return render(<MemoryRouter><OverviewPage /></MemoryRouter>) }
const scrollDescriptor = Object.getOwnPropertyDescriptor(Element.prototype, 'scrollIntoView')
beforeAll(() => Object.defineProperty(Element.prototype, 'scrollIntoView', { configurable: true, value: vi.fn() }))
afterAll(() => { if (scrollDescriptor) Object.defineProperty(Element.prototype, 'scrollIntoView', scrollDescriptor); else Reflect.deleteProperty(Element.prototype, 'scrollIntoView') })

beforeEach(() => {
  vi.spyOn(apiClient, 'request').mockImplementation(async (path) => {
    if (path.startsWith('/reports/summary')) return summary
    if (path.startsWith('/reports/revenue-series')) return series
    if (path.startsWith('/invoices')) return empty
    if (path.startsWith('/customers')) return { items: [{ id: 'customer-a', display_name: 'Example workshop', email: 'workshop@example.invalid' }], total: 1, page: 1, page_size: 25 }
    if (path === '/billing/run-due') return { data: { invoices_created: 1, processed_periods: 1, failed_subscription_count: 0, has_more_due: false } }
    throw new Error(`Unexpected test request ${path}`)
  })
})

describe('report date semantics', () => {
  it('uses UTC calendar days across leap years and serializes exclusive ranges', () => {
    expect(shiftDate('2024-02-29', 1)).toBe('2024-03-01')
    expect(shiftDate('2026-11-01', -1)).toBe('2026-10-31')
    expect(shiftDate('2026-02-30', 1)).toBe('')
    expect(reportQuery({ from: '2026-10-01', to: '2026-11-01', customerId: 'abc', customerName: '' }, 'DAILY')).toBe('?from=2026-10-01&to=2026-11-01&customer_id=abc&cadence=DAILY')
  })
})

describe('Overview', () => {
  it('does not submit enclosing filters when customer-search Enter has loading or empty results', async () => {
    let resolveSearch!: (value: { items: []; total: number; page: number; page_size: number }) => void
    vi.mocked(apiClient.request).mockImplementation(() => new Promise(resolve => { resolveSearch = resolve }))
    const submit = vi.fn()
    const choose = vi.fn()
    render(<form onSubmit={event => { event.preventDefault(); submit() }}><CustomerFilter selectedId="" selectedName="" onChange={choose} /><button type="submit">Apply</button></form>)
    await userEvent.click(screen.getByRole('button', { name: 'All customers' }))
    await waitFor(() => expect(apiClient.request).toHaveBeenCalled())
    const search = screen.getByRole('combobox', { name: 'Find a customer' })
    await userEvent.keyboard('{Enter}')
    expect(submit).not.toHaveBeenCalled()
    expect(choose).not.toHaveBeenCalled()
    resolveSearch({ items: [], total: 0, page: 1, page_size: 25 })
    await screen.findByText('No matching customers.')
    await userEvent.keyboard('{Enter}')
    expect(submit).not.toHaveBeenCalled()
    expect(choose).not.toHaveBeenCalled()
    expect(search).toHaveFocus()
  })
  it('shows backend amounts and current-state labels with accessible chart data', async () => {
    setup()
    expect(await screen.findByText('INR 5,870.16')).toBeVisible()
    expect(screen.getByText('Selected range, tax inclusive')).toBeVisible()
    expect(screen.getByText('No overdue invoices')).toBeVisible()
    const chart = await screen.findByRole('img', { name: /Invoiced and received/ })
    expect(chart.querySelector('g title')).toHaveTextContent('2026-10-01 to 2026-10-02 (exclusive): invoiced INR 200.00; received INR 750.00')
    await userEvent.click(screen.getByRole('button', { name: 'View chart data' }))
    expect(screen.getByRole('region', { name: 'Chart data' })).toHaveTextContent('INR 750.00')
    expect(apiClient.request).toHaveBeenCalledWith('/reports/summary', expect.anything())
  })
  it('applies inclusive final day as an exclusive API end without date-filtering current overdue rows', async () => {
    setup()
    const start = screen.getByLabelText('Report start date')
    await waitFor(() => expect(start).toHaveValue('2026-10-01'))
    await userEvent.clear(screen.getByLabelText('Report final day'))
    await userEvent.type(screen.getByLabelText('Report final day'), '2026-10-20')
    await userEvent.click(screen.getByRole('button', { name: 'Apply filters' }))
    await waitFor(() => expect(apiClient.request).toHaveBeenCalledWith('/reports/summary?from=2026-10-01&to=2026-10-21', expect.anything()))
    const invoiceCalls = vi.mocked(apiClient.request).mock.calls.filter(([path]) => path.startsWith('/invoices'))
    expect(invoiceCalls.every(([path]) => !path.includes('from=') && !path.includes('to='))).toBe(true)
  })
  it('uses searched customer IDs and preserves that filter in reports and current invoice queries', async () => {
    setup()
    await screen.findByText('INR 5,870.16')
    await userEvent.click(screen.getByRole('button', { name: 'All customers' }))
    const search = screen.getByRole('combobox', { name: 'Find a customer' })
    await userEvent.type(search, 'workshop')
    await screen.findByRole('option', { name: /Example workshop/ })
    await userEvent.keyboard('{Enter}')
    await userEvent.click(screen.getByRole('button', { name: 'Apply filters' }))
    await waitFor(() => expect(apiClient.request).toHaveBeenCalledWith('/reports/summary?from=2026-10-01&to=2026-11-01&customer_id=customer-a', expect.anything()))
    await waitFor(() => expect(apiClient.request).toHaveBeenCalledWith('/invoices?overdue=true&page=1&page_size=5&customer_id=customer-a', expect.anything()))
  })
  it('keeps invoice errors independent of successful summary and chart responses', async () => {
    const original = vi.mocked(apiClient.request).getMockImplementation()!
    vi.mocked(apiClient.request).mockImplementation((path, options) => path.startsWith('/invoices') ? Promise.reject(new ApiError(503, 'UNAVAILABLE', 'Invoice service unavailable')) : original(path, options))
    setup()
    expect(await screen.findByText('Invoice service unavailable')).toBeVisible()
    expect(screen.getByText('INR 5,870.16')).toBeVisible()
    expect(screen.queryByText('No overdue invoices')).not.toBeInTheDocument()
  })
  it('does not retain customer result-count guidance after a search error', async () => {
    const original = vi.mocked(apiClient.request).getMockImplementation()!
    vi.mocked(apiClient.request).mockImplementation((path, options) => {
      if (path.startsWith('/customers')) {
        if (new URLSearchParams(path.split('?')[1]).get('q')) return Promise.reject(new ApiError(503, 'UNAVAILABLE', 'Customer search unavailable'))
        return Promise.resolve({ items: [{ id: 'customer-a', display_name: 'Example workshop', email: 'workshop@example.invalid' }], total: 40, page: 1, page_size: 25 })
      }
      return original(path, options)
    })
    setup()
    await screen.findByText('INR 5,870.16')
    await userEvent.click(screen.getByRole('button', { name: 'All customers' }))
    await screen.findByText('Showing the first 25 matches. Refine your search.')
    await userEvent.type(screen.getByRole('combobox', { name: 'Find a customer' }), 'offline')
    expect(await screen.findByText('Customer search unavailable')).toBeVisible()
    expect(screen.queryByText('Showing the first 25 matches. Refine your search.')).not.toBeInTheDocument()
  })
  it('performs explicit billing once and refetches actual reporting records', async () => {
    setup()
    await screen.findByText('INR 5,870.16')
    const before = vi.mocked(apiClient.request).mock.calls.filter(([path]) => path === '/reports/summary').length
    await userEvent.click(screen.getByRole('button', { name: 'Run due billing' }))
    expect(await screen.findByRole('status')).toHaveTextContent('1 invoices created from 1 processed periods.')
    expect(apiClient.request).toHaveBeenCalledWith('/billing/run-due', { method: 'POST', json: {} })
    await waitFor(() => expect(vi.mocked(apiClient.request).mock.calls.filter(([path]) => path === '/reports/summary').length).toBeGreaterThan(before))
  })
})
