/** Final T30: built static UI -> native NGINX -> real API/PostgreSQL. No mocks. */
import { readFileSync, renameSync, writeFileSync } from 'node:fs'
import { cpus, platform, release, totalmem } from 'node:os'
import { dirname } from 'node:path'
import { performance } from 'node:perf_hooks'
import { fileURLToPath } from 'node:url'
import { devices, expect, test, type Browser, type BrowserContext, type Page } from '@playwright/test'
import { checkedOrigin, PERFORMANCE_INGRESS_HEADERS, digest, readManifest, runtimeInputs, tmpPath, type NativeEvidence } from './performance-server'

type Json = Record<string, unknown>
type Storage = Awaited<ReturnType<BrowserContext['storageState']>>
type ActorKey = 'admin' | 'staff' | 'customer_a' | 'anonymous'
type Ref = { id: string; name: string }
type InvoiceRef = { id: string; number: string; total: string; paid_amount: string; balance_due: string; status: string }
type Fixture = {
  test_only: true; kind: 'T30'; database: 'cadentra_performance_test'; schema: string; run: string;
  actors: Record<Exclude<ActorKey, 'anonymous'>, { id: string; email: string; password: string; storage_state?: Storage }>;
  customers: string[]; customer_names: string[]; counts: Record<string, number>;
  expected: Record<string, string | number>; first_subscription: { id: string; number: string };
  paid_invoice: InvoiceRef; partial_invoice: InvoiceRef; reset_form_token: 'fixture-form-only-invalid';
  refs: { product: Ref; variant: { id: string; attribute_name: string; attribute_value: string };
    plan: Ref & { base_fee: string }; template: Ref & { valid_days: number };
    tax: Ref & { rate_percent: string }; discount: Ref & { kind: string; value: string } };
  seed_environment: Json; financial_reconciliation: Json;
}
const credentialPath = tmpPath(process.env.CADENTRA_PERFORMANCE_CREDENTIALS, 'Private fixture manifest')
const fixture: Fixture = readManifest(credentialPath)
for (const [key, count] of Object.entries({ subscriptions: 5000, invoices: 20000, payments: 20000, invoice_lines: 40000,
  customers: 2, products: 1, product_variants: 1, plans: 1, quotation_templates: 1, tax_rules: 1, discount_rules: 1 })) {
  if (fixture.counts[key] !== count) throw new Error(`Fixture count ${key} does not match the final T30 contract`)
}
if (fixture.reset_form_token !== 'fixture-form-only-invalid') throw new Error('Only the public invalid reset-form sentinel is permitted')
const origin = checkedOrigin()
const artifact = tmpPath(process.env.CADENTRA_PERFORMANCE_ARTIFACT, 'Measurement artifact')
const metadataPath = tmpPath(process.env.CADENTRA_PERFORMANCE_SERVER_METADATA, 'Native server metadata')
const native: NativeEvidence = JSON.parse(readFileSync(metadataPath, 'utf8'))
if (native.test_only !== true || native.serving !== 'native-nginx-static' || native.origin !== origin
  || native.api_origin !== 'http://127.0.0.1:8004' || native.database !== fixture.database || native.schema !== fixture.schema || native.dataset_run !== fixture.run
  || native.production_config !== 'nginx.production.conf' || native.api_environment !== 'test'
  || native.ingress_fixture?.original_peer !== '10.0.1.20' || native.ingress_fixture?.native_peer !== '127.0.0.1'
  || native.ingress_fixture?.cf_connecting_ip !== PERFORMANCE_INGRESS_HEADERS['CF-Connecting-IP']
  || native.docker_verified !== false || native.traefik_verified !== false || native.production_deployment_verified !== false || native.server_stopped) throw new Error('Native server and fixture provenance do not match')
