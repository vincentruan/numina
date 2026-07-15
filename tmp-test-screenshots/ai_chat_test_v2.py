#!/usr/bin/env python3
"""AI Chat E2E test v2: correct mode labels (闪速/思考/Pro/Ultra)."""
import asyncio
import json
from pathlib import Path

from playwright.async_api import async_playwright

BASE_URL = "http://localhost:5173"
SCREENSHOT_DIR = Path(__file__).parent
QUERIES = [
    ("帮我研究下比亚迪的市场趋势", "byd-research"),
    ("分析家庭资产负债，联网搜索优化建议", "asset-analysis"),
]
# Chinese mode labels from i18n
MODES = ["闪速", "思考", "Pro", "Ultra"]


async def screenshot(page, name):
    path = SCREENSHOT_DIR / f"{name}.png"
    await page.screenshot(path=str(path), full_page=False)
    print(f"  ✓ screenshot: {name}.png")


async def wait_for_stream_done(page, timeout_ms=180000):
    """Wait until streaming indicator disappears."""
    start = asyncio.get_event_loop().time()
    while (asyncio.get_event_loop().time() - start) * 1000 < timeout_ms:
        streaming = await page.evaluate("""() => {
            // Check for active streaming indicators
            const indicators = document.querySelectorAll(
                '[class*="streaming-indicator"], [class*="typing-indicator"], .three-dot-loader'
            );
            // Also check if send button shows "stop" state
            const stopBtn = document.querySelector('[class*="stop"], [class*="cancel"]');
            return indicators.length > 0 || stopBtn !== null;
        }""")
        if not streaming:
            await asyncio.sleep(2)
            return True
        await asyncio.sleep(1)
    print("  ⚠ stream timeout")
    return False


async def extract_metrics(page):
    return await page.evaluate("""() => {
        // Token usage
        const tokenEl = document.querySelector('[class*="token-usage"], [class*="TokenUsage"]');
        const tokenText = tokenEl ? tokenEl.innerText : '';
        // Chain of thought
        const cotEl = document.querySelector('[class*="chain-of-thought"], [class*="ChainOfThought"]');
        const hasCoT = cotEl !== null;
        // Citations
        const citations = document.querySelectorAll('[class*="citation"], [class*="Citation"]');
        // Tool calls
        const toolCalls = document.querySelectorAll('[class*="tool-call"], [class*="ToolCall"]');
        // Messages
        const messages = document.querySelectorAll('[class*="message-group"], [class*="MessageGroup"]');
        // Mode selector - check which mode is active
        const modeTrigger = document.querySelector('[class*="mode-trigger"]');
        const modeClass = modeTrigger ? Array.from(modeTrigger.classList).find(c => c.includes('mode-trigger--')) : '';
        const modeName = modeClass ? modeClass.replace('mode-trigger--', '') : 'unknown';
        return {
            tokenUsage: tokenText.slice(0, 200),
            hasChainOfThought: hasCoT,
            citationCount: citations.length,
            toolCallCount: toolCalls.length,
            messageCount: messages.length,
            activeMode: modeName
        };
    }""")


async def select_mode(page, mode_label):
    """Click mode trigger, then select the mode by label."""
    try:
        # Click the mode trigger button
        mode_trigger = page.locator('[class*="mode-trigger"]').first
        if await mode_trigger.is_visible(timeout=3000):
            await mode_trigger.click()
            await asyncio.sleep(0.8)

            # Click the mode option by label text
            mode_option = page.locator(f'.mode-item-label:has-text("{mode_label}")').first
            if await mode_option.is_visible(timeout=3000):
                await mode_option.click()
                await asyncio.sleep(0.5)
                print(f"  ✓ mode set to: {mode_label}")
                return True
            else:
                print(f"  ⚠ mode option '{mode_label}' not visible")
    except Exception as e:
        print(f"  ⚠ mode selection failed: {e}")
    return False


async def test_query(page, query, query_name, mode):
    test_name = f"{query_name}-{mode.lower().replace(' ', '-')}"
    print(f"\n=== {test_name} ===")
    print(f"  Query: {query}")

    # Navigate to AI chat fresh
    await page.goto(f"{BASE_URL}/ai/chat", wait_until="networkidle", timeout=30000)
    await asyncio.sleep(2)

    # Select mode
    mode_selected = await select_mode(page, mode)
    await screenshot(page, f"{test_name}-01-ready")

    # Type query
    input_el = page.locator('textarea').first
    await input_el.fill(query)
    await asyncio.sleep(0.5)

    # Send via send button or Enter
    send_btn = page.locator('[class*="send-button"], button[class*="send"]').first
    try:
        if await send_btn.is_visible(timeout=2000):
            await send_btn.click()
        else:
            await input_el.press("Enter")
    except Exception:
        await input_el.press("Enter")

    print("  ⏳ waiting for response...")
    await asyncio.sleep(3)
    await screenshot(page, f"{test_name}-02-streaming")

    # Wait for completion
    await wait_for_stream_done(page, timeout_ms=180000)
    await screenshot(page, f"{test_name}-03-final")

    # Scroll to capture full response
    try:
        msg_list = page.locator('[class*="message-list"], [class*="MessageList"]').first
        await msg_list.evaluate("el => el.scrollTop = el.scrollHeight")
        await asyncio.sleep(1)
        await screenshot(page, f"{test_name}-04-bottom")
    except Exception:
        pass

    metrics = await extract_metrics(page)
    print(f"  metrics: {json.dumps(metrics, ensure_ascii=False)}")
    return metrics


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, args=["--window-size=1400,900"])
        context = await browser.new_context(viewport={"width": 1400, "height": 900}, device_scale_factor=2)
        page = await context.new_page()

        # Login
        print("Logging in...")
        await page.goto(f"{BASE_URL}/login", wait_until="networkidle", timeout=30000)
        await asyncio.sleep(2)

        await page.locator('input[placeholder*="用户名"]').first.fill("demouser")
        await page.locator('input[placeholder*="密码"]').first.fill("DemoPass123")
        await asyncio.sleep(0.5)
        await page.locator('button:has-text("下一步")').first.click()

        await page.wait_for_load_state("networkidle", timeout=30000)
        await asyncio.sleep(3)

        if "login" in page.url:
            print("  ⚠ login failed")
            await browser.close()
            return

        print("  ✓ logged in")

        # Run tests
        results = []
        for query, query_name in QUERIES:
            for mode in MODES:
                try:
                    metrics = await test_query(page, query, query_name, mode)
                    results.append({"query": query, "mode": mode, "metrics": metrics})
                except Exception as e:
                    print(f"  ✗ error: {e}")
                    results.append({"query": query, "mode": mode, "error": str(e)})

        # Summary
        print("\n=== SUMMARY ===")
        print(json.dumps(results, ensure_ascii=False, indent=2))

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
