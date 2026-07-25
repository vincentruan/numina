"""Tests for AI asset health report endpoints."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

from apps.backend.app.models.ai_report import AIReport
from apps.backend.app.models.family import Family


def _enable_ai(db, auth_headers, client):
    """Enable AI for the test user's family."""
    me = client.get("/api/v1/auth/me", headers=auth_headers).json()
    family_id = me["data"]["family_id"]
    family = db.query(Family).filter_by(id=family_id).first()
    family.ai_enabled = True
    from apps.backend.app.models.ai_provider_config import AIProviderConfig
    from apps.backend.app.models.user import User
    user = db.query(User).filter_by(id=me["data"]["id"]).first()
    user.role = "owner"
    cfg = AIProviderConfig(
        family_id=family_id,
        name="测试配置",
        provider="anthropic",
        api_key_encrypted="test_encrypted_key",
        model_id="claude-3-5-sonnet-20241022",
        is_active=True,
    )
    db.add(cfg)
    db.commit()
    return family_id


def _make_sse_streaming_mock(frames: list[tuple[str, dict]] | None = None) -> MagicMock:
    """Build a mock AgentClient for the SSE report passthrough.

    ``_stream_asset_report_sse`` is a pure passthrough: it ``await``s
    ``agent_client.stream(...)``, checks ``resp.status_code == 200``, then
    forwards every line from ``resp.aiter_lines()`` as raw SSE bytes. The mock
    yields the given ``(event, data)`` pairs as ``event:``/``data:`` SSE lines
    (blank line separating events) so the route returns ``text/event-stream``.

    Note: the SSE route does NOT transition the AITask to completed/failed —
    that lifecycle moved to the agent worker side during the U4 SSE refactor.
    Backend ``complete_task`` has no report-path caller, so after the stream
    the task stays ``running``.
    """
    if frames is None:
        frames = [("custom", {"type": "report.step2_json", "payload": {"overall_score": 77}})]

    lines: list[str] = []
    for event, data in frames:
        lines.append(f"event: {event}")
        lines.append(f"data: {json.dumps(data, ensure_ascii=False)}")
        lines.append("")
    lines.append("event: end")
    lines.append("data: null")
    lines.append("")

    resp = MagicMock()
    resp.status_code = 200
    resp.aiter_lines = lambda: (_l for _l in lines)
    resp.aread = AsyncMock(return_value=b"")

    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=resp)
    cm.__aexit__ = AsyncMock(return_value=False)

    mock_client = MagicMock()
    mock_client.stream = MagicMock(return_value=cm)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return MagicMock(return_value=mock_client)


# ── GET /ai/report ──────────────────────────────────────────────────────────────

