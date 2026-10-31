// Explicit local-demo integration check. Creates one fictional customer per run.
import { chromium } from '../frontend/node_modules/@playwright/test/index.mjs'

const origin = new URL(process.env.GATE_A_ORIGIN || 'http://localhost:5171')
if (!['localhost', '127.0.0.1'].includes(origin.hostname) || origin.protocol !== 'http:' || origin.username || origin.password) {
  throw new Error('Gate A check is restricted to an explicit local demo origin')
}
const browser = await chromium.launch({ headless: true, ...(process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE } : {}) })
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } })
  page.setDefaultTimeout(10000)
  page.setDefaultNavigationTimeout(20000)
  const errors = []
  page.on('pageerror', error => errors.push(error.message))
  await page.goto(new URL('/sign-in', origin).href)
  const result = await page.evaluate(async () => {
    const email = `foundation-${Date.now()}@example.com`
    const password = crypto.randomUUID() + 'Aa!'
    const request = (path, body, headers = {}) => fetch('/api/v1' + path, {
      method: body ? 'POST' : 'GET', credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', ...headers },
      ...(body ? { body: JSON.stringify(body) } : {}),
    })
    const health = await request('/health')
    const signup = await request('/auth/signup', { name: 'Foundation Customer', email, password })
    const login = await request('/auth/login', { email, password })
    const signed = await login.json()
    const session = await request('/auth/session')
    const forbidden = await request('/products')
    const missingCSRF = await request('/auth/logout', {})
    return { health: health.status, signup: signup.status, login: login.status, session: session.status, role: signed.data?.actor?.role, forbidden: forbidden.status, missingCSRF: missingCSRF.status }
  })
  const expected = { health: 200, signup: 201, login: 200, session: 200, role: 'CUSTOMER', forbidden: 403, missingCSRF: 403 }
  if (JSON.stringify(result) !== JSON.stringify(expected)) throw new Error(JSON.stringify(result))
  await page.goto(new URL('/portal/subscriptions', origin).href)
  await page.getByRole('navigation', { name: 'Customer navigation' }).waitFor()
  await page.getByRole('heading', { name: 'My subscriptions', exact: true }).waitFor()
  await page.getByText('No subscriptions yet', { exact: true }).waitFor()
  if (process.env.GATE_A_SCREENSHOT) await page.screenshot({ path: process.env.GATE_A_SCREENSHOT, fullPage: true })
  const logout = await page.evaluate(async () => {
    const session = await (await fetch('/api/v1/auth/session')).json()
    const out = await fetch('/api/v1/auth/logout', { method: 'POST', headers: { 'X-CSRF-Token': session.data.csrf_token } })
    const again = await fetch('/api/v1/auth/session')
    return { logout: out.status, afterLogout: again.status }
  })
  if (logout.logout !== 200 || logout.afterLogout !== 401 || errors.length) throw new Error('Logout/session/render check failed')
  console.log(JSON.stringify({ gateA: 'PASS', ...result, ...logout, portalDataRendered: true, pageErrors: errors.length }))
} finally { await browser.close() }
