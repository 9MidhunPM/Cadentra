import type { Page } from '@playwright/test'

/** Isolated UI fixtures; real HTTP/PostgreSQL coverage uses the separate live config. */
export async function mockFeatureReads(page: Page) {
  const list = { items: [], total: 0, page: 1, page_size: 25 }
  await page.route('**/api/v1/reports/summary**', route => route.fulfill({ json: { data: {
    as_of: '2026-10-31', range_from: '2026-10-01', range_to: '2026-11-01', currency: 'INR',
    active_subscriptions: 0, invoiced_gross_in_range: '0.00', cash_received_in_range: '0.00',
    outstanding_now: '0.00', overdue_now: '0.00', overdue_invoice_count: 0, metric_basis: {},
  } } }))
  await page.route('**/api/v1/reports/revenue-series**', route => route.fulfill({ json: { data: {
    range_from: '2026-10-01', range_to: '2026-11-01', currency: 'INR', cadence: 'DAILY', buckets: [],
  } } }))
  await page.route('**/api/v1/reports/cycleguard**', route => route.fulfill({ json: { ...list, as_of: '2026-10-31' } }))
  await page.route(/\/api\/v1\/(?:customers|products|plans|tax-rules|discount-rules|quotation-templates|subscriptions|invoices)(?:\?.*)?$/, route => route.fulfill({ json: list }))
  await page.route(/\/api\/v1\/portal\/subscriptions(?:\?.*)?$/, route => route.fulfill({ json: list }))
  await page.route(/\/api\/v1\/portal\/invoices(?:\?.*)?$/, route => route.fulfill({ json: list }))
  await page.route('**/api/v1/portal/me', route => route.fulfill({ json: { data: {
    id: 'test-customer', display_name: 'Foundation customer', email: 'fixture@example.invalid', company_name: null, billing_address: {},
  } } }))
}
