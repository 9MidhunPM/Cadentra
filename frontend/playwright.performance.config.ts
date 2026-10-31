import { defineConfig, devices } from '@playwright/test'
import { checkedOrigin, tmpPath } from './e2e/performance-server'

const run = process.env.CADENTRA_PERFORMANCE_RUN
if (!run || !/^[a-zA-Z0-9_-]{1,80}$/.test(run)) throw new Error('Set a unique safe CADENTRA_PERFORMANCE_RUN')
tmpPath(process.env.CADENTRA_PERFORMANCE_CREDENTIALS, 'Private fixture manifest')
tmpPath(process.env.CADENTRA_PERFORMANCE_ARTIFACT, 'Measurement artifact')
tmpPath(process.env.CADENTRA_PERFORMANCE_SERVER_METADATA, 'Native static server evidence')
export default defineConfig({
  testDir: './e2e',
  testMatch: 'performance.ts',
  outputDir: process.env.CADENTRA_PERFORMANCE_OUTPUT
    ? tmpPath(process.env.CADENTRA_PERFORMANCE_OUTPUT, 'Performance output') : `/tmp/cadentra-${run}-results`,
  timeout: 180_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: 'list',
  use: { baseURL: checkedOrigin(), trace: 'off', screenshot: 'only-on-failure' },
  projects: [{ name: 'static-performance', use: { ...devices['Desktop Chrome'], viewport: { width: 1497, height: 1049 } } }],
  // Deliberately no webServer: the separately owned native server must already
  // serve the recorded production build. This suite must never start Vite.
})