const repo = dirname(dirname(dirname(fileURLToPath(import.meta.url))))
const inputs = runtimeInputs(repo)
if (inputs.source_sha256 !== native.inputs.source_sha256 || inputs.dist_sha256 !== native.inputs.dist_sha256
  || inputs.harness_sha256 !== native.inputs.harness_sha256) {
  throw new Error('Runtime source/build changed after native server startup')
}
const measurementRun = process.env.CADENTRA_PERFORMANCE_RUN!
let existing: Json | null = null
try { existing = JSON.parse(readFileSync(artifact, 'utf8')) }
catch (error) { if ((error as NodeJS.ErrnoException).code !== 'ENOENT') throw error }
if (existing && (existing.dataset_run !== fixture.run || existing.schema !== fixture.schema
  || existing.measurement_run !== measurementRun || existing.runtime_source_sha256 !== inputs.source_sha256
  || existing.dist_sha256 !== inputs.dist_sha256 || existing.harness_sha256 !== inputs.harness_sha256 || existing.commit !== native.commit)) {
  throw new Error('Artifact belongs to another dataset/run/runtime; use a new artifact filename')
}
const report: Json = existing || {
  started_at: new Date().toISOString(), dataset_run: fixture.run, schema: fixture.schema, database: fixture.database,
  measurement_run: measurementRun, commit: native.commit, working_tree_dirty: native.working_tree_dirty,
  runtime_source_sha256: inputs.source_sha256, dist_sha256: inputs.dist_sha256, harness_sha256: inputs.harness_sha256, native,
  environment: { platform: platform(), release: release(), logical_cpus: cpus().length, cpu_model: cpus()[0]?.model,
    memory_bytes: totalmem(), node: process.version, viewport: { width: 1497, height: 1049 },
    serving: 'Production dist served by native NGINX; real loopback API and isolated PostgreSQL schema', seed: fixture.seed_environment },
  counts: fixture.counts, financial_reconciliation: fixture.financial_reconciliation,
  method: { warm: '20 document navigations/interactions in one context after one excluded route warmup',
    cold: '5 fresh browser contexts with empty browser cache; valid actor cookies reused; server/OS/PostgreSQL caches remain warm',
    browser_ms: 'Navigation start through validated required API bodies, all observed API completion, exact visible data, fonts and two frames; includes initial navigation for filters/forms',
    api_ms: 'Independent same-origin GET and complete response body after each browser sample; expected status retained per endpoint',
    percentiles: 'Nearest rank; fresh-context n=5 p95 is maximum; sequential local measurements, not concurrent load',
    authentication: 'One real login per fixture actor cached only inside its mode0600 manifest; public forms anonymous; no repeated login/reset mutations',
    anonymous_401: 'Allowed only for /api/v1/auth/session on explicitly anonymous auth-form cases',
    reset: 'Public invalid sentinel renders form only; no real token or reset mutation',
    docker_verified: false },
  coverage_limits: [
    'All5000 subscriptions are ACTIVE; no other lifecycle-state-specific form latency is claimed.',
    'Only authentication setup creates sessions. No financial, lifecycle, catalog, rule or account mutation latency is measured.',
    'Reset uses a public invalid form sentinel; no real token, reset mutation or email delivery is verified.',
    'Catalog/configuration tables have their recorded small fixture counts; these are not5000-product stress tests.',
    'Strict production NGINX uses a native loopback trusted-peer adaptation and public fixture CF header; API remains APP_ENV=test. This does not verify real Traefik/Cloudflare, production API-peer enforcement, Docker or deployment.',
  ],
  routes: {}, gaps: [], captures: [],
}
const results = report.routes as Record<string, Json>
const save = () => {
  writeFileSync(`${artifact}.tmp`, JSON.stringify(report, null, 2))
  renameSync(`${artifact}.tmp`, artifact)
}
function stats(values: number[]) {
  const sorted = [...values].sort((a, b) => a - b)
  const rank = (quantile: number) => sorted[Math.max(0, Math.ceil(sorted.length * quantile) - 1)]
  return { n: values.length, p50_ms: rank(.5), p95_ms: rank(.95), max_ms: sorted.at(-1) }
}
const count = (key: string) => {
  const value = fixture.expected[key]
  if (typeof value !== 'number') throw new Error(`Missing expected persisted count ${key}`)
  return value
}
const amount = (key: string) => {
  const value = fixture.expected[key]
  if (typeof value !== 'string' || !/^\d+\.\d{2}$/.test(value)) throw new Error(`Missing expected decimal ${key}`)
  return value
}
// Formatting expected server decimal strings is presentation, never financial arithmetic.
const money = (value: string) => `INR ${new Intl.NumberFormat('en-IN', { minimumFractionDigits: 2 }).format(Number(value))}`
const apiPath = (path: string) => `/api/v1${path}`
type Api = { path: string; status?: number; html?: boolean; validate: (payload: Json | string) => void }
type Route = { key: string; actor: ActorKey; path: string; scope: string; apis: Api[]; rawDocument?: boolean;
  enter?: (page: Page) => Promise<void>; ready: (page: Page) => Promise<void> }
const object = (value: Json | string) => {
  if (typeof value === 'string') throw new Error('Expected a JSON API body')
  return value
}
const data = (value: Json | string) => object(value).data as Json
const sessionApi = (actor: ActorKey): Api => ({ path: apiPath('/auth/session'), status: actor === 'anonymous' ? 401 : 200,
  validate: value => {
    if (actor === 'anonymous') expect((object(value).error as Json).code).toBe('UNAUTHENTICATED')
    else {
      const session = data(value)
      expect((session.actor as Json).id).toBe(fixture.actors[actor].id)
      expect((session.actor as Json).role).toBe({ admin: 'ADMIN', staff: 'STAFF', customer_a: 'CUSTOMER' }[actor])
      expect(typeof session.csrf_token).toBe('string')
    }
  } })
function list(path: string, total: number, rowCount = Math.min(25, total), ref?: Ref): Api {
  return { path: apiPath(path), validate: value => {
    const result = object(value)
    expect(result.total).toBe(total)
    expect(Array.isArray(result.items)).toBe(true)
    const rows = result.items as Json[]
    expect(rows.length).toBe(rowCount)
    if (ref) expect(rows.find(row => row.id === ref.id)?.name).toBe(ref.name)
  } }
}
const customerList = (size = 100, search = '') => list(`/customers?page_size=${size}&q=${encodeURIComponent(search)}`,
  search ? 1 : fixture.counts.customers, search ? 1 : fixture.counts.customers)
function detail(path: string, id: string, validate: (row: Json) => void): Api {
  return { path: apiPath(path), validate: value => { const row = data(value); expect(row.id).toBe(id); validate(row) } }
}
function metric(page: Page, label: string) {
  return page.locator('.report-metric').filter({ has: page.getByRole('heading', { name: label, exact: true }) }).locator('strong')
}
const table = (page: Page, caption: string) => page.getByRole('region', { name: caption, exact: true })
async function rows(page: Page, caption: string, expected: number, total: number) {
  await expect(table(page, caption).locator('tbody tr')).toHaveCount(expected)
  await expect(page.getByRole('navigation', { name: `${caption} pagination`, exact: true })).toContainText(`${total} ${total === 1 ? 'record' : 'records'}`)
}
const heading = (page: Page, title: string) => expect(page.getByRole('heading', { name: title, exact: true })).toBeVisible()
const customerName = fixture.customer_names[0]
const summary = (customer = false, range = false): Api => ({
  path: apiPath(`/reports/summary${range ? `?from=2026-07-01&to=2026-11-01${customer ? `&customer_id=${fixture.customers[0]}` : ''}` : ''}`),
  validate: value => {
    const row = data(value)
    expect(row.active_subscriptions).toBe(customer ? count('customer_active') : count('active'))
    expect(row.outstanding_now).toBe(amount(customer ? 'customer_outstanding' : 'outstanding'))
    expect(row.invoiced_gross_in_range).toBe(range ? amount(customer ? 'customer_invoiced' : 'invoiced') : '0.00')
    expect(row.cash_received_in_range).toBe(range ? amount(customer ? 'customer_cash' : 'cash') : '0.00')
    expect(row.overdue_invoice_count).toBe(count(customer ? 'customer_overdue' : 'overdue'))
    expect(row.as_of).toBe('2026-11-02')
  },
})
const series = (customer = false, range = false, cadence = 'DAILY'): Api => ({
  path: apiPath(`/reports/revenue-series?cadence=${cadence}${range ? `&from=2026-07-01&to=2026-11-01${customer ? `&customer_id=${fixture.customers[0]}` : ''}` : ''}`),
  validate: value => {
    const row = data(value)
    expect(row.range_from).toBe(range ? '2026-07-01' : '2026-11-01')
    expect(row.range_to).toBe(range ? '2026-11-01' : '2026-11-03')
    expect(Array.isArray(row.buckets)).toBe(true)
    expect((row.buckets as Json[]).length).toBe(cadence === 'MONTHLY' ? 4 : range ? 123 : 2)
    for (const bucket of row.buckets as Json[]) {
      expect(bucket.invoiced_gross).toMatch(/^\d+\.\d{2}$/)
      expect(bucket.cash_received).toMatch(/^\d+\.\d{2}$/)
    }
  },
})
const overdue = (customer = false) => list(`/invoices?overdue=true&page=1&page_size=5${customer ? `&customer_id=${fixture.customers[0]}` : ''}`,
  count(customer ? 'customer_overdue' : 'overdue'), 5)
