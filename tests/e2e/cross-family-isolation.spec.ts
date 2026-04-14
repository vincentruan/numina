import { test, expect } from '@playwright/test'
import { richFamily, emptyFamily } from '../lib/fixtures'

/**
 * 跨家庭数据隔离测试
 *
 * 验证家庭级数据隔离在浏览器层面有效：
 *   - Family B 无法通过直接 URL 访问 Family A 的资产
 *   - Family B 无法通过直接 URL 访问 Family A 的负债
 *   - Family B 无法通过直接 URL 访问 Family A 的心愿
 *
 * 使用两个独立的 browser context 模拟两个同时在线的用户。
 * Family A = test_rich（有完整数据）
 * Family B = test_empty（空家庭）
 *
 * 隔离机制：后端在 get_asset/get_liability/get_wish 中校验
 * resource.family_id === current_user.family_id，不匹配返回 404。
 * 前端收到 404 后应渲染错误页或跳转，不应显示资源内容。
 */

test.describe('cross-family data isolation', () => {
  test('Family B 无法通过 URL 访问 Family A 的资产', async ({ browser }) => {
    // 两个独立 context — 完全隔离的 cookie/localStorage
    const ctxA = await browser.newContext()
    const ctxB = await browser.newContext()
    const pageA = await ctxA.newPage()
    const pageB = await ctxB.newPage()

    try {
      // Family A 登录，获取第一个资产的 ID
      await richFamily(pageA)
      const assetsResp = await pageA.request.get('/api/v1/assets')
      expect(assetsResp.ok()).toBeTruthy()
      const assetsData = await assetsResp.json()
      const assets = assetsData.items ?? assetsData
      expect(assets.length, 'test_rich 应有资产').toBeGreaterThan(0)
      const assetId: string = assets[0].id

      // Family B 登录，尝试直接访问 Family A 的资产 URL
      await emptyFamily(pageB)

      // 1. API 层隔离：直接请求应返回 404
      const apiResp = await pageB.request.get(`/api/v1/assets/${assetId}`)
      expect(
        apiResp.status(),
        `Family B 访问 Family A 资产 API 应返回 404，实际: ${apiResp.status()}`
      ).toBe(404)

      // 2. 浏览器层隔离：导航到资产详情页不应显示 Family A 的资产名称
      await pageB.goto(`/assets/${assetId}`)
      await pageB.waitForLoadState('networkidle', { timeout: 8_000 }).catch(() => {})

      // 不应显示 Family A 资产的名称（测试房产）
      const assetName: string = assets[0].name
      await expect(pageB.locator(`text=${assetName}`)).not.toBeVisible({ timeout: 5_000 })

      // 应显示错误状态或跳转（van-empty、错误提示、或回到列表页）
      const hasErrorState =
        (await pageB.locator('.van-empty, [class*="error"], [class*="not-found"]').count()) > 0
      const redirectedToList = pageB.url().includes('/assets') && !pageB.url().includes(assetId)
      const redirectedToHome = pageB.url() === 'http://localhost/' || pageB.url().endsWith('/')

      expect(
        hasErrorState || redirectedToList || redirectedToHome,
        `Family B 访问 Family A 资产后应显示错误或跳转，当前 URL: ${pageB.url()}`
      ).toBeTruthy()
    } finally {
      await ctxA.close()
      await ctxB.close()
    }
  })

  test('Family B 无法通过 URL 访问 Family A 的负债', async ({ browser }) => {
    const ctxA = await browser.newContext()
    const ctxB = await browser.newContext()
    const pageA = await ctxA.newPage()
    const pageB = await ctxB.newPage()

    try {
      await richFamily(pageA)
      const liabResp = await pageA.request.get('/api/v1/liabilities')
      expect(liabResp.ok()).toBeTruthy()
      const liabilities = await liabResp.json()
      const items = liabilities.items ?? liabilities
      expect(items.length, 'test_rich 应有负债').toBeGreaterThan(0)
      const liabilityId: string = items[0].id

      await emptyFamily(pageB)

      // API 层隔离
      const apiResp = await pageB.request.get(`/api/v1/liabilities/${liabilityId}`)
      expect(
        apiResp.status(),
        `Family B 访问 Family A 负债 API 应返回 404，实际: ${apiResp.status()}`
      ).toBe(404)

      // 浏览器层隔离
      await pageB.goto(`/liabilities/${liabilityId}`)
      await pageB.waitForLoadState('networkidle', { timeout: 8_000 }).catch(() => {})

      const liabilityName: string = items[0].name
      await expect(pageB.locator(`text=${liabilityName}`)).not.toBeVisible({ timeout: 5_000 })
    } finally {
      await ctxA.close()
      await ctxB.close()
    }
  })

  test('Family B 无法通过 URL 访问 Family A 的心愿', async ({ browser }) => {
    const ctxA = await browser.newContext()
    const ctxB = await browser.newContext()
    const pageA = await ctxA.newPage()
    const pageB = await ctxB.newPage()

    try {
      await richFamily(pageA)
      const wishResp = await pageA.request.get('/api/v1/wishes')
      expect(wishResp.ok()).toBeTruthy()
      const wishes = await wishResp.json()
      const items = wishes.items ?? wishes
      expect(items.length, 'test_rich 应有心愿').toBeGreaterThan(0)
      const wishId: string = items[0].id

      await emptyFamily(pageB)

      // API 层隔离
      const apiResp = await pageB.request.get(`/api/v1/wishes/${wishId}`)
      expect(
        apiResp.status(),
        `Family B 访问 Family A 心愿 API 应返回 404，实际: ${apiResp.status()}`
      ).toBe(404)

      // 浏览器层隔离
      await pageB.goto(`/wishes/${wishId}`)
      await pageB.waitForLoadState('networkidle', { timeout: 8_000 }).catch(() => {})

      const wishName: string = items[0].name
      await expect(pageB.locator(`text=${wishName}`)).not.toBeVisible({ timeout: 5_000 })
    } finally {
      await ctxA.close()
      await ctxB.close()
    }
  })
})
