import { test, expect } from '@playwright/test'
import { singleAsset } from '../lib/fixtures'

test.describe('smoke: asset pages render without errors', () => {
  test('asset list page renders at least one asset', async ({ page }) => {
    const errors: string[] = []
    const networkErrors: string[] = []
    const errorBodies: string[] = []
    page.on('console', (msg) => {
      if (msg.type() === 'error') errors.push(msg.text())
    })
    page.on('response', async (resp) => {
      if (resp.status() >= 400 && resp.url().includes('/api/')) {
        networkErrors.push(`${resp.status()} ${resp.url()}`)
        try {
          const body = await resp.text()
          errorBodies.push(body)
        } catch {}
      }
    })

    const creds = await singleAsset(page)
    const token = creds.accessToken!

    // Verify assets exist via API (using Bearer token)
    const assetsResp = await page.request.get('/api/v1/assets', {
      headers: { Authorization: `Bearer ${token}` },
    })
    expect(assetsResp.ok()).toBeTruthy()
    const assetsData = await assetsResp.json()
    const raw = assetsData.data ?? assetsData
    const assets = Array.isArray(raw) ? raw : (raw.items ?? [])
    expect(assets.length, 'test_asset should have 1 asset').toBeGreaterThan(0)

    // Navigate to frontend
    await page.goto('/assets')

    // Page should not redirect to login
    await expect(page).not.toHaveURL(/\/login/)

    // Debug: log network errors and bodies before waiting for assets
    console.log('Network errors:', JSON.stringify(networkErrors))
    console.log('Error bodies:', JSON.stringify(errorBodies))

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

    const creds = await singleAsset(page)
    const token = creds.accessToken!

    // Get asset ID via API
    const assetsResp = await page.request.get('/api/v1/assets', {
      headers: { Authorization: `Bearer ${token}` },
    })
    expect(assetsResp.ok()).toBeTruthy()
    const assetsData = await assetsResp.json()
    const raw = assetsData.data ?? assetsData
    const assets = Array.isArray(raw) ? raw : (raw.items ?? [])
    expect(assets.length).toBeGreaterThan(0)
    const assetId = assets[0].id

    await page.goto(`/assets/${assetId}`)
    await expect(page).not.toHaveURL(/\/login/)

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