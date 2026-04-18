import { test, expect } from '@playwright/test'
import { childFamily, richFamily } from '../lib/fixtures'

/**
 * 家务审批流程 E2E 测试
 *
 * 验证完整的家务审批循环：
 *   1. 儿童标记家务完成（API）
 *   2. 父母在审批页看到待审批卡片（UI）
 *   3. 父母点击批准（UI）
 *   4. 儿童星星币余额增加（API）
 *
 * 使用两个独立 browser context 模拟儿童和父母同时在线。
 * 前置条件：seed-accounts.sh 已创建 test_child 和「测试家务」模板。
 */
test.describe('chore approval flow', () => {
  test('child completes chore → parent approves → coins credited', async ({ browser }) => {
    const ctxChild = await browser.newContext()
    const ctxParent = await browser.newContext()
    const pageChild = await ctxChild.newPage()
    const pageParent = await ctxParent.newPage()

    try {
      // ── Setup: log in both contexts ──────────────────────────────────────
      const { childId, parentToken } = await childFamily(pageChild)
      await richFamily(pageParent)

      // ── Step 1: Get today's chore instance for 测试家务 ──────────────────
      const today = new Date().toISOString().split('T')[0]
      const choreResp = await pageChild.request.get(`/api/v1/child/chores?date=${today}`)
      expect(choreResp.ok(), `GET /child/chores failed: ${choreResp.status()}`).toBeTruthy()
      const choreData = await choreResp.json()
      const instances: Array<{ id: string; chore_name: string; status: string; coin_reward: number }> =
        choreData.data ?? choreData
      const instance = instances.find((i) => i.chore_name === '测试家务')
      expect(instance, '「测试家务」instance not found for today — check seed-accounts.sh').toBeTruthy()
      const instanceId = instance!.id
      const coinReward = instance!.coin_reward

      // Skip if already pending/approved (idempotent re-runs)
      if (instance!.status === 'pending_approval' || instance!.status === 'approved') {
        test.info().annotations.push({ type: 'note', description: `Instance already ${instance!.status}, skipping complete step` })
      } else {
        // ── Step 2: Child marks chore complete ──────────────────────────────
        const completeResp = await pageChild.request.post(`/api/v1/child/chores/${instanceId}/complete`)
        expect(completeResp.ok(), `POST /child/chores/${instanceId}/complete failed: ${completeResp.status()}`).toBeTruthy()
      }

      // ── Step 3: Record balance before approval ───────────────────────────
      const balanceBefore = await getChildBalance(pageChild)

      // ── Step 4: Parent sees approval card in UI ──────────────────────────
      await pageParent.goto('/family/chore-approvals')
      await expect(pageParent.locator('text=测试家务').first()).toBeVisible({ timeout: 10_000 })
      await expect(pageParent.locator(`text=test_child`).first()).toBeVisible({ timeout: 5_000 })

      // ── Step 5: Parent approves via UI ───────────────────────────────────
      // Find the approve button in the card containing 测试家务
      const approveBtn = pageParent.locator('[class*="approve"], button:has-text("批准"), button:has-text("通过")').first()
      await expect(approveBtn).toBeVisible({ timeout: 5_000 })
      await approveBtn.click()

      // Card should disappear after approval
      await expect(pageParent.locator(`text=测试家务`)).not.toBeVisible({ timeout: 8_000 })

      // ── Step 6: Verify coins credited ────────────────────────────────────
      // Wait briefly for async approval processing
      await pageChild.waitForTimeout(1000)
      const balanceAfter = await getChildBalance(pageChild)
      expect(
        balanceAfter,
        `Balance should increase by at least ${coinReward} after approval (before: ${balanceBefore}, after: ${balanceAfter})`
      ).toBeGreaterThanOrEqual(balanceBefore + coinReward)
    } finally {
      await ctxChild.close()
      await ctxParent.close()
    }
  })
})

import type { Page } from '@playwright/test'

async function getChildBalance(page: Page): Promise<number> {
  const resp = await page.request.get('/api/v1/child/coins/balance')
  if (!resp.ok()) return 0
  const data = await resp.json()
  return (data.data?.balance ?? data.balance ?? 0) as number
}
