import { expect, test, type Page } from '@playwright/test'
import { mockFeatureReads } from './fixtures'

// Foundation-only fixtures. These do not prove real authentication or Gate A.
async function session(page: Page, role: 'ADMIN' | 'STAFF' | 'CUSTOMER' = 'ADMIN') {
  await mockFeatureReads(page)
  await page.route('**/api/v1/auth/session', route => route.fulfill({ json: {
    data: { actor: { id: 'test-actor', name: 'Foundation tester', role, customer_id: role === 'CUSTOMER' ? 'test-customer' : null }, csrf_token: 'test-csrf' },
  } }))
}

async function navigate(page: Page, label: string) {
  const opener = page.getByRole('button', { name: 'Open navigation' })
  if (await opener.isVisible()) await opener.click()
  await page.getByRole('navigation').getByRole('link', { name: label, exact: true }).click()
}

test('staff shell imports every feature route', async ({ page }, testInfo) => {
  await session(page)
  const errors: string[] = []
  page.on('pageerror', error => errors.push(error.message))
  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'Overview', exact: true })).toBeVisible()
  await page.screenshot({ path: testInfo.outputPath('overview.png'), fullPage: true })
  for (const label of ['Customers', 'Products', 'Plans', 'Subscriptions', 'Quotation templates', 'Invoices', 'Taxes', 'Discounts', 'Staff settings']) {
    await navigate(page, label)
    await expect(page.getByRole('heading', { name: label === 'Taxes' ? 'Tax rules' : label, exact: true })).toBeVisible()
    await expect(page).toHaveTitle(`${label === 'Taxes' ? 'Tax rules' : label} · Cadentra`)
    await expect(page.getByRole('heading', { name: label === 'Taxes' ? 'Tax rules' : label, exact: true })).toBeFocused()
  }
  await page.reload()
  await expect(page.getByRole('heading', { name: 'Staff settings' })).toBeVisible()
  expect(errors).toEqual([])
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
})

test('staff cannot open admin settings directly', async ({ page }) => {
  await session(page, 'STAFF')
  await page.goto('/settings/staff')
  await expect(page.getByRole('heading', { name: 'Access restricted' })).toBeVisible()
  await page.getByRole('link', { name: 'Return to your workspace' }).click()
  await expect(page.getByRole('heading', { name: 'Overview', exact: true })).toBeVisible()
  await expect(page.getByRole('link', { name: 'Staff settings' })).toHaveCount(0)
})

test('customer uses a separate portal and cannot open staff routes', async ({ page }) => {
  await session(page, 'CUSTOMER')
  await page.goto('/')
  await expect(page).toHaveURL(/\/portal\/subscriptions$/)
  await navigate(page, 'My invoices')
  await expect(page.getByRole('heading', { name: 'My invoices', exact: true })).toBeVisible()
  await navigate(page, 'Account')
  await expect(page.getByRole('heading', { name: 'Account', exact: true })).toBeVisible()
  await page.goto('/billing/invoices')
  await expect(page.getByRole('heading', { name: 'Access restricted' })).toBeVisible()
})

test('anonymous users reach identity placeholder instead of a fake session', async ({ page }) => {
  await page.route('**/api/v1/auth/session', route => route.fulfill({ status: 401, json: { error: { code: 'UNAUTHENTICATED', message: 'Sign in' } } }))
  await page.goto('/overview')
  await expect(page).toHaveURL(/\/sign-in$/)
  await expect(page.getByRole('heading', { name: 'Sign in', exact: true })).toBeVisible()
  await expect(page.getByRole('navigation')).toHaveCount(0)
})

test('backend failures remain visible and retry restores the session', async ({ page }) => {
  await mockFeatureReads(page)
  let healthy = false
  await page.route('**/api/v1/auth/session', route => route.fulfill(healthy ? { json: { data: { actor: { id: 'test', name: 'Tester', role: 'ADMIN', customer_id: null }, csrf_token: 'csrf' } } } : { status: 503, json: { error: { code: 'UNAVAILABLE', message: 'Service temporarily unavailable' } } }))
  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'We couldn’t connect' })).toBeVisible()
  healthy = true
  await page.getByRole('button', { name: 'Try again' }).click()
  await expect(page.getByRole('heading', { name: 'Overview', exact: true })).toBeVisible()
})

test('logout sends CSRF and clears the restored session', async ({ page }) => {
  await session(page)
  let signedOut = false
  await page.route('**/api/v1/auth/logout', async route => {
    expect(route.request().headers()['x-csrf-token']).toBe('test-csrf')
    signedOut = true
    await route.fulfill({ status: 204 })
  })
  await page.goto('/')
  await page.getByRole('button', { name: 'Sign out', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Sign in', exact: true })).toBeVisible()
  expect(signedOut).toBe(true)
})

test('mobile navigation closes with Escape and restores focus', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'mobile', 'Mobile drawer only')
  await session(page)
  await page.goto('/')
  const open = page.getByRole('button', { name: 'Open navigation' })
  await open.click()
  await expect(page.getByRole('dialog', { name: 'Workspace sidebar' })).toBeVisible()
  await page.keyboard.press('Control+k')
  await expect(page.getByRole('dialog', { name: 'Search pages' })).toHaveCount(0)
  await page.keyboard.press('Escape')
  await expect(open).toBeFocused()
  await expect(page.getByRole('dialog')).toHaveCount(0)
})

test('keyboard navigation focuses and announces the destination', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop', 'Desktop keyboard navigation')
  await session(page)
  await page.goto('/')
  const link = page.getByRole('navigation').getByRole('link', { name: 'Customers', exact: true })
  await link.focus()
  await page.keyboard.press('Enter')
  await expect(page.getByRole('heading', { name: 'Customers', exact: true })).toBeFocused()
  await expect(page).toHaveTitle('Customers · Cadentra')
})
