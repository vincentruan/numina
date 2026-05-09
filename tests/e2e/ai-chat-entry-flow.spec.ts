import { test, expect } from '@playwright/test'
import { loginAs } from '../lib/auth'

test.describe('AI chat entry flow', () => {
  test('demouser can hand off AI hub input state into chat streaming UI', async ({ page }) => {
    const consoleErrors: string[] = []
    page.on('console', (msg) => {
      if (msg.type() === 'error') consoleErrors.push(msg.text())
    })

    await loginAs(page, 'demouser', 'DemoPass123')
    await page.goto('/ai')
    await page.waitForLoadState('domcontentloaded')

    await page.getByRole('button', { name: '深度思考' }).click()
    await page.getByRole('button', { name: '联网搜索' }).click()
    await page.getByLabel('向 AI 提问').fill('请概括我们家的资产情况')

    const streamRequest = page.waitForRequest((request) =>
      request.url().includes('/api/v1/ai/chat/stream')
    )

    await page.getByRole('button', { name: '发送' }).click()
    await expect(page).toHaveURL(/\/ai\/chat/)

    await expect(page.getByRole('button', { name: '深度思考' })).toHaveAttribute('aria-pressed', 'true')
    await expect(page.getByRole('button', { name: '联网搜索' })).toHaveAttribute('aria-pressed', 'true')
    await expect(page.locator('.bubble-text', { hasText: '请概括我们家的资产情况' }).first()).toBeVisible()
    await expect(page.getByText(/正在连接模型|深度思考中|组织回答中/)).toBeVisible({ timeout: 10_000 })

    await streamRequest

    const realErrors = consoleErrors.filter(
      (e) => !e.includes('Failed to load resource') && !e.includes('AxiosError') && !e.includes('WebSocket')
    )
    expect(realErrors, `Console errors: ${realErrors.join(', ')}`).toHaveLength(0)
  })

  test('demouser sees phase feedback and final answer without leaked reasoning', async ({ page }) => {
    await loginAs(page, 'demouser', 'DemoPass123')
    await page.request.delete('/api/v1/ai/chat/history')
    await page.goto('/ai/chat')
    await page.waitForLoadState('domcontentloaded')

    await page.getByLabel('向 AI 提问').fill('我们家净资产是多少？')
    await page.getByRole('button', { name: '发送' }).click()

    await expect(page.getByText(/正在连接模型|组织回答中/)).toBeVisible({ timeout: 10_000 })
    await expect(page.locator('.bubble.assistant').last()).toContainText(/净资产.*28,649,021\.74/, {
      timeout: 30_000,
    })
    await expect(page.locator('.bubble.assistant').last()).not.toContainText(/分析请求|检查限制|最终润色/)
  })
})
