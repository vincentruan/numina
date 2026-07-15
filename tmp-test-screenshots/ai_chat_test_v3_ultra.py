#!/usr/bin/env python3
"""AI Chat E2E test v3: Ultra mode only, with correct stream detection."""
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


async def screenshot(page, name):
    path = SCREENSHOT_DIR / f"{name}.png"
    await page.screenshot(path=str(path), full_page=False)
    print(f"  ✓ screenshot: {name}.png")


async def wait_for_stream_done(page, timeout_ms=300000):
    """Wait until streaming completes.

    Strategy: first wait for Vue app to render content,
    then wait for the streaming to finish (no loading indicators).
    """
    # Phase 1: Wait for Vue app to render substantial content (up to 60s)
    start = asyncio.get_event_loop().time()
    while (asyncio.get_event_loop().time() - start) * 1000 < 60000:
        has_content = await page.evaluate("""() => {
            // Check Vue-rendered content via #app innerText
            const app = document.querySelector('#app');
            const text = app ? app.innerText : document.body.innerText;
            // Look for substantial content: user message echoed, AI response, or subtasks
            return text.length > 200 ||
                   text.includes('正在执行') ||
                   text.includes('调用') ||
                   text.includes('比亚迪') ||
                   text.includes('资产');
        }""")
        if has_content:
            print("  ✓ content appeared")
            break
        await asyncio.sleep(2)

    # Phase 2: Wait for streaming to finish (no loading indicators)
    start = asyncio.get_event_loop().time()
    stable_count = 0
    while (asyncio.get_event_loop().time() - start) * 1000 < timeout_ms:
        is_loading = await page.evaluate("""() => {
            // Check for any loading/streaming indicators
            const indicators = document.querySelectorAll(
                '.streaming-indicator, .three-dot-loader, [class*="typing-indicator"]'
            );
            if (indicators.length > 0) return true;
            // Check if send button is in "stop" state (has stop icon)
            const sendBtn = document.querySelector('button[class*="send"]');
            if (sendBtn && sendBtn.querySelector('svg[class*="stop"]')) return true;
            // Check for "正在执行" subtask text (subtasks still running)
            const app = document.querySelector('#app');
            const text = app ? app.innerText : '';
            if (text.includes('正在执行') && text.includes('个子任务')) return true;
            return false;
        }""")
        if not is_loading:
            stable_count += 1
            if stable_count >= 3:  # Stable for 3 checks (6s)
                return True
        else:
            stable_count = 0
        await asyncio.sleep(2)
    print("  ⚠ stream timeout (5 min)")
    return False


async def extract_metrics(page):
    """Extract metrics using multiple text extraction methods."""
    return await page.evaluate("""() => {
        // Try multiple ways to get text - Vue may use different rendering
        const methods = {
            innerText: document.body.innerText || '',
            textContent: document.body.textContent || '',
            appInnerText: document.querySelector('#app')?.innerText || '',
            appTextContent: document.querySelector('#app')?.textContent || '',
        };

        // Use the longest result
        const allText = Object.values(methods).reduce((a, b) =>
            a.length > b.length ? a : b, '');

        // Token usage
        const tokenMatch = allText.match(/([\d,]+)\s*(tokens|输入|输出)/i) ||
                          allText.match(/(\d+)\s*\/\s*(\d+)/);
        const tokenText = tokenMatch ? tokenMatch[0] : '';

        // Chain of thought
        const hasCoT = allText.includes('调用') || allText.includes('web_search') ||
                      allText.includes('Tool');

        // Citations
        const citations = document.querySelectorAll('a[href*="citation"], [class*="citation"]');

        // Tool calls
        const toolCallSections = allText.match(/web_search|search|工具/gi) || [];

        // Messages
        const messages = document.querySelectorAll('[class*="message"], [class*="Message"]');

        // Subtasks
        const subtaskMatch = allText.match(/正在执行\s*(\d+)\s*个子任务/g);
        const subtaskCount = subtaskMatch ? subtaskMatch.length : 0;

        // Mode
        const modeTrigger = document.querySelector('[class*="mode-trigger"]');
        const modeClass = modeTrigger ?
            Array.from(modeTrigger.classList).find(c => c.includes('mode-trigger--')) : '';
        const modeName = modeClass ? modeClass.replace('mode-trigger--', '') : 'unknown';

        // Subtask statuses
        const subtaskStatuses = [];
        if (allText.includes('已取消')) subtaskStatuses.push('cancelled');
        if (allText.includes('已完成')) subtaskStatuses.push('completed');
        if (allText.includes('失败')) subtaskStatuses.push('failed');
        if (allText.includes('正在执行')) subtaskStatuses.push('in_progress');

        return {
            tokenUsage: tokenText.slice(0, 200),
            hasChainOfThought: hasCoT,
            citationCount: citations.length,
            toolCallCount: toolCallSections.length,
            messageCount: messages.length,
            subtaskCount: subtaskCount,
            subtaskStatuses,
            activeMode: modeName,
            pageTextLength: allText.length,
            hasContent: allText.length > 100,
            // Debug: show which method returned most text
            debugLengths: Object.fromEntries(
                Object.entries(methods).map(([k, v]) => [k, v.length])
            )
        };
    }""")


