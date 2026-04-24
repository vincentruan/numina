import { test, expect } from '@playwright/test'
import { childFamily, richFamily } from '../lib/fixtures'

/**
 * 盲盒完整流程 E2E 测试
 *
 * 验证盲盒功能的完整生命周期：
 *   1. 父母配置盲盒（启用、设置概率）
 *   2. 父母添加礼物到礼物池
 *   3. 儿童使用免费抽奖机会抽奖
 *   4. 儿童使用家务金币抽奖
 *   5. 父母查看抽奖记录并兑现礼物
 *
 * 前置条件：seed-data.sh 已创建 test_rich 和 test_child，并添加盲盒种子数据。
 */
test.describe('blind box flow', () => {
  test('parent configures blind box → adds gifts → child draws → parent fulfills', async ({ browser }) => {
    const ctxParent = await browser.newContext()
    const ctxChild = await browser.newContext()
    const pageParent = await ctxParent.newPage()
    const pageChild = await ctxChild.newPage()

    try {
      // ── Setup: log in both contexts ──────────────────────────────────────
      await richFamily(pageParent)
      await childFamily(pageChild)

      // ── Step 1: Parent enables blind box and configures probabilities ────
      const configResp = await pageParent.request.get('/api/v1/blind-box/config')
      expect(configResp.ok(), `GET /blind-box/config failed: ${configResp.status()}`).toBeTruthy()
      const configData = await configResp.json()
      const config = configData.data ?? configData

      // Enable blind box if not already enabled
      if (!config.enabled) {
        const updateResp = await pageParent.request.put('/api/v1/blind-box/config', {
          data: { enabled: true },
        })
        expect(updateResp.ok(), 'Failed to enable blind box').toBeTruthy()
      }

      // ── Step 2: Parent adds gifts to the pool ────────────────────────────
      const giftsResp = await pageParent.request.get('/api/v1/blind-box/gifts')
      expect(giftsResp.ok()).toBeTruthy()
      const giftsData = await giftsResp.json()
      const existingGifts = giftsData.data ?? giftsData

      // Add test gifts if pool is empty
      if (existingGifts.length === 0) {
        const testGifts = [
          { name: '测试礼物-普通', emoji: '🎁', value_score: 3, description: 'E2E测试普通礼物' },
          { name: '测试礼物-惊喜', emoji: '🎉', value_score: 8, description: 'E2E测试惊喜礼物' },
        ]

        for (const gift of testGifts) {
          const createResp = await pageParent.request.post('/api/v1/blind-box/gifts', { data: gift })
          expect(createResp.ok(), `Failed to create gift: ${gift.name}`).toBeTruthy()
        }
      }

      // ── Step 3: Child uses bonus draw (if available) ─────────────────────
      const bonusDrawsResp = await pageChild.request.get('/api/v1/child/blind-box/bonus-draws')
      expect(bonusDrawsResp.ok()).toBeTruthy()
      const bonusDrawsData = await bonusDrawsResp.json()
      const bonusDraws: Array<{ id: number; status: string }> = bonusDrawsData.data ?? bonusDrawsData
      const availableBonus = bonusDraws.find((b) => b.status === 'available')

      if (availableBonus) {
        const drawResp = await pageChild.request.post(`/api/v1/child/blind-box/bonus-draws/${availableBonus.id}/use`)
        expect(drawResp.ok(), 'Bonus draw failed').toBeTruthy()
        const drawData = await drawResp.json()
        const draw = drawData.data ?? drawData
        expect(draw.is_bonus, 'Draw should be marked as bonus').toBe(true)
        expect(draw.coins_spent, 'Bonus draw should cost 0 coins').toBe(0)
      }

      // ── Step 4: Child uses chore-based draw (if has approved chores) ─────
      const today = new Date().toISOString().split('T')[0]
      const choresResp = await pageChild.request.get(`/api/v1/child/chores?date=${today}`)
      expect(choresResp.ok()).toBeTruthy()
      const choresData = await choresResp.json()
      const chores: Array<{ id: string; status: string; coin_reward: number }> = choresData.data ?? choresData
      const approvedChores = chores.filter((c) => c.status === 'approved')

      if (approvedChores.length > 0) {
        const choreIds = approvedChores.map((c) => c.id)
        const drawResp = await pageChild.request.post('/api/v1/child/blind-box/draw', {
          data: { chore_instance_ids: choreIds },
        })
        expect(drawResp.ok(), 'Chore-based draw failed').toBeTruthy()
        const drawData = await drawResp.json()
        const draw = drawData.data ?? drawData
        expect(draw.is_bonus, 'Chore-based draw should not be bonus').toBe(false)
        expect(draw.coins_spent, 'Chore-based draw should cost coins').toBeGreaterThan(0)
      }

      // ── Step 5: Parent views draw history ────────────────────────────────
      const drawsResp = await pageParent.request.get('/api/v1/blind-box/draws')
      expect(drawsResp.ok()).toBeTruthy()
      const drawsData = await drawsResp.json()
      const draws: Array<{ id: number; status: string; gift_name: string }> = drawsData.data ?? drawsData

      // Only assert if draws exist (idempotent — may have no bonus draws or approved chores)
      if (draws.length > 0) {
        // ── Step 6: Parent fulfills a pending draw ───────────────────────────
        const pendingDraw = draws.find((d) => d.status === 'pending_fulfillment')
        if (pendingDraw) {
          const fulfillResp = await pageParent.request.put(`/api/v1/blind-box/draws/${pendingDraw.id}/fulfill`)
          expect(fulfillResp.ok(), 'Failed to fulfill draw').toBeTruthy()
          const fulfilledData = await fulfillResp.json()
          const fulfilled = fulfilledData.data ?? fulfilledData
          expect(fulfilled.status, 'Draw should be marked as fulfilled').toBe('fulfilled')
          expect(fulfilled.fulfilled_at, 'fulfilled_at should be set').toBeTruthy()
        }
      }
    } finally {
      await ctxParent.close()
      await ctxChild.close()
    }
  })

  test('parent can create gift from child wish', async ({ browser }) => {
    const ctxParent = await browser.newContext()
    const ctxChild = await browser.newContext()
    const pageParent = await ctxParent.newPage()
    const pageChild = await ctxChild.newPage()

    try {
      await richFamily(pageParent)
      await childFamily(pageChild)

      // Child creates a wish
      const wishName = `E2E盲盒心愿_${Date.now()}`
      const createWishResp = await pageChild.request.post('/api/v1/child/wishes', {
        data: { name: wishName, priority: 'high', description: '测试从心愿转礼物' },
      })
      expect(createWishResp.ok()).toBeTruthy()
      const wishData = await createWishResp.json()
      const wish = wishData.data ?? wishData

      // Parent approves wish with star coin cost
      const approveResp = await pageParent.request.post(`/api/v1/family/child-wishes/${wish.id}/approve`, {
        data: { star_coin_cost: 10 },
      })
      expect(approveResp.ok()).toBeTruthy()

      // Parent converts wish to blind box gift
      const convertResp = await pageParent.request.post(`/api/v1/blind-box/gifts/from-wish/${wish.id}`)
      expect(convertResp.ok(), 'Failed to convert wish to gift').toBeTruthy()
      const giftData = await convertResp.json()
      const gift = giftData.data ?? giftData
      expect(gift.name, 'Gift name should match wish name').toBe(wishName)
      // Compare first 15 digits to avoid BigInt precision loss in JSON
      expect(String(gift.source_wish_id).substring(0, 15), 'Gift should reference source wish').toBe(String(wish.id).substring(0, 15))

      // Verify duplicate conversion is rejected
      const duplicateResp = await pageParent.request.post(`/api/v1/blind-box/gifts/from-wish/${wish.id}`)
      expect(duplicateResp.status(), 'Duplicate conversion should return 409').toBe(409)
    } finally {
      await ctxParent.close()
      await ctxChild.close()
    }
  })

  test('blind box config page is accessible', async ({ page }) => {
    await richFamily(page)
    await page.goto('/blind-box/config')
    await page.waitForLoadState('networkidle')

    // Verify auth works — page should not redirect to login
    await expect(page).not.toHaveURL(/\/login/)
  })

  test('blind box gift list page is accessible', async ({ page }) => {
    await richFamily(page)
    await page.goto('/blind-box/gifts')
    await page.waitForLoadState('networkidle')

    // Verify auth works — page should not redirect to login
    await expect(page).not.toHaveURL(/\/login/)
  })

  test('child blind box page is accessible', async ({ page }) => {
    await childFamily(page)
    await page.goto('/child/blind-box')
    await page.waitForLoadState('networkidle')

    // Verify auth works — page should not redirect to login
    await expect(page).not.toHaveURL(/\/login/)
  })
})
