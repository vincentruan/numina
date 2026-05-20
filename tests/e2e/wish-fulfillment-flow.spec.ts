import { test, expect, type Page } from '@playwright/test'
import { childFamily, richFamily } from '../lib/fixtures'

/**
 * 心愿兑现流程 E2E 测试
 *
 * 验证完整的心愿兑现流水线：
 *   1. 儿童创建心愿（API）
 *   2. 父母审批心愿并设置星星币成本（API）
 *   3. 儿童申请兑现（API）
 *   4. 父母在心愿审核页看到兑现申请（UI）
 *   5. 父母点击兑现（UI）
 *   6. 儿童星星币余额减少（API）
 *
 * 使用两个独立 browser context 模拟儿童和父母同时在线。
 * 前置条件：seed-accounts.sh 已创建 test_child。
 */
test.describe('wish fulfillment flow', () => {
  test('child creates wish → parent approves → child redeems → parent realizes → coins deducted', async ({ browser }) => {
    const ctxChild = await browser.newContext()
    const ctxParent = await browser.newContext()
    const pageChild = await ctxChild.newPage()
    const pageParent = await ctxParent.newPage()

    try {
      // ── Setup: log in both contexts ──────────────────────────────────────
      await childFamily(pageChild)
      await richFamily(pageParent)

      const WISH_COST = 5
      const wishName = `E2E测试心愿_${Date.now()}`

      // ── Step 1: Child creates wish ────────────────────────────────────────
      const createWishResp = await pageChild.request.post('/api/v1/child/wishes', {
        data: { name: wishName, priority: 'high', description: 'E2E 测试心愿' },
      })
      expect(createWishResp.ok(), `POST /child/wishes failed: ${createWishResp.status()}`).toBeTruthy()
      const createWishData = await createWishResp.json()
      const wishId: string = (createWishData.data ?? createWishData).id

      // ── Step 2: Parent approves wish with cost ────────────────────────────
      const approveWishResp = await pageParent.request.post(`/api/v1/family/child-wishes/${wishId}/approve`, {
        data: { star_coin_cost: WISH_COST },
      })
      expect(approveWishResp.ok(), `POST /family/child-wishes/${wishId}/approve failed: ${approveWishResp.status()}`).toBeTruthy()

      // ── Step 3: Child requests redemption ─────────────────────────────────
      const redeemResp = await pageChild.request.post(`/api/v1/child/wishes/${wishId}/request-redemption`)
      expect(redeemResp.ok(), `POST /child/wishes/${wishId}/request-redemption failed: ${redeemResp.status()}`).toBeTruthy()

      // ── Step 4: Record balance before realization ─────────────────────────
      const balanceBefore = await getChildBalance(pageChild)

      // ── Step 5: Parent sees redemption request in UI ──────────────────────
      // Wait for the WishReview API response so the assertion below isn't
      // racing with the initial page load.
      const queueResp = pageParent.waitForResponse(
        (resp) => resp.url().includes('/api/v1/family/child-wishes') && resp.status() === 200,
        { timeout: 10_000 },
      )
      await pageParent.goto('/wish-review')
      await queueResp
      await expect(pageParent.locator(`text=${wishName}`).first()).toBeVisible({ timeout: 10_000 })

      // ── Step 6: Parent realizes wish via UI ───────────────────────────────
      // Clicking "兑现" opens a confirmation dialog
      const realizeBtn = pageParent.locator('.btn-realize').first()
      await expect(realizeBtn, '兑现 button should be visible').toBeVisible({ timeout: 5_000 })
      await realizeBtn.click()

      // Dialog appears - click confirm button
      const confirmBtn = pageParent.locator('.btn-realize-confirm')
      await expect(confirmBtn, '确认兑现 button in dialog should be visible').toBeVisible({ timeout: 3_000 })
      await confirmBtn.click()

      // Dialog should close after confirmation
      await expect(pageParent.locator('.dialog-overlay')).not.toBeVisible({ timeout: 5_000 })

      // ── Step 7: Verify coins deducted ─────────────────────────────────────
      await pageChild.waitForTimeout(1000)
      const balanceAfter = await getChildBalance(pageChild)
      expect(
        balanceAfter,
        `Balance should decrease by ${WISH_COST} after realization (before: ${balanceBefore}, after: ${balanceAfter})`
      ).toBeLessThanOrEqual(balanceBefore - WISH_COST)
    } finally {
      await ctxChild.close()
      await ctxParent.close()
    }
  })
})

async function getChildBalance(page: Page): Promise<number> {
  const resp = await page.request.get('/api/v1/child/coins/balance')
  if (!resp.ok()) return 0
  const data = await resp.json()
  return (data.data?.balance ?? data.balance ?? 0) as number
}
