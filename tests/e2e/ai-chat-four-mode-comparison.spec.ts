import { test, expect, type Page } from '@playwright/test'
import { loginAs } from '../lib/auth'
import * as fs from 'fs'
import * as path from 'path'

/**
 * Four-Mode Comparison Test
 *
 * Tests all 4 DeerFlow execution modes (Flash / Thinking / Pro / Ultra)
 * with 2 different queries, measuring completion time and capturing screenshots.
 *
 * Key design: each (mode, query) combination gets a FRESH page context via
 * page.goto() with a unique route. For the second query within the same mode,
 * we navigate to /ai/chat?newSession=1 and do a HARD reload to force Vue
 * component remount (SPA navigation to the same route does NOT re-trigger
 * onMounted, so initializeFromUrl never processes newSession=1).
 */

const QUERIES = [
  '帮我研究下比亚迪的市场趋势',
  '分析家庭资产负债，联网搜索优化建议',
]

const MODES = ['flash', 'thinking', 'pro', 'ultra'] as const
type Mode = (typeof MODES)[number]

const MODE_LABELS: Record<Mode, string> = {
  flash: '闪速',
  thinking: '思考',
  pro: 'Pro',
  ultra: 'Ultra',
}

// Timeout per query per mode (5 minutes)
const QUERY_TIMEOUT = 300_000

const SCREENSHOT_DIR = path.join(__dirname, '..', 'screenshot', 'four-mode-comparison')

interface TestResult {
  mode: Mode
  query: string
  status: 'success' | 'timeout' | 'error'
  durationMs: number
  errorMessage?: string
  screenshotPath?: string
}

const results: TestResult[] = []

async function debugScreenshot(page: Page, name: string) {
  const p = path.join(SCREENSHOT_DIR, `debug-${name}.png`)
  await page.screenshot({ path: p })
  console.log(`    [screenshot] ${p}`)
}

async function selectMode(page: Page, mode: Mode) {
  console.log(`    [selectMode] Selecting mode: ${mode} (${MODE_LABELS[mode]})`)

  // The mode selector button is the control-btn between model-btn and search toggle
  const controlBtns = page.locator('.control-btn')
  const count = await controlBtns.count()
  console.log(`    [selectMode] .control-btn count: ${count}`)

  let modeBtnClicked = false
  for (let i = 0; i < count; i++) {
    const cls = await controlBtns.nth(i).getAttribute('class') || ''
    if (!cls.includes('model-btn') && !cls.includes('control-btn--search')) {
      console.log(`    [selectMode] Found mode button at index ${i}, class="${cls}"`)
      await controlBtns.nth(i).click()
      modeBtnClicked = true
      break
    }
  }

  if (!modeBtnClicked) {
    const allBtns = page.locator('button')
    const allCount = await allBtns.count()
    for (let i = 0; i < allCount; i++) {
      const cls = await allBtns.nth(i).getAttribute('class') || ''
      if (cls.includes('control-btn') && !cls.includes('model') && !cls.includes('search') && !cls.includes('header') && !cls.includes('submit')) {
        console.log(`    [selectMode] Fallback found: button[${i}] class="${cls}"`)
        await allBtns.nth(i).click()
        modeBtnClicked = true
        break
      }
    }
  }

  if (!modeBtnClicked) {
    await debugScreenshot(page, `no-mode-btn-${mode}`)
    throw new Error('Mode button not found')
  }

  console.log(`    [selectMode] Mode button clicked`)

  // Wait for the dropdown to appear (Teleported to body)
  await page.waitForTimeout(500)

  const dropdownSelectors = [
    '[class*="mode-dropdown"]',
    '.mode-dropdown',
    '[class*="mode-item"]',
  ]

  let dropdownVisible = false
  for (const sel of dropdownSelectors) {
    const loc = page.locator(sel)
    const c = await loc.count()
    if (c > 0) {
      const vis = await loc.first().isVisible()
      console.log(`    [selectMode] Selector "${sel}": count=${c}, visible=${vis}`)
      if (vis) {
        dropdownVisible = true
        break
      }
    }
  }

  if (!dropdownVisible) {
    const modeElements = await page.evaluate(() => {
      const els = Array.from(document.querySelectorAll('[class*="mode"]'))
      return els.map(e => ({
        tag: e.tagName,
        classes: e.className,
        text: e.textContent?.trim().slice(0, 50),
        visible: (e as HTMLElement).offsetParent !== null,
      }))
    })
    console.log(`    [selectMode] Elements with "mode" in class:`)
    modeElements.forEach((e, i) => {
      console.log(`      [${i}] <${e.tag}> class="${e.classes}" visible=${e.visible} text="${e.text}"`)
    })

    await debugScreenshot(page, `no-dropdown-${mode}`)
    throw new Error('Mode dropdown did not appear')
  }

  // Click the mode item by label text
  const modeLabel = MODE_LABELS[mode]
  const modeItem = page.locator('[class*="mode-item"]').filter({ hasText: modeLabel })
  const itemCount = await modeItem.count()
  console.log(`    [selectMode] Mode items matching "${modeLabel}": ${itemCount}`)

  if (itemCount === 0) {
    const allItems = page.locator('[class*="mode-item"]')
    const allCount = await allItems.count()
    for (let i = 0; i < allCount; i++) {
      const text = await allItems.nth(i).textContent()
      console.log(`    [selectMode]   mode-item[${i}]: "${text?.trim()}"`)
    }
    await debugScreenshot(page, `no-mode-item-${mode}`)
    throw new Error(`Mode "${modeLabel}" not found in dropdown`)
  }

  await modeItem.first().click()
  console.log(`    [selectMode] Mode item clicked: ${modeLabel}`)

  // Wait for popup to close
  await page.waitForTimeout(500)
}

