import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  retries: 0,
  workers: 1,
  reporter: [['list'], ['html', { open: 'never' }]],

  use: {
    baseURL: 'http://localhost:5173',
    viewport: { width: 390, height: 844 },
    screenshot: 'on',
    trace: 'on',
    // httpOnly cookies require credentials to be sent
    // Axios uses withCredentials: true — browser context handles this automatically
  },

  projects: [
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
        channel: 'chrome',
        viewport: { width: 390, height: 844 },
      },
    },
  ],
})
