import { defineConfig, devices } from '@playwright/test'

if (!process.env.CADENTRA_JOURNEY_MANIFEST) {
  throw new Error('Set CADENTRA_JOURNEY_MANIFEST to a private /tmp T31 manifest after the database owner releases it')
}

export default defineConfig({
  testDir: './e2e',
  testMatch: 'complete-journey.ts',
  outputDir: 'test-results/complete-journey',
  timeout: 240_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: 'list',
  use: {
    baseURL: 'http://127.0.0.1:5174',
    trace: 'off',
    screenshot: 'only-on-failure',
    video: 'off',
  },
  projects: [{ name: 'complete-journey', use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 1000 } } }],
  // Start the reviewed real API separately against the guarded disposable DB.
  // This harness never installs a mock route or starts a fake financial service.
  webServer: {
    command: 'API_PORT=8004 npm run dev',
    url: 'http://127.0.0.1:5174',
    reuseExistingServer: true,
  },
})
