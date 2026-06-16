import { test, expect } from '@playwright/test'
import { loginAs } from '../lib/auth'

/**
 * DeerFlow Parity: Welcome State Tests
 *
 * Validates Numina AI chat welcome state matches DeerFlow reference.
 * Reference: docs/screenshots/deerflow-baseline/deerflow-new-chat-welcome.png
 */
test.describe('DeerFlow parity: welcome state', () => {
  test.skip(!process.env.RUN_DEMOUSER_TESTS, 'demouser-only test — set RUN_DEMOUSER_TESTS=1 to run')

  test('welcome state shows proper header and prompt', async ({ page }) => {
    await loginAs(page, 'demouser', 'DemoPass123')
    await page.goto('/ai/chat')
    await page.waitForLoadState('domcontentloaded')

    // Header should show "新对话" (matches DeerFlow "开始新对话")
    await expect(page.getByRole('heading', { name: '新对话' })).toBeVisible({ timeout: 5000 })

    // Welcome prompt heading
    await expect(page.getByRole('heading', { name: '有什么想问的？' })).toBeVisible()

    // Subtext guidance
    await expect(page.getByText('输入问题，智能助手帮你分析家庭资产')).toBeVisible()
  })

  test('welcome state has category buttons', async ({ page }) => {
    await loginAs(page, 'demouser', 'DemoPass123')
    await page.goto('/ai/chat')
    await page.waitForLoadState('domcontentloaded')

    // Category buttons: 分析, 规划, 学习, 优化
    await expect(page.getByRole('button', { name: '分析' })).toBeVisible()
    await expect(page.getByRole('button', { name: '规划' })).toBeVisible()
    await expect(page.getByRole('button', { name: '学习' })).toBeVisible()
    await expect(page.getByRole('button', { name: '优化' })).toBeVisible()
  })

  test('welcome state has random prompt button', async ({ page }) => {
    await loginAs(page, 'demouser', 'DemoPass123')
    await page.goto('/ai/chat')
    await page.waitForLoadState('domcontentloaded')

    // Random prompt button (Numina extra feature)
    await expect(page.getByRole('button', { name: '随机提问' })).toBeVisible()
  })

  test('welcome state input placeholder', async ({ page }) => {
    await loginAs(page, 'demouser', 'DemoPass123')
    await page.goto('/ai/chat')
    await page.waitForLoadState('domcontentloaded')

    // Input placeholder should be visible
    const input = page.getByRole('textbox', { name: '请输入您的问题' })
    await expect(input).toBeVisible()
    await expect(input).toHaveAttribute('placeholder', '请输入您的问题…')
  })

  test('welcome state send button disabled', async ({ page }) => {
    await loginAs(page, 'demouser', 'DemoPass123')
    await page.goto('/ai/chat')
    await page.waitForLoadState('domcontentloaded')

    // Send button should be disabled when no text
    const sendButton = page.getByRole('button', { name: '发送' }).or(
      page.locator('button[disabled]').filter({ hasText: '发送' })
    )
    await expect(sendButton).toBeDisabled()
  })
})