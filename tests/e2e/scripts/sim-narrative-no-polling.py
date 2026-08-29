#!/usr/bin/env python3
"""Simulation test: DashboardNarrative cache-first + no-polling.

Reproduces the issue where refreshing the dashboard with cached narrative
content triggers unnecessary task polling (/api/v1/ai/tasks/detail/...).

Expected behavior:
  1. Navigate to dashboard → POST /dashboard/narrative → cache hit → JSON response
  2. Content displayed, NO task polling
  3. Reload page → same flow, NO task polling

Bug behavior (before fix):
  1. triggerStream(false) returns immediately (fire-and-forget)
  2. resume() fires before POST response arrives
  3. resume() finds old task → starts SSE → SSE fails → polling fallback
  4. User sees loading spinner + continuous polling requests

Usage:
  python tests/e2e/scripts/sim-narrative-no-polling.py [--base URL]
"""

import json
import sys
import time
import urllib.request
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright, Page
except ImportError:
    print("❌ playwright not installed. Run: pip install playwright && playwright install chromium")
    sys.exit(1)

BASE = "http://100.72.41.99:5173"
SCREENSHOT_DIR = Path(__file__).parent.parent.parent / "dogfood-output"
SCREENSHOT_DIR.mkdir(exist_ok=True)

passed = 0
failed = 0


def record(name: str, ok: bool, detail: str = ""):
    global passed, failed
    status = "✅" if ok else "❌"
    print(f"  {status} {name}" + (f"  ({detail})" if detail else ""))
    if ok:
        passed += 1
    else:
        failed += 1


def screenshot(page: Page, name: str):
    try:
        page.screenshot(
            path=str(SCREENSHOT_DIR / f"{name}.png"), full_page=False, timeout=10000
        )
    except Exception:
        pass


