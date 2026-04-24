import { test, expect } from '@playwright/test'
import { richFamily, emptyFamily } from '../lib/fixtures'

/**
 * AI 功能 E2E 测试
 *
 * 验证 AI 功能模块的完整流程：
 *   1. AI Hub 页面渲染（健康评分、报告摘要）
 *   2. AI 报告生成与查看
 *   3. AI 聊天页面
 *   4. AI 子功能页面（预警、处置建议、负债顾问、资产配置）
 *   5. AI 配置页面
 *
 * 使用 test_rich 账号（有完整资产数据，AI 功能需要数据才能生成报告）。
 */
test.describe('AI hub and features', () => {
  test('AI hub page renders with health score', async ({ page }) => {
    const errors: string[] = []
    page.on('console', (msg) => {
      if (msg.type() === 'error') errors.push(msg.text())
    })

    await richFamily(page)
    await page.goto('/ai')

    // Hub header should render
    await expect(page.locator('.hub-header, [class*="hub"], text=家庭资产智能助手').first()).toBeVisible({
      timeout: 10_000,
    })

    // Health score ring or score number should be visible
    await expect(
      page.locator('.hub-score-ring, .score-number, [aria-label*="资产健康评分"]').first()
    ).toBeVisible({ timeout: 8_000 })

    // No critical JS errors (filter network errors)
    const realErrors = errors.filter(
      (e) => !e.includes('Failed to load resource') && !e.includes('AxiosError') && !e.includes('WebSocket')
    )
    expect(realErrors, `Console errors on /ai: ${realErrors.join(', ')}`).toHaveLength(0)
  })

  test('AI hub shows report summary or empty state', async ({ page }) => {
    await richFamily(page)
    await page.goto('/ai')

    // Either a report summary card or an empty state should be visible
    await expect(
      page.locator('.report-summary-card, .report-empty-card, text=最新资产体检报告, text=暂无报告').first()
    ).toBeVisible({ timeout: 10_000 })
  })

  test('AI report page renders', async ({ page }) => {
    const errors: string[] = []
    page.on('console', (msg) => {
      if (msg.type() === 'error') errors.push(msg.text())
    })

    await richFamily(page)
    await page.goto('/ai/report')

    await expect(page).not.toHaveURL(/\/login/)

    // Report page should render some content
    await expect(
      page.locator('text=资产体检报告, text=生成报告, text=暂无报告, [class*="report"]').first()
    ).toBeVisible({ timeout: 10_000 })

    const realErrors = errors.filter(
      (e) => !e.includes('Failed to load resource') && !e.includes('AxiosError') && !e.includes('WebSocket')
    )
    expect(realErrors, `Console errors on /ai/report: ${realErrors.join(', ')}`).toHaveLength(0)
  })

  test('AI report generation API works', async ({ page }) => {
    await richFamily(page)

    // Trigger report generation via API
    const generateResp = await page.request.post('/api/v1/ai/report/generate')
    // 200 = generated, 202 = already generating, 429 = rate limited — all acceptable
    expect(
      [200, 201, 202, 429].includes(generateResp.status()),
      `Unexpected status from report generation: ${generateResp.status()}`
    ).toBeTruthy()
  })

  test('AI alerts page renders', async ({ page }) => {
    const errors: string[] = []
    page.on('console', (msg) => {
      if (msg.type() === 'error') errors.push(msg.text())
    })

    await richFamily(page)
    await page.goto('/ai/alerts')

    await expect(page).not.toHaveURL(/\/login/)
    await expect(
      page.locator('text=预警, text=风险, text=暂无预警, [class*="alert"]').first()
    ).toBeVisible({ timeout: 10_000 })

    const realErrors = errors.filter(
      (e) => !e.includes('Failed to load resource') && !e.includes('AxiosError') && !e.includes('WebSocket')
    )
    expect(realErrors, `Console errors on /ai/alerts: ${realErrors.join(', ')}`).toHaveLength(0)
  })

  test('AI disposal advisor page renders', async ({ page }) => {
    const errors: string[] = []
    page.on('console', (msg) => {
      if (msg.type() === 'error') errors.push(msg.text())
    })

    await richFamily(page)
    await page.goto('/ai/disposal')

    await expect(page).not.toHaveURL(/\/login/)
    await expect(
      page.locator('text=处置, text=建议, text=闲置, [class*="disposal"]').first()
    ).toBeVisible({ timeout: 10_000 })

    const realErrors = errors.filter(
      (e) => !e.includes('Failed to load resource') && !e.includes('AxiosError') && !e.includes('WebSocket')
    )
    expect(realErrors, `Console errors on /ai/disposal: ${realErrors.join(', ')}`).toHaveLength(0)
  })

  test('AI liability advisor page renders', async ({ page }) => {
    const errors: string[] = []
    page.on('console', (msg) => {
      if (msg.type() === 'error') errors.push(msg.text())
    })

    await richFamily(page)
    await page.goto('/ai/liability')

    await expect(page).not.toHaveURL(/\/login/)
    await expect(
      page.locator('text=负债, text=还款, text=建议, [class*="liability"]').first()
    ).toBeVisible({ timeout: 10_000 })

    const realErrors = errors.filter(
      (e) => !e.includes('Failed to load resource') && !e.includes('AxiosError') && !e.includes('WebSocket')
    )
    expect(realErrors, `Console errors on /ai/liability: ${realErrors.join(', ')}`).toHaveLength(0)
  })

  test('AI allocation page renders', async ({ page }) => {
    const errors: string[] = []
    page.on('console', (msg) => {
      if (msg.type() === 'error') errors.push(msg.text())
    })

    await richFamily(page)
    await page.goto('/ai/allocation')

    await expect(page).not.toHaveURL(/\/login/)
    await expect(
      page.locator('text=配置, text=资产, text=建议, [class*="allocation"]').first()
    ).toBeVisible({ timeout: 10_000 })

    const realErrors = errors.filter(
      (e) => !e.includes('Failed to load resource') && !e.includes('AxiosError') && !e.includes('WebSocket')
    )
    expect(realErrors, `Console errors on /ai/allocation: ${realErrors.join(', ')}`).toHaveLength(0)
  })

  test('AI chat page renders and accepts input', async ({ page }) => {
    const errors: string[] = []
    page.on('console', (msg) => {
      if (msg.type() === 'error') errors.push(msg.text())
    })

    await richFamily(page)
    await page.goto('/ai/chat')

    await expect(page).not.toHaveURL(/\/login/)

    // Chat input should be visible
    await expect(
      page.locator('textarea, input[type="text"], .van-field__control, [class*="chat-input"]').first()
    ).toBeVisible({ timeout: 10_000 })

    const realErrors = errors.filter(
      (e) => !e.includes('Failed to load resource') && !e.includes('AxiosError') && !e.includes('WebSocket')
    )
    expect(realErrors, `Console errors on /ai/chat: ${realErrors.join(', ')}`).toHaveLength(0)
  })

  test('AI config page renders', async ({ page }) => {
    const errors: string[] = []
    page.on('console', (msg) => {
      if (msg.type() === 'error') errors.push(msg.text())
    })

    await richFamily(page)
    await page.goto('/settings/ai')

    await expect(page).not.toHaveURL(/\/login/)
    await expect(
      page.locator('text=AI, text=配置, text=模型, [class*="ai-config"]').first()
    ).toBeVisible({ timeout: 10_000 })

    const realErrors = errors.filter(
      (e) => !e.includes('Failed to load resource') && !e.includes('AxiosError') && !e.includes('WebSocket')
    )
    expect(realErrors, `Console errors on /settings/ai: ${realErrors.join(', ')}`).toHaveLength(0)
  })

  test('AI hub navigates to sub-pages', async ({ page }) => {
    await richFamily(page)
    await page.goto('/ai')

    // Click on a feature card to navigate to a sub-page
    // The hub has feature cards that navigate to /ai/report, /ai/alerts, etc.
    const featureCard = page.locator('[class*="feat"], [class*="feature"], [class*="card"]').first()
    await expect(featureCard).toBeVisible({ timeout: 8_000 })
    await featureCard.click()

    // Should navigate to an AI sub-page
    await expect(page).toHaveURL(/\/ai\//, { timeout: 5_000 })
  })

  test('empty family AI hub shows no-data state gracefully', async ({ page }) => {
    const errors: string[] = []
    page.on('console', (msg) => {
      if (msg.type() === 'error') errors.push(msg.text())
    })

    await emptyFamily(page)
    await page.goto('/ai')

    await expect(page).not.toHaveURL(/\/login/)

    // Should render without crashing even with no data
    await expect(
      page.locator('.hub-header, [class*="hub"], text=家庭资产智能助手').first()
    ).toBeVisible({ timeout: 10_000 })

    const realErrors = errors.filter(
      (e) => !e.includes('Failed to load resource') && !e.includes('AxiosError') && !e.includes('WebSocket')
    )
    expect(realErrors, `Console errors on /ai with empty family: ${realErrors.join(', ')}`).toHaveLength(0)
  })
})
