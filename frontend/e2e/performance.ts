/** Real-data T30 measurements. No interception, synthetic fetches, or fake successes. */
import { execFileSync } from 'node:child_process'
import { readFileSync, statSync, writeFileSync } from 'node:fs'
import { cpus, platform, release, totalmem } from 'node:os'
import { performance } from 'node:perf_hooks'
import { expect, test, type Browser, type BrowserContext, type Page } from '@playwright/test'

type Json = Record<string, unknown>
type Fixture = {
  test_only: boolean; kind: string; database: string;
  actors: Record<string, { email: string; password: string }>;
  customers: string[]; counts: Record<string, number>;
  first_subscription: { id: string; number: string }; first_invoice: { id: string; number: string };
  seed_environment: Json; financial_reconciliation: Json;
}
const credentialPath = process.env.CADENTRA_PERFORMANCE_CREDENTIALS!
if (statSync(credentialPath).mode & 0o077) throw new Error('Fixture credentials must be mode0600')
const fixture: Fixture = JSON.parse(readFileSync(credentialPath, 'utf8'))
if (!fixture.test_only || fixture.kind !== 'T30' || fixture.database !== 'cadentra_experience_test'
  || fixture.counts.subscriptions !== 5000 || fixture.counts.invoices !== 20000 || fixture.counts.payments !== 20000) {
  throw new Error('Require the explicitly seeded 5000-subscription/20000-invoice T30 dataset')
}
const baseURL = 'http://127.0.0.1:5174'
const artifactPath = process.env.CADENTRA_PERFORMANCE_ARTIFACT!
const warmSamples = 20
const coldSamples = 5
const report: Json = {
  started_at: new Date().toISOString(), commit: execFileSync('git', ['rev-parse', 'HEAD'], { encoding: 'utf8' }).trim(),
  working_tree_dirty: Boolean(execFileSync('git', ['status', '--porcelain'], { encoding: 'utf8' }).trim()),
  environment: { platform: platform(), release: release(), cpus: cpus().length, cpu_model: cpus()[0]?.model,
    memory_bytes: totalmem(), node: process.version, viewport: { width: 1497, height: 1049 },
    base_url: baseURL, serving: 'Vite development server; FastAPI loopback; local PostgreSQL',
    seed: fixture.seed_environment },
  counts: fixture.counts, financial_reconciliation: fixture.financial_reconciliation,
  method: { warm: '20 document navigations/interactions in one authenticated context after one excluded warmup',
    cold: '5 new browser contexts with empty browser cache, reusing valid auth cookies; server/OS/DB caches stay warm',
    browser_ms: 'wall time from navigation/action start through required successful API bodies, exact visible data and two animation frames',
    api_ms: 'independent same-origin APIRequestContext GET including response body; measured after each browser sample',
    percentile: 'nearest rank; cold n=5 p95 equals maximum; sequential local samples, not concurrent load',
    navigation: 'document navigations retain browser HTTP cache in warm context; filters include visible control interaction',
    no_threshold_claim: true },
  routes: {}, gaps: [],
}
const results = report.routes as Record<string, Json>
const gaps = report.gaps as Json[]
const save = () => writeFileSync(artifactPath, JSON.stringify(report, null, 2))
function stats(values: number[]) {
  const sorted = [...values].sort((a, b) => a - b)
  const rank = (fraction: number) => sorted[Math.max(0, Math.ceil(sorted.length * fraction) - 1)]
  return { n: values.length, p50_ms: rank(0.5), p95_ms: rank(0.95), max_ms: sorted.at(-1) }
}
function metric(page: Page, name: string) {
  return page.locator('.report-metric').filter({ has: page.getByRole('heading', { name, exact: true }) }).locator('strong')
}
const rupees = (value: string) => `INR ${new Intl.NumberFormat('en-IN', { minimumFractionDigits: 2 }).format(Number(value))}`

