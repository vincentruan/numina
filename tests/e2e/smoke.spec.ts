import { test, expect } from '@playwright/test'
import { singleAsset } from '../lib/fixtures'

test.describe('smoke: asset pages render without errors', () => {
  test('asset list page renders at least one asset', async ({ page }) => {
    const errors: string[] = []
    page.on('console', (msg) => {
      if (msg.type() === 'error') errors.push(msg.text())
    })

    await singleAsset(page)
    await page.goto('/assets')

    // Page should not redirect to login
    await expect(page).not.toHaveURL(/\/login/)

    // At least one asset item should be visible
    const assetItems = page.locator('.asset-card, .asset-list-item')
    await expect(assetItems.first()).toBeVisible({ timeout: 10_000 })

    // No JS console errors (filter out network errors from rate limiting)
    const realErrors = errors.filter((e) => !e.includes('Failed to load resource') && !e.includes('AxiosError'))
    expect(realErrors, `Console errors on /assets: ${realErrors.join(', ')}`).toHaveLength(0)
  })

  test('asset detail page renders asset name', async ({ page }) => {
    const errors: string[] = []
    page.on('console', (msg) => {
      if (msg.type() === 'error') errors.push(msg.text())
    })

    await singleAsset(page)
    await page.goto('/assets')
    await expect(page).not.toHaveURL(/\/login/)

    // Click the first asset to navigate to its detail page
    const firstAsset = page.locator('.asset-card, .asset-list-item').first()
    await expect(firstAsset).toBeVisible({ timeout: 10_000 })
    await firstAsset.click()

    // Should be on an asset detail page (UUID-based IDs)
    await expect(page).toHaveURL(/\/assets\/[\w-]+/)

    // Asset name should be visible somewhere on the page
    await expect(page.locator('text=测试房产').first()).toBeVisible({ timeout: 10_000 })

    // No JS console errors (filter out network errors from rate limiting)
    const realErrors = errors.filter((e) => !e.includes('Failed to load resource') && !e.includes('AxiosError'))
    expect(realErrors, `Console errors on asset detail: ${realErrors.join(', ')}`).toHaveLength(0)
  })

  test('dashboard renders without JS errors', async ({ page }) => {
    const errors: string[] = []
    page.on('console', (msg) => {
      if (msg.type() === 'error') errors.push(msg.text())
    })

    await singleAsset(page)
    await page.goto('/')
    await expect(page).not.toHaveURL(/\/login/)

    // Dashboard should render some content — wait for the main layout
    // The dashboard has a net worth display or asset summary
    await expect(
      page.locator('.van-nav-bar, [class*="dashboard"], [class*="overview"], main').first()
    ).toBeVisible({ timeout: 10_000 })

    // No JS console errors (filter out network errors from rate limiting)
    const realErrors = errors.filter((e) => !e.includes('Failed to load resource') && !e.includes('AxiosError'))
    expect(realErrors, `Console errors on dashboard: ${realErrors.join(', ')}`).toHaveLength(0)
  })
})
