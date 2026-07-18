"""Tests for AI asset health report endpoints."""

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


def _make_two_phase_streaming_mock(markdown_path: str = "/tmp/test-report.md"):
    """Build a mock AgentClient for the two-phase report pipeline.

    proxy_report_events calls _call_agent_skill twice:
      Phase 1 (report_generate) → capability.end with result.success=True + result.path
      Phase 2 (report_structured) → capability.end with summary containing STRUCTURED_DATA JSON

    The mock's .stream() returns the phase-1 stream on the first call and the
    phase-2 stream on the second, matching the call sequence.
    """
    import json

    phase1_chunks = [
        json.dumps({"type": "capability.end", "result": {"success": True, "path": markdown_path}}),
    ]
    structured = (
        "报告解析完成。\n"
        "<!-- STRUCTURED_DATA "
        '{"overall_score": 75, "data_completeness_score": 0.8, "narrative": "示例", "sections": {}, '
        '"indicators": ['
        '{"key": "liquidity", "label": "流动性", "score": 4, "narrative": "良好"}, '
        '{"key": "debt", "label": "负债", "score": 3, "narrative": "适中"}, '
        '{"key": "growth", "label": "增长", "score": 5, "narrative": "强劲"}'
        "]}"
        " -->"
    )
    phase2_chunks = [
        json.dumps({"type": "capability.end", "result": {"summary": structured}}),
    ]

    def _make_resp(chunks):
        async def _aiter_lines():
            for chunk in chunks:
                yield chunk

        resp = MagicMock()
        resp.aiter_lines = _aiter_lines
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=resp)
        cm.__aexit__ = AsyncMock(return_value=False)
        return cm

    streams = [_make_resp(phase1_chunks), _make_resp(phase2_chunks)]
    call_state = {"i": 0}

    def _stream(*a, **k):
        cm = streams[min(call_state["i"], len(streams) - 1)]
        call_state["i"] += 1
        return cm

    mock_client = MagicMock()
    mock_client.stream = MagicMock(side_effect=_stream)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_cls = MagicMock(return_value=mock_client)
    return mock_cls


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
    """POST /ai/report/generate/events streams response and creates a completed AITask."""
    from apps.backend.app.models.ai_task import AITask

    family_id = _enable_ai(db, auth_headers, client)

    with patch("apps.backend.app.routers._ai_events_helper.AgentClient", new=_make_two_phase_streaming_mock()):
        resp = client.post("/api/v1/ai/report/generate/events", headers=auth_headers)

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/x-ndjson")

    # CRITICAL: Consume entire response body to let generator complete execution
    # TestClient.post() returns after first chunk, but generator hasn't finished yet
    _ = resp.content  # Force full response consumption

    db.expire_all()
    task = db.query(AITask).filter_by(family_id=family_id, capability="report").first()
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

    with patch("apps.backend.app.routers._ai_events_helper.AgentClient", new=_make_two_phase_streaming_mock()):
        resp = client.post("/api/v1/ai/report/generate/events", headers=auth_headers)

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/x-ndjson")


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
        capability="report",
        status="running",
        session_id=session.id,
        started_at=datetime.utcnow(),
    )
    db.add(task)
    db.commit()

    with patch("apps.backend.app.routers._ai_events_helper.AgentClient", new=_make_two_phase_streaming_mock()):
        resp = client.post("/api/v1/ai/report/generate/events", headers=auth_headers)

    # Should resume (200 + NDJSON stream) instead of 409
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/x-ndjson")


def test_generate_report_marks_error_on_agent_failure(client, auth_headers, db):
    """If agent streaming fails, AITask is marked as failed and error event is yielded."""
    from apps.backend.app.models.ai_task import AITask

    family_id = _enable_ai(db, auth_headers, client)

    async def _aiter_raises():
        raise Exception("Agent error")
        yield  # make it an async generator

    mock_resp = MagicMock()
    mock_resp.aiter_lines = _aiter_raises

    mock_stream_cm = MagicMock()
    mock_stream_cm.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_stream_cm.__aexit__ = AsyncMock(return_value=False)

    mock_client = MagicMock()
    mock_client.stream = MagicMock(return_value=mock_stream_cm)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    mock_cls = MagicMock(return_value=mock_client)

    with patch("apps.backend.app.routers._ai_events_helper.AgentClient", new=mock_cls):
        resp = client.post("/api/v1/ai/report/generate/events", headers=auth_headers)

    # Response should still be 200 with error event (helper catches errors)
    assert resp.status_code == 200

    # CRITICAL: Consume response to let generator's except/finally block execute
    _ = resp.content

    # The task should be marked failed in DB
    db.expire_all()
    task = db.query(AITask).filter_by(family_id=family_id, capability="report").first()
    assert task is not None
    assert task.status == "failed"


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