type Api = { path: string; validate: (payload: Json) => void }
type Route = {
  key: string; actor: string; path: string; apis: Api[]; scope: string;
  prepare?: (page: Page) => Promise<void>; action?: (page: Page) => Promise<unknown>;
  complete: (page: Page) => Promise<void>; dependency?: boolean;
}
const summaryApi = (customer = false): Api => ({
  path: `/api/v1/reports/summary${customer ? `?from=2026-07-01&to=2026-11-01&customer_id=${fixture.customers[0]}` : ''}`,
  validate: payload => {
    const data = payload.data as Json
    expect(data.active_subscriptions).toBe(customer ? 2500 : 5000)
    expect(data.outstanding_now).toBe(customer ? '250000.00' : '500000.00')
    if (customer) {
      expect(data.invoiced_gross_in_range).toBe('1000000.00')
      expect(data.cash_received_in_range).toBe('750000.00')
    }
  },
})
const seriesApi = (customer = false): Api => ({
  path: `/api/v1/reports/revenue-series${customer ? `?from=2026-07-01&to=2026-11-01&customer_id=${fixture.customers[0]}&cadence=DAILY` : '?cadence=DAILY'}`,
  validate: payload => expect((payload.data as Json).buckets).toBeInstanceOf(Array),
})
const listApi = (path: string, total: number, pageSize = 25): Api => ({ path, validate: payload => {
  expect(payload.total).toBe(total)
  expect(payload.items).toBeInstanceOf(Array)
  expect((payload.items as Json[]).length).toBe(pageSize)
} })
async function overviewComplete(page: Page, customer = false) {
  await expect(metric(page, 'Active subscriptions')).toHaveText(customer ? '2500' : '5000')
  await expect(metric(page, 'Outstanding')).toHaveText(rupees(customer ? '250000.00' : '500000.00'))
  await expect(page.getByRole('img', { name: 'Invoiced and received' })).toBeVisible()
  if (customer) await expect(metric(page, 'Invoiced')).toHaveText(rupees('1000000.00'))
}
async function tableComplete(page: Page, heading: string) {
  await expect(page.getByRole('heading', { name: heading, exact: true })).toBeVisible()
  await expect(page.locator('tbody tr')).toHaveCount(25)
  await expect(page.locator('tbody tr').first().getByRole('link')).toBeVisible()
}
const routes: Route[] = [
  { key: 'overview-complete', actor: 'staff', path: '/overview', dependency: true,
    apis: [summaryApi(), seriesApi(), listApi('/api/v1/invoices?overdue=true&page=1&page_size=5', 10000, 5)],
    scope: 'Complete Overview: exact summary, chart and five real overdue invoice rows',
    complete: async page => {
      await overviewComplete(page)
      await expect(page.locator('.report-invoices tbody tr')).toHaveCount(5)
      await expect(page.locator('.report-invoices tbody tr').first().getByRole('link')).toBeVisible()
      await expect(page.getByText('Overdue invoices unavailable', { exact: true })).toHaveCount(0)
    } },
  { key: 'overview-summary-chart', actor: 'staff', path: '/overview', apis: [summaryApi(), seriesApi()],
    scope: 'Overview summary and chart only; excludes independently failing overdue invoice table',
    complete: page => overviewComplete(page) },
  { key: 'overview-customer-date-filter', actor: 'staff', path: '/overview', dependency: true,
    apis: [summaryApi(true), seriesApi(true), listApi(`/api/v1/invoices?overdue=true&page=1&page_size=5&customer_id=${fixture.customers[0]}`, 5000, 5)],
    scope: 'Complete filtered Overview: customer search + date range -> exact summary/chart and five real overdue rows, API total5000',
    prepare: async page => { await page.goto('/overview'); await overviewComplete(page) },
    action: async page => {
      await page.getByRole('button', { name: 'All customers', exact: true }).click()
      await page.getByRole('combobox', { name: 'Find a customer' }).fill('T30 Fictional Customer 1')
      await page.getByRole('option').filter({ hasText: 'T30 Fictional Customer 1' }).click()
      await page.getByLabel('Report start date').fill('2026-07-01')
      await page.getByLabel('Report final day').fill('2026-10-31')
      await page.getByRole('button', { name: 'Apply filters', exact: true }).click()
    }, complete: async page => {
      await overviewComplete(page, true)
      await expect(page.locator('.report-invoices tbody tr')).toHaveCount(5)
      await expect(page.locator('.report-invoices tbody tr').first().getByRole('link')).toBeVisible()
      await expect(page.locator('.report-invoices tbody tr').getByText('T30 Fictional Customer 1', { exact: true })).toHaveCount(5)
      await expect(page.getByText('Overdue invoices unavailable', { exact: true })).toHaveCount(0)
    } },
  ...[1, 2].map(pageNumber => ({ key: `portal-subscriptions-page-${pageNumber}`, actor: 'customer_a',
    path: `/portal/subscriptions?page=${pageNumber}`,
    apis: [listApi(`/api/v1/portal/subscriptions?page=${pageNumber}&page_size=25`, 2500)],
    scope: 'Own paginated 25-record table, exact total2500 API validation',
    complete: (page: Page) => tableComplete(page, 'My subscriptions') })),
  ...[1, 2].map(pageNumber => ({ key: `portal-invoices-page-${pageNumber}`, actor: 'customer_a',
    path: `/portal/invoices?page=${pageNumber}`,
    apis: [listApi(`/api/v1/portal/invoices?page=${pageNumber}&page_size=25`, 10000)],
    scope: 'Own paginated 25-record invoice/payment/balance table, exact total10000 API validation',
    complete: (page: Page) => tableComplete(page, 'My invoices') })),
  { key: 'portal-account', actor: 'customer_a', path: '/portal/account',
    apis: [{ path: '/api/v1/portal/me', validate: payload => expect((payload.data as Json).display_name).toBe('T30 Fictional Customer 1') }],
    scope: 'Persisted customer profile', complete: async page => {
      await expect(page.getByRole('heading', { name: 'T30 Fictional Customer 1', exact: true })).toBeVisible()
      await expect(page.getByText('Fictional City', { exact: true })).toBeVisible()
    } },
  { key: 'portal-subscription-drilldown', actor: 'customer_a', path: `/portal/subscriptions/${fixture.first_subscription.id}`,
    apis: [{ path: `/api/v1/portal/subscriptions/${fixture.first_subscription.id}`, validate: payload => {
      expect((payload.data as Json).number).toBe(fixture.first_subscription.number)
      expect(((payload.data as Json).invoices as Json[]).length).toBe(4)
    } }], scope: 'Own subscription snapshot and four real invoice links', complete: async page => {
      await expect(page.getByRole('heading', { name: 'T30 fictional monthly service', exact: true })).toBeVisible()
      await expect(page.locator('.portal-document-list li')).toHaveCount(4)
      await expect(page.getByRole('link', { name: fixture.first_invoice.number })).toBeVisible()
    } },
  { key: 'portal-invoice-drilldown', actor: 'customer_a', path: `/portal/invoices/${fixture.first_invoice.id}`, dependency: true,
    apis: [{ path: `/api/v1/portal/invoices/${fixture.first_invoice.id}`, validate: payload => {
      expect((payload.data as Json).number).toBe(fixture.first_invoice.number)
      expect((payload.data as Json).total).toBe('100.00')
    } }], scope: 'Own stored invoice, line and recorded payment', complete: async page => {
      await expect(page.getByRole('heading', { name: fixture.first_invoice.number, exact: true })).toBeVisible()
      await expect(page.getByRole('heading', { name: 'Recorded payments', exact: true })).toBeVisible()
      await expect(page.getByRole('link', { name: 'Print invoice', exact: true })).toBeVisible()
    } },
  ...[{ key: 'staff-subscriptions', path: '/subscriptions', api: '/api/v1/subscriptions?page=1&page_size=25', total: 5000, heading: 'Subscriptions' },
    { key: 'staff-invoices', path: '/billing/invoices', api: '/api/v1/invoices?page=1&page_size=25', total: 20000, heading: 'Invoices' }].map(row => ({
    key: row.key, actor: 'staff', path: row.path, apis: [listApi(row.api, row.total)], dependency: true,
    scope: 'Owner-backed staff list, only measured after API and rendered table are integrated',
    complete: (page: Page) => tableComplete(page, row.heading),
  })),
]
async function authenticatedContext(browser: Browser, actor: string) {
  const context = await browser.newContext({ baseURL, viewport: { width: 1497, height: 1049 } })
  const response = await context.request.post('/api/v1/auth/login', {
    headers: { Origin: baseURL }, data: { email: fixture.actors[actor].email, password: fixture.actors[actor].password },
  })
  expect(response.status()).toBe(200)
  return context
}
async function sample(context: BrowserContext, route: Route) {
  const page = await context.newPage()
  const errors: string[] = []
  page.on('pageerror', error => errors.push(error.message))
  try {
    if (route.prepare) await route.prepare(page)
    const responses = Promise.all(route.apis.map(api => page.waitForResponse(response => {
      const actual = new URL(response.url())
      const wanted = new URL(api.path, baseURL)
      return actual.pathname === wanted.pathname && [...wanted.searchParams].every(([key, value]) => actual.searchParams.get(key) === value)
    })))
    const start = performance.now()
    const [bodies] = await Promise.all([responses, route.action ? route.action(page) : page.goto(route.path)])
    for (const [index, response] of bodies.entries()) {
      expect(response.status(), `${route.key}: ${route.apis[index].path}`).toBe(200)
      route.apis[index].validate(await response.json())
    }
    await route.complete(page)
    await page.evaluate(async () => {
      await document.fonts.ready
      await new Promise<void>(resolve => requestAnimationFrame(() => requestAnimationFrame(() => resolve())))
    })
    const browserMs = performance.now() - start
    expect(errors).toEqual([])
    const apiMs: Record<string, number> = {}
    for (const api of route.apis) {
      const before = performance.now()
      const response = await context.request.get(api.path)
      const body: Json = await response.json()
      apiMs[api.path] = performance.now() - before
      expect(response.status()).toBe(200)
      api.validate(body)
    }
    return { browser_ms: browserMs, api_ms: apiMs }
  } finally { await page.close() }
}

