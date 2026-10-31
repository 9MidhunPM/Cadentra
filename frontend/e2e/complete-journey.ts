/** T31: real browser writes, actual PostgreSQL, no route interception or fake totals. */
import { randomUUID } from 'node:crypto'
import { execFileSync } from 'node:child_process'
import { lstatSync, readFileSync, renameSync, writeFileSync } from 'node:fs'
import { dirname, isAbsolute } from 'node:path'
import { fileURLToPath } from 'node:url'
import { expect, test, type Page } from '@playwright/test'
import type { SubscriptionDetail } from '../src/features/portal/types'

type Kind = 'products' | 'variants' | 'plans' | 'tax_rules' | 'discount_rules' | 'templates' | 'subscriptions' | 'invoices' | 'payments'
type ActorKey = 'admin' | 'customer_a' | 'customer_b'
type Manifest = {
  test_only: boolean; kind: string; database: string; run_id: string; prefix: string;
  business_date: string; service_end: string;
  actors: Record<ActorKey, { id: string; email: string; password: string; role: string }>;
  customers: Record<'A' | 'B', { id: string; name: string }>;
  owned: Record<Kind, string[]>;
  completed?: boolean;
}
type Invoice = { id: string; number: string; status: string; subtotal: string; discount_total: string; tax_total: string; total: string; paid_amount: string; balance_due: string; payments: { id: string; amount: string }[] }
type VerifiedFacts = Record<string, string | number | boolean | null | string[]>
type Evidence = {
  scenario: 'T31'; started_at: string; finished_at: string | null; status: string;
  git_start: ReturnType<typeof gitState>; git_end: ReturnType<typeof gitState> | null;
  browser: { name: string; version: string };
  viewports: Record<string, { width: number; height: number } | null>;
  requested_business_date: string;
  verified: Record<string, { verified_at: string; facts: VerifiedFacts }>;
}
let evidence: Evidence
function gitState() {
  const cwd = fileURLToPath(new URL('../..', import.meta.url))
  const git = (...args: string[]) => execFileSync('git', args, { cwd, encoding: 'utf8' }).trim()
  return { head: git('rev-parse', 'HEAD'), dirty: git('status', '--porcelain=v1', '--untracked-files=all').length > 0 }
}
function verified(name: string, facts: VerifiedFacts) {
  // Only explicit scalar facts belong here, never credentials, headers or response bodies.
  evidence.verified[name] = { verified_at: new Date().toISOString(), facts }
}
const manifestPath = process.env.CADENTRA_JOURNEY_MANIFEST ?? ''
if (!isAbsolute(manifestPath) || dirname(manifestPath) !== '/tmp') throw new Error('T31 manifest must be directly under /tmp')
const metadata = lstatSync(manifestPath)
if (!metadata.isFile() || (metadata.mode & 0o077) !== 0) throw new Error('T31 manifest must be a regular private mode-0600 file')
const fixture = JSON.parse(readFileSync(manifestPath, 'utf8')) as Manifest
if (!fixture.test_only || fixture.kind !== 'cadentra-complete-journey' || fixture.database !== 'cadentra_experience_test' || fixture.business_date !== '2026-11-02' || fixture.service_end !== '2027-01-02') {
  throw new Error('Use the guarded T31 seed manifest with its fixed test-only business date')
}
const privateNote = `PRIVATE-T31-${fixture.run_id}`
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i
function remember(kind: Kind, id: string) {
  if (!uuid.test(id)) throw new Error(`The ${kind} endpoint did not return a valid UUID`)
  if (!fixture.owned[kind].includes(id)) fixture.owned[kind].push(id)
  saveManifest()
}
function saveManifest() {
  const temporary = `${manifestPath}.${randomUUID()}.tmp`
  writeFileSync(temporary, JSON.stringify(fixture, null, 2), { mode: 0o600, flag: 'wx' })
  renameSync(temporary, manifestPath)
}
async function mutation<T extends { id?: string }>(page: Page, path: string, action: () => Promise<unknown>, kind?: Kind): Promise<T> {
  const pending = page.waitForResponse(response => response.request().method() === 'POST' && new URL(response.url()).pathname === `/api/v1${path}`)
  await action()
  const response = await pending
  expect(response.ok(), `Real POST ${path} must succeed; missing owner implementation is a dependency failure`).toBe(true)
  const payload = await response.json() as { data: T }
  if (kind) {
    if (!payload.data.id) throw new Error(`Cannot record ownership for ${kind}: response has no id`)
    remember(kind, payload.data.id)
  }
  return payload.data
}
async function login(page: Page, key: ActorKey) {
  await page.goto('/sign-in')
  await expect(page.getByLabel('Email address', { exact: true }), 'Integrated identity UI is required; a placeholder cannot pass T31').toBeVisible()
  await page.getByLabel('Email address', { exact: true }).fill(fixture.actors[key].email)
  await page.getByLabel('Password', { exact: true }).fill(fixture.actors[key].password)
  await page.getByRole('button', { name: 'Sign in', exact: true }).click()
  await expect(page).toHaveURL(key === 'admin' ? /\/overview$/ : /\/portal\/subscriptions$/)
}
function assertPublicProjection(value: unknown): void {
  if (Array.isArray(value)) {
    value.forEach(assertPublicProjection)
  } else if (value !== null && typeof value === 'object') {
    for (const [key, child] of Object.entries(value)) {
      expect(/cost|^staff|^internal|^private|^audit|^(note|notes|created_by|request_key|request_payload_hash|external_reference|cancellation_reason|close_reason)$/.test(key.toLowerCase()), `Customer response must exclude internal field ${key}`).toBe(false)
      assertPublicProjection(child)
    }
  } else if (typeof value === 'string') {
    expect(value.includes(privateNote), 'Customer responses must omit private product/payment notes').toBe(false)
    expect(value.includes(fixture.actors.admin.email), 'Customer responses must omit staff identity').toBe(false)
  }
}
async function publicRead<T>(page: Page, path: string): Promise<T> {
  const response = await page.request.get(`/api/v1${path}`)
  expect(response.status()).toBe(200)
  const payload = await response.json() as T
  assertPublicProjection(payload)
  return payload
}
async function ownerSubscriptionIds(page: Page): Promise<string[]> {
  const ids: string[] = []
  let total: number | undefined
  for (let current = 1; ; current += 1) {
    const result = await publicRead<{ items: { id: string }[]; total: number }>(page, `/portal/subscriptions?page=${current}&page_size=100`)
    total ??= result.total
    expect(result.total, 'Subscription count must stay stable during pagination').toBe(total)
    ids.push(...result.items.map(item => item.id))
    if (ids.length >= total) break
    expect(result.items.length, 'A page cannot be empty before the complete subscription list is read').toBeGreaterThan(0)
  }
  expect(ids).toHaveLength(total)
  expect(new Set(ids).size).toBe(total)
  return ids.sort()
}
async function portalAction(page: Page, id: string, action: string, trigger: string, title: string, confirm: string) {
  await page.getByRole('button', { name: trigger, exact: true }).click()
  const dialog = page.getByRole('dialog', { name: title, exact: true })
  await expect(dialog).toBeVisible()
  const result = await mutation<SubscriptionDetail>(page, `/portal/subscriptions/${id}/${action}`, () => dialog.getByRole('button', { name: confirm, exact: true }).click(), action === 'renew' ? 'subscriptions' : undefined)
  assertPublicProjection(result)
  await expect(dialog).toHaveCount(0)
  return result
}
async function readInvoice(page: Page, id: string): Promise<Invoice> {
  const result = await page.request.get(`/api/v1/invoices/${id}`)
  expect(result.status()).toBe(200)
  return (await result.json()).data as Invoice
}
function metric(page: Page, name: string) {
  return page.locator('.report-metric').filter({ has: page.getByRole('heading', { name, exact: true }) }).locator('strong')
}
async function lifecycle(page: Page, subscriptionId: string, action: string, name: string) {
  await page.getByRole('button', { name, exact: true }).click()
  const form = page.locator('form').filter({ has: page.getByRole('heading', { name, exact: true }) })
  await expect(form).toBeVisible()
  if (action === 'confirm') await form.getByLabel('I have reviewed the service dates, prices and full-cycle policy.').check()
  return mutation<{ id: string; state: string }>(page, `/subscriptions/${subscriptionId}/${action}`, () => form.getByRole('button', { name, exact: true }).click())
}