async function overview(page: Page, customer = false, range = false) {
  await heading(page, 'Overview')
  await expect(metric(page, 'Active subscriptions')).toHaveText(String(count(customer ? 'customer_active' : 'active')))
  await expect(metric(page, 'Outstanding')).toHaveText(money(amount(customer ? 'customer_outstanding' : 'outstanding')))
  await expect(metric(page, 'Invoiced')).toHaveText(money(range ? amount(customer ? 'customer_invoiced' : 'invoiced') : '0.00'))
  await expect(page.getByRole('img', { name: 'Invoiced and received' })).toBeVisible()
  await rows(page, 'Overdue invoices', 5, count(customer ? 'customer_overdue' : 'overdue'))
}
async function rangeControls(page: Page, customer = false) {
  if (customer) {
    await page.getByRole('button', { name: 'All customers', exact: true }).click()
    await page.getByRole('combobox', { name: 'Find a customer' }).fill(customerName)
    await page.getByRole('option').filter({ hasText: customerName }).click()
  }
  await page.getByLabel('Report start date').fill('2026-07-01')
  await page.getByLabel('Report final day').fill('2026-10-31')
  await page.getByRole('button', { name: 'Apply filters', exact: true }).click()
}
const invoiceApi = (portal: boolean, row: InvoiceRef) => detail(`${portal ? '/portal' : ''}/invoices/${row.id}`, row.id, value => {
  expect(value.number).toBe(row.number); expect(value.status).toBe(row.status)
  expect(value.total).toBe(row.total); expect(value.paid_amount).toBe(row.paid_amount); expect(value.balance_due).toBe(row.balance_due)
  expect((value.lines as Json[]).length).toBe(count('invoice_lines_count'))
  expect((value.payments as Json[]).length).toBe(1)
})
async function invoiceReady(page: Page, portal: boolean, row: InvoiceRef) {
  await heading(page, row.number)
  await expect(page.locator('.ui-badge').filter({ hasText: row.status === 'PAID' ? /^Paid$/ : /^Partially paid$/ }).first()).toBeVisible()
  await expect(page.getByRole('link', { name: 'Print invoice', exact: true })).toBeVisible()
  if (portal) {
    await heading(page, 'Recorded payments')
    await expect(page.locator('.portal-balance')).toContainText(money(row.balance_due))
    await expect(page.locator('.portal-detail-main table').first().locator('tbody tr')).toHaveCount(count('invoice_lines_count'))
  } else {
    await heading(page, 'Stored invoice lines')
    await rows(page, 'Payments', 1, 1)
    await expect(table(page, 'Stored invoice lines').locator('tbody tr')).toHaveCount(count('invoice_lines_count'))
    await expect(page.locator('.billing-totals').filter({ has: page.getByText('Balance due', { exact: true }) })).toContainText(money(row.balance_due))
    if (row.status === 'CONFIRMED') {
      await heading(page, 'Record a manual payment')
      await expect(page.getByLabel('Amount', { exact: true })).toBeVisible()
    } else await expect(page.getByRole('heading', { name: 'Record a manual payment', exact: true })).toHaveCount(0)
  }
}
const subscriptionApi = (portal: boolean) => detail(`${portal ? '/portal' : ''}/subscriptions/${fixture.first_subscription.id}`,
  fixture.first_subscription.id, row => {
    expect(row.number).toBe(fixture.first_subscription.number); expect(row.state).toBe('ACTIVE')
    expect((row.invoice_references as Json[]).length).toBe(4)
    expect((row.lines as Json[]).length).toBe(1)
    expect(row.recurring_subtotal).toBe('100.00')
  })
async function subscriptionReady(page: Page, portal: boolean) {
  await heading(page, portal ? 'My subscription' : fixture.first_subscription.number)
  await heading(page, 'Agreed product lines')
  await expect(page.locator('.ui-badge').filter({ hasText: /^Active$/ }).first()).toBeVisible()
  if (portal) await expect(page.locator('.portal-document-list li')).toHaveCount(4)
  else {
    await heading(page, 'Invoice history')
    await expect(page.locator('a[href^="/billing/invoices/"]')).toHaveCount(4)
  }
  await expect(page.getByRole('link', { name: new RegExp(fixture.paid_invoice.number) })).toBeVisible()
}
const catalogLookups: Api[] = [list('/customers?page=1&page_size=100', 2, 2),
  list('/plans?page=1&page_size=100', 1, 1, fixture.refs.plan), list('/products?page=1&page_size=100', 1, 1, fixture.refs.product),
  list('/quotation-templates?page=1&page_size=100', 1, 1, fixture.refs.template)]
