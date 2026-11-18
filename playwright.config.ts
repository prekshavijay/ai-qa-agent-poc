import { defineConfig, devices } from '@playwright/test'
import path from 'node:path'

const ARTIFACTS = path.join(__dirname, 'artifacts', 'test-execution')

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  workers: 1,
  timeout: 180_000,
  expect: { timeout: 30_000 },
  reporter: [['list'], ['json', { outputFile: path.join(ARTIFACTS, 'playwright-results.json') }]],
  use: {
    baseURL: 'http://127.0.0.1:5173',
    headless: false,
    viewport: { width: 1440, height: 900 },
    actionTimeout: 15_000,
    navigationTimeout: 30_000,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: {
      mode: 'on',
      size: { width: 1440, height: 900 },
    },
    launchOptions: {
      slowMo: 250,
    },
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'], channel: undefined },
    },
  ],
  outputDir: path.join(ARTIFACTS, 'playwright-output'),
})