async function waitForModelsLoaded(page: Page) {
  console.log(`    [waitForModels] Waiting for /ai/models API response...`)
  await (page as any)._modelsReadyPromise
  await page.waitForTimeout(300)
  console.log(`    [waitForModels] Models ready`)
}

function setupModelsListener(page: Page) {
  ;(page as any)._modelsReadyPromise = page.waitForResponse(
    (resp) => resp.url().includes('/ai/models') && resp.status() === 200,
    { timeout: 15000 },
  )
}

/**
 * Navigate to a fresh chat page.
 *
 * Key insight: page.goto() to a different URL (with unique timestamp) forces
 * Vue Router to unmount and remount AIChatBox, triggering onMounted() which
 * processes newSession=1 and clears activeThreadId.
 *
 * After navigation, we must wait for InputBox to actually initialize its
 * model_name from the /ai/models API response. The API response alone is
 * not enough — Vue's reactivity system needs time to process the data and
 * update the component's internal state.
 */
async function navigateToFreshChat(page: Page) {
  const timestamp = Date.now()
  await page.goto(`/ai/chat?newSession=1&_t=${timestamp}`)
  await page.waitForLoadState('networkidle')
  await page.locator('.chat-textarea').waitFor({ state: 'visible', timeout: 10000 })

  // Wait for InputBox to initialize model_name by checking UI state.
  // The mode trigger button shows the current mode (e.g., "mode-trigger--thinking").
  // This proves the component has processed the /ai/models response and set
  // context.value.model_name, which is required for onSubmit() to work.
  await page.waitForFunction(() => {
    const modeTrigger = document.querySelector('[class*="mode-trigger"]')
    return modeTrigger && modeTrigger.className.includes('mode-trigger--')
  }, { timeout: 10000, polling: 200 })

  // Additional wait for Vue reactivity to settle
  await page.waitForTimeout(500)
}

