import { test, expect } from '@playwright/test'
import { loginAs } from '../lib/auth'

/**
 * Visual Regression Tests for DeerFlow Parity
 *
 * Compares Numina AI chat screenshots against DeerFlow baseline.
 * Baseline screenshots: docs/screenshots/deerflow-baseline/
 */
test.describe('DeerFlow visual regression', () => {
  test.skip(!process.env.RUN_VISUAL_TESTS, 'Visual tests require RUN_VISUAL_TESTS=1')

  const viewports = [
    { name: 'mobile-375x812', width: 375, height: 812 },
    { name: 'mobile-390x844', width: 390, height: 844 },
    { name: 'desktop-1440x900', width: 1440, height: 900 },
  ]

  for (const viewport of viewports) {
    test.describe(`viewport ${viewport.name}`, () => {
      test.use({ viewport: { width: viewport.width, height: viewport.height } })

      test(`welcome state matches baseline (${viewport.name})`, async ({ page }) => {
        await loginAs(page, 'demouser', 'DemoPass123')
        await page.goto('/ai/chat')
        await page.waitForLoadState('networkidle')

        // Take screenshot
        await expect(page).toHaveScreenshot(
          `deerflow-local-welcome-${viewport.name}.png`,
          {
            maxDiffPixels: 1000, // Allow minor rendering differences
            threshold: 0.2,
          }
        )
      })

      test(`input focus state (${viewport.name})`, async ({ page }) => {
        await loginAs(page, 'demouser', 'DemoPass123')
        await page.goto('/ai/chat')
        await page.waitForLoadState('domcontentloaded')

        const input = page.getByRole('textbox', { name: '请输入您的问题' })
        await input.click()
        await page.waitForTimeout(500)

        await expect(page).toHaveScreenshot(
          `deerflow-local-input-focus-${viewport.name}.png`,
          { maxDiffPixels: 500, threshold: 0.2 }
        )
      })

      test(`input with text (${viewport.name})`, async ({ page }) => {
        await loginAs(page, 'demouser', 'DemoPass123')
        await page.goto('/ai/chat')
        await page.waitForLoadState('domcontentloaded')

        const input = page.getByRole('textbox', { name: '请输入您的问题' })
        await input.fill('我的净资产是多少？')
        await page.waitForTimeout(500)

        await expect(page).toHaveScreenshot(
          `deerflow-local-input-text-${viewport.name}.png`,
          { maxDiffPixels: 500, threshold: 0.2 }
        )
      })
    })
  }

  test('mode selector dialog', async ({ page }) => {
    test.use({ viewport: { width: 390, height: 844 } })

    await loginAs(page, 'demouser', 'DemoPass123')
    await page.goto('/ai/chat')
    await page.waitForLoadState('domcontentloaded')

    await page.getByRole('button', { name: /闪电|专业/ }).click()
    await page.waitForTimeout(500)

    await expect(page).toHaveScreenshot(
      'deerflow-local-mode-selector.png',
      { maxDiffPixels: 500, threshold: 0.2 }
    )
  })

  test('model selector dialog', async ({ page }) => {
    test.use({ viewport: { width: 390, height: 844 } })

    await loginAs(page, 'demouser', 'DemoPass123')
    await page.goto('/ai/chat')
    await page.waitForLoadState('domcontentloaded')

    await page.getByRole('button', { name: '选择模型' }).click()
    await page.waitForTimeout(500)

    await expect(page).toHaveScreenshot(
      'deerflow-local-model-selector.png',
      { maxDiffPixels: 500, threshold: 0.2 }
    )
  })

  test('sending state', async ({ page }) => {
    test.use({ viewport: { width: 390, height: 844 } })

    await loginAs(page, 'demouser', 'DemoPass123')
    await page.goto('/ai/chat')
    await page.waitForLoadState('domcontentloaded')

    const input = page.getByRole('textbox', { name: '请输入您的问题' })
    await input.fill('测试发送')
    await page.getByRole('button').filter({ hasText: '发送' }).last().click()
    await page.waitForTimeout(300)

    // Capture "发送中" state quickly
    await expect(page).toHaveScreenshot(
      'deerflow-local-sending.png',
      { maxDiffPixels: 1000, threshold: 0.3 }
    )
  })
})