const productDetail = detail(`/products/${fixture.refs.product.id}`, fixture.refs.product.id, value => {
  expect(value.name).toBe(fixture.refs.product.name)
  expect((value.variants as Json[]).some(row => row.id === fixture.refs.variant.id)).toBe(true)
})
async function option(page: Page, label: string, id: string) {
  await expect(page.getByLabel(label, { exact: true }).locator(`option[value="${id}"]`)).toHaveCount(1)
}
const routes: Route[] = [
  ...['/overview', '/'].map(path => ({ key: path === '/' ? 'staff-landing' : 'overview', actor: 'staff' as const, path,
    scope: 'Complete dashboard with summary/chart/five real overdue invoices', apis: [summary(), series(), overdue()], ready: (page: Page) => overview(page) })),
  ...[false, true].map(customer => ({ key: customer ? 'overview-customer-date-filter' : 'overview-date-filter', actor: 'staff' as const,
    path: '/overview', scope: 'Navigation plus visible date/customer filter completion; exact stored amounts and overdue table',
    apis: [summary(customer, true), series(customer, true), overdue(customer), ...(customer ? [customerList(25, customerName)] : [])],
    enter: async (page: Page) => { await page.goto('/overview'); await overview(page); await rangeControls(page, customer) },
    ready: (page: Page) => overview(page, customer, true) })),
  { key: 'overview-monthly-chart', actor: 'staff', path: '/overview', scope: 'Selected range and monthly chart cadence',
    apis: [summary(false, true), series(false, true, 'MONTHLY'), overdue()], enter: async page => {
      await page.goto('/overview'); await overview(page); await rangeControls(page)
      await page.getByLabel('Group by').selectOption('MONTHLY')
    }, ready: async page => { await overview(page, false, true); await expect(page.getByLabel('Group by')).toHaveValue('MONTHLY') } },
  { key: 'overview-overdue-drilldown', actor: 'staff', path: '/overview', scope: 'Actual dashboard overdue link honors URL query on the merged owner UI',
    apis: [list('/invoices?page=1&page_size=25&overdue=true', count('overdue')), customerList()], enter: async page => {
      await page.goto('/overview'); await overview(page)
      await page.getByRole('link', { name: 'View overdue invoices', exact: true }).click()
    }, ready: async page => { await heading(page, 'Invoices'); await rows(page, 'Invoices', 25, count('overdue'))
      await expect(page.getByLabel('Collection', { exact: true })).toHaveValue('true') } },
  ...[1, 2].map(page => ({ key: `staff-subscriptions-page-${page}`, actor: 'staff' as const, path: `/subscriptions?page=${page}`,
    scope: '25 real staff subscription records from the5000-row dataset', apis: [list(`/subscriptions?page=${page}&page_size=25`, 5000)],
    ready: async (browserPage: Page) => { await heading(browserPage, 'Subscriptions'); await rows(browserPage, 'Subscriptions', 25, 5000) } })),
  { key: 'staff-subscriptions-customer-state-filter', actor: 'staff', path: '/subscriptions', scope: 'Visible customer search plus ACTIVE-state filter',
    apis: [list(`/subscriptions?page=1&page_size=25&q=${encodeURIComponent(customerName)}&state=ACTIVE`, count('customer_active'))],
    enter: async page => { await page.goto('/subscriptions'); await rows(page, 'Subscriptions', 25, 5000)
      await page.getByLabel('Search subscriptions').fill(customerName); await page.getByLabel('State', { exact: true }).selectOption('ACTIVE')
      await page.getByRole('button', { name: 'Apply filters', exact: true }).click() },
    ready: async page => { await rows(page, 'Subscriptions', 25, count('customer_active')); await expect(table(page, 'Subscriptions')).toContainText(customerName) } },
  { key: 'staff-subscription-reference-search', actor: 'staff', path: '/subscriptions', scope: 'Exact subscription search and visible link to persisted record',
    apis: [list(`/subscriptions?page=1&page_size=25&q=${encodeURIComponent(fixture.first_subscription.number)}`, 1, 1)],
    enter: async page => { await page.goto('/subscriptions'); await rows(page, 'Subscriptions', 25, 5000)
      await page.getByLabel('Search subscriptions').fill(fixture.first_subscription.number)
      await page.getByRole('button', { name: 'Apply filters', exact: true }).click() },
    ready: async page => { await rows(page, 'Subscriptions', 1, 1); await expect(page.getByRole('link', { name: fixture.first_subscription.number, exact: true })).toBeVisible() } },
  { key: 'staff-subscription-detail', actor: 'staff', path: `/subscriptions/${fixture.first_subscription.id}`,
    scope: 'Persisted agreement/product line and four stored invoices', apis: [subscriptionApi(false)], ready: page => subscriptionReady(page, false) },
  ...[1, 2].map(page => ({ key: `staff-invoices-page-${page}`, actor: 'staff' as const, path: `/billing/invoices?page=${page}`,
    scope: '25 real staff invoice records and loaded customer selector', apis: [list(`/invoices?page=${page}&page_size=25`, 20000), customerList()],
    ready: async (browserPage: Page) => { await heading(browserPage, 'Invoices'); await rows(browserPage, 'Invoices', 25, 20000)
      await option(browserPage, 'Customer', fixture.customers[0]) } })),
  { key: 'staff-invoices-customer-status-date-filter', actor: 'staff', path: '/billing/invoices', scope: 'All visible invoice filter controls, including customer search; nonempty persisted partial invoices',
    apis: [list(`/invoices?page=1&page_size=25&customer_id=${fixture.customers[0]}&status=CONFIRMED&overdue=true&from=2026-10-01&to=2026-11-01`, count('customer_October_confirmed')),
      customerList(100, customerName)], enter: async page => {
      await page.goto('/billing/invoices'); await rows(page, 'Invoices', 25, 20000)
      await page.getByLabel('Find customer', { exact: true }).fill(customerName)
      await option(page, 'Customer', fixture.customers[0])
      await page.getByLabel('Customer', { exact: true }).selectOption(fixture.customers[0])
      await page.getByLabel('Invoice status').selectOption('CONFIRMED'); await page.getByLabel('Collection', { exact: true }).selectOption('true')
      await page.getByLabel('Invoice date from').fill('2026-10-01'); await page.getByLabel('Invoice date before').fill('2026-11-01')
    }, ready: async page => { await rows(page, 'Invoices', 25, count('customer_October_confirmed')); await expect(table(page, 'Invoices')).toContainText(customerName)
      await expect(table(page, 'Invoices').locator('tbody tr').first()).toContainText(money('50.00')) } },
  ...['PAID', 'CONFIRMED'].map(status => ({ key: `staff-invoices-status-${status.toLowerCase()}`, actor: 'staff' as const,
    path: `/billing/invoices?status=${status}`, scope: `Nonempty persisted ${status} invoice status`,
    apis: [list(`/invoices?page=1&page_size=25&status=${status}`, 10000), customerList()],
    ready: async (page: Page) => { await rows(page, 'Invoices', 25, 10000); await expect(page.getByLabel('Invoice status')).toHaveValue(status) } })),
]
for (const portal of [false, true]) {
  for (const [status, row] of [['paid', fixture.paid_invoice], ['partial', fixture.partial_invoice]] as const) {
    routes.push({ key: `${portal ? 'portal' : 'staff'}-invoice-${status}`, actor: portal ? 'customer_a' : 'staff',
      path: `${portal ? '/portal' : '/billing'}/invoices/${row.id}`, scope: 'Stored invoice lines, payment, total and paid/partial status; no mutation',
      apis: [invoiceApi(portal, row)], ready: page => invoiceReady(page, portal, row) })
    routes.push({ key: `${portal ? 'portal' : 'staff'}-invoice-${status}-print`, actor: portal ? 'customer_a' : 'staff',
      path: apiPath(`${portal ? '/portal' : ''}/invoices/${row.id}/print`), rawDocument: true,
      scope: 'Authorized real HTML invoice document; no print-dialog interaction',
      apis: [{ path: apiPath(`${portal ? '/portal' : ''}/invoices/${row.id}/print`), html: true, validate: value => {
        if (typeof value !== 'string') throw new Error('Expected the actual HTML invoice body')
        expect(value).toContain(row.number); expect(value).toContain(`Total ${row.total}`)
        expect(value).toContain(`paid ${row.paid_amount}`); expect(value).toContain(`balance ${row.balance_due}`)
      } }], ready: async page => { await heading(page, `Invoice ${row.number}`); await expect(page.locator('tbody tr')).toHaveCount(count('invoice_lines_count')) } })
  }
}
for (const pageNumber of [1, 2]) {
  for (const kind of ['subscriptions', 'invoices'] as const) {
    const total = count(kind === 'subscriptions' ? 'customer_active' : 'customer_invoices')
    const caption = kind === 'subscriptions' ? 'My subscriptions' : 'My invoices'
    routes.push({ key: `portal-${kind}-page-${pageNumber}`, actor: 'customer_a', path: `/portal/${kind}?page=${pageNumber}`,
      scope: 'Own paginated records with server totals', apis: [list(`/portal/${kind}?page=${pageNumber}&page_size=25`, total)],
      ready: async page => { await heading(page, caption); await rows(page, caption, 25, total) } })
  }
}
routes.push(
  { key: 'customer-landing', actor: 'customer_a', path: '/', scope: 'Real customer landing redirect to own subscriptions',
    apis: [list('/portal/subscriptions?page=1&page_size=25', count('customer_active'))], ready: async page => {
      await heading(page, 'My subscriptions'); await rows(page, 'My subscriptions', 25, count('customer_active'))
    } },
  { key: 'portal-subscription-detail', actor: 'customer_a', path: `/portal/subscriptions/${fixture.first_subscription.id}`,
    scope: 'Canonical own subscription DTO and four real invoice references', apis: [subscriptionApi(true)], ready: page => subscriptionReady(page, true) },
  { key: 'portal-account', actor: 'customer_a', path: '/portal/account', scope: 'Persisted own profile and billing address',
    apis: [detail('/portal/me', fixture.customers[0], row => expect(row.display_name).toBe(customerName))], ready: async page => {
      await heading(page, 'Account'); await heading(page, customerName); await expect(page.locator('.portal-profile address')).toContainText('Fictional City')
    } },
)
const smallLists = [
  { key: 'customers', path: '/customers', caption: 'Customers', total: 2, ref: undefined },
  { key: 'products', path: '/catalog/products', caption: 'Products', total: 1, ref: fixture.refs.product },
  { key: 'plans', path: '/catalog/plans', caption: 'Plans', total: 1, ref: fixture.refs.plan },
]
for (const catalog of smallLists) {
  const path = catalog.key === 'customers' ? '/customers' : catalog.key === 'products' ? '/products' : '/plans'
  const apis = [list(`${path}?page=1&page_size=25`, catalog.total, catalog.total, catalog.ref)]
  routes.push({ key: `catalog-${catalog.key}`, actor: 'admin', path: catalog.path,
    scope: 'Actual catalog list; small catalog counts recorded separately from5000 subscriptions', apis,
    ready: async page => { await heading(page, catalog.caption); await rows(page, catalog.caption, catalog.total, catalog.total) } })
  for (const edit of [false, true]) {
    const title = `${edit ? 'Edit' : 'New'} ${catalog.key === 'customers' ? 'customer' : catalog.key === 'products' ? 'product' : 'plan'}`
    const refName = catalog.key === 'customers' ? customerName : catalog.ref!.name
    routes.push({ key: `catalog-${catalog.key}-${edit ? 'edit' : 'new'}-form`, actor: 'admin', path: catalog.path,
      scope: 'Editor readiness with real list data; no save request',
      apis: [...apis, ...(catalog.key === 'plans' ? [list('/tax-rules?page=1&page_size=25', 1, 1, fixture.refs.tax)] : [])],
      enter: async page => {
        await page.goto(catalog.path); await rows(page, catalog.caption, catalog.total, catalog.total)
        await page.getByRole('button', { name: edit ? `Edit ${refName}` : title, exact: true }).click()
      }, ready: async page => {
        await heading(page, title)
        const editor = page.getByRole('region', { name: title, exact: true })
        await expect(editor.getByRole('button', { name: 'Save changes', exact: true })).toBeEnabled()
        const label = catalog.key === 'customers' ? 'Customer name' : catalog.key === 'products' ? 'Product name' : 'Plan name'
        if (edit) await expect(editor.getByLabel(label, { exact: true })).toHaveValue(refName)
        else await expect(editor.getByLabel(label, { exact: true })).toBeVisible()
        if (catalog.key === 'plans') await expect(editor.locator('.catalog-tax-option')).toContainText(fixture.refs.tax.name)
      } })
  }
}
routes.push({ key: 'customers-search', actor: 'staff', path: '/customers', scope: 'Real customer search result, one expected record',
  apis: [list(`/customers?page=1&page_size=25&q=${encodeURIComponent(customerName)}`, 1, 1)],
  enter: async page => { await page.goto('/customers'); await rows(page, 'Customers', 2, 2)
    await page.getByLabel('Search customers', { exact: true }).fill(customerName)
    await page.getByRole('button', { name: 'Search', exact: true }).click() },
  ready: async page => { await rows(page, 'Customers', 1, 1); await expect(table(page, 'Customers')).toContainText(customerName) } })
