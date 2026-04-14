import { test, expect } from '@playwright/test'
import { emptyFamily } from '../lib/fixtures'

/**
 * Empty-state gauntlet
 *
 * 使用 emptyFamily() fixture（无资产/负债/心愿的全新家庭），
 * 访问所有列表页和 Dashboard，断言：
 *   1. 不跳转到 /login（auth 正常）
 *   2. 无 JS console.error
 *   3. 空状态 UI 组件可见（van-empty 或自定义 empty 元素）
 *
 * 空状态选择器说明：
 *   - .van-empty        — Vant 官方空状态组件（WishList、Dashboard、DataStats、LiabilityList、AssetList）
 *   - .report-empty-card — AIHub 自定义空报告卡片
 *   - .empty-state      — AIReport、AIAlerts 等 AI 页面自定义空状态
 */

// 需要空状态断言的页面配置
const EMPTY_STATE_PAGES = [
  {
    name: 'Dashboard',
    path: '/',
    // Dashboard 空状态：asset_count === 0 时显示 van-empty
    emptySelector: '.van-empty',
    description: 'Dashboard 显示空状态引导',
  },
  {
    name: 'AssetList',
    path: '/assets',
    emptySelector: '.van-empty',
    description: '资产列表显示空状态',
  },
  {
    name: 'LiabilityList',
    path: '/liabilities',
    emptySelector: '.van-empty',
    description: '负债列表显示空状态',
  },
  {
    name: 'WishList',
    path: '/wishes',
    emptySelector: '.van-empty',
    description: '心愿列表显示空状态',
  },
  {
    name: 'DataStats',
    path: '/stats',
    emptySelector: '.van-empty',
    description: '统计页显示空状态',
  },
  {
    name: 'AIHub',
    path: '/ai',
    // AIHub 无报告时显示 .report-empty-card
    emptySelector: '.report-empty-card',
    description: 'AI 中心显示空报告引导卡片',
  },
]

// 只需断言「不报错、不跳转」的页面（有内容但无空状态组件）
const NO_ERROR_PAGES = [
  { name: 'Family', path: '/family' },
  { name: 'Settings', path: '/settings' },
  { name: 'CategoryManage', path: '/settings/categories' },
  { name: 'TagManage', path: '/settings/tags' },
  { name: 'AIConfig', path: '/settings/ai' },
]

test.describe('empty-state gauntlet: 空家庭下所有页面正常渲染', () => {
  // 每个测试独立登录（workers:1，无并发问题）
  test.beforeEach(async ({ page }) => {
    await emptyFamily(page)
  })

  // ── 空状态组件断言 ──────────────────────────────────────────
  for (const { name, path, emptySelector, description } of EMPTY_STATE_PAGES) {
    test(`${name} (${path}): ${description}`, async ({ page }) => {
      const errors: string[] = []
      page.on('console', (msg) => {
        if (msg.type() === 'error') errors.push(msg.text())
      })

      await page.goto(path)

      // 不应跳转到登录页
      await expect(page).not.toHaveURL(/\/login/, { timeout: 8_000 })

      // 空状态组件应可见
      await expect(page.locator(emptySelector).first()).toBeVisible({ timeout: 10_000 })

      // 无 JS 控制台错误
      expect(
        errors.filter((e) => !isKnownNoise(e)),
        `${name} 页面有 console.error:\n  ${errors.join('\n  ')}`
      ).toHaveLength(0)
    })
  }

  // ── 无报错断言（有内容页面）──────────────────────────────────
  for (const { name, path } of NO_ERROR_PAGES) {
    test(`${name} (${path}): 正常渲染无 JS 错误`, async ({ page }) => {
      const errors: string[] = []
      page.on('console', (msg) => {
        if (msg.type() === 'error') errors.push(msg.text())
      })

      await page.goto(path)
      await expect(page).not.toHaveURL(/\/login/, { timeout: 8_000 })

      // 等待页面主体渲染
      await expect(
        page.locator('.van-nav-bar, .van-cell-group, main, [class*="page"]').first()
      ).toBeVisible({ timeout: 10_000 })

      expect(
        errors.filter((e) => !isKnownNoise(e)),
        `${name} 页面有 console.error:\n  ${errors.join('\n  ')}`
      ).toHaveLength(0)
    })
  }
})

/**
 * 过滤已知的非关键噪音错误（如第三方资源加载失败等）。
 * 只过滤明确无害的错误，保持断言的严格性。
 */
function isKnownNoise(msg: string): boolean {
  // 浏览器扩展注入的错误
  if (msg.includes('chrome-extension://')) return true
  // favicon 加载失败（不影响功能）
  if (msg.includes('favicon')) return true
  return false
}
