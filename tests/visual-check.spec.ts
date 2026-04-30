import { test, expect } from '@playwright/test'

const BASE = 'http://localhost:5175'

test.use({ viewport: { width: 375, height: 812 } })

test('light mode — dashboard at 375px', async ({ page }) => {
  await page.goto(BASE, { waitUntil: 'networkidle', timeout: 10000 }).catch(() => {})
  await page.waitForTimeout(1500)
  await page.screenshot({ path: 'tests/screenshots/light-mode.png', fullPage: false })
})

test('dark mode — dashboard at 375px', async ({ page }) => {
  await page.goto(BASE, { waitUntil: 'networkidle', timeout: 10000 }).catch(() => {})
  await page.evaluate(() => {
    document.documentElement.setAttribute('data-theme', 'dark')
  })
  await page.waitForTimeout(800)
  await page.screenshot({ path: 'tests/screenshots/dark-mode.png', fullPage: false })
})

test('light mode — full page scroll', async ({ page }) => {
  await page.goto(BASE, { waitUntil: 'networkidle', timeout: 10000 }).catch(() => {})
  await page.waitForTimeout(1500)
  await page.screenshot({ path: 'tests/screenshots/light-full.png', fullPage: true })
})