for (const editor of ['none', 'new', 'edit'] as const) {
  routes.push({ key: `product-variants${editor === 'none' ? '' : `-${editor}-form`}`, actor: 'admin', path: '/catalog/products',
    scope: 'Real product detail/variant record; editor cases do not submit',
    apis: [list('/products?page=1&page_size=25', 1, 1, fixture.refs.product), productDetail], enter: async page => {
      await page.goto('/catalog/products'); await rows(page, 'Products', 1, 1)
      await page.getByRole('button', { name: `Variants for ${fixture.refs.product.name}`, exact: true }).click()
      await heading(page, `${fixture.refs.product.name} variants`)
      await expect(page.getByText(`${fixture.refs.variant.attribute_name}: ${fixture.refs.variant.attribute_value}`, { exact: true })).toBeVisible()
      if (editor !== 'none') await page.getByRole('button', { name: editor === 'new' ? 'Add variant' : `Edit variant ${fixture.refs.variant.attribute_value}`, exact: true }).click()
    }, ready: async page => {
      if (editor === 'none') await expect(page.getByText(`${fixture.refs.variant.attribute_name}: ${fixture.refs.variant.attribute_value}`, { exact: true })).toBeVisible()
      else {
        await heading(page, `${editor === 'new' ? 'New' : 'Edit'} variant`)
        await expect(page.getByLabel('Attribute name', { exact: true })).toBeVisible()
        if (editor === 'edit') await expect(page.getByLabel('Attribute value', { exact: true })).toHaveValue(fixture.refs.variant.attribute_value)
      }
    } })
}
routes.push({ key: 'quotation-templates', actor: 'staff', path: '/subscriptions/templates', scope: 'Real template list and resolved plan name',
  apis: [list('/quotation-templates?page=1&page_size=25', 1, 1, fixture.refs.template), list('/plans?page=1&page_size=100', 1, 1, fixture.refs.plan)],
  ready: async page => { await heading(page, 'Quotation templates'); await rows(page, 'Quotation templates', 1, 1)
    await expect(table(page, 'Quotation templates')).toContainText(fixture.refs.plan.name) } })