async def select_mode(page, mode_label):
    """Click mode trigger, then select the mode by label."""
    try:
        mode_trigger = page.locator('.mode-trigger').first
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
    test_name = f"v3-{query_name}-{mode.lower().replace(' ', '-')}"
    print(f"\n=== {test_name} ===")
    print(f"  Query: {query}")

    # Track agent API requests specifically
    agent_requests = []
    def on_request(req):
        if '/api/threads' in req.url or '/runs' in req.url:
            agent_requests.append(f"→ {req.method} {req.url}")
    def on_response(res):
        if '/api/threads' in res.url or '/runs' in res.url:
            agent_requests.append(f"  ← {res.status} {res.url}")
    page.on("request", on_request)
    page.on("response", on_response)

    await page.goto(f"{BASE_URL}/ai/chat", wait_until="networkidle", timeout=30000)
    await asyncio.sleep(2)

    mode_selected = await select_mode(page, mode)
    await screenshot(page, f"{test_name}-01-ready")

    # Fill textarea and verify
    input_el = page.locator('textarea').first
    await input_el.fill(query)
    await asyncio.sleep(0.5)

    # Verify textarea has content
    textarea_value = await input_el.input_value()
    print(f"  📝 textarea value length: {len(textarea_value)}")

    # Try clicking send button
    send_btn = page.locator('button[class*="send"], button:has([class*="send"])').first
    try:
        if await send_btn.is_visible(timeout=2000):
            await send_btn.click()
            print(f"  ✓ clicked send button")
        else:
            await input_el.press("Enter")
            print(f"  ✓ pressed Enter")
    except Exception as e:
        await input_el.press("Enter")
        print(f"  ⚠ send button not found, pressed Enter: {e}")

    await asyncio.sleep(2)
    await screenshot(page, f"{test_name}-02-early")

    # Check if any agent requests were made
    print(f"  📡 Agent API requests so far: {len(agent_requests)}")
    for req in agent_requests:
        print(f"    {req}")

    if not agent_requests:
        print("  ⚠ No agent API requests detected! Message may not have been sent.")
        # Try alternative: find and click the actual send button
        try:
            # Look for the send button by its icon
            send_icon = page.locator('[class*="send"] svg, button svg[class*="send"]').first
            if await send_icon.is_visible(timeout=2000):
                await send_icon.click()
                print("  ✓ clicked send icon")
                await asyncio.sleep(2)
        except Exception:
            pass

    print("  ⏳ waiting for response (up to 5 min)...")
    await wait_for_stream_done(page, timeout_ms=300000)
    await screenshot(page, f"{test_name}-03-final")

    # Scroll to bottom to capture subtask results
    try:
        msg_list = page.locator('.message-list, [class*="MessageList"]').first
        await msg_list.evaluate("el => el.scrollTop = el.scrollHeight")
        await asyncio.sleep(1)
        await screenshot(page, f"{test_name}-04-bottom")
    except Exception:
        pass

    # Print final request log
    print(f"  📡 Total agent API requests: {len(agent_requests)}")
    for req in agent_requests[-15:]:
        print(f"    {req}")

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

        # Only test Ultra mode
        results = []
        for query, query_name in QUERIES:
            try:
                metrics = await test_query(page, query, query_name, "Ultra")
                results.append({"query": query, "mode": "Ultra", "metrics": metrics})
            except Exception as e:
                print(f"  ✗ error: {e}")
                results.append({"query": query, "mode": "Ultra", "error": str(e)})

        print("\n=== SUMMARY ===")
        print(json.dumps(results, ensure_ascii=False, indent=2))

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
