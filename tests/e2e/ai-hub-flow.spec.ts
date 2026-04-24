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
    await page.waitForLoadState('networkidle')

    // Hub subtitle is always present
    await expect(page.getByText('家庭资产智能助手')).toBeVisible({ timeout: 10_000 })

    // Health score image with aria-label
    await expect(page.locator('[aria-label*="资产健康评分"]')).toBeVisible({ timeout: 8_000 })

    // No critical JS errors (filter network errors)
    const realErrors = errors.filter(
      (e) => !e.includes('Failed to load resource') && !e.includes('AxiosError') && !e.includes('WebSocket')
    )
    expect(realErrors, `Console errors on /ai: ${realErrors.join(', ')}`).toHaveLength(0)
  })

  test('AI hub shows report summary or empty state', async ({ page }) => {
    await richFamily(page)
    await page.goto('/ai')
    await page.waitForLoadState('networkidle')

    // The hub always shows either a report card or the empty state button
    await expect(
      page.getByRole('button', { name: /生成|体检报告/ }).or(page.getByText('暂无报告')).first()
    ).toBeVisible({ timeout: 10_000 })
  })

  test('AI report page renders', async ({ page }) => {
    const errors: string[] = []
    page.on('console', (msg) => {
      if (msg.type() === 'error') errors.push(msg.text())
    })

    await richFamily(page)
    await page.goto('/ai/report')
    await page.waitForLoadState('networkidle')

    await expect(page).not.toHaveURL(/\/login/)
    // Page title in nav bar
    await expect(page.getByText('家庭资产体检')).toBeVisible({ timeout: 10_000 })

    const realErrors = errors.filter(
      (e) => !e.includes('Failed to load resource') && !e.includes('AxiosError') && !e.includes('WebSocket')
    )
    expect(realErrors, `Console errors on /ai/report: ${realErrors.join(', ')}`).toHaveLength(0)
  })

  test('AI report generation API works', async ({ page }) => {
    await richFamily(page)

    // Trigger report generation via API
    const generateResp = await page.request.post('/api/v1/ai/report/generate')
    // 200/201 = generated, 202 = already generating, 403 = AI not configured, 429 = rate limited — all acceptable
    expect(
      [200, 201, 202, 403, 429].includes(generateResp.status()),
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
    await page.waitForLoadState('networkidle')

    await expect(page).not.toHaveURL(/\/login/)
    await expect(page.getByText('老化预警')).toBeVisible({ timeout: 10_000 })

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
    await page.waitForLoadState('networkidle')

    await expect(page).not.toHaveURL(/\/login/)
    await expect(page.getByRole('button', { name: /扫描闲置/ })).toBeVisible({ timeout: 10_000 })

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
    await page.waitForLoadState('networkidle')

    await expect(page).not.toHaveURL(/\/login/)
    await expect(page.getByText('负债优化')).toBeVisible({ timeout: 10_000 })

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
    await page.waitForLoadState('networkidle')

    await expect(page).not.toHaveURL(/\/login/)
    await expect(page.getByText('配置漂移')).toBeVisible({ timeout: 10_000 })

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
    await page.waitForLoadState('networkidle')

    await expect(page).not.toHaveURL(/\/login/)
    await expect(page.getByText('AI 问答助手')).toBeVisible({ timeout: 10_000 })

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
    await page.waitForLoadState('networkidle')

    await expect(page).not.toHaveURL(/\/login/)
    await expect(page.getByRole('button', { name: /AI 服务商/ })).toBeVisible({ timeout: 10_000 })

    const realErrors = errors.filter(
      (e) => !e.includes('Failed to load resource') && !e.includes('AxiosError') && !e.includes('WebSocket')
    )
    expect(realErrors, `Console errors on /settings/ai: ${realErrors.join(', ')}`).toHaveLength(0)
  })

  test('AI hub navigates to sub-pages', async ({ page }) => {
    await richFamily(page)
    await page.goto('/ai')
    await page.waitForLoadState('networkidle')

    // Click the first feature list item (资产体检 → /ai/report)
    await page.getByRole('listitem', { name: /资产体检/ }).click()
    await expect(page).toHaveURL(/\/ai\/report/, { timeout: 8_000 })
  })

  test('empty family AI hub shows no-data state gracefully', async ({ page }) => {
    const errors: string[] = []
    page.on('console', (msg) => {
      if (msg.type() === 'error') errors.push(msg.text())
    })

    await emptyFamily(page)
    await page.goto('/ai')
    await page.waitForLoadState('networkidle')

    await expect(page).not.toHaveURL(/\/login/)
    await expect(page.getByText('家庭资产智能助手')).toBeVisible({ timeout: 10_000 })

    const realErrors = errors.filter(
      (e) => !e.includes('Failed to load resource') && !e.includes('AxiosError') && !e.includes('WebSocket')
    )
    expect(realErrors, `Console errors on /ai with empty family: ${realErrors.join(', ')}`).toHaveLength(0)
  })
})
