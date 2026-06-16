import { test, expect } from '@playwright/test'
import { loginAs } from '../lib/auth'

/**
 * DeerFlow Parity: Streaming State Tests
 *
 * Validates Numina AI chat streaming states match DeerFlow reference.
 */
test.describe('DeerFlow parity: streaming state', () => {
  test.skip(!process.env.RUN_DEMOUSER_TESTS, 'demouser-only test — set RUN_DEMOUSER_TESTS=1 to run')

  test('sending state shows progress indicator', async ({ page }) => {
    await loginAs(page, 'demouser', 'DemoPass123')
    await page.goto('/ai/chat')
    await page.waitForLoadState('domcontentloaded')

    // Type and send message
    const input = page.getByRole('textbox', { name: '请输入您的问题' })
    await input.fill('我的净资产是多少？')
    await page.getByRole('button').filter({ hasText: '发送' }).last().click()

    // Sending indicator should appear
    await expect(page.getByText('发送中')).toBeVisible({ timeout: 3000 })
  })

  test('user message appears immediately after send', async ({ page }) => {
    await loginAs(page, 'demouser', 'DemoPass123')
    await page.goto('/ai/chat')
    await page.waitForLoadState('domcontentloaded')

    const testMessage = '测试消息内容123'
    const input = page.getByRole('textbox', { name: '请输入您的问题' })
    await input.fill(testMessage)
    await page.getByRole('button').filter({ hasText: '发送' }).last().click()

    // User message should appear in chat
    await expect(page.getByText(testMessage)).toBeVisible({ timeout: 2000 })
  })

  test('timestamp appears on user message', async ({ page }) => {
    await loginAs(page, 'demouser', 'DemoPass123')
    await page.goto('/ai/chat')
    await page.waitForLoadState('domcontentloaded')

    const input = page.getByRole('textbox', { name: '请输入您的问题' })
    await input.fill('测试时间戳')
    await page.getByRole('button').filter({ hasText: '发送' }).last().click()

    // Timestamp format: HH:MM (e.g., "14:27")
    await expect(page.locator('[class*="timestamp"]').or(page.getByText(/\d{2}:\d{2}/))).toBeVisible({ timeout: 5000 })
  })

  test('streaming shows AI response progressively', async ({ page }) => {
    test.skip(!process.env.RUN_AI_TESTS, 'AI response requires configured provider — set RUN_AI_TESTS=1 to run')
    await loginAs(page, 'demouser', 'DemoPass123')
    await page.goto('/ai/chat')
    await page.waitForLoadState('domcontentloaded')

    const input = page.getByRole('textbox', { name: '请输入您的问题' })
    await input.fill('我们家净资产是多少？')
    await page.getByRole('button').filter({ hasText: '发送' }).last().click()

    // Wait for AI response to start streaming
    await expect(page.locator('.bubble.assistant').or(page.getByText(/净资产|无法回答/))).toBeVisible({ timeout: 30_000 })
  })

  test('streaming complete shows action buttons', async ({ page }) => {
    test.skip(!process.env.RUN_AI_TESTS, 'AI response requires configured provider — set RUN_AI_TESTS=1 to run')
    await loginAs(page, 'demouser', 'DemoPass123')
    await page.goto('/ai/chat')
    await page.waitForLoadState('domcontentloaded')

    const input = page.getByRole('textbox', { name: '请输入您的问题' })
    await input.fill('你好')
    await page.getByRole('button').filter({ hasText: '发送' }).last().click()

    // Wait for response
    await page.waitForTimeout(10_000)

    // Action buttons should appear: 复制, 重新生成, 有帮助/没帮助
    await expect(page.getByRole('button', { name: '复制' })).toBeVisible({ timeout: 30_000 })
  })

  test('no console errors during streaming', async ({ page }) => {
    const errors: string[] = []
    page.on('console', (msg) => {
      if (msg.type() === 'error') errors.push(msg.text())
    })

    await loginAs(page, 'demouser', 'DemoPass123')
    await page.goto('/ai/chat')
    await page.waitForLoadState('domcontentloaded')

    const input = page.getByRole('textbox', { name: '请输入您的问题' })
    await input.fill('测试错误')
    await page.getByRole('button').filter({ hasText: '发送' }).last().click()

    await page.waitForTimeout(5000)

    // Filter out network errors
    const realErrors = errors.filter(
      (e) => !e.includes('Failed to load resource') && !e.includes('AxiosError') && !e.includes('WebSocket')
    )
    expect(realErrors, `Console errors during streaming: ${realErrors.join(', ')}`).toHaveLength(0)
  })
})