test.beforeAll(async ({ browser }) => {
  report.browser = browser.version()
  const context = await authenticatedContext(browser, 'staff')
  try {
    const response = await context.request.get('/api/v1/invoices?overdue=true&page=1&page_size=5')
    if ([404, 501].includes(response.status())) gaps.push({ surface: 'Overview overdue table', reason: `Owner API HTTP${response.status()}; excluded from summary/chart component samples` })
    else expect(response.status()).toBe(200)
  } finally { await context.close(); save() }
})
test.afterAll(() => { report.finished_at = new Date().toISOString(); save() })
for (const route of routes) {
  test(`${route.key}: 20 warm + 5 fresh-context navigations`, async ({ browser }) => {
    const context = await authenticatedContext(browser, route.actor)
    const raw: { mode: string; browser_ms: number; api_ms: Record<string, number> }[] = []
    results[route.key] = { scope: route.scope, status: 'running', samples: raw }
    try {
      if (route.dependency) {
        for (const api of route.apis) {
          const probe = await context.request.get(api.path)
          if ([404, 501].includes(probe.status())) {
            const reason = `Owner API ${new URL(api.path, baseURL).pathname} HTTP${probe.status()}; no successful navigation measurements`
            gaps.push({ surface: route.key, reason }); results[route.key].status = 'dependency-gap'; save()
            test.skip(true, reason)
          }
          expect(probe.status()).toBe(200)
        }
        const page = await context.newPage()
        await page.goto(route.path)
        const placeholder = page.getByText('This feature is not implemented yet.', { exact: false })
        if (await placeholder.isVisible()) {
          const reason = 'Owner UI remains a placeholder; no successful navigation measurements'
          gaps.push({ surface: route.key, reason }); results[route.key].status = 'dependency-gap'; save()
          test.skip(true, reason)
        }
        await page.close()
      }
      await sample(context, route) // Excluded route warmup; validates actual data before measurements.
      for (let index = 0; index < warmSamples; index++) {
        raw.push({ mode: 'warm', ...await sample(context, route) }); save()
      }
      const storageState = await context.storageState()
      for (let index = 0; index < coldSamples; index++) {
        const cold = await browser.newContext({ baseURL, storageState, viewport: { width: 1497, height: 1049 } })
        try { raw.push({ mode: 'cold', ...await sample(cold, route) }); save() }
        finally { await cold.close() }
      }
      for (const mode of ['warm', 'cold']) {
        const samples = raw.filter(row => row.mode === mode)
        results[route.key][mode] = { browser: stats(samples.map(row => row.browser_ms)),
          api: Object.fromEntries(route.apis.map(api => [api.path, stats(samples.map(row => row.api_ms[api.path]))])) }
      }
      results[route.key].status = 'measured'
    } catch (error) {
      // Playwright skip throws internally; preserve its explicit dependency status.
      if (results[route.key].status !== 'dependency-gap') results[route.key].status = 'failed'
      throw error
    } finally { await context.close(); save() }
  })
}