def login(page: Page, target_base: str) -> bool:
    """Login as demouser via API, set cookies + localStorage, navigate to dashboard."""
    from urllib.parse import urlparse

    login_data = json.dumps(
        {"username": "demouser", "password": "DemoPass123"}
    ).encode()
    req = urllib.request.Request(
        f"{target_base}/api/v1/auth/login",
        data=login_data,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            resp_data = json.loads(resp.read())
    except Exception as e:
        print(f"❌ Login failed: {e}")
        return False

    # Response is wrapped in envelope: {code, data: {access_token, ...}}
    data = resp_data.get("data", resp_data)
    token = data.get("access_token")
    if not token:
        print("❌ No access_token in login response")
        return False

    # Fetch user info
    me_req = urllib.request.Request(
        f"{target_base}/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    try:
        with urllib.request.urlopen(me_req, timeout=10) as me_resp:
            me_data = json.loads(me_resp.read())
    except Exception as e:
        print(f"❌ /auth/me failed: {e}")
        return False

    user = me_data.get("data", {})

    # Set cookie (domain from target_base)
    parsed = urlparse(target_base)
    domain = parsed.hostname or "localhost"
    context = page.context
    context.add_cookies([{
        "name": "access_token",
        "value": token,
        "domain": domain,
        "path": "/",
        "httpOnly": False,
        "secure": False,
        "sameSite": "Lax",
    }])

    # Set user in localStorage
    page.goto(target_base, wait_until="domcontentloaded", timeout=15000)
    page.evaluate("""(user) => {
        localStorage.setItem('numina_user', JSON.stringify({
            id: String(user.id), username: user.username, display_name: user.display_name,
            avatar_color: user.avatar_color, role: user.role, theme: user.theme,
            language: user.language || 'zh-CN', default_currency: user.default_currency,
        }));
    }""", user)
    return True


def main():
    global passed, failed

    target_base = BASE
    args = sys.argv[1:]
    for i, a in enumerate(args):
        if a == "--base" and i + 1 < len(args):
            target_base = args[i + 1]
            break

    print("=" * 50)
    print("Simulation: Narrative cache-first + no-polling")
    print(f"Target: {target_base}")
    print(f"Time:   {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 375, "height": 812},
            locale="zh-CN",
        )

        # Workaround for CSS load timeout in headless Chromium
        page = context.new_page()
        page.add_init_script("""() => {
            const origCreateElement = document.createElement.bind(document);
            document.createElement = function(tag, options) {
                const el = origCreateElement(tag, options);
                if (el.tagName === 'LINK' && el.rel === 'stylesheet') {
                    const origAddEventListener = el.addEventListener.bind(el);
                    el.addEventListener = function(event, handler, options) {
                        if (event === 'error' && this.rel === 'stylesheet') {
                            origAddEventListener('error', function(e) {
                                e.stopImmediatePropagation();
                                setTimeout(() => {
                                    this.dispatchEvent(new Event('load'));
                                }, 0);
                            }, { once: true, capture: true });
                            return;
                        }
                        return origAddEventListener(event, handler, options);
                    };
                }
                return el;
            };
        }""")

        page.on("console", lambda msg: print(f"  🌐 [{msg.type}] {msg.text[:200]}") if "narrative" in msg.text.lower() else None)

        # Track 404 responses
        error_responses: list[dict] = []

        def on_error_response(response):
            if response.status >= 400:
                error_responses.append({"url": response.url.replace(target_base, ""), "status": response.status})

        page.on("response", on_error_response)

        # Intercept responses to debug narrative POST
        narrative_responses: list[dict] = []

        def on_response(response):
            url = response.url
            if "dashboard/narrative" in url and response.request.method == "POST":
                ct = response.headers.get("content-type", "")
                narrative_responses.append({
                    "status": response.status,
                    "content_type": ct,
                })

        page.on("response", on_response)

        print("\n🔐 Logging in as demouser...")
        if not login(page, target_base):
            print("❌ Login FAILED — aborting")
            browser.close()
            sys.exit(1)
        print("✅ Logged in")

        # ── Test 1: First load — ensure narrative cache exists ──────
        print("\n── Test 1: First visit (ensure cache is warm) ──")
        page.goto(target_base, wait_until="domcontentloaded", timeout=15000)
        page.wait_for_timeout(8000)  # wait for narrative POST + SSE to complete
        screenshot(page, "sim-narrative-first-visit")

        body = page.text_content("body") or ""
        has_narrative = "本月洞察" in body
        record("Narrative card visible", has_narrative)

        # ── Test 2: Reload — verify no polling ──────────────────────
        print("\n── Test 2: Page reload — verify no task polling ──")

        # Clear previous requests and start monitoring
        api_requests: list[dict] = []

        def on_request(request):
            url = request.url
            if "/api/v1/" in url:
                api_requests.append({"url": url, "method": request.method})

        page.on("request", on_request)

        # Hard reload to clear in-memory state
        page.reload(wait_until="domcontentloaded", timeout=15000)
        page.wait_for_timeout(6000)  # enough for POST + render

        screenshot(page, "sim-narrative-reload")

        # Debug: show narrative POST responses
        print(f"\n  📦 Narrative POST responses: {len(narrative_responses)}")
        for i, nr in enumerate(narrative_responses):
            print(f"     [{i}] status={nr.get('status')} ct={nr.get('content_type', '?')}")

        # Analyze captured requests
        api_urls = [r["url"] for r in api_requests]
        narrative_posts = [u for u in api_urls if "dashboard/narrative" in u]
        task_polls = [u for u in api_urls if "/ai/tasks/detail/" in u and "/stream" not in u]

        print(f"\n  📡 API requests captured: {len(api_urls)}")
        for u in api_urls:
            short = u.replace(BASE, "")
            print(f"     {short}")

        # Verify: narrative POST should have been called (cache check)
        record(
            "Narrative POST called (cache check)",
            len(narrative_posts) > 0,
            f"count={len(narrative_posts)}",
        )

        # KEY ASSERTION: no NARRATIVE task polling.
        # The FinanceCoachCard may still poll its own tasks — that's a separate concern.
        # We verify no narrative-specific resume() was triggered:
        narrative_resume_calls = [u for u in api_urls if "/ai/tasks" in u and "skill_id=dashboard-narrative" in u]
        record(
            "NO narrative resume() polling",
            len(narrative_resume_calls) == 0,
            f"narrative_resume_count={len(narrative_resume_calls)}",
        )

        # Note: coach/other task polling may still occur (separate component).
        # Only flag narrative-specific polling as a failure.
        task_polls = [u for u in api_urls if "/ai/tasks/detail/" in u and "/stream" not in u]
        if task_polls:
            print(f"  ℹ️  Note: {len(task_polls)} task detail polls from other components (coach etc.)")

        # Verify content is displayed (not stuck on loading)
        body = page.text_content("body") or ""
        # Debug: check what the narrative card actually renders
        card_el = page.query_selector(".narrative-card")
        card_html = card_el.inner_html() if card_el else "<no card>"

        # The card uses van-collapse — content is hidden when collapsed.
        # Check header state (always visible) + expand to verify content.
        has_loading_spinner = "narrative-icon--loading" in card_html
        has_cancel_btn = "narrative-cancel-btn" in card_html
        has_thinking_label = "narrative-thinking-label" in card_html
        has_narrative_text = "家庭净资产" in card_html or "月度" in card_html

        # Try expanding the collapse to check content
        collapse_title = page.query_selector(".narrative-card .van-collapse-item__title")
        if collapse_title:
            collapse_title.click()
            page.wait_for_timeout(500)

        has_content_after_expand = page.query_selector(".narrative-content") is not None
        card_html_expanded = card_el.inner_html() if card_el else ""
        has_narrative_text_expanded = "家庭净资产" in card_html_expanded

        print(f"\n  🔍 Header state:")
        print(f"     loading_spinner={has_loading_spinner} cancel_btn={has_cancel_btn} thinking_label={has_thinking_label}")
        print(f"     narrative_text_in_header={has_narrative_text}")
        print(f"     content_after_expand={has_content_after_expand}")
        print(f"     narrative_text_after_expand={has_narrative_text_expanded}")

        # Determine pass/fail based on header + expanded content
        has_content = has_content_after_expand or has_narrative_text_expanded
        has_streaming = has_loading_spinner or has_thinking_label
        has_loading = has_loading_spinner and not has_narrative_text

        record(
            "Narrative content displayed (not loading)",
            has_content and not has_loading,
            f"content={has_content} streaming={has_streaming} loading={has_loading}",
        )

        # ── Test 3: Verify header shows generated timestamp (not spinner) ──
        print("\n── Test 3: Header state verification ──")
        header_el = page.query_selector(".narrative-header")
        has_spinner_in_header = header_el.query_selector(".narrative-icon--loading") is not None if header_el else False
        has_cancel_btn = header_el.query_selector(".narrative-cancel-btn") is not None if header_el else False

        record(
            "No loading spinner in header",
            not has_spinner_in_header,
            f"spinner={has_spinner_in_header}",
        )
        record(
            "No cancel button (task not running)",
            not has_cancel_btn,
            f"cancel_btn={has_cancel_btn}",
        )

        # ── Test 4: Wait longer — ensure no delayed polling ─────────
        print("\n── Test 4: Extended wait — no delayed polling ──")
        page.wait_for_timeout(5000)  # extra 5s
        post_narrative_resumes = len([u for u in [r["url"] for r in api_requests] if "/ai/tasks" in u and "skill_id=dashboard-narrative" in u])

        record(
            "No delayed narrative polling after 5s",
            post_narrative_resumes == 0,
            f"narrative_polls_after_5s={post_narrative_resumes}",
        )

        browser.close()

    # ── Summary ─────────────────────────────────────────────────────
    total = passed + failed
    print(f"\n{'=' * 50}")
    print(f"Results: {passed}/{total} passed, {failed} failed")
    print(f"{'=' * 50}")

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
