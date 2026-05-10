/**
 * Login flow + post-login navigation tests against production.
 *
 * Covers:
 *   1. Phase 1 → Phase 2 transition (numeric PIN, demouser)
 *   2. Successful login → dashboard redirect
 *   3. Bottom navigation bar renders and tabs work
 *   4. Child emoji-PIN login flow (testchild)
 */

import { test, expect } from '@playwright/test'

const PROD = 'https://numina.xiaoshutiao.space'

/** Full UI login helper — phase 1 credentials + phase 2 PIN + trust dialog dismissal */
async function uiLogin(page: import('@playwright/test').Page, pin = '123456') {
  await page.goto(`${PROD}/login`, { waitUntil: 'domcontentloaded' })
  await page.waitForTimeout(2000)

  await page.fill('input[name="username"]', 'demouser')
  await page.fill('input[type="password"]', 'DemoPass123')
  await page.click('button:has-text("下一步")')

  // Wait for PIN pad
  await expect(page.locator('.numpad-btn').first()).toBeVisible({ timeout: 8000 })

  for (const digit of pin.split('')) {
    await page.locator(`.numpad-btn:has-text("${digit}")`).first().click()
    await page.waitForTimeout(150)
  }

  await page.click('button:has-text("确认")')

  // Dismiss trust-device dialog — wait up to 8s for it to appear, then dismiss
  const trustBtn = page.locator('button:has-text("暂不")')
  try {
    await trustBtn.waitFor({ state: 'visible', timeout: 8000 })
    await trustBtn.click()
  } catch {
    // dialog didn't appear — already trusted or not shown
  }
}

test.describe('login flow — production', () => {
  test.setTimeout(90000)

  test('demouser: phase 1 shows PIN pad, phase 2 succeeds → dashboard', async ({ page }) => {
    const errors: string[] = []
    page.on('pageerror', e => errors.push(e.message))

    await uiLogin(page)

    // Should redirect away from /login
    await expect(page).not.toHaveURL(/\/login/, { timeout: 15000 })

    // No JS errors
    expect(errors.filter(e => !e.includes('AxiosError'))).toHaveLength(0)
  })

  test('demouser: bottom nav bar renders all tabs after login', async ({ page }) => {
    await uiLogin(page)

    // Wait for redirect away from login
    await expect(page).not.toHaveURL(/\/login/, { timeout: 15000 })

    // Bottom nav bar should be visible
    const tabbar = page.locator('.van-tabbar, [class*="tabbar"], [class*="tab-bar"]').first()
    await expect(tabbar).toBeVisible({ timeout: 10000 })

    // At least 3 tab items
    const tabItems = page.locator('.van-tabbar-item, [class*="tabbar-item"]')
    const count = await tabItems.count()
    expect(count).toBeGreaterThanOrEqual(3)
  })

  test('testchild: emoji PIN login flow', async ({ page }) => {
    // Step 1: parent login to get family/children
    const parentResp = await page.request.post(`${PROD}/api/v1/auth/login/step1`, {
      data: { username: 'demouser', password: 'DemoPass123' },
    })
    expect(parentResp.ok()).toBeTruthy()
    const parentStep1 = await parentResp.json()
    const parentTemp: string = parentStep1.data.temp_token

    const parentStep2 = await page.request.post(`${PROD}/api/v1/auth/login/step2`, {
      data: { temp_token: parentTemp, factor_type: 'numeric_pin', payload: { pin: '123456' } },
    })
    expect(parentStep2.ok()).toBeTruthy()
    const parentTokenData = await parentStep2.json()
    const parentToken: string = parentTokenData.data.access_token

    // Get children list
    const childrenResp = await page.request.get(`${PROD}/api/v1/family/children`, {
      headers: { Authorization: `Bearer ${parentToken}` },
    })
    expect(childrenResp.ok()).toBeTruthy()
    const childrenBody = await childrenResp.json()
    const children: Array<{ id: string; display_name: string }> = childrenBody.data ?? childrenBody
    const child = children.find(c => c.display_name === 'test_child' || c.display_name === 'testchild' || c.display_name === 'Test Child')
    expect(child, `testchild not found in: ${children.map(c => c.display_name).join(', ')}`).toBeTruthy()

    // Child emoji PIN login
    const childLoginResp = await page.request.post(`${PROD}/api/v1/auth/child/login`, {
      data: { child_id: child!.id, pin_sequence: ['🐱', '🐶', '🐸', '🦊'] },
    })
    expect(childLoginResp.ok(), `child login failed: ${await childLoginResp.text()}`).toBeTruthy()
    const childData = await childLoginResp.json()
    expect(childData.data?.access_token ?? childData.access_token).toBeTruthy()
  })
})
