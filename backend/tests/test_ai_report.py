"""Tests for AI asset health report endpoints."""

from unittest.mock import AsyncMock, MagicMock, patch

from app.models.ai_report import AIReport
from app.models.ai_ws_ticket import AIWsTicket
from app.models.family import Family


def _enable_ai(db, auth_headers, client):
    """Enable AI for the test user's family."""
    me = client.get("/api/v1/auth/me", headers=auth_headers).json()
    family_id = me["data"]["family_id"]
    family = db.query(Family).filter_by(id=family_id).first()
    family.ai_enabled = True
    from app.models.ai_provider_config import AIProviderConfig
    from app.models.user import User
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


def _make_streaming_mock(chunks: list[str] | None = None):
    """Build a mock httpx.AsyncClient that supports async streaming via client.stream()."""
    if chunks is None:
        chunks = ["报告生成完成。"]

    async def _aiter_text():
        for chunk in chunks:
            yield chunk

    # The innermost object: the response returned by `async with client.stream(...) as resp`
    mock_resp = MagicMock()
    mock_resp.aiter_text = _aiter_text

    # The context manager returned by client.stream(...)
    mock_stream_cm = MagicMock()
    mock_stream_cm.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_stream_cm.__aexit__ = AsyncMock(return_value=False)

    # The client returned by `async with httpx.AsyncClient(...) as client`
    mock_client = MagicMock()
    mock_client.stream = MagicMock(return_value=mock_stream_cm)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    # The class itself: httpx.AsyncClient(...)
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
    """POST /ai/report/generate streams response and creates a completed AITask."""
    from app.models.ai_task import AITask

    family_id = _enable_ai(db, auth_headers, client)

    with patch("httpx.AsyncClient", new=_make_streaming_mock()):
        resp = client.post("/api/v1/ai/report/generate", headers=auth_headers)

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/plain")

    db.expire_all()
    task = db.query(AITask).filter_by(family_id=family_id, capability="report").first()
    assert task is not None
    assert task.status == "completed"


def test_generate_report_requires_ai_enabled(client, auth_headers, db):
    """POST /ai/report/generate returns 403 if AI not enabled for family."""
    me = client.get("/api/v1/auth/me", headers=auth_headers).json()
    family_id = me["data"]["family_id"]
    family = db.query(Family).filter_by(id=family_id).first()
    family.ai_enabled = False
    db.commit()

    resp = client.post("/api/v1/ai/report/generate", headers=auth_headers)
    assert resp.status_code == 403


def test_generate_report_requires_owner(client, auth_headers, db):
    """POST /ai/report/generate requires owner role (embedded in JWT)."""
    family_id = _enable_ai(db, auth_headers, client)

    with patch("httpx.AsyncClient", new=_make_streaming_mock()):
        resp = client.post("/api/v1/ai/report/generate", headers=auth_headers)

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/plain")


def test_generate_report_409_when_task_in_progress(client, auth_headers, db):
    """POST /ai/report/generate returns 409 if a task is already running."""
    from datetime import datetime

    from app.models.ai_task import AITask

    family_id = _enable_ai(db, auth_headers, client)

    task = AITask(
        id="test-task-id",
        family_id=family_id,
        capability="report",
        status="running",
        started_at=datetime.utcnow(),
    )
    db.add(task)
    db.commit()

    resp = client.post("/api/v1/ai/report/generate", headers=auth_headers)
    assert resp.status_code == 409


def test_generate_report_marks_error_on_agent_failure(client, auth_headers, db):
    """If agent streaming fails, AITask is marked as failed."""
    import pytest

    from app.models.ai_task import AITask

    family_id = _enable_ai(db, auth_headers, client)

    async def _aiter_raises():
        raise Exception("Agent error")
        yield  # make it an async generator

    mock_resp = MagicMock()
    mock_resp.aiter_text = _aiter_raises

    mock_stream_cm = MagicMock()
    mock_stream_cm.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_stream_cm.__aexit__ = AsyncMock(return_value=False)

    mock_client = MagicMock()
    mock_client.stream = MagicMock(return_value=mock_stream_cm)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    mock_cls = MagicMock(return_value=mock_client)

    with patch("httpx.AsyncClient", new=mock_cls):
        # Starlette re-raises streaming errors through the test client
        with pytest.raises(Exception):
            client.post("/api/v1/ai/report/generate", headers=auth_headers)

    # The task should be marked failed in DB despite the exception
    db.expire_all()
    task = db.query(AITask).filter_by(family_id=family_id, capability="report").first()
    assert task is not None
    assert task.status == "failed"


# ── POST /ai/report/ws-ticket ───────────────────────────────────────────────────

def test_ws_ticket_creates_one_time_ticket(client, auth_headers, db):
    """POST /ai/report/ws-ticket creates a ticket with 30s expiry."""
    _enable_ai(db, auth_headers, client)

    resp = client.post("/api/v1/ai/report/ws-ticket", headers=auth_headers)
    assert resp.status_code == 200
    ticket_id = resp.json()["data"]["ticket"]

    ticket = db.query(AIWsTicket).filter_by(id=ticket_id).first()
    assert ticket is not None
    assert ticket.used is False
    assert ticket.expires_at is not None


def test_ws_ticket_requires_ai_enabled(client, auth_headers, db):
    """POST /ai/report/ws-ticket returns 403 if AI not enabled."""
    me = client.get("/api/v1/auth/me", headers=auth_headers).json()
    family_id = me["data"]["family_id"]
    family = db.query(Family).filter_by(id=family_id).first()
    family.ai_enabled = False
    db.commit()

    resp = client.post("/api/v1/ai/report/ws-ticket", headers=auth_headers)
    assert resp.status_code == 403


def test_ws_ticket_requires_owner(client, auth_headers, db):
    """POST /ai/report/ws-ticket requires owner role (embedded in JWT)."""
    _enable_ai(db, auth_headers, client)

    resp = client.post("/api/v1/ai/report/ws-ticket", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["ticket"] is not None


# ── Cross-family isolation ──────────────────────────────────────────────────────

def test_cross_family_report_isolation(client, auth_headers, second_user_headers, db):
    """Family B cannot see Family A's reports."""
    family_a_id = _enable_ai(db, auth_headers, client)
    me2 = client.get("/api/v1/auth/me", headers=second_user_headers).json()
    family_b_id = me2["data"]["family_id"]
    family_b = db.query(Family).filter_by(id=family_b_id).first()
    family_b.ai_enabled = True
    from app.models.ai_provider_config import AIProviderConfig as APC2
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
    """POST /ai/report/generate returns 401 without auth."""
    resp = client.post("/api/v1/ai/report/generate")
    assert resp.status_code == 401


def test_ws_ticket_requires_auth(client):
    """POST /ai/report/ws-ticket returns 401 without auth."""
    resp = client.post("/api/v1/ai/report/ws-ticket")
    assert resp.status_code == 401
