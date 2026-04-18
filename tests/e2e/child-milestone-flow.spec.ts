import { test, expect } from '@playwright/test'
import { childFamily, richFamily } from '../lib/fixtures'

/**
 * 里程碑触发流程 E2E 测试
 *
 * 验证完成第一个家务后触发 first_chore 里程碑，庆典弹窗显示。
 *
 * 注意：first_chore 是一次性里程碑。如果 test_child 已经获得过，
 * 本测试跳过审批步骤，直接清除 seen_milestones 并验证弹窗仍然显示。
 *
 * 前置条件：seed-accounts.sh 已创建 test_child 和「测试家务」模板。
 */
test.describe('child milestone flow', () => {
  test('first chore approval triggers first_chore milestone celebration', async ({ browser }) => {
    const ctxChild = await browser.newContext()
    const ctxParent = await browser.newContext()
    const pageChild = await ctxChild.newPage()
    const pageParent = await ctxParent.newPage()

    try {
      // ── Setup ─────────────────────────────────────────────────────────────
      await childFamily(pageChild)
      await richFamily(pageParent)

      // ── Check if first_chore milestone already exists ─────────────────────
      const milestonesResp = await pageChild.request.get('/api/v1/child/milestones')
      expect(milestonesResp.ok()).toBeTruthy()
      const milestonesData = await milestonesResp.json()
      const milestones: Array<{ milestone_type: string }> = milestonesData.data ?? milestonesData
      const alreadyEarned = milestones.some((m) => m.milestone_type === 'first_chore')

      if (!alreadyEarned) {
        // ── Trigger first_chore: complete + approve a chore ──────────────────
        const today = new Date().toISOString().split('T')[0]
        const choreResp = await pageChild.request.get(`/api/v1/child/chores?date=${today}`)
        expect(choreResp.ok()).toBeTruthy()
        const choreData = await choreResp.json()
        const instances: Array<{ id: string; chore_name: string; status: string }> =
          choreData.data ?? choreData
        const instance = instances.find((i) => i.chore_name === '测试家务')
        expect(instance, '「测试家务」instance not found — check seed-accounts.sh').toBeTruthy()

        // Mark complete if not already pending
        if (instance!.status === 'available') {
          const completeResp = await pageChild.request.post(`/api/v1/child/chores/${instance!.id}/complete`)
          expect(completeResp.ok()).toBeTruthy()
        }

        // Parent approves
        const approvalsResp = await pageParent.request.get('/api/v1/family/chore-approvals')
        expect(approvalsResp.ok()).toBeTruthy()
        const approvalsData = await approvalsResp.json()
        const approvals: Array<{ id: string }> = approvalsData.data ?? approvalsData
        const approval = approvals.find((a) => (a as { chore_name?: string }).chore_name === '测试家务' ||
          (a as { id: string }).id === instance!.id)

        if (approval) {
          const approveResp = await pageParent.request.post(
            `/api/v1/family/chore-approvals/${approval.id}/approve`
          )
          expect(approveResp.ok(), `Approve failed: ${approveResp.status()}`).toBeTruthy()
        }

        // Wait for async milestone processing
        await pageChild.waitForTimeout(1500)

        // Verify milestone was created
        const milestonesAfterResp = await pageChild.request.get('/api/v1/child/milestones')
        const milestonesAfterData = await milestonesAfterResp.json()
        const milestonesAfter: Array<{ milestone_type: string }> = milestonesAfterData.data ?? milestonesAfterData
        expect(
          milestonesAfter.some((m) => m.milestone_type === 'first_chore'),
          'first_chore milestone should exist after first chore approval'
        ).toBeTruthy()
      } else {
        test.info().annotations.push({
          type: 'note',
          description: 'first_chore already earned — skipping approval step, testing UI display only',
        })
      }

      // ── UI assertion: clear seen_milestones and navigate to /child/tasks ──
      // Navigate to root first so localStorage is accessible
      await pageChild.goto('/')
      await pageChild.evaluate(() => {
        localStorage.removeItem('seen_milestones')
      })

      // Navigate to child tasks page — milestone celebration should appear
      await pageChild.goto('/child/tasks')

      // The MilestoneCelebration component checks milestones on mount
      // and shows a modal for any unseen milestones
      const celebrationModal = pageChild.locator(
        '.milestone-modal, [class*="milestone"][class*="modal"], [class*="celebration"]'
      ).first()

      // Also try text-based selectors as fallback
      const celebrationText = pageChild.locator('text=恭喜, text=里程碑, text=first_chore').first()

      const modalVisible = await celebrationModal.isVisible({ timeout: 8_000 }).catch(() => false)
      const textVisible = await celebrationText.isVisible({ timeout: 3_000 }).catch(() => false)

      expect(
        modalVisible || textVisible,
        'Milestone celebration modal should be visible after clearing seen_milestones'
      ).toBeTruthy()
    } finally {
      await ctxChild.close()
      await ctxParent.close()
    }
  })
})
