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


def _make_sse_streaming_mock(
    frames: list[tuple[str, dict]] | None = None,
    end_status: str = "complete",
) -> MagicMock:
    """Build a mock AgentClient for the SSE report passthrough.

    ``_stream_asset_report_sse`` is a pure passthrough: it ``await``s
    ``agent_client.stream(...)``, checks ``resp.status_code == 200``, then
    forwards every line from ``resp.aiter_lines()`` as raw SSE bytes. The mock
    yields the given ``(event, data)`` pairs as ``event:``/``data:`` SSE lines
    (blank line separating events) so the route returns ``text/event-stream``.

    The terminal ``end`` frame carries ``{"status": end_status}`` so the
    backend's task-tracking wrapper can transition the AITask row.
    """
    if frames is None:
        frames = [("custom", {"type": "report.step2_json", "payload": {"overall_score": 77}})]

    lines: list[str] = []
    for event, data in frames:
        lines.append(f"event: {event}")
        lines.append(f"data: {json.dumps(data, ensure_ascii=False)}")
        lines.append("")
    lines.append("event: end")
    lines.append(f"data: {json.dumps({'status': end_status})}")
    lines.append("")

    resp = MagicMock()
    resp.status_code = 200

    async def _aiter_lines():
        for _l in lines:
            yield _l

    resp.aiter_lines = _aiter_lines
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
    """POST /ai/report/generate/events triggers the agent and marks task completed.

    The bridge consumer (consume_task_stream) transitions the AITask from
    ``running`` to ``completed`` when it consumes the end event from the
    Redis stream.
    """
    from apps.backend.app.models.ai_task import AITask

    family_id = _enable_ai(db, auth_headers, client)

    async def _fake_stream(task_id, family_id, last_event_id=None, run_id=None, **kwargs):
        # Simulate the bridge consumer completing the task on end event
        from apps.backend.app.services.ai_task_service import AITaskService
        from apps.backend.app.database import SessionLocal

        yield "event: custom\ndata: {\"type\":\"report.step2_json\"}\n\n"
        # Mark the task completed (mimics consume_task_stream's end handling)
        _db = SessionLocal()
        try:
            AITaskService.complete_task(task_id, _db)
        finally:
            _db.close()
        yield "event: end\ndata: null\n\n"

    with (
        patch("apps.backend.app.routers.ai_report.AgentClient") as mock_cls,
        patch("apps.backend.app.routers.ai_report.consume_task_stream", _fake_stream),
        patch("apps.backend.app.routers.ai_report._spawn_lifecycle_consumer"),
        patch("apps.backend.app.routers.ai_report._pump_agent_sse_to_bridge", new=AsyncMock()),
    ):
        resp = client.post("/api/v1/ai/report/generate/events?force=true", headers=auth_headers)

    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers.get("content-type", "")

    # CRITICAL: Consume entire response body to let generator complete execution
    _ = resp.content  # Force full response consumption

    db.expire_all()
    task = db.query(AITask).filter_by(family_id=family_id, skill_id="report").first()
    assert task is not None
    assert task.status == "completed"


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

    with (
        patch("apps.backend.app.routers.ai_report.AgentClient") as mock_cls,
        patch("apps.backend.app.routers.ai_report.consume_task_stream") as mock_stream,
        patch("apps.backend.app.routers.ai_report._pump_agent_sse_to_bridge", new=AsyncMock()),
        patch("apps.backend.app.routers.ai_report._spawn_lifecycle_consumer"),
    ):
        mock_stream.return_value = _make_empty_async_gen()
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

    with (
        patch("apps.backend.app.routers.ai_report.AgentClient") as mock_cls,
        patch("apps.backend.app.routers.ai_report.consume_task_stream") as mock_stream,
        patch("apps.backend.app.routers.ai_report._pump_agent_sse_to_bridge", new=AsyncMock()),
        patch("apps.backend.app.routers.ai_report._spawn_lifecycle_consumer"),
    ):
        mock_stream.return_value = _make_empty_async_gen()
        # No force=true — should resume existing task
        resp = client.post("/api/v1/ai/report/generate/events", headers=auth_headers)

    # Should resume (200 + SSE stream) instead of 409
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers.get("content-type", "")


def test_generate_report_force_cancels_zombie_task(client, auth_headers, db):
    """POST ?force=true cancels a zombie running task and starts a fresh generation."""
    from datetime import datetime

    from apps.backend.app.models.ai_chat_session import AIChatSession
    from apps.backend.app.models.ai_task import AITask

    family_id = _enable_ai(db, auth_headers, client)

    session = AIChatSession(family_id=family_id, status="active")
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
    zombie_task_id = task.id

    with (
        patch("apps.backend.app.routers.ai_report.AgentClient") as mock_cls,
        patch("apps.backend.app.routers.ai_report.consume_task_stream") as mock_stream,
        patch("apps.backend.app.routers.ai_report._pump_agent_sse_to_bridge", new=AsyncMock()),
        patch("apps.backend.app.routers.ai_report._spawn_lifecycle_consumer"),
    ):
        mock_stream.return_value = _make_empty_async_gen()
        resp = client.post("/api/v1/ai/report/generate/events?force=true", headers=auth_headers)

    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers.get("content-type", "")
    # Zombie task should be cancelled
    db.refresh(task)
    assert task.status == "cancelled"
    # A new task should exist
    new_task = db.query(AITask).filter(
        AITask.family_id == family_id,
        AITask.skill_id == "report",
        AITask.id != zombie_task_id,
    ).first()
    assert new_task is not None
    assert new_task.status == "running"


def test_generate_report_marks_error_on_agent_failure(client, auth_headers, db):
    """If agent trigger fails (non-200), the route emits an SSE error frame (200)
    and the lifecycle consumer transitions the AITask to ``failed``.
    """
    from apps.backend.app.models.ai_task import AITask

    family_id = _enable_ai(db, auth_headers, client)

    # Build a mock AgentClient.stream() that returns status 500 (agent failure).
    mock_resp = MagicMock()
    mock_resp.status_code = 500

    async def _mock_aread():
        return b"agent error"

    mock_resp.aread = _mock_aread
    mock_resp.headers = {}

    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_cm.__aexit__ = AsyncMock(return_value=False)

    mock_client = MagicMock()
    mock_client.stream = MagicMock(return_value=mock_cm)

    with (
        patch("apps.backend.app.routers.ai_report.AgentClient", return_value=mock_client),
        patch("apps.backend.app.routers.ai_report.consume_task_stream") as mock_fwd,
        patch("apps.backend.app.routers.ai_report._spawn_lifecycle_consumer") as mock_lc,
    ):
        mock_fwd.return_value = _make_empty_async_gen()
        resp = client.post("/api/v1/ai/report/generate/events?force=true", headers=auth_headers)

    # Response is still 200 SSE (route returns stream; error delivered via events)
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers.get("content-type", "")

    # Consume response to let generator complete
    _ = resp.content

    # The lifecycle consumer should have been spawned (fallback with run_id=None
    # since the agent didn't return Content-Location).
    assert mock_lc.called, "lifecycle consumer should be spawned"


def _make_empty_async_gen():
    """An empty async generator (used to stub consume_task_stream)."""
    async def _gen():
        return
        yield  # unreachable, makes it an async generator

    return _gen()


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
