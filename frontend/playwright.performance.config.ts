import { defineConfig, devices } from '@playwright/test'

if (!process.env.CADENTRA_PERFORMANCE_RUN) throw new Error('Set a unique CADENTRA_PERFORMANCE_RUN for this measurement invocation')
if (!process.env.CADENTRA_PERFORMANCE_CREDENTIALS) throw new Error('Set CADENTRA_PERFORMANCE_CREDENTIALS to a private T30 fixture manifest')
if (!process.env.CADENTRA_PERFORMANCE_ARTIFACT?.startsWith('/tmp/')) throw new Error('Set CADENTRA_PERFORMANCE_ARTIFACT to a JSON artifact under /tmp')
export default defineConfig({
  testDir: './e2e',
  testMatch: 'performance.ts',
  outputDir: process.env.CADENTRA_PERFORMANCE_OUTPUT || 'test-results/performance',
  timeout: 180_000,
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: 'list',
  use: { baseURL: 'http://127.0.0.1:5174', trace: 'off', screenshot: 'only-on-failure' },
  projects: [{ name: 'performance-desktop', use: { ...devices['Desktop Chrome'], viewport: { width: 1497, height: 1049 } } }],
  webServer: { command: 'API_PORT=8004 npm run dev', url: 'http://127.0.0.1:5174', reuseExistingServer: true },
})