async function sendQuery(page: Page, query: string) {
  // Ensure models are loaded before attempting to send
  await waitForModelsLoaded(page)

  const textarea = page.locator('.chat-textarea')
  await textarea.waitFor({ state: 'visible', timeout: 5000 })

  // Click textarea first to ensure focus, then clear and type
  await textarea.click()
  await textarea.fill('')
  await page.waitForTimeout(100)
  await textarea.fill(query)
  await page.waitForTimeout(200)

  // Verify textarea has the expected value
  const textareaValue = await textarea.inputValue()
  console.log(`    [sendQuery] Textarea value: "${textareaValue}"`)

  // On Mac, need Cmd+Enter to send (Enter inserts newline)
  // On Windows/Linux, need Ctrl+Enter
  const isMac = process.platform === 'darwin'
  const modifier = isMac ? 'Meta' : 'Control'

  console.log(`    [sendQuery] Sending with ${modifier}+Enter`)
  await textarea.press(`${modifier}+Enter`)

  // Wait for user bubble to appear — this proves the message was sent
  // and the backend received it (optimistic user message rendered).
  // Only check actual user bubbles, not message-group (which includes AI messages).
  const querySnippet = query.slice(0, 6)
  await page.waitForFunction(
    (snippet: string) => {
      const userBubbles = document.querySelectorAll('[class*="user-bubble"], [class*="user-message"]')
      for (const bubble of userBubbles) {
        if (bubble.textContent && bubble.textContent.includes(snippet)) return true
      }
      return false
    },
    querySnippet,
    { timeout: 8000, polling: 200 },
  )
  console.log(`    [sendQuery] User bubble detected — message successfully sent`)
  // Give the page time to update and backend to start processing
  await page.waitForTimeout(500)
}

async function waitForCompletion(page: Page, query: string, timeoutMs: number): Promise<{ status: 'success' | 'timeout'; durationMs: number }> {
  const start = Date.now()

  try {
    // Phase 1: Wait for streaming to START — look for the specific query text
    // in a user bubble. This proves the message was sent and the backend started.
    const querySnippet = query.slice(0, 8)
    await page.waitForFunction(
      (snippet: string) => {
        const userBubbles = document.querySelectorAll('[class*="user-bubble"], [class*="user-message"]')
        for (const bubble of userBubbles) {
          if (bubble.textContent && bubble.textContent.includes(snippet)) return true
        }
        return false
      },
      querySnippet,
      { timeout: 10000, polling: 200 },
    )
    console.log(`    [completion] Phase 1: streaming started (${((Date.now() - start) / 1000).toFixed(1)}s)`)

    // Phase 2: Wait for streaming to END with stability check.
    // AI streaming has pauses (tool calls, thinking gaps) where indicators briefly disappear.
    // We require content to be stable for STABILITY_WINDOW_MS to confirm completion.
    const STABILITY_WINDOW_MS = 5000 // 5 seconds of no change = done
    const CHECK_INTERVAL_MS = 1500
    let lastContentLength = 0
    let stableSince = 0

    while (Date.now() - start < timeoutMs) {
      const hasStreamingIndicator = await page.evaluate(() => {
        const body = document.body.innerText
        return body.includes('发送中') || body.includes('AI 正在回答') || body.includes('回答中')
      })

      if (hasStreamingIndicator) {
        // Still streaming, reset stability timer
        stableSince = 0
        await page.waitForTimeout(CHECK_INTERVAL_MS)
        continue
      }

      // No streaming indicator — check content length
      const currentLength = await page.evaluate(() => {
        const messageGroups = document.querySelectorAll('.message-group')
        let total = 0
        for (const group of messageGroups) {
          const className = group.className || ''
          if (className.includes('group--assistant')) {
            total += (group.textContent?.trim() || '').length
          }
        }
        return total
      })

      if (currentLength === lastContentLength && currentLength > 50) {
        // Content hasn't changed
        if (stableSince === 0) {
          stableSince = Date.now()
        } else if (Date.now() - stableSince >= STABILITY_WINDOW_MS) {
          // Stable for long enough — truly done
          const durationMs = Date.now() - start
          console.log(`    [completion] Phase 2: streaming completed (${(durationMs / 1000).toFixed(1)}s, content=${currentLength} chars)`)
          return { status: 'success', durationMs }
        }
      } else {
        // Content changed or too short, reset stability timer
        lastContentLength = currentLength
        stableSince = 0
      }

      await page.waitForTimeout(CHECK_INTERVAL_MS)
    }

    throw new Error('Timeout waiting for completion')
  } catch {
    const timeoutScreenshot = path.join(SCREENSHOT_DIR, `timeout-${Date.now()}.png`)
    await page.screenshot({ path: timeoutScreenshot })
    console.log(`    [timeout screenshot] ${timeoutScreenshot}`)
    return { status: 'timeout', durationMs: Date.now() - start }
  }
}

