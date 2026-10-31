import { expect, test } from '@playwright/test'
import { mockFeatureReads } from './fixtures'

test.beforeEach(async ({ page }) => {
  await mockFeatureReads(page)
  await page.route('**/api/v1/auth/session', route => route.fulfill({ json: { data: {
    actor: { id: 'test-staff', name: 'Experience tester', role: 'STAFF', customer_id: null }, csrf_token: 'fixture-csrf',
  } } }))
})

test('Graphite Mint defaults dark and Sage preference persists after reload', async ({ page }, testInfo) => {
  if (testInfo.project.name === 'desktop') await page.setViewportSize({ width: 1497, height: 1049 })
  await page.goto('/app')
  await expect(page.getByRole('heading', { name: 'Overview', exact: true })).toBeVisible()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
  await expect(page.locator('body')).toHaveCSS('color', 'rgb(236, 242, 235)')
  await page.screenshot({ path: testInfo.outputPath('graphite-mint.png'), fullPage: true })
  await page.getByRole('button', { name: 'Switch to light mode' }).click()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light')
  await expect(page.locator('meta[name="theme-color"]')).toHaveAttribute('content', '#f2f4ef')
  await expect(page.locator('body')).toHaveCSS('color', 'rgb(32, 39, 34)')
  await expect(page.getByRole('button', { name: 'Switch to dark mode' }).locator('svg')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Switch to dark mode' }).locator(':scope > span')).toHaveCSS('opacity', '1')
  await page.screenshot({ path: testInfo.outputPath('sage-commerce.png'), fullPage: true })
  await page.reload()
  await expect(page.getByRole('button', { name: 'Switch to dark mode' })).toBeVisible()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light')
  await page.getByRole('button', { name: 'Switch to dark mode' }).click()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
  expect(await page.evaluate(() => localStorage.getItem('cadentra:theme'))).toBe('dark')
})

test('page search filters permitted routes and opens a page by keyboard', async ({ page }) => {
  await page.goto('/app')
  await page.getByRole('button', { name: 'Search pages', exact: true }).click()
  const search = page.getByRole('combobox', { name: 'Search pages' })
  await expect(search).toBeFocused()
  await expect(page.getByRole('option', { name: 'Staff settings' })).toHaveCount(0)
  await search.fill('invoice')
  await expect(page.getByRole('option')).toHaveCount(1)
  await search.press('Enter')
  await expect(page).toHaveURL(/\/billing\/invoices$/)
  await expect(page.getByRole('heading', { name: 'Invoices', exact: true })).toBeFocused()
})

test('page-search shortcut and Escape restore focus; empty results are announced', async ({ page }) => {
  await page.goto('/app')
  await expect(page.getByRole('heading', { name: 'Overview', exact: true })).toBeVisible()
  await page.keyboard.press('Control+k')
  const search = page.getByRole('combobox', { name: 'Search pages' })
  await search.fill('No such destination')
  await expect(page.getByRole('status')).toHaveText('No matching pages. Try a different name.')
  await search.press('Escape')
  await expect(page.getByRole('dialog')).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Search pages', exact: true })).toBeFocused()
})

test('reduced motion keeps navigation and theme controls usable', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.goto('/app')
  await expect(page.getByRole('heading', { name: 'Overview', exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Switch to light mode' }).click()
  await page.getByRole('button', { name: 'Search pages', exact: true }).click()
  await page.getByRole('combobox').fill('Customers')
  await page.getByRole('combobox').press('Enter')
  await expect(page.getByRole('heading', { name: 'Customers', exact: true })).toBeFocused()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
})

test('keyboard page selection stays visible in a short viewport', async ({ page }) => {
  await page.setViewportSize({ width: 900, height: 420 })
  await page.goto('/app')
  await page.getByRole('button', { name: 'Search pages', exact: true }).click()
  const input = page.getByRole('combobox', { name: 'Search pages' })
  const options = page.getByRole('option')
  const count = await options.count()
  for (let index = 1; index < count; index += 1) await input.press('ArrowDown')
  await expect(options.last()).toBeInViewport({ ratio: 1 })
  await input.press('Enter')
  await expect(page.getByRole('heading', { name: 'Discounts', exact: true })).toBeFocused()
})
