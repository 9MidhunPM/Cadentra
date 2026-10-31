import { readFileSync } from 'node:fs'
import { expect, test, type Page } from '@playwright/test'

type Actor = { email: string; password: string; id: string }
type RecordRef = { id: string; number: string; customer_id: string }
const fixture = JSON.parse(readFileSync(process.env.CADENTRA_LIVE_CREDENTIALS!, 'utf8')) as {
  test_only: boolean; actors: Record<string, Actor>; customers: Record<string, string>;
  subscriptions: Record<string, RecordRef>; invoices: Record<string, RecordRef>;
}
if (!fixture.test_only) throw new Error('A disposable live fixture is required')

async function login(page: Page, actor: string) {
  const response = await page.request.post('/api/v1/auth/login', {
    headers: { Origin: 'http://127.0.0.1:5174' },
    data: { email: fixture.actors[actor].email, password: fixture.actors[actor].password },
  })
  expect(response.status()).toBe(200)
}
async function navigation(page: Page, label: string) {
  await expect(page.locator('main h1')).toBeVisible()
  const menu = page.getByRole('button', { name: 'Open navigation' })
  if (await menu.isVisible()) await menu.click()
  await page.getByRole('navigation').getByRole('link', { name: label, exact: true }).click()
}
function metric(page: Page, label: string) {
  return page.locator('.report-metric').filter({ has: page.getByRole('heading', { name: label, exact: true }) }).locator('strong')
}

test('real database reports reconcile and survive browser reload', async ({ page }, testInfo) => {
  await login(page, 'staff')
  const errors: string[] = []
  page.on('pageerror', error => errors.push(error.message))
  await page.goto('/overview')
  await expect(metric(page, 'Active subscriptions')).toHaveText('2')
  await page.getByLabel('Report start date').fill('2026-10-01')
  await page.getByLabel('Report final day').fill('2026-10-31')
  await page.getByRole('button', { name: 'Apply filters', exact: true }).click()
  await expect(metric(page, 'Invoiced')).toHaveText('INR 5,870.16')
  await expect(metric(page, 'Payments received')).toHaveText('INR 3,050.00')
  await expect(metric(page, 'Outstanding')).toHaveText('INR 3,570.16')
  await expect(metric(page, 'Overdue')).toHaveText('INR 3,170.16')
  await page.getByRole('button', { name: 'View chart data' }).click()
  await expect(page.getByRole('region', { name: 'Chart data' })).toContainText('INR 4,970.16')
  const response = await page.request.get('/api/v1/reports/summary?from=2026-10-01&to=2026-11-01')
  expect((await response.json()).data.invoiced_gross_in_range).toBe('5870.16')
  await page.getByRole('button', { name: 'Hide chart data' }).click()
  await page.evaluate(() => window.scrollTo(0, 0))
  const dark = page.getByRole('button', { name: 'Switch to light mode' })
  await expect(dark).toBeVisible()
  await page.screenshot({ path: testInfo.outputPath('live-report-graphite.png'), fullPage: true })
  await dark.click()
  await expect(page.getByRole('button', { name: 'Switch to dark mode' }).locator(':scope > span')).toHaveCSS('opacity', '1')
  await page.screenshot({ path: testInfo.outputPath('live-report-sage.png'), fullPage: true })
  await page.reload()
  await expect(metric(page, 'Active subscriptions')).toHaveText('2')
  await expect(metric(page, 'Outstanding')).toHaveText('INR 3,570.16')
  expect(errors).toEqual([])
})

test('real customer portal owns records and rejects another customer', async ({ page }) => {
  await login(page, 'customer_a')
  await page.goto('/portal/subscriptions')
  await expect(page.getByRole('heading', { name: 'My subscriptions', exact: true })).toBeVisible()
  const foreign = Object.values(fixture.subscriptions).find(row => row.customer_id === fixture.customers.B)!
  const own = Object.values(fixture.subscriptions).find(row => row.customer_id === fixture.customers.A)!
  expect((await page.request.get(`/api/v1/portal/subscriptions/${own.id}`)).status()).toBe(200)
  expect((await page.request.get(`/api/v1/portal/subscriptions/${foreign.id}`)).status()).toBe(404)
  await expect(page.getByRole('link', { name: foreign.number, exact: true })).toHaveCount(0)
  await page.getByRole('link', { name: own.number, exact: true }).click()
  await expect(page.getByRole('heading', { name: 'My subscription', exact: true })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Reporting fixture', exact: true })).toBeVisible()
  for (const step of await page.getByRole('list', { name: 'Subscription lifecycle' }).getByRole('listitem').all()) {
    await expect(step).toBeInViewport({ ratio: 1 })
  }
  await page.reload()
  await expect(page.getByRole('heading', { name: 'Reporting fixture', exact: true })).toBeVisible()
  await navigation(page, 'My invoices')
  const foreignInvoice = Object.values(fixture.invoices).find(row => row.customer_id === fixture.customers.B)!
  await expect(page.getByRole('heading', { name: 'My invoices', exact: true })).toBeVisible()
  await expect(page.getByRole('link', { name: foreignInvoice.number, exact: true })).toHaveCount(0)
  await expect(page.getByText('INR 2,970.16', { exact: true })).toBeVisible()
  await page.reload()
  await expect(page.getByText('INR 2,970.16', { exact: true })).toBeVisible()
  await navigation(page, 'Account')
  await expect(page.getByRole('heading', { name: 'Fixture Customer A' })).toBeVisible()
  expect((await page.request.get('/api/v1/reports/summary')).status()).toBe(403)
})

test('invoice detail and print isolation require owner-backed endpoints', async ({ page }) => {
  await login(page, 'customer_a')
  const own = Object.values(fixture.invoices).find(row => row.customer_id === fixture.customers.A)!
  const foreign = Object.values(fixture.invoices).find(row => row.customer_id === fixture.customers.B)!
  const response = await page.request.get(`/api/v1/portal/invoices/${own.id}`)
  expect(response.status()).toBe(200)
  expect((await page.request.get(`/api/v1/portal/invoices/${foreign.id}`)).status()).toBe(404)
  expect((await page.request.get(`/api/v1/portal/invoices/${own.id}/print`)).status()).toBe(200)
  expect((await page.request.get(`/api/v1/portal/invoices/${foreign.id}/print`)).status()).toBe(404)
})
