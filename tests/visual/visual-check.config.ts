import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: '.',
  testMatch: 'visual-check.spec.ts',
  timeout: 20_000,
  retries: 0,
  workers: 1,
  reporter: [['list']],
  use: {
    baseURL: 'http://localhost:5175',
    viewport: { width: 375, height: 812 },
  },
  projects: [{ name: 'chromium', use: { channel: 'chromium' } }],
})