test.describe('Four-Mode Comparison Test', () => {
  test('compare all 4 modes with 2 queries', async ({ page }) => {
    test.setTimeout(30 * 60 * 1000) // 30 minutes total for 8 combinations

    // Ensure screenshot dir exists
    fs.mkdirSync(SCREENSHOT_DIR, { recursive: true })
    console.log(`Screenshot dir: ${SCREENSHOT_DIR}`)

    // Login
    console.log('=== Logging in as demouser ===')
    await loginAs(page, 'demouser', 'DemoPass123')

    for (const mode of MODES) {
      for (let qi = 0; qi < QUERIES.length; qi++) {
        const query = QUERIES[qi]
        const label = `${mode}-q${qi + 1}`
        console.log(`\n=== Testing: mode=${mode}, query="${query}" ===`)

        // Navigate to a fresh chat page with hard reload to force remount
        await navigateToFreshChat(page)
        console.log(`  Page loaded, clean state confirmed`)

        // Verify clean state: no user message bubbles should exist
        const bubbleCount = await page.locator('[class*="user-bubble"], [class*="user-message"]').count()
        if (bubbleCount > 0) {
          console.log(`  WARNING: Found ${bubbleCount} stale user bubbles, forcing another reload...`)
          await page.reload({ waitUntil: 'networkidle' })
          await page.locator('.chat-textarea').waitFor({ state: 'visible', timeout: 10000 })
          await waitForModelsLoaded(page)
        }

        // Select mode
        try {
          await selectMode(page, mode)
          console.log(`  Mode set to: ${MODE_LABELS[mode]}`)
        } catch (err: any) {
          console.error(`  Failed to select mode ${mode}: ${err.message}`)
          results.push({
            mode,
            query,
            status: 'error',
            durationMs: 0,
            errorMessage: `Failed to select mode: ${err.message}`,
          })
          continue
        }

        // Take pre-send screenshot
        const preScreenshot = path.join(SCREENSHOT_DIR, `${label}-pre.png`)
        await page.screenshot({ path: preScreenshot })

        // Send query
        await sendQuery(page, query)
        console.log(`  Query sent, waiting for completion...`)

        // Wait for completion
        const { status, durationMs } = await waitForCompletion(page, query, QUERY_TIMEOUT)
        console.log(`  Result: ${status}, duration: ${(durationMs / 1000).toFixed(1)}s`)

        // Take post-completion screenshot
        const postScreenshot = path.join(SCREENSHOT_DIR, `${label}-post.png`)
        await page.screenshot({ path: postScreenshot })

        results.push({
          mode,
          query,
          status,
          durationMs,
          screenshotPath: postScreenshot,
        })
      }
    }

    // Write results summary
    const summaryPath = path.join(SCREENSHOT_DIR, 'results-summary.json')
    fs.writeFileSync(summaryPath, JSON.stringify(results, null, 2))
    console.log(`\n\n=== RESULTS SUMMARY ===`)
    for (const r of results) {
      console.log(`  ${r.mode.padEnd(10)} | ${r.query.slice(0, 15).padEnd(17)} | ${r.status.padEnd(8)} | ${(r.durationMs / 1000).toFixed(1)}s | ${r.errorMessage || ''}`)
    }
    console.log(`\nScreenshots saved to: ${SCREENSHOT_DIR}`)
    console.log(`Results saved to: ${summaryPath}`)
  })
})
