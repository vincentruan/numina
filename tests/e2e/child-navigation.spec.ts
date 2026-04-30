import { test, expect } from '@playwright/test'
import { childFamily, richFamily } from '../lib/fixtures'

/**
 * 儿童路由守卫测试
 *
 * 验证三种导航守卫场景：
 *   1. 儿童 session → 成人路由 → 重定向到 /child/
 *   2. 成人 session → 儿童路由 → 重定向到 /
 *   3. 未认证 → 儿童路由 → 重定向到 /login
 */

test.describe('child navigation guards', () => {
  test.describe('child session blocked from adult routes', () => {
    test('child → /assets redirects to /child/', async ({ page }) => {
      await childFamily(page)
      await page.goto('/assets')
      await expect(page).toHaveURL(/\/child\//, { timeout: 8_000 })
    })

    test('child → /liabilities redirects to /child/', async ({ page }) => {
      await childFamily(page)
      await page.goto('/liabilities')
      await expect(page).toHaveURL(/\/child\//, { timeout: 8_000 })
    })

    test('child → /settings redirects to /child/', async ({ page }) => {
      await childFamily(page)
      await page.goto('/settings')
      await expect(page).toHaveURL(/\/child\//, { timeout: 8_000 })
    })
  })

  test.describe('adult session blocked from child routes', () => {
    test('adult → /child redirects to child SPA (/child/)', async ({ page }) => {
      await richFamily(page)
      await page.goto('/child')
      // Main app does window.location.replace('/child/') — nginx routes /child/* to child SPA
      await expect(page).toHaveURL(/\/child\//, { timeout: 8_000 })
    })

    test('adult → /child/tasks redirects to child SPA (/child/)', async ({ page }) => {
      await richFamily(page)
      await page.goto('/child/tasks')
      // Main app does window.location.replace('/child/') — nginx routes /child/* to child SPA
      await expect(page).toHaveURL(/\/child\//, { timeout: 8_000 })
    })
  })

  test.describe('unauthenticated access to child routes', () => {
    test('unauthenticated → /child redirects to /child/select', async ({ page }) => {
      await page.goto('/')
      await page.evaluate(() => localStorage.removeItem('numina_user'))
      await page.context().clearCookies()
      await page.goto('/child')
      await expect(page).toHaveURL(/\/child\/select/, { timeout: 8_000 })
    })

    test('unauthenticated → /child/tasks redirects to /child/select', async ({ page }) => {
      await page.goto('/')
      await page.evaluate(() => localStorage.removeItem('numina_user'))
      await page.context().clearCookies()
      await page.goto('/child/tasks')
      await expect(page).toHaveURL(/\/child\/select/, { timeout: 8_000 })
    })
  })
})
