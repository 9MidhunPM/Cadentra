import { defineConfig, devices } from '@playwright/test'

if (!process.env.CADENTRA_LIVE_CREDENTIALS) throw new Error('Set CADENTRA_LIVE_CREDENTIALS to the private disposable-fixture manifest')
export default defineConfig({
  testDir: './e2e',
  outputDir: process.env.CADENTRA_LIVE_OUTPUT || 'test-results/live',
  testMatch: 'live-reporting.ts',
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: 'list',
  use: { baseURL: 'http://127.0.0.1:5174', trace: 'off', screenshot: 'only-on-failure' },
  projects: [
    { name: 'live-desktop', use: { ...devices['Desktop Chrome'], viewport: { width: 1497, height: 1049 } } },
    { name: 'live-mobile', use: { ...devices['iPhone 13'], defaultBrowserType: 'chromium' } },
  ],
  webServer: { command: 'API_PORT=8004 npm run dev', url: 'http://127.0.0.1:5174', reuseExistingServer: true },
})
