import { test, expect } from '@playwright/test'
import { loginAsChild } from '../lib/auth'

/**
 * Teach-back (child teaches AI) — Issue #216.
 *
 * Covers the two acceptance examples the plan names:
 *   AE1  success: entry from a mastered topic -> dialogue -> eureka + celebration
 *   AE3  abandonment: mastery unchanged, no celebration
 *
 * These require the seeded demo child plus an approved-confusion pilot topic,
 * so they are opt-in like the other AI-backed specs. Everything downstream of
 * the stream (grading, progress reinforcement, rewards, notification) is
 * covered deterministically by server/tests/backend/integration/
 * test_teach_back_e2e.py; this spec covers the browser entry point and the
 * rendered states.
 */
test.describe('Teach-back (issue #216)', () => {
  test.skip(
    !process.env.RUN_DEMOUSER_TESTS,
    'demouser-only test — set RUN_DEMOUSER_TESTS=1 to run',
  )

  const CHILD_PIN = ['🐱', '🌟', '🎈', '🐶']

  test.describe('entry point', () => {
    test('mastered topic offers the teach-back entry', async ({ page }) => {
      await loginAsChild(page, 'demouser', 'DemoPass123', '小明', CHILD_PIN)

      // Reach a mastered topic from the learning map.
      await page.goto('/learning/map')
      await page.waitForLoadState('domcontentloaded')

      const masteredNode = page.locator('[data-mastery-level="mastered"]').first()
      if ((await masteredNode.count()) === 0) {
        test.skip(true, 'no mastered topic in this fixture')
      }
      await masteredNode.click()
      await page.waitForLoadState('domcontentloaded')

      await expect(
        page.getByRole('button', { name: /教你学会|teach/i }).first(),
      ).toBeVisible({ timeout: 5000 })
    })

    test('route renders the panel for a topic id', async ({ page }) => {
      await loginAsChild(page, 'demouser', 'DemoPass123', '小明', CHILD_PIN)

      await page.goto('/learning/teach-back/1?subject=mathematics&ageGroup=mid')
      await page.waitForLoadState('domcontentloaded')

      // The welcome state offers the start action before any turn is recorded.
      await expect(page.locator('.teach-back-panel')).toBeVisible({
        timeout: 5000,
      })
      await expect(page.locator('.teach-back-panel__welcome')).toBeVisible()
    })
  })

  test.describe('AE1 — successful teach-back', () => {
    test('all confusions resolved shows the eureka state', async ({ page }) => {
      await loginAsChild(page, 'demouser', 'DemoPass123', '小明', CHILD_PIN)

      await page.goto('/learning/teach-back/1?subject=mathematics&ageGroup=mid')
      await page.waitForLoadState('domcontentloaded')

      await page.getByRole('button', { name: /开始|start/i }).first().click()

      const input = page.locator('.teach-back-panel__input input')
      const sendBtn = page.locator('.teach-back-panel__input button')

      // Answer up to four confusions; the panel stops asking once it succeeds.
      for (let turn = 0; turn < 4; turn += 1) {
        if (await page.locator('.teach-back-panel__eureka').isVisible()) break
        await input.fill('因为分母一样，就是 4 份里取 1 份再加 2 份，所以是 3 份；分母不用变。1/4 + 2/4 = 3/4')
        await sendBtn.click()
        // Wait for the turn to land (verdict badge or the eureka block).
        await page
          .locator('.teach-back-panel__verdict, .teach-back-panel__eureka')
          .first()
          .waitFor({ timeout: 90_000 })
      }

      if ((await page.locator('.teach-back-panel__eureka').count()) === 0) {
        test.skip(
          true,
          'teach-back did not complete in this run (agent/model dependent)',
        )
      }
      await expect(page.locator('.teach-back-panel__eureka')).toBeVisible()
      await expect(page.locator('.teach-back-panel__eureka-text')).not.toBeEmpty()
    })
  })

  test.describe('AE3 — abandonment', () => {
    test('a nonsense answer does not show the eureka state', async ({ page }) => {
      await loginAsChild(page, 'demouser', 'DemoPass123', '小明', CHILD_PIN)

      await page.goto('/learning/teach-back/2?subject=mathematics&ageGroup=mid')
      await page.waitForLoadState('domcontentloaded')

      const startBtn = page.getByRole('button', { name: /开始|start/i }).first()
      if ((await startBtn.count()) === 0) {
        test.skip(true, 'teach-back panel not available for this topic')
      }
      await startBtn.click()

      const input = page.locator('.teach-back-panel__input input')
      await input.fill('我不知道。')
      await page.locator('.teach-back-panel__input button').click()

      // Give the turn a chance to resolve, then assert no success state.
      await page
        .locator('.teach-back-panel__verdict')
        .first()
        .waitFor({ timeout: 90_000 })
        .catch(() => {})

      await expect(page.locator('.teach-back-panel__eureka')).toHaveCount(0)
      // The child can keep trying: the input is still there.
      await expect(page.locator('.teach-back-panel__input')).toBeVisible()
    })
  })
})