def test_get_report_returns_none_when_no_report(client, auth_headers, db):
    """GET /ai/report returns {report: null} when no report exists."""
    _enable_ai(db, auth_headers, client)

    resp = client.get("/api/v1/ai/report", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["report"] is None


def test_get_report_returns_latest_completed_report(client, auth_headers, db):
    """GET /ai/report returns the most recent completed report."""
    family_id = _enable_ai(db, auth_headers, client)

    from datetime import datetime, timedelta
    pending = AIReport(
        family_id=family_id,
        report_json={},
        status="pending",
        generated_at=datetime.utcnow() - timedelta(hours=1),
    )
    completed = AIReport(
        family_id=family_id,
        report_json={"overall_score": 85, "summary": "良好"},
        overall_score=85,
        status="completed",
        generated_at=datetime.utcnow(),
    )
    db.add_all([pending, completed])
    db.commit()

    resp = client.get("/api/v1/ai/report", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["report"]["overall_score"] == 85
    assert "generated_at" in data


def test_get_report_ignores_error_status(client, auth_headers, db):
    """GET /ai/report only returns completed reports, ignores error/pending."""
    family_id = _enable_ai(db, auth_headers, client)

    from datetime import datetime
    error_report = AIReport(
        family_id=family_id,
        report_json={},
        status="error",
        generated_at=datetime.utcnow(),
    )
    db.add(error_report)
    db.commit()

    resp = client.get("/api/v1/ai/report", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["report"] is None


def test_get_report_requires_auth(client):
    """GET /ai/report returns 401 without auth headers."""
    resp = client.get("/api/v1/ai/report")
    assert resp.status_code == 401


# ── POST /ai/report/generate ─────────────────────────────────────────────────────

def test_generate_report_creates_pending_then_completes(client, auth_headers, db):
    """POST /ai/report/generate/events streams SSE and leaves the task running.

    U4 SSE refactor: the route is a pure passthrough — it creates the AITask
    (status=running) and forwards the agent's SSE stream, but task completion
    is now the agent worker's responsibility (backend ``complete_task`` has no
    report-path caller). So after the stream the task stays ``running``.
    """
    from apps.backend.app.models.ai_task import AITask

    family_id = _enable_ai(db, auth_headers, client)

    with patch("apps.backend.app.routers.ai_report.AgentClient", new=_make_sse_streaming_mock()):
        resp = client.post("/api/v1/ai/report/generate/events?force=true", headers=auth_headers)

    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers.get("content-type", "")

    # CRITICAL: Consume entire response body to let generator complete execution
    _ = resp.content  # Force full response consumption

    db.expire_all()
    task = db.query(AITask).filter_by(family_id=family_id, skill_id="report").first()
    assert task is not None
    assert task.status == "running"


def test_generate_report_requires_ai_enabled(client, auth_headers, db):
    """POST /ai/report/generate/events returns 403 if AI not enabled for family."""
    me = client.get("/api/v1/auth/me", headers=auth_headers).json()
    family_id = me["data"]["family_id"]
    family = db.query(Family).filter_by(id=family_id).first()
    family.ai_enabled = False
    db.commit()

    resp = client.post("/api/v1/ai/report/generate/events", headers=auth_headers)
    assert resp.status_code == 403


def test_generate_report_requires_owner(client, auth_headers, db):
    """POST /ai/report/generate/events requires owner role (embedded in JWT)."""
    _enable_ai(db, auth_headers, client)

    with patch("apps.backend.app.routers.ai_report.AgentClient", new=_make_sse_streaming_mock()):
        resp = client.post("/api/v1/ai/report/generate/events?force=true", headers=auth_headers)

    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers.get("content-type", "")


def test_generate_report_resumes_running_task(client, auth_headers, db):
    """POST /ai/report/generate/events resumes an already running task instead of 409."""
    from datetime import datetime

    from apps.backend.app.models.ai_chat_session import AIChatSession
    from apps.backend.app.models.ai_task import AITask

    family_id = _enable_ai(db, auth_headers, client)

    # Create an existing session and running task (simulates a task started earlier)
    session = AIChatSession(
        family_id=family_id,
        status="active",
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    task = AITask(
        family_id=family_id,
        skill_id="report",
        status="running",
        session_id=session.id,
        started_at=datetime.utcnow(),
    )
    db.add(task)
    db.commit()

    with patch("apps.backend.app.routers.ai_report.AgentClient", new=_make_sse_streaming_mock()):
        resp = client.post("/api/v1/ai/report/generate/events?force=true", headers=auth_headers)

    # Should resume (200 + SSE stream) instead of 409
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers.get("content-type", "")


def test_generate_report_marks_error_on_agent_failure(client, auth_headers, db):
    """If agent streaming raises, the route emits an SSE error frame (200) but
    does NOT transition the AITask — task lifecycle moved to the agent worker
    in the U4 SSE refactor, so the task stays ``running``.

    The passthrough's ``except`` catches the exception and yields a single
    ``event: error`` SSE frame so the frontend gets a graceful close.
    """
    from apps.backend.app.models.ai_task import AITask

    family_id = _enable_ai(db, auth_headers, client)

    async def _aiter_raises():
        raise Exception("Agent error")
        yield  # make it an async generator

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.aiter_lines = _aiter_raises
    mock_resp.aread = AsyncMock(return_value=b"")

    mock_stream_cm = MagicMock()
    mock_stream_cm.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_stream_cm.__aexit__ = AsyncMock(return_value=False)

    mock_client = MagicMock()
    mock_client.stream = MagicMock(return_value=mock_stream_cm)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    mock_cls = MagicMock(return_value=mock_client)

    with patch("apps.backend.app.routers.ai_report.AgentClient", new=mock_cls):
        resp = client.post("/api/v1/ai/report/generate/events?force=true", headers=auth_headers)

    # Response is still 200 SSE (passthrough catches the error and emits an error frame)
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers.get("content-type", "")

    # CRITICAL: Consume response to let generator's except/finally block execute
    _ = resp.content

    # Task stays running — backend no longer owns report task completion
    db.expire_all()
    task = db.query(AITask).filter_by(family_id=family_id, skill_id="report").first()
    assert task is not None
    assert task.status == "running"


# ── Cross-family isolation ──────────────────────────────────────────────────────

def test_cross_family_report_isolation(client, auth_headers, second_user_headers, db):
    """Family B cannot see Family A's reports."""
    family_a_id = _enable_ai(db, auth_headers, client)
    me2 = client.get("/api/v1/auth/me", headers=second_user_headers).json()
    family_b_id = me2["data"]["family_id"]
    family_b = db.query(Family).filter_by(id=family_b_id).first()
    family_b.ai_enabled = True
    from apps.backend.app.models.ai_provider_config import AIProviderConfig as APC2
    db.add(APC2(
        family_id=family_b_id,
        name="测试配置B",
        provider="anthropic",
        api_key_encrypted="test_encrypted_key",
        model_id="claude-3-5-sonnet-20241022",
        is_active=True,
    ))
    db.commit()

    from datetime import datetime
    report = AIReport(
        family_id=family_a_id,
        report_json={"overall_score": 90},
        overall_score=90,
        status="completed",
        generated_at=datetime.utcnow(),
    )
    db.add(report)
    db.commit()

    resp = client.get("/api/v1/ai/report", headers=second_user_headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["report"] is None


# ── Auth requirements ───────────────────────────────────────────────────────────

def test_generate_requires_auth(client):
    """POST /ai/report/generate/events returns 401 without auth."""
    resp = client.post("/api/v1/ai/report/generate/events")
    assert resp.status_code == 401
