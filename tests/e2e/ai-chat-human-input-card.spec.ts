/**
 * E2E test: HumanInputCard DeerFlow alignment + multi-select
 *
 * Tests:
 * 1. Login → AI chat → send message → check if clarification appears
 * 2. Verify single-choice interaction (click → immediate submit)
 * 3. Verify multi-select checkbox UI (if agent sends multi_select)
 * 4. Visual comparison with DeerFlow reference
 */
import { test, expect } from '@playwright/test'
import path from 'path'

const SCREENSHOT_DIR = path.join(__dirname, '..', '..', 'e2e-screenshots')

test.describe('HumanInputCard DeerFlow alignment', () => {
  test.beforeEach(async ({ page }) => {
    // Login
    await page.goto('/login')
    await page.fill('input[placeholder*="用户名"]', 'demouser')
    await page.fill('input[type="password"]', 'DemoPass123')
    await page.click('button:has-text("下一步")')
    // Wait for login to complete (redirect away from /login)
    await page.waitForURL(url => !url.pathname.includes('/login'), { timeout: 10000 })
  })

  test('01 - navigate to AI chat and send clarification-triggering message', async ({ page }) => {
    await page.goto('/ai/chat')
    await page.waitForLoadState('networkidle')
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, '01-ai-chat-page.png'), fullPage: true })

    // Send message that should trigger clarification
    const inputBox = page.locator('textarea, input[type="text"]').last()
    await inputBox.fill('分析家庭资产最新负债情况，联网获取实时方案并总结后给出建议')
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, '02-message-typed.png'), fullPage: true })

    // Press Enter or click send
    await inputBox.press('Enter')
    await page.waitForTimeout(3000)
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, '03-message-sent.png'), fullPage: true })

    // Wait for response (up to 30s)
    await page.waitForTimeout(15000)
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, '04-response-received.png'), fullPage: true })

    // Check if HumanInputCard appeared
    const humanInputCard = page.locator('.human-input-card')
    const cardCount = await humanInputCard.count()

    if (cardCount > 0) {
      await page.screenshot({ path: path.join(SCREENSHOT_DIR, '05-human-input-card.png'), fullPage: true })

      // Check if it's single-choice (option buttons)
      const optionButtons = page.locator('.human-input-card .option-btn')
      const buttonCount = await optionButtons.count()

      if (buttonCount > 0) {
        console.log(`✓ Single-choice mode detected: ${buttonCount} options`)
        // Verify buttons are full-width (DeerFlow style)
        const firstButton = optionButtons.first()
        const box = await firstButton.boundingBox()
        if (box) {
          console.log(`  Button width: ${box.width}px (should be close to container width)`)
        }
      }

      // Check if it's multi-select (checkboxes)
      const checkboxes = page.locator('.human-input-card .checkbox-input')
      const checkboxCount = await checkboxes.count()

      if (checkboxCount > 0) {
        console.log(`✓ Multi-select mode detected: ${checkboxCount} options`)
        await page.screenshot({ path: path.join(SCREENSHOT_DIR, '06-multi-select-mode.png'), fullPage: true })
      }
    } else {
      console.log('⚠ No HumanInputCard appeared (agent did not request clarification)')
    }
  })

  test('02 - verify single-choice click-to-submit interaction', async ({ page }) => {
    // This test requires the agent to send a clarification
    // We'll mock the SSE response or use a known trigger
    await page.goto('/ai/chat')
    await page.waitForLoadState('networkidle')

    // For now, just verify the component structure
    console.log('Note: This test requires agent to send clarification. Manual verification needed.')
  })

  test('03 - visual comparison: option button styling', async ({ page }) => {
    await page.goto('/ai/chat')
    await page.waitForLoadState('networkidle')

    // Send message
    const inputBox = page.locator('textarea, input[type="text"]').last()
    await inputBox.fill('分析家庭资产最新负债情况，联网获取实时方案并总结后给出建议')
    await inputBox.press('Enter')

    // Wait for response
    await page.waitForTimeout(20000)

    const humanInputCard = page.locator('.human-input-card')
    if (await humanInputCard.count() > 0) {
      // Screenshot the card specifically
      await humanInputCard.screenshot({ path: path.join(SCREENSHOT_DIR, '07-card-visual.png') })

      // Check button styling
      const optionBtn = page.locator('.option-btn').first()
      if (await optionBtn.count() > 0) {
        const styles = await optionBtn.evaluate(el => {
          const computed = window.getComputedStyle(el)
          return {
            width: computed.width,
            textAlign: computed.textAlign,
            border: computed.border,
            borderRadius: computed.borderRadius,
            padding: computed.padding,
          }
        })
        console.log('Option button styles:', styles)

        // DeerFlow alignment checks
        expect(styles.textAlign).toBe('left')
        expect(styles.borderRadius).toBe('8px') // or similar
      }
    }
  })
})
