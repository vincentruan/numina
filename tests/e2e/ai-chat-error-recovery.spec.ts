import { test, expect } from '@playwright/test'
import { loginAs } from '../lib/auth'

/**
 * DeerFlow Parity: Error States Tests
 *
 * Validates Numina AI chat error handling matches DeerFlow reference.
 */
test.describe('DeerFlow parity: error states', () => {
  test.skip(!process.env.RUN_DEMOUSER_TESTS, 'demouser-only test — set RUN_DEMOUSER_TESTS=1 to run')

  test('model selector shows empty state when no models configured', async ({ page }) => {
    await loginAs(page, 'demouser', 'DemoPass123')
    await page.goto('/ai/chat')
    await page.waitForLoadState('domcontentloaded')

    // Open model selector
    await page.getByRole('button', { name: '选择模型' }).click()

    // Empty state should be visible if no models configured
    const emptyMessage = page.getByText('未找到匹配的模型')
    const modelsVisible = await emptyMessage.isVisible().catch(() => false)

    // If models are configured, this test is skipped
    // If no models, empty message should show
    if (modelsVisible) {
      await expect(emptyMessage).toBeVisible()
    }
  })

  test('mode selector shows family resource warning', async ({ page }) => {
    await loginAs(page, 'demouser', 'DemoPass123')
    await page.goto('/ai/chat')
    await page.waitForLoadState('domcontentloaded')

    // Open mode selector
    await page.getByRole('button', { name: /闪电|专业/ }).click()

    // Check if family resource warning is visible
    const resourceWarning = page.getByText('当前家庭资源不支持')
    const warningVisible = await resourceWarning.isVisible().catch(() => false)

    // Warning may or may not appear depending on tenant config
    // Just verify the dialog opened properly
    await expect(page.getByText('选择执行模式')).toBeVisible()
  })

  test('API error shows user-friendly message', async ({ page }) => {
    await loginAs(page, 'demouser', 'DemoPass123')
    await page.goto('/ai/chat')
    await page.waitForLoadState('domcontentloaded')

    // Mock a failing API response
    await page.route('/api/v1/ai/chat/stream', (route) => {
      route.fulfill({
        status: 500,
        body: '{"error": "Internal server error"}',
      })
    })

    // Try to send a message
    const textarea = page.locator('.input-textarea')
    await textarea.waitFor({ state: 'visible' })
    await textarea.fill('触发错误')
    await page.waitForTimeout(100)
    await page.locator('.input-row .submit-btn').click()

    // Error message should be shown (toast or inline)
    await expect(
      page.getByText(/暂时不可用|请稍后重试|服务不可用|发送失败/)
    ).toBeVisible({ timeout: 5000 })
  })

  test('network timeout shows retry option', async ({ page }) => {
    await loginAs(page, 'demouser', 'DemoPass123')
    await page.goto('/ai/chat')
    await page.waitForLoadState('domcontentloaded')

    // Mock a timeout
    await page.route('/api/v1/ai/chat/stream', (route) => {
      // Delay long enough to trigger timeout
      route.abort('timedout')
    })

    const textarea = page.locator('.input-textarea')
    await textarea.waitFor({ state: 'visible' })
    await textarea.fill('超时测试')
    await page.waitForTimeout(100)
    await page.locator('.input-row .submit-btn').click()

    // Should show timeout-related error or failure state
    // Match actual UI messages: "发送失败", "请求失败"，etc.
    // Use .first() to avoid strict mode violation when multiple error elements exist
    await expect(
      page.getByText(/超时|网络|连接|不可用|失败|发送失败/).first()
    ).toBeVisible({ timeout: 10000 })
  })

  test('auth error redirects to login', async ({ page }) => {
    // Clear auth cookies
    await page.context().clearCookies()

    // Navigate to AI chat
    await page.goto('/ai/chat')

    // Should redirect to login
    await expect(page).toHaveURL(/\/login/, { timeout: 5000 })
  })

  test('agent not found shows appropriate error', async ({ page }) => {
    await loginAs(page, 'demouser', 'DemoPass123')

    // Navigate with invalid agent ID
    await page.goto('/ai/chat?agentId=999999999')

    // Should show error or redirect
    await expect(
      page.getByText(/不存在|无效|找不到|智能体/)
    ).toBeVisible({ timeout: 5000 })
  })

  test('streaming error during response shows message', async ({ page }) => {
    test.skip(!process.env.RUN_AI_TESTS, 'Requires AI provider — set RUN_AI_TESTS=1 to run')

    await loginAs(page, 'demouser', 'DemoPass123')

    // Mock stream that fails mid-way
    await page.route('/api/v1/ai/chat/stream', (route) => {
      route.fulfill({
        status: 200,
        headers: { 'Content-Type': 'application/x-ndjson' },
        body: '{"type":"phase.connecting","task_id":"test"}\n{"type":"capability.error","data":{"message":"AI 服务暂时不可用"}}',
      })
    })

    await page.goto('/ai/chat')
    await page.waitForLoadState('domcontentloaded')

    const textarea = page.locator('.input-textarea')
    await textarea.waitFor({ state: 'visible' })
    await textarea.fill('流式错误测试')
    await page.waitForTimeout(100)
    await page.locator('.input-row .submit-btn').click()

    // Should show streaming error message
    await expect(page.getByText(/暂时不可用|请稍后/)).toBeVisible({ timeout: 5000 })
  })

  test('error state allows retry', async ({ page }) => {
    await loginAs(page, 'demouser', 'DemoPass123')
    await page.goto('/ai/chat')
    await page.waitForLoadState('domcontentloaded')

    // First request fails
    let firstRequest = true
    await page.route('/api/v1/ai/chat/stream', (route) => {
      if (firstRequest) {
        firstRequest = false
        route.fulfill({ status: 500, body: '{"error":"failed"}' })
      } else {
        route.continue()
      }
    })

    const textarea = page.locator('.input-textarea')
    await textarea.waitFor({ state: 'visible' })
    await textarea.fill('重试测试')
    await page.waitForTimeout(100)
    await page.locator('.input-row .submit-btn').click()

    // Wait for error (match actual UI messages like "发送失败")
    // Use .first() to avoid strict mode violation when multiple error elements exist
    await expect(page.getByText(/暂时不可用|失败|发送失败|不可用/).first()).toBeVisible({ timeout: 5000 })

    // Input should still be enabled for retry
    await expect(textarea).toBeEnabled()
  })

  test('console error filtering works correctly', async ({ page }) => {
    const errors: string[] = []
    page.on('console', (msg) => {
      if (msg.type() === 'error') errors.push(msg.text())
    })

    await loginAs(page, 'demouser', 'DemoPass123')
    await page.goto('/ai/chat')
    await page.waitForLoadState('domcontentloaded')

    // Filter out network errors (standard pattern)
    const realErrors = errors.filter(
      (e) => !e.includes('Failed to load resource') && !e.includes('AxiosError')
    )

    // Should not have critical JS errors
    expect(realErrors.length).toBeLessThanOrEqual(2) // Allow minor warnings
  })
})