for (const edit of [false, true]) {
  const path = edit ? `/subscriptions/templates/${fixture.refs.template.id}/edit` : '/subscriptions/templates/new'
  routes.push({ key: `quotation-template-${edit ? 'edit' : 'new'}-form`, actor: 'staff', path,
    scope: 'Real template/catalog/product-variant options; no write', apis: [...catalogLookups, ...(edit ? [productDetail] : [])],
    ready: async page => {
      await heading(page, edit ? 'Edit quotation template' : 'New quotation template')
      await option(page, 'Plan', fixture.refs.plan.id); await option(page, 'Product 1', fixture.refs.product.id)
      await expect(page.getByRole('button', { name: edit ? 'Save template' : 'Create template', exact: true })).toBeEnabled()
      if (edit) {
        await expect(page.getByLabel('Template name', { exact: true })).toHaveValue(fixture.refs.template.name)
        await expect(page.getByLabel('Quotation validity (days)', { exact: true })).toHaveValue(String(fixture.refs.template.valid_days))
        await option(page, 'Variant 1', fixture.refs.variant.id)
      }
    } })
}
routes.push({ key: 'new-subscription-form', actor: 'staff', path: '/subscriptions/new', scope: 'All real creation selectors loaded; no draft creation',
  apis: catalogLookups, ready: async page => {
    await heading(page, 'New subscription'); await option(page, 'Customer', fixture.customers[0])
    await option(page, 'Plan', fixture.refs.plan.id); await option(page, 'Product 1', fixture.refs.product.id)
    await option(page, 'Quotation template (optional)', fixture.refs.template.id)
    await expect(page.getByLabel('Service start (included)', { exact: true })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Create draft', exact: true })).toBeEnabled()
  } })
for (const kind of ['tax', 'discount'] as const) {
  const ref = fixture.refs[kind]
  const caption = kind === 'tax' ? 'Tax rules' : 'Discount rules'
  const path = `/billing/${kind === 'tax' ? 'taxes' : 'discounts'}`
  const ruleApi = list(`/${kind}-rules?page=1&page_size=25`, 1, 1, ref)
  routes.push({ key: `${kind}-rules`, actor: 'admin', path, scope: 'Real retained configuration revision; nonempty list', apis: [ruleApi],
    ready: async page => { await heading(page, caption); await rows(page, caption, 1, 1); await expect(table(page, caption)).toContainText(ref.name) } })
  for (const edit of [false, true]) {
    routes.push({ key: `${kind}-${edit ? 'revision' : 'new'}-form`, actor: 'admin', path,
      scope: 'Real rule/product lookup and form controls; no configuration mutation',
      apis: [ruleApi, list('/products?page=1&page_size=100&q=', 1, 1, fixture.refs.product)], enter: async page => {
        await page.goto(path); await rows(page, caption, 1, 1)
        await page.getByRole('button', { name: edit ? 'Schedule revision' : `Create ${kind} rule`, exact: true }).click()
      }, ready: async page => {
        await heading(page, edit ? 'Schedule a retained revision' : `New ${kind} rule`)
        await expect(page.getByLabel('Rule name', { exact: true })).toBeVisible()
        if (edit) { await expect(page.getByLabel('Rule name', { exact: true })).toHaveValue(ref.name)
          await expect(page.getByLabel('Revision effective from', { exact: true })).toBeVisible() }
        await expect(page.getByLabel(kind === 'tax' ? 'Tax rate (%)' : 'Discount percentage', { exact: true })).toBeVisible()
      } })
  }
}
routes.push({ key: 'admin-staff-settings', actor: 'admin', path: '/settings/staff', scope: 'Administrator access-management form only; no account creation',
  apis: [], ready: async page => {
    await heading(page, 'Staff settings'); await heading(page, 'Add a staff member')
    for (const label of ['Staff name', 'Staff email', 'Temporary password']) await expect(page.getByLabel(label, { exact: true })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Create staff account', exact: true })).toBeEnabled()
  } })
for (const auth of [
  { key: 'signin', path: '/sign-in', heading: 'Welcome back.', labels: ['Email address', 'Password'], button: 'Sign in' },
  { key: 'signup', path: '/sign-up', heading: 'Make yourself at home.', labels: ['Your name', 'Email address', 'Password'], button: 'Create account' },
  { key: 'forgot', path: '/forgot-password', heading: 'Find your way back.', labels: ['Email address'], button: 'Request reset link' },
  { key: 'reset', path: '/reset-password?token=fixture-form-only-invalid', heading: 'A fresh start.', labels: ['New password', 'Confirm new password'], button: 'Save new password' },
]) {
  routes.push({ key: `auth-${auth.key}-form`, actor: 'anonymous', path: auth.path,
    scope: 'Anonymous form-render performance only; normal session401 explicit; no login/signup/reset mutation or delivery claim',
    apis: [], ready: async page => { await heading(page, auth.heading)
      for (const label of auth.labels) await expect(page.getByLabel(label, { exact: true })).toBeVisible()
      await expect(page.getByRole('button', { name: auth.button, exact: true })).toBeEnabled()
    } })
}
routes.push({ key: 'overview-customer-overdue-drilldown', actor: 'staff', path: '/overview',
  scope: 'Applied customer is preserved in the real dashboard overdue drilldown; current-state debt remains independent of range',
  apis: [list(`/invoices?page=1&page_size=25&overdue=true&customer_id=${fixture.customers[0]}`, count('customer_overdue')), customerList()],
  enter: async page => { await page.goto('/overview'); await overview(page); await rangeControls(page, true); await overview(page, true, true)
    await page.getByRole('link', { name: 'View overdue invoices', exact: true }).click() },
  ready: async page => { await heading(page, 'Invoices'); await rows(page, 'Invoices', 25, count('customer_overdue'))
    await expect(page.getByLabel('Customer', { exact: true })).toHaveValue(fixture.customers[0])
    await expect(page.getByLabel('Collection', { exact: true })).toHaveValue('true') } })

routes.push({ key: 'overview-chart-data', actor: 'staff', path: '/overview',
  scope: 'Exact server chart data table after full dashboard readiness', apis: [summary(), series(), overdue()],
  enter: async page => { await page.goto('/overview'); await overview(page)
    await page.getByRole('button', { name: 'View chart data', exact: true }).click() },
  ready: async page => { await expect(page.getByRole('region', { name: 'Chart data', exact: true }).locator('tbody tr')).toHaveCount(2)
    await expect(page.getByRole('button', { name: 'Hide chart data', exact: true })).toBeVisible() } })

async function contextFor(browser: Browser, actor: ActorKey, mobile = false) {
  const device = mobile ? devices['iPhone 13'] : { viewport: { width: 1497, height: 1049 } }
  const credentials = actor === 'anonymous' ? undefined : fixture.actors[actor]
  const context = await browser.newContext({ ...device, baseURL: origin, extraHTTPHeaders: PERFORMANCE_INGRESS_HEADERS, storageState: credentials?.storage_state })
  try {
    if (credentials && !credentials.storage_state) {
      const response = await context.request.post(apiPath('/auth/login'), { headers: { ...PERFORMANCE_INGRESS_HEADERS, Origin: origin },
        data: { email: credentials.email, password: credentials.password } })
      expect(response.status()).toBe(200)
      credentials.storage_state = await context.storageState()
      writeFileSync(credentialPath, JSON.stringify(fixture), { mode: 0o600 })
    }
    return context
  } catch (error) { await context.close(); throw error }
}
function confirmedAbort(text: string) { return /ERR_ABORTED|cancelled|canceled|NS_BINDING_ABORTED/i.test(text) }
async function frames(page: Page) {
  await page.evaluate(async () => {
    await document.fonts.ready
    await new Promise<void>(done => requestAnimationFrame(() => requestAnimationFrame(() => done())))
  })
}
async function sample(context: BrowserContext, route: Route, capture?: string) {
  const page = await context.newPage()
  const pageErrors: string[] = []
  const protocolErrors: string[] = []
  const pending: Promise<void>[] = []
  page.on('pageerror', error => pageErrors.push(error.message))
  page.on('request', request => {
    const pathname = new URL(request.url()).pathname
    if (!pathname.startsWith('/api/')) return
    if (!['GET', 'HEAD'].includes(request.method())) protocolErrors.push(`Unexpected mutation ${request.method()} ${pathname}`)
    const observed = (async () => {
      const response = await request.response()
      if (!response) {
        const failure = request.failure()?.errorText || 'Missing response'
        if (!confirmedAbort(failure)) protocolErrors.push(`${pathname}: ${failure}`)
        return
      }
      const failure = await response.finished()
      if (failure) {
        if (!confirmedAbort(request.failure()?.errorText || '')) protocolErrors.push(`${pathname}: incomplete response`)
        return
      }
      const allowedAnonymous = route.actor === 'anonymous' && pathname === '/api/v1/auth/session' && response.status() === 401
      if (response.status() !== 200 && !allowedAnonymous) protocolErrors.push(`${pathname}: HTTP${response.status()}`)
    })().catch(() => { protocolErrors.push(`${pathname}: protocol observation failed`) })
    pending.push(observed)
  })
  const apis = [...(route.rawDocument ? [] : [sessionApi(route.actor)]), ...route.apis]
  const start = performance.now()
  try {
    const required = Promise.all(apis.map(api => page.waitForResponse(async response => {
      const actual = new URL(response.url()), wanted = new URL(api.path, origin)
      if (response.request().method() !== 'GET' || actual.pathname !== wanted.pathname
        || ![...wanted.searchParams].every(([key, value]) => actual.searchParams.get(key) === value)) return false
      const failure = await response.finished()
      if (failure) {
        if (confirmedAbort(response.request().failure()?.errorText || '')) return false
        throw failure
      }
      expect(response.status(), `Required API ${wanted.pathname}`).toBe(api.status ?? 200)
      api.validate(api.html ? await response.text() : await response.json())
      return true
    })))
    await Promise.all([required, route.enter ? route.enter(page) : page.goto(route.path)])
    await route.ready(page)
    await expect(page.locator('.ui-error, .feature-placeholder, vite-error-overlay')).toHaveCount(0)
    await expect(page.locator('.ui-loading')).toHaveCount(0)
    // Include all real auxiliary lookups, including forms whose options load
    // after the first render. Cancellation is accepted only with transport proof.
    for (let pass = 0; pass < 8; pass++) {
      const observed = pending.length
      await Promise.all(pending)
      await frames(page)
      if (pending.length === observed) break
      if (pass === 7) throw new Error('API activity did not settle after page readiness')
    }
    expect(pageErrors).toEqual([])
    expect(protocolErrors).toEqual([])
    const browserMs = performance.now() - start
    const measurements: Record<string, { elapsed_ms: number; status: number; content_type: string }> = {}
    for (const api of apis) {
      const before = performance.now()
      const response = await context.request.get(api.path, { headers: PERFORMANCE_INGRESS_HEADERS })
      const value = api.html ? await response.text() : await response.json()
      const elapsed = performance.now() - before
      expect(response.status()).toBe(api.status ?? 200)
      api.validate(value)
      measurements[api.path] = { elapsed_ms: elapsed, status: response.status(), content_type: response.headers()['content-type'] || '' }
    }
    if (capture) {
      await page.evaluate(async () => {
        await document.fonts.ready
        let previous = '', stable = 0
        for (let frame = 0; frame < 120; frame++) {
          await new Promise<void>(done => requestAnimationFrame(() => done()))
          const current = `${innerWidth}:${document.documentElement.scrollWidth}:${document.documentElement.scrollHeight}`
          stable = previous === current ? stable + 1 : 0
          previous = current
          if (stable >= 3) return
        }
        throw new Error('Mobile invoice layout did not settle')
      })
      await page.evaluate(() => window.scrollTo(0, 0))
      await frames(page)
      await page.screenshot({ path: capture, fullPage: true })
    }
    return { browser_ms: browserMs, api: measurements }
  } finally { await page.close() }
}

test.beforeAll(async ({ browser }) => { report.browser = browser.version(); report.route_matrix = routes.map(route => ({
  key: route.key, path: route.path, actor: route.actor, scope: route.scope,
  required_apis: [...(route.rawDocument ? [] : [sessionApi(route.actor)]), ...route.apis].map(api => ({ path: api.path, status: api.status ?? 200 })),
})); save() })
test.afterAll(() => {
  const after = runtimeInputs(repo)
  report.runtime_stable = after.source_sha256 === inputs.source_sha256 && after.dist_sha256 === inputs.dist_sha256
    && after.harness_sha256 === inputs.harness_sha256
  report.finished_at = new Date().toISOString()
  save()
  expect(report.runtime_stable, 'Runtime source/dist must remain frozen through measurement').toBe(true)
})
for (const route of routes) {
  test(`${route.key}: 20 warm + 5 fresh-context samples`, async ({ browser }) => {
    const raw: { mode: string; browser_ms: number; api: Record<string, { elapsed_ms: number; status: number; content_type: string }> }[] = []
    results[route.key] = { scope: route.scope, path: route.path, actor: route.actor, status: 'running', samples: raw }
    let context: BrowserContext | undefined
    try {
      context = await contextFor(browser, route.actor)
      await sample(context, route) // Excluded warmup also proves full real-data readiness.
      for (let index = 0; index < 20; index++) { raw.push({ mode: 'warm', ...await sample(context, route) }); save() }
      const storageState = await context.storageState()
      for (let index = 0; index < 5; index++) {
        const cold = await browser.newContext({ baseURL: origin, extraHTTPHeaders: PERFORMANCE_INGRESS_HEADERS, viewport: { width: 1497, height: 1049 }, storageState })
        try { raw.push({ mode: 'cold', ...await sample(cold, route) }); save() }
        finally { await cold.close() }
      }
      for (const mode of ['warm', 'cold']) {
        const selected = raw.filter(row => row.mode === mode)
        results[route.key][mode] = { browser: stats(selected.map(row => row.browser_ms)),
          api: Object.fromEntries(Object.keys(selected[0].api).map(path => [path, {
            ...stats(selected.map(row => row.api[path].elapsed_ms)), expected_status: selected[0].api[path].status,
            content_type: selected[0].api[path].content_type,
          }])) }
      }
      results[route.key].status = 'measured'
    } catch (error) {
      results[route.key].status = 'failed'
      results[route.key].failure = error instanceof Error ? error.message : 'Unknown measurement failure'
      throw error
    } finally { save(); await context?.close() }
  })
}
test('settled mobile paid invoice evidence from this new namespace', async ({ browser }) => {
  const context = await contextFor(browser, 'customer_a', true)
  const filename = artifact.replace(/\.json$/, '') + '-mobile-paid.png'
  const route = routes.find(route => route.key === 'portal-invoice-paid')!
  try {
    await sample(context, route, filename)
    ;(report.captures as Json[]).push({ path: filename, sha256: digest(readFileSync(filename)),
      schema: fixture.schema, dataset_run: fixture.run, invoice_id: fixture.paid_invoice.id,
      label: 'Settled real paid-invoice mobile frame; separate from latency samples', viewport: devices['iPhone 13'].viewport })
  } finally { save(); await context.close() }
})
