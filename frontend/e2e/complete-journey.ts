/** T31: real browser writes, actual PostgreSQL, no route interception or fake totals. */
import { randomUUID } from 'node:crypto'
import { lstatSync, readFileSync, renameSync, writeFileSync } from 'node:fs'
import { dirname, isAbsolute } from 'node:path'
import { expect, test, type Page } from '@playwright/test'

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
const manifestPath = process.env.CADENTRA_JOURNEY_MANIFEST ?? ''
if (!isAbsolute(manifestPath) || dirname(manifestPath) !== '/tmp') throw new Error('T31 manifest must be directly under /tmp')
const metadata = lstatSync(manifestPath)
if (!metadata.isFile() || (metadata.mode & 0o077) !== 0) throw new Error('T31 manifest must be a regular private mode-0600 file')
const fixture = JSON.parse(readFileSync(manifestPath, 'utf8')) as Manifest
if (!fixture.test_only || fixture.kind !== 'cadentra-complete-journey' || fixture.database !== 'cadentra_experience_test' || fixture.business_date !== '2026-11-02') {
  throw new Error('Use the guarded T31 seed manifest with its fixed test-only business date')
}
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

  await test.step('Create actual product, variant and tax/discount configuration', async () => {
    await page.goto('/catalog/products')
    await page.getByRole('button', { name: 'New product', exact: true }).click()
    const editor = page.getByRole('region', { name: 'New product', exact: true })
    await editor.getByLabel('Product name', { exact: true }).fill(productName)
    await editor.getByLabel('Sales price (INR)', { exact: true }).fill('1000.00')
    await editor.getByLabel('Internal cost (INR)', { exact: true }).fill('100.00')
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
      await page.getByLabel('Payment note', { exact: true }).fill('T31 manual payment already received; fictional test data')
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
  })

  const ownerContext = await browser.newContext({ baseURL: 'http://127.0.0.1:5174', viewport: { width: 1440, height: 1000 } })
  const foreignContext = await browser.newContext({ baseURL: 'http://127.0.0.1:5174', viewport: { width: 390, height: 844 } })
  try {
    const owner = await ownerContext.newPage()
    const foreign = await foreignContext.newPage()
    owner.on('pageerror', error => errors.push(error.message))
    foreign.on('pageerror', error => errors.push(error.message))
    await test.step('Two real customer contexts, persisted portal and authenticated printing', async () => {
      await login(owner, 'customer_a')
      await expect(owner.getByRole('link', { name: subscriptionNumber, exact: true })).toBeVisible()
      await owner.goto('/portal/invoices')
      await owner.getByRole('link', { name: invoiceNumber, exact: true }).click()
      await owner.reload()
      await expect(owner.getByRole('heading', { name: invoiceNumber, exact: true })).toBeVisible()
      const response = await owner.request.get(`/api/v1/portal/invoices/${invoiceId}`)
      expect(response.status()).toBe(200)
      expect((await response.json()).data).toMatchObject({ status: 'PAID', paid_amount: '4970.16', balance_due: '0.00' })
      await expect(owner.getByText('INR 2,000.00', { exact: true })).toBeVisible()
      await expect(owner.getByText('INR 2,970.16', { exact: true })).toBeVisible()
      const popupEvent = owner.waitForEvent('popup')
      await owner.getByRole('link', { name: 'Print invoice', exact: true }).click()
      const print = await popupEvent
      await print.waitForLoadState('domcontentloaded')
      await expect(print).toHaveURL(new RegExp(`/api/v1/portal/invoices/${invoiceId}/print$`))
      await expect(print.locator('body')).toContainText(invoiceNumber)
      await expect(print.locator('body')).toContainText('4970.16')
      await print.emulateMedia({ media: 'print' })
      await print.screenshot({ path: testInfo.outputPath('T31-print-invoice.png'), fullPage: true })
      await print.close()
      await owner.setViewportSize({ width: 390, height: 844 })
      await expect.poll(() => owner.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
      await owner.screenshot({ path: testInfo.outputPath('T31-mobile-paid-invoice.png'), fullPage: true })
      await login(foreign, 'customer_b')
      await expect(foreign.getByRole('link', { name: subscriptionNumber, exact: true })).toHaveCount(0)
      await foreign.goto('/portal/invoices')
      await expect(foreign.getByRole('heading', { name: 'My invoices', exact: true })).toBeVisible()
      await expect(foreign.getByRole('link', { name: invoiceNumber, exact: true })).toHaveCount(0)
      for (const path of [`/portal/subscriptions/${subscriptionId}`, `/portal/invoices/${invoiceId}`, `/portal/invoices/${invoiceId}/print`]) {
        expect((await foreign.request.get(`/api/v1${path}`)).status()).toBe(404)
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
      }
      const unchanged = await page.request.get(`/api/v1/subscriptions/${subscriptionId}`)
      expect(unchanged.status()).toBe(200)
      expect((await unchanged.json()).data.state).toBe('ACTIVE')
      expect((await readInvoice(page, invoiceId)).payments).toHaveLength(2)
    })
  } finally {
    await ownerContext.close()
    await foreignContext.close()
  }
  expect(errors).toEqual([])
  fixture.completed = true
  saveManifest()
})
