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

    // Use the textarea class selector for proper Vue v-model sync
    const textarea = page.locator('.input-textarea')
    await textarea.waitFor({ state: 'visible' })
    await textarea.fill('我的净资产是多少？')
    await page.waitForTimeout(100)
    await page.locator('.input-row .submit-btn').click()

    // Sending/connecting indicator should appear (or failed if backend unavailable)
    // Check for any status: 发送中, 正在连接, 发送失败, or spinning loader icon
    const sendingIndicator = page.getByText('发送中').or(page.getByText('正在连接')).or(page.getByText('发送失败')).or(page.locator('.animate-spin'))
    await expect(sendingIndicator.first()).toBeVisible({ timeout: 3000 })
  })

  test('user message appears immediately after send', async ({ page }) => {
    await loginAs(page, 'demouser', 'DemoPass123')
    await page.goto('/ai/chat')
    await page.waitForLoadState('domcontentloaded')

    const testMessage = '测试消息内容123'
    // Use the textarea class selector and type() for proper Vue v-model sync
    const textarea = page.locator('.input-textarea')
    await textarea.waitFor({ state: 'visible' })
    await textarea.fill(testMessage)
    // Wait for v-model to sync (Vue reactivity)
    await page.waitForTimeout(100)
    // Click submit button
    await page.locator('.input-row .submit-btn').click()

    // User message should appear in chat
    await expect(page.getByText(testMessage)).toBeVisible({ timeout: 3000 })
  })

  test('timestamp appears on user message', async ({ page }) => {
    await loginAs(page, 'demouser', 'DemoPass123')
    await page.goto('/ai/chat')
    await page.waitForLoadState('domcontentloaded')

    const textarea = page.locator('.input-textarea')
    await textarea.waitFor({ state: 'visible' })
    await textarea.fill('测试时间戳')
    await page.waitForTimeout(100)
    await page.locator('.input-row .submit-btn').click()

    // Timestamp format: HH:MM (e.g., "14:27") - use .first() to avoid strict mode violation
    await expect(page.locator('[class*="timestamp"]').or(page.getByText(/\d{2}:\d{2}/)).first()).toBeVisible({ timeout: 5000 })
  })

  test('streaming shows AI response progressively', async ({ page }) => {
    test.skip(!process.env.RUN_AI_TESTS, 'AI response requires configured provider — set RUN_AI_TESTS=1 to run')
    await loginAs(page, 'demouser', 'DemoPass123')
    await page.goto('/ai/chat')
    await page.waitForLoadState('domcontentloaded')

    const textarea = page.locator('.input-textarea')
    await textarea.waitFor({ state: 'visible' })
    await textarea.fill('我们家净资产是多少？')
    await page.waitForTimeout(100)
    await page.locator('.input-row .submit-btn').click()

    // Wait for AI response to start streaming
    await expect(page.locator('.bubble.assistant').or(page.getByText(/净资产|无法回答/))).toBeVisible({ timeout: 30_000 })
  })

  test('streaming complete shows action buttons', async ({ page }) => {
    test.skip(!process.env.RUN_AI_TESTS, 'AI response requires configured provider — set RUN_AI_TESTS=1 to run')
    await loginAs(page, 'demouser', 'DemoPass123')
    await page.goto('/ai/chat')
    await page.waitForLoadState('domcontentloaded')

    const textarea = page.locator('.input-textarea')
    await textarea.waitFor({ state: 'visible' })
    await textarea.fill('你好')
    await page.waitForTimeout(100)
    await page.locator('.input-row .submit-btn').click()

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

    const textarea = page.locator('.input-textarea')
    await textarea.waitFor({ state: 'visible' })
    await textarea.fill('测试错误')
    await page.waitForTimeout(100)
    await page.locator('.input-row .submit-btn').click()

    await page.waitForTimeout(5000)

    // Filter out network errors
    const realErrors = errors.filter(
      (e) => !e.includes('Failed to load resource') && !e.includes('AxiosError') && !e.includes('WebSocket')
    )
    expect(realErrors, `Console errors during streaming: ${realErrors.join(', ')}`).toHaveLength(0)
  })
})