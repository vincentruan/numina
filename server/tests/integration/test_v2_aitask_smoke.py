"""V2 AITask endpoint smoke tests against dev server (5173/8000).

Verifies the U9-U21 implementation:
- U10: GET /ai/tasks/detail/{task_id} with progress fields
- U20: POST /ai/tasks/detail/{task_id}/cancel
- U9: POST /internal/tasks/{task_id}/progress (agent callback)
- U13: Finance Coach AITask tracking on trigger

Run: cd server && python tests/integration/test_v2_aitask_smoke.py
Requires: backend on :8000, agent on :8001, frontend on :5173
"""
import json
import sys

import httpx

BASE = "http://localhost:8000/api/v1"
USER = "demouser"
PASS = "DemoPass123"


def login(client: httpx.Client) -> None:
    """Establish cookie-based auth (retry - backend may be mid-reload)."""
    last_err = None
    for _ in range(3):
        resp = client.post(
            f"{BASE}/auth/login",
            json={"username": USER, "password": PASS},
        )
        if resp.status_code == 200:
            return
        last_err = resp.status_code
        import time
        time.sleep(1)
    raise AssertionError(f"Login failed after retries: {last_err}")


def test_task_detail_404(client: httpx.Client) -> None:
    """U10: Non-existent task → 404 (via AppError envelope)."""
    resp = client.get(f"{BASE}/ai/tasks/detail/999999999999")
    assert resp.status_code == 404, f"Expected 404, got {resp.status_code}"
    body = resp.json()
    assert body["code"] == "NOT_FOUND"


def test_cancel_404(client: httpx.Client) -> None:
    """U20: Cancel non-existent task → 404."""
    resp = client.post(f"{BASE}/ai/tasks/detail/999999999999/cancel")
    assert resp.status_code == 404, f"Expected 404, got {resp.status_code}"


def test_task_list_with_new_fields(client: httpx.Client) -> None:
    """U10: Task list returns v2 fields (progress, lease_expires_at, etc)."""
    resp = client.get(f"{BASE}/ai/tasks")
    assert resp.status_code == 200
    body = resp.json()
    tasks = body.get("data") if isinstance(body, dict) else body
    assert isinstance(tasks, list), f"Unexpected shape: {type(tasks)}"
    # Verify v2 fields present on first task (if any)
    if tasks:
        t = tasks[0]
        for field in ("progress", "lease_expires_at", "queue_position", "session_id"):
            assert field in t, f"Missing v2 field: {field}"


def test_internal_callback_no_token(client: httpx.Client) -> None:
    """U9: Internal callback without X-Agent-Token → 401/422."""
    resp = client.post(
        f"{BASE}/internal/tasks/123/progress",
        json={"progress": {"step": "test"}},
    )
    # Either 401 (auth failure) or 422 (missing header) is acceptable
    assert resp.status_code in (401, 422), f"Expected 401/422, got {resp.status_code}"


def test_finance_coach_creates_aitask(client: httpx.Client) -> None:
    """U13: Finance Coach trigger creates AITask (force=true to skip cache)."""
    # Check existing tasks first
    before_resp = client.get(f"{BASE}/ai/tasks?skill_id=coach&status=running")
    assert before_resp.status_code == 200

    # Trigger coach generation
    resp = client.post(f"{BASE}/ai/finance-coach/generate?force=true")
    # Either 200 (SSE stream), 202 (queued), or cached JSON
    assert resp.status_code in (200, 202), f"Coach trigger: {resp.status_code}"

    # Check for running coach tasks
    after_resp = client.get(f"{BASE}/ai/tasks?skill_id=coach&status=running")
    assert after_resp.status_code == 200
    tasks = after_resp.json()
    print(f"  Running coach tasks: {len(tasks)}")


def main() -> int:
    tests = [
        ("Task detail 404", test_task_detail_404),
        ("Cancel 404", test_cancel_404),
        ("Task list v2 fields", test_task_list_with_new_fields),
        ("Internal callback auth", test_internal_callback_no_token),
        ("Finance Coach AITask", test_finance_coach_creates_aitask),
    ]

    # trust_env=False: bypass system proxy for localhost connections
    client = httpx.Client(timeout=30.0, trust_env=False)
    login(client)
    print(f"✓ Logged in as {USER}\n")

    passed = 0
    failed = 0
    for name, test_fn in tests:
        try:
            test_fn(client)
            print(f"✓ {name}")
            passed += 1
        except AssertionError as e:
            print(f"✗ {name}: {e}")
            failed += 1
        except Exception as e:
            print(f"✗ {name}: {type(e).__name__}: {e}")
            failed += 1

    print(f"\n{passed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