test.beforeEach(async ({ page, browser }, testInfo) => {
  evidence = {
    scenario: 'T31', started_at: new Date().toISOString(), finished_at: null, status: 'running',
    git_start: gitState(), git_end: null,
    browser: { name: browser.browserType().name(), version: browser.version() },
    viewports: { staff: page.viewportSize() }, requested_business_date: fixture.business_date, verified: {},
  }
  writeFileSync(testInfo.outputPath('T31-evidence.json'), JSON.stringify(evidence, null, 2), { mode: 0o600 })
})
// Playwright requires a destructured fixtures argument even when only TestInfo is used.
// eslint-disable-next-line no-empty-pattern
test.afterEach(async ({}, testInfo) => {
  evidence.finished_at = new Date().toISOString()
  evidence.status = testInfo.status ?? 'unknown'
  evidence.git_end = gitState()
  const path = testInfo.outputPath('T31-evidence.json')
  writeFileSync(path, JSON.stringify(evidence, null, 2), { mode: 0o600 })
  await testInfo.attach('T31 verification evidence', { path, contentType: 'application/json' })
})

// Explicit single scenario: a partial failure is never retried against its mutated dataset.
test('T31 product to paid invoice, reports and isolated customer portal', async ({ page, browser }, testInfo) => {
  expect(fixture.completed, 'Use a fresh seed for each journey, not a previously completed manifest').not.toBe(true)
  expect(Object.values(fixture.owned).flat(), 'An interrupted journey needs scoped cleanup before another run').toEqual([])
  const errors: string[] = []
  page.on('pageerror', error => errors.push(error.message))
  const day = fixture.business_date
  const productName = `${fixture.prefix} Product`
  const planName = `${fixture.prefix} Monthly`
  const templateName = `${fixture.prefix} Three seats`
  await login(page, 'admin')
  const summaryResponse = await page.request.get('/api/v1/reports/summary')
  expect(summaryResponse.status()).toBe(200)
  const baseline = (await summaryResponse.json()).data
  expect(baseline.as_of, 'Run the test-only fixed-clock API; do not use the production clock').toBe(day)
  expect(baseline.active_subscriptions).toBe(0)
  expect(baseline.outstanding_now).toBe('0.00')
  verified('business_clock_and_empty_baseline', { as_of: baseline.as_of, active_subscriptions: 0, outstanding_now: '0.00' })

  await test.step('Create actual product, variant and tax/discount configuration', async () => {
    await page.goto('/catalog/products')
    await page.getByRole('button', { name: 'New product', exact: true }).click()
    const editor = page.getByRole('region', { name: 'New product', exact: true })
    await editor.getByLabel('Product name', { exact: true }).fill(productName)
    await editor.getByLabel('Sales price (INR)', { exact: true }).fill('1000.00')
    await editor.getByLabel('Internal cost (INR)', { exact: true }).fill('100.00')
    await editor.getByLabel('Notes', { exact: true }).fill(privateNote)
    const product = await mutation<{ id: string }>(page, '/products', () => editor.getByRole('button', { name: 'Save changes', exact: true }).click(), 'products')
    await page.getByRole('button', { name: `Variants for ${productName}`, exact: true }).click()
    await page.getByRole('button', { name: 'Add variant', exact: true }).click()
    const variant = page.getByRole('region', { name: 'New variant', exact: true })
    await variant.getByLabel('Attribute name', { exact: true }).fill('Brand')
    await variant.getByLabel('Attribute value', { exact: true }).fill('Odoo')
    await variant.getByLabel('Price adjustment (INR)', { exact: true }).fill('560.00')
    await mutation(page, `/products/${product.id}/variants`, () => variant.getByRole('button', { name: 'Save changes', exact: true }).click(), 'variants')
    await page.goto('/billing/taxes')
    await page.getByRole('button', { name: 'Create tax rule', exact: true }).click()
    await page.getByLabel('Rule name', { exact: true }).fill(`${fixture.prefix} Tax`)
    await page.getByLabel('Tax rate (%)', { exact: true }).fill('18')
    await page.getByLabel('Eligibility starts on', { exact: true }).fill(day)
    await page.getByRole('checkbox', { name: productName, exact: true }).check()
    await mutation(page, '/tax-rules', () => page.getByRole('button', { name: 'Create rule', exact: true }).click(), 'tax_rules')
    await page.goto('/billing/discounts')
    await page.getByRole('button', { name: 'Create discount rule', exact: true }).click()
    await page.getByLabel('Rule name', { exact: true }).fill(`${fixture.prefix} Discount`)
    await page.getByLabel('Discount kind', { exact: true }).selectOption('PERCENT')
    await page.getByLabel('Discount percentage', { exact: true }).fill('10')
    await page.getByLabel('Discount scope', { exact: true }).selectOption('SUBSCRIPTION')
    await page.getByLabel('Eligibility starts on', { exact: true }).fill(day)
    await page.getByLabel('Minimum eligible product quantity', { exact: true }).fill('3')
    await mutation(page, '/discount-rules', () => page.getByRole('button', { name: 'Create rule', exact: true }).click(), 'discount_rules')
  })

  let subscriptionId = ''
  let subscriptionNumber = ''
  await test.step('Create plan and template, then preserve all five-state workflow prerequisites', async () => {
    await page.goto('/catalog/plans')
    await page.getByRole('button', { name: 'New plan', exact: true }).click()
    const editor = page.getByRole('region', { name: 'New plan', exact: true })
    await editor.getByLabel('Plan name', { exact: true }).fill(planName)
    await editor.getByLabel('Base fee per billing cycle (INR)', { exact: true }).fill('0.00')
    await editor.getByLabel('Billing cadence', { exact: true }).selectOption('MONTHLY')
    await editor.getByLabel('Minimum product quantity', { exact: true }).fill('3')
    await editor.getByLabel('Available from', { exact: true }).fill(day)
    await editor.getByLabel('Allow scheduled pause', { exact: true }).check()
    await editor.getByLabel('Allow early closure', { exact: true }).check()
    await editor.getByLabel('Allow renewal', { exact: true }).check()
    await mutation(page, '/plans', () => editor.getByRole('button', { name: 'Save changes', exact: true }).click(), 'plans')
    await page.goto('/subscriptions/templates/new')
    await page.getByLabel('Template name', { exact: true }).fill(templateName)
    await page.getByLabel('Plan', { exact: true }).selectOption({ label: planName })
    await page.getByLabel('Quotation validity (days)', { exact: true }).fill('7')
    await page.getByLabel('Product 1', { exact: true }).selectOption({ label: productName })
    await page.getByLabel('Variant 1', { exact: true }).selectOption({ label: 'Brand: Odoo' })
    await page.getByLabel('Quantity 1', { exact: true }).fill('3')
    await mutation(page, '/quotation-templates', () => page.getByRole('button', { name: 'Create template', exact: true }).click(), 'templates')
    await expect(page).toHaveURL(/\/subscriptions\/templates$/)
    await page.goto('/subscriptions/new')
    await page.getByLabel('Customer', { exact: true }).selectOption(fixture.customers.A.id)
    await page.getByLabel('Quotation template (optional)', { exact: true }).selectOption({ label: templateName })
    await page.getByLabel('Service start (included)', { exact: true }).fill(day)
    await page.getByLabel('Service end (excluded)', { exact: true }).fill(fixture.service_end)
    await page.getByLabel('Payment terms (days)', { exact: true }).fill('7')
    const draft = await mutation<{ id: string; number: string; state: string }>(page, '/subscriptions', () => page.getByRole('button', { name: 'Create draft', exact: true }).click(), 'subscriptions')
    subscriptionId = draft.id
    subscriptionNumber = draft.number
    await expect(page).toHaveURL(new RegExp(`/subscriptions/${subscriptionId}$`))
    expect(draft.state).toBe('DRAFT')
    expect((await lifecycle(page, subscriptionId, 'issue-quotation', 'Issue quotation')).state).toBe('QUOTATION')
    expect((await lifecycle(page, subscriptionId, 'confirm', 'Confirm quotation')).state).toBe('CONFIRMED')
    expect((await lifecycle(page, subscriptionId, 'activate', 'Activate subscription')).state).toBe('ACTIVE')
  })

  let invoiceId = ''
  let invoiceNumber = ''
  await test.step('Generate once, confirm, and record two real manual payments', async () => {
    await page.goto('/billing/invoices')
    const first = await mutation<{ invoices_created: number; failed_subscription_count: number; id?: string }>(page, '/billing/run-due', () => page.getByRole('button', { name: 'Run due billing', exact: true }).click())
    expect(first.invoices_created).toBe(1)
    expect(first.failed_subscription_count).toBe(0)
    const list = await page.request.get(`/api/v1/invoices?customer_id=${fixture.customers.A.id}`)
    expect(list.status()).toBe(200)
    const rows = await list.json() as { items: Invoice[]; total: number }
    expect(rows.total).toBe(1)
    invoiceId = rows.items[0].id
    invoiceNumber = rows.items[0].number
    remember('invoices', invoiceId)
    const retry = await mutation<{ invoices_created: number; id?: string }>(page, '/billing/run-due', () => page.getByRole('button', { name: 'Run due billing', exact: true }).click())
    expect(retry.invoices_created).toBe(0)
    await page.getByRole('link', { name: invoiceNumber, exact: true }).click()
    const initial = await readInvoice(page, invoiceId)
    expect(initial).toMatchObject({ status: 'DRAFT', subtotal: '4680.00', discount_total: '468.00', tax_total: '758.16', total: '4970.16', balance_due: '4970.16' })
    await expect(page.locator('.billing-totals').filter({ hasText: 'Balance due' })).toContainText('INR 4,970.16')
    await page.getByRole('button', { name: 'Confirm invoice', exact: true }).click()
    const dialog = page.getByRole('dialog', { name: 'Confirm this invoice?' })
    await mutation(page, `/invoices/${invoiceId}/confirm`, () => dialog.getByRole('button', { name: 'Confirm', exact: true }).click())
    for (const [amount, balance] of [['2000.00', '2970.16'], ['2970.16', '0.00']]) {
      await page.getByLabel('Amount', { exact: true }).fill(amount)
      await page.getByLabel('Payment date', { exact: true }).fill(day)
      await page.getByLabel('Payment note', { exact: true }).fill(privateNote)
      await mutation(page, `/invoices/${invoiceId}/payments`, () => page.getByRole('button', { name: 'Record payment', exact: true }).click())
      await expect.poll(async () => (await readInvoice(page, invoiceId)).balance_due).toBe(balance)
      const record = await readInvoice(page, invoiceId)
      for (const payment of record.payments) remember('payments', payment.id)
      expect(record.status).toBe(balance === '0.00' ? 'PAID' : 'CONFIRMED')
      await expect(page.locator('.billing-totals > div').filter({ has: page.getByText('Balance due', { exact: true }) }).locator('dd')).toHaveText(balance === '0.00' ? 'INR 0.00' : 'INR 2,970.16')
    }
    await page.reload()
    await expect(page.getByRole('heading', { name: invoiceNumber, exact: true })).toBeVisible()
    const settled = await readInvoice(page, invoiceId)
    expect(settled).toMatchObject({ paid_amount: '4970.16', balance_due: '0.00', status: 'PAID' })
    expect(settled.payments.map(payment => payment.amount).sort()).toEqual(['2000.00', '2970.16'])
    await expect(page.getByRole('table', { name: 'Payments', exact: true }).getByRole('row')).toHaveCount(3)
    verified('paid_invoice_after_reload', { currency: 'INR', total: settled.total, paid_amount: settled.paid_amount, balance_due: settled.balance_due, status: settled.status, payments: settled.payments.map(payment => payment.amount).sort(), payment_count: 2, initial_run_created: 1, second_run_created: 0 })
  })

  await test.step('Reports reconcile and survive reload', async () => {
    await page.goto('/overview')
    await page.getByLabel('Report start date', { exact: true }).fill(day)
    await page.getByLabel('Report final day', { exact: true }).fill(day)
    await page.getByRole('button', { name: 'All customers', exact: true }).click()
    await page.getByRole('combobox', { name: 'Find a customer' }).fill(fixture.customers.A.name)
    await page.getByRole('option').filter({ hasText: fixture.customers.A.name }).click()
    await page.getByRole('button', { name: 'Apply filters', exact: true }).click()
    for (const reload of [false, true]) {
      if (reload) await page.reload()
      await expect(metric(page, 'Active subscriptions')).toHaveText('1')
      await expect(metric(page, 'Invoiced')).toHaveText('INR 4,970.16')
      await expect(metric(page, 'Payments received')).toHaveText('INR 4,970.16')
      await expect(metric(page, 'Outstanding')).toHaveText('INR 0.00')
    }
    await page.screenshot({ path: testInfo.outputPath('T31-reconciled-report.png'), fullPage: true })
    verified('report_after_reload', { active_subscriptions: 1, invoiced: '4970.16', payments_received: '4970.16', outstanding: '0.00', customer_filter_applied: true })
  })

  const ownerContext = await browser.newContext({ baseURL: 'http://127.0.0.1:5174', viewport: { width: 1440, height: 1000 } })
  const foreignContext = await browser.newContext({ baseURL: 'http://127.0.0.1:5174', viewport: { width: 390, height: 844 } })
  try {
    const owner = await ownerContext.newPage()
    const foreign = await foreignContext.newPage()
    evidence.viewports.customer_a_desktop = owner.viewportSize()
    evidence.viewports.customer_b = foreign.viewportSize()
    owner.on('pageerror', error => errors.push(error.message))
    foreign.on('pageerror', error => errors.push(error.message))
    await test.step('Two real customer contexts, persisted portal and authenticated printing', async () => {
      await login(owner, 'customer_a')
      await publicRead(owner, '/portal/me')
      await publicRead(owner, '/portal/subscriptions')
      await publicRead(owner, '/portal/invoices')
      await expect(owner.getByRole('link', { name: subscriptionNumber, exact: true })).toBeVisible()
      await owner.goto('/portal/invoices')
      await owner.getByRole('link', { name: invoiceNumber, exact: true }).click()
      await owner.reload()
      await expect(owner.getByRole('heading', { name: invoiceNumber, exact: true })).toBeVisible()
      const invoice = await publicRead<{ data: Invoice }>(owner, `/portal/invoices/${invoiceId}`)
      expect(invoice.data).toMatchObject({ status: 'PAID', paid_amount: '4970.16', balance_due: '0.00' })
      await expect(owner.getByText('INR 2,000.00', { exact: true })).toBeVisible()
      await expect(owner.getByText('INR 2,970.16', { exact: true })).toBeVisible()
      const popupEvent = owner.waitForEvent('popup')
      await owner.getByRole('link', { name: 'Print invoice', exact: true }).click()
      const print = await popupEvent
      await print.waitForLoadState('domcontentloaded')
      await expect(print).toHaveURL(new RegExp(`/api/v1/portal/invoices/${invoiceId}/print$`))
      await expect(print.locator('body')).toContainText(invoiceNumber)
      await expect(print.locator('body')).toContainText('4970.16')
      expect((await print.locator('body').textContent())?.includes(privateNote), 'Printable invoices must omit private notes').toBe(false)
      expect((await print.locator('body').textContent())?.includes(fixture.actors.admin.email), 'Printable invoices must omit staff identity').toBe(false)
      await expect(print.getByText(/internal cost|cost price|staff note/i)).toHaveCount(0)
      await print.emulateMedia({ media: 'print' })
      await print.screenshot({ path: testInfo.outputPath('T31-print-invoice.png'), fullPage: true })
      await print.close()
      await owner.setViewportSize({ width: 390, height: 844 })
      evidence.viewports.customer_a_mobile = owner.viewportSize()
      await expect.poll(() => owner.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
      await owner.screenshot({ path: testInfo.outputPath('T31-mobile-paid-invoice.png'), fullPage: true })
      verified('portal_invoice_reload_and_print', { paid_invoice_reloaded: true, authenticated_print: true, print_total: '4970.16', private_note_absent: true, staff_identity_absent: true, internal_cost_labels_absent: true, mobile_overflow_absent: true })
    })
    await test.step('Customer schedules pause, cancels it, schedules closure and creates a linked draft', async () => {
      await owner.goto(`/portal/subscriptions/${subscriptionId}`)
      const before = (await publicRead<{ data: SubscriptionDetail }>(owner, `/portal/subscriptions/${subscriptionId}`)).data
      expect(before).toMatchObject({ state: 'ACTIVE', end_date: '2027-01-02', next_billing_date: '2026-12-02' })
      const paused = await portalAction(owner, subscriptionId, 'pause', 'Pause subscription', 'Pause subscription?', 'Confirm pause')
      expect(paused).toMatchObject({ state: 'ACTIVE', paused: false, pause_effective_on: '2026-12-02', pause_interval: { starts_on: '2026-12-02', ends_on: null } })
      await expect(owner.locator('.portal-notice')).toContainText('Pause scheduled for')
      await expect(owner.locator('.portal-notice time')).toHaveAttribute('datetime', '2026-12-02')
      await expect(owner.locator('.portal-notice')).toBeFocused()
      await owner.reload()
      expect((await publicRead<{ data: SubscriptionDetail }>(owner, `/portal/subscriptions/${subscriptionId}`)).data.pause_effective_on).toBe('2026-12-02')
      await expect(owner.locator('.portal-facts > div').filter({ has: owner.getByText('Pause takes effect', { exact: true }) }).locator('time')).toHaveAttribute('datetime', '2026-12-02')
      verified('pause', { effective_on: paused.pause_effective_on ?? null, state: paused.state, notice_focused: true, persisted_after_reload: true })
      const resumed = await portalAction(owner, subscriptionId, 'resume', 'Cancel scheduled pause', 'Cancel scheduled pause?', 'Cancel scheduled pause')
      expect(resumed).toMatchObject({ state: 'ACTIVE', pause_interval: null, pause_effective_on: null, resume_effective_on: null })
      await expect(owner.locator('.portal-notice')).toHaveText('Your scheduled pause was cancelled.')
      await expect(owner.locator('.portal-notice')).toBeFocused()
      await owner.reload()
      expect((await publicRead<{ data: SubscriptionDetail }>(owner, `/portal/subscriptions/${subscriptionId}`)).data.pause_interval).toBeNull()
      await expect(owner.getByText('Pause takes effect', { exact: true })).toHaveCount(0)
      verified('cancel_scheduled_pause', { interval: null, notice_focused: true, persisted_after_reload: true })
      const closed = await portalAction(owner, subscriptionId, 'close', 'Close subscription', 'Close subscription?', 'Confirm close')
      expect(closed).toMatchObject({ state: 'ACTIVE', close_effective_on: '2026-12-02', end_date: '2027-01-02' })
      await expect(owner.locator('.portal-notice')).toContainText('Closure takes effect on')
      await expect(owner.locator('.portal-notice time')).toHaveAttribute('datetime', '2026-12-02')
      await expect(owner.getByRole('button', { name: 'Close subscription', exact: true })).toBeFocused()
      await owner.reload()
      expect((await publicRead<{ data: SubscriptionDetail }>(owner, `/portal/subscriptions/${subscriptionId}`)).data.close_effective_on).toBe('2026-12-02')
      await expect(owner.locator('.portal-facts > div').filter({ has: owner.getByText('Closure takes effect', { exact: true }) }).locator('time')).toHaveAttribute('datetime', '2026-12-02')
      expect((await publicRead<{ data: Invoice }>(owner, `/portal/invoices/${invoiceId}`)).data).toMatchObject({ status: 'PAID', total: '4970.16', paid_amount: '4970.16', balance_due: '0.00' })
      verified('schedule_close', { effective_on: closed.close_effective_on ?? null, state: closed.state, connected_trigger_focused: true, persisted_after_reload: true, settled_invoice_unchanged: true })
      await owner.getByLabel('Renewal start date', { exact: true }).fill('2026-12-02')
      await owner.getByLabel('Renewal ends before', { exact: true }).fill('2027-01-02')
      const renewal = await portalAction(owner, subscriptionId, 'renew', 'Create renewal draft', 'Create a renewal draft?', 'Create draft')
      expect(renewal).toMatchObject({ state: 'DRAFT', prior_subscription_id: subscriptionId, start_date: '2026-12-02', end_date: '2027-01-02' })
      expect(renewal.id).not.toBe(subscriptionId)
      await expect(owner).toHaveURL(new RegExp(`/portal/subscriptions/${renewal.id}$`))
      await expect(owner.locator('.portal-notice')).toHaveText('Your linked renewal draft was created. Brightloop staff will review and confirm it.')
      await expect(owner.getByRole('link', { name: 'View previous subscription', exact: true })).toHaveAttribute('href', `/portal/subscriptions/${subscriptionId}`)
      await owner.reload()
      expect((await publicRead<{ data: SubscriptionDetail }>(owner, `/portal/subscriptions/${renewal.id}`)).data).toMatchObject({ state: 'DRAFT', prior_subscription_id: subscriptionId })
      const invoices = await publicRead<{ items: Invoice[]; total: number }>(owner, '/portal/invoices')
      expect(invoices.total).toBe(1)
      expect(invoices.items[0].id).toBe(invoiceId)
      expect((await publicRead<{ data: Invoice }>(owner, `/portal/invoices/${invoiceId}`)).data.payments).toHaveLength(2)
      await owner.screenshot({ path: testInfo.outputPath('T31-customer-renewal-draft.png'), fullPage: true })
      verified('renewal', { state: renewal.state, start_date: renewal.start_date, end_date: renewal.end_date, linked_to_original: true, staff_review_notice: true, persisted_after_reload: true, invoice_count: 1, payment_count: 2 })
    })
    await test.step('Foreign customer cannot read or mutate the original lifecycle records', async () => {
      const before = (await publicRead<{ data: SubscriptionDetail }>(owner, `/portal/subscriptions/${subscriptionId}`)).data
      const subscriptionsBefore = await ownerSubscriptionIds(owner)
      expect(subscriptionsBefore).toEqual([...fixture.owned.subscriptions].sort())
      await login(foreign, 'customer_b')
      await publicRead(foreign, '/portal/me')
      const foreignSubscriptions = await publicRead<{ total: number }>(foreign, '/portal/subscriptions')
      const foreignInvoices = await publicRead<{ total: number }>(foreign, '/portal/invoices')
      expect(foreignSubscriptions.total).toBe(0)
      expect(foreignInvoices.total).toBe(0)
      await expect(foreign.getByRole('link', { name: subscriptionNumber, exact: true })).toHaveCount(0)
      await foreign.goto('/portal/invoices')
      await expect(foreign.getByRole('heading', { name: 'My invoices', exact: true })).toBeVisible()
      await expect(foreign.getByRole('link', { name: invoiceNumber, exact: true })).toHaveCount(0)
      for (const path of [`/portal/subscriptions/${subscriptionId}`, `/portal/invoices/${invoiceId}`, `/portal/invoices/${invoiceId}/print`]) {
        const response = await foreign.request.get(`/api/v1${path}`)
        expect(response.status()).toBe(404)
        assertPublicProjection(await response.json())
      }
      const session = await foreign.request.get('/api/v1/auth/session')
      expect(session.status()).toBe(200)
      const csrf = (await session.json()).data.csrf_token as string
      for (const action of ['pause', 'resume', 'close', 'renew']) {
        const result = await foreign.request.post(`/api/v1/portal/subscriptions/${subscriptionId}/${action}`, {
          headers: { Origin: 'http://127.0.0.1:5174', 'X-CSRF-Token': csrf },
          data: action === 'renew' ? { start_date: '2026-12-02', end_date: '2027-01-02' } : {},
        })
        expect(result.status()).toBe(404)
        assertPublicProjection(await result.json())
      }
      const unchanged = (await publicRead<{ data: SubscriptionDetail }>(owner, `/portal/subscriptions/${subscriptionId}`)).data
      expect(unchanged).toMatchObject({ state: 'ACTIVE', revision: before.revision, close_effective_on: '2026-12-02', pause_interval: null })
      expect(await ownerSubscriptionIds(owner)).toEqual(subscriptionsBefore)
      const invoice = (await publicRead<{ data: Invoice }>(owner, `/portal/invoices/${invoiceId}`)).data
      expect(invoice.payments).toHaveLength(2)
      expect(invoice).toMatchObject({ total: '4970.16', paid_amount: '4970.16', balance_due: '0.00' })
      expect((await publicRead<{ total: number }>(owner, '/portal/invoices')).total).toBe(1)
      verified('foreign_isolation_and_safe_projections', { read_statuses: ['subscription:404', 'invoice:404', 'print:404'], action_statuses: ['pause:404', 'resume:404', 'close:404', 'renew:404'], all_owner_subscription_ids_unchanged: true, owner_subscription_count: subscriptionsBefore.length, original_revision_unchanged: true, invoice_count: 1, payment_count: 2, total: invoice.total, paid_amount: invoice.paid_amount, balance_due: invoice.balance_due, customer_lists_empty: true, checked_customer_projections_exclude_private_fields: true })
    })
  } finally {
    await ownerContext.close()
    await foreignContext.close()
  }
  expect(errors).toEqual([])
  verified('browser_errors', { page_error_count: 0 })
  fixture.completed = true
  saveManifest()
})
