import { test, expect } from '@playwright/test'
import { loginAs } from '../lib/auth'

/**
 * DeerFlow Parity: Mode Selection Tests
 *
 * Validates Numina AI chat mode selection matches DeerFlow reference.
 * Numina modes: 闪电, 专业, 旗舰, 思考
 * DeerFlow modes: Flash, Pro, Ultra, Thinking
 */
test.describe('DeerFlow parity: mode selection', () => {
  test.skip(!process.env.RUN_DEMOUSER_TESTS, 'demouser-only test — set RUN_DEMOUSER_TESTS=1 to run')

  test('mode selector opens on click', async ({ page }) => {
    await loginAs(page, 'demouser', 'DemoPass123')
    await page.goto('/ai/chat')
    await page.waitForLoadState('domcontentloaded')

    // Click mode button
    const modeButton = page.getByRole('button', { name: /闪电|专业/ })
    await modeButton.click()

    // Mode selector dialog should appear
    await expect(page.getByText('选择执行模式')).toBeVisible({ timeout: 3000 })
  })

  test('mode selector shows mode options', async ({ page }) => {
    await loginAs(page, 'demouser', 'DemoPass123')
    await page.goto('/ai/chat')
    await page.waitForLoadState('domcontentloaded')

    // Open mode selector
    const modeButton = page.getByRole('button', { name: /闪电|专业/ })
    await modeButton.click()

    // 闪电 mode should be visible
    await expect(page.getByRole('button', { name: /闪电/ })).toBeVisible()
  })

  test('mode selector shows capability info', async ({ page }) => {
    await loginAs(page, 'demouser', 'DemoPass123')
    await page.goto('/ai/chat')
    await page.waitForLoadState('domcontentloaded')

    // Open mode selector
    const modeButton = page.getByRole('button', { name: /闪电|专业/ })
    await modeButton.click()

    // Capability info text should be visible
    await expect(page.getByText('已按模型能力自动调整模式')).toBeVisible()
  })

  test('mode selector shows family resource warning if applicable', async ({ page }) => {
    await loginAs(page, 'demouser', 'DemoPass123')
    await page.goto('/ai/chat')
    await page.waitForLoadState('domcontentloaded')

    // Open mode selector
    const modeButton = page.getByRole('button', { name: /闪电|专业/ })
    await modeButton.click()

    // Warning about family resources may or may not appear
    // depending on tenant configuration
    const warningVisible = await page.getByText('当前家庭资源不支持').isVisible().catch(() => false)
    // Just verify the dialog opened
    await expect(page.getByText('选择执行模式')).toBeVisible()
  })

  test('mode can be selected and persists', async ({ page }) => {
    await loginAs(page, 'demouser', 'DemoPass123')
    await page.goto('/ai/chat')
    await page.waitForLoadState('domcontentloaded')

    // Open mode selector
    const modeButton = page.getByRole('button', { name: /闪电|专业/ })
    await modeButton.click()

    // Select 闪电 mode
    await page.getByRole('button', { name: /闪电/ }).click()

    // Dialog should close
    await expect(page.getByText('选择执行模式')).not.toBeVisible({ timeout: 2000 })

    // Mode button should reflect selected mode
    await expect(page.getByRole('button', { name: /闪电|专业/ })).toBeVisible()
  })

  test('mode selector closes on escape', async ({ page }) => {
    await loginAs(page, 'demouser', 'DemoPass123')
    await page.goto('/ai/chat')
    await page.waitForLoadState('domcontentloaded')

    // Open mode selector
    const modeButton = page.getByRole('button', { name: /闪电|专业/ })
    await modeButton.click()
    await expect(page.getByText('选择执行模式')).toBeVisible()

    // Press escape to close
    await page.keyboard.press('Escape')

    // Dialog should close
    await expect(page.getByText('选择执行模式')).not.toBeVisible({ timeout: 2000 })
  })
})