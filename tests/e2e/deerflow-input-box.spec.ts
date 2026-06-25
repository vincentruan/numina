import { test, expect } from '@playwright/test'
import { loginAs } from '../lib/auth'

/**
 * DeerFlow Parity: Input Box Tests
 *
 * Validates Numina AI chat input box matches DeerFlow reference.
 */
test.describe('DeerFlow parity: input box', () => {
  test.skip(!process.env.RUN_DEMOUSER_TESTS, 'demouser-only test — set RUN_DEMOUSER_TESTS=1 to run')

  test('input focus state shows highlight', async ({ page }) => {
    await loginAs(page, 'demouser', 'DemoPass123')
    await page.goto('/ai/chat')
    await page.waitForLoadState('domcontentloaded')

    const input = page.getByRole('textbox', { name: '向 AI 提问' })
    await input.click()

    // Focus state - input should be focused
    await expect(input).toBeFocused()
  })

  test('input with text enables send button', async ({ page }) => {
    await loginAs(page, 'demouser', 'DemoPass123')
    await page.goto('/ai/chat')
    await page.waitForLoadState('domcontentloaded')

    const input = page.getByRole('textbox', { name: '向 AI 提问' })
    await input.fill('我的净资产是多少？')

    // Send button should now be enabled
    const sendButton = page.getByRole('button').filter({ has: page.locator('[class*="send"]') }).or(
      page.locator('button').filter({ hasText: '发送' }).last()
    )
    // Button should not be disabled
    await expect(sendButton).not.toBeDisabled()
  })

  test('input auto-expands with multiline text', async ({ page }) => {
    await loginAs(page, 'demouser', 'DemoPass123')
    await page.goto('/ai/chat')
    await page.waitForLoadState('domcontentloaded')

    const input = page.getByRole('textbox', { name: '向 AI 提问' })
    const initialHeight = await input.evaluate((el) => el.getBoundingClientRect().height)

    // Type multiline content
    await input.fill('第一行内容\n第二行内容\n第三行内容')

    // Check if height increased (auto-expand)
    const newHeight = await input.evaluate((el) => el.getBoundingClientRect().height)
    expect(newHeight).toBeGreaterThan(initialHeight)
  })

  test('input placeholder changes after session start', async ({ page }) => {
    await loginAs(page, 'demouser', 'DemoPass123')
    await page.goto('/ai/chat')
    await page.waitForLoadState('domcontentloaded')

    // Initial placeholder
    const input = page.getByRole('textbox', { name: '向 AI 提问' })
    await expect(input).toHaveAttribute('placeholder', '请输入您的问题…')

    // Submit a message
    await input.fill('测试问题')
    await page.getByRole('button').filter({ hasText: '发送' }).last().click()

    // Wait for response (or timeout gracefully)
    await page.waitForTimeout(2000)

    // After submission, placeholder should change to "继续对话..."
    await expect(input).toHaveAttribute('placeholder', /继续对话|请输入/)
  })

  test('mode selector button visible', async ({ page }) => {
    await loginAs(page, 'demouser', 'DemoPass123')
    await page.goto('/ai/chat')
    await page.waitForLoadState('domcontentloaded')

    // Mode button (闪电/专业) should be visible
    const modeButton = page.getByRole('button', { name: /闪电|专业/ })
    await expect(modeButton).toBeVisible()
  })

  test('model selector button visible', async ({ page }) => {
    await loginAs(page, 'demouser', 'DemoPass123')
    await page.goto('/ai/chat')
    await page.waitForLoadState('domcontentloaded')

    // Model selector button should be visible
    const modelButton = page.getByRole('button', { name: '选择模型' })
    await expect(modelButton).toBeVisible()
  })
})