import { test, expect } from '@playwright/test'
import { loginAs } from '../lib/auth'

/**
 * DeerFlow Parity: Header and Navigation Tests
 *
 * Validates Numina AI chat header matches DeerFlow reference.
 */
test.describe('DeerFlow parity: header and navigation', () => {
  test.skip(!process.env.RUN_DEMOUSER_TESTS, 'demouser-only test — set RUN_DEMOUSER_TESTS=1 to run')

  test('header shows back button', async ({ page }) => {
    await loginAs(page, 'demouser', 'DemoPass123')
    await page.goto('/ai/chat')
    await page.waitForLoadState('domcontentloaded')

    await expect(page.getByRole('button', { name: '返回' })).toBeVisible()
  })

  test('header shows history button', async ({ page }) => {
    await loginAs(page, 'demouser', 'DemoPass123')
    await page.goto('/ai/chat')
    await page.waitForLoadState('domcontentloaded')

    await expect(page.getByRole('button', { name: '会话历史' })).toBeVisible()
  })

  test('header shows agent info button', async ({ page }) => {
    await loginAs(page, 'demouser', 'DemoPass123')
    await page.goto('/ai/chat')
    await page.waitForLoadState('domcontentloaded')

    await expect(page.getByRole('button', { name: '查看智能体信息' })).toBeVisible()
  })

  test('header shows new chat button', async ({ page }) => {
    await loginAs(page, 'demouser', 'DemoPass123')
    await page.goto('/ai/chat')
    await page.waitForLoadState('domcontentloaded')

    await expect(page.getByRole('button', { name: '新对话' })).toBeVisible()
  })

  test('header shows edit title button', async ({ page }) => {
    await loginAs(page, 'demouser', 'DemoPass123')
    await page.goto('/ai/chat')
    await page.waitForLoadState('domcontentloaded')

    // Edit title button should be visible
    await expect(page.getByRole('button', { name: '修改标题' })).toBeVisible()
  })

  test('session title displays correctly', async ({ page }) => {
    await loginAs(page, 'demouser', 'DemoPass123')
    await page.goto('/ai/chat')
    await page.waitForLoadState('domcontentloaded')

    // Session title heading should be visible
    // For new chat: "新对话"
    // For existing: derived from first message
    const titleHeading = page.getByRole('heading', { level: 1 })
    await expect(titleHeading).toBeVisible()

    const titleText = await titleHeading.textContent()
    expect(titleText).toBeTruthy()
    expect(titleText!.length).toBeGreaterThan(0)
  })

  test('back button navigates to AI hub', async ({ page }) => {
    await loginAs(page, 'demouser', 'DemoPass123')
    await page.goto('/ai/chat')
    await page.waitForLoadState('domcontentloaded')

    await page.getByRole('button', { name: '返回' }).click()

    // Should navigate back to /ai hub
    await expect(page).toHaveURL(/\/ai$/, { timeout: 5000 })
  })

  test('new chat confirmation dialog', async ({ page }) => {
    await loginAs(page, 'demouser', 'DemoPass123')
    // Navigate to existing session first
    await page.goto('/ai/chat')
    await page.waitForLoadState('domcontentloaded')

    // Send a message to create a session
    const input = page.getByRole('textbox', { name: '请输入您的问题' })
    await input.fill('创建会话')
    await page.getByRole('button').filter({ hasText: '发送' }).last().click()
    await page.waitForTimeout(2000)

    // Now click new chat
    await page.getByRole('button', { name: '新对话' }).click()

    // Confirmation dialog should appear
    await expect(page.getByText('开始新对话？')).toBeVisible({ timeout: 3000 })
    await expect(page.getByRole('button', { name: '取消' })).toBeVisible()
    await expect(page.getByRole('button', { name: '确认' })).toBeVisible()
  })

  test('new chat confirmation can be cancelled', async ({ page }) => {
    await loginAs(page, 'demouser', 'DemoPass123')
    await page.goto('/ai/chat')
    await page.waitForLoadState('domcontentloaded')

    // Send a message to create a session
    const input = page.getByRole('textbox', { name: '请输入您的问题' })
    await input.fill('测试取消')
    await page.getByRole('button').filter({ hasText: '发送' }).last().click()
    await page.waitForTimeout(2000)

    // Click new chat
    await page.getByRole('button', { name: '新对话' }).click()

    // Cancel the dialog
    await page.getByRole('button', { name: '取消' }).click()

    // Dialog should close
    await expect(page.getByText('开始新对话？')).not.toBeVisible({ timeout: 2000 })
  })
})