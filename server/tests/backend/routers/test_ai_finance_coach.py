"""finance_coach trigger endpoint: cache hit / force / circuit breaker (Plan A T8)."""
from unittest.mock import patch

from apps.backend.app.models.family import Family
from apps.backend.app.models.user import User


def _enable_ai(db, auth_headers, client):
    """Enable AI for the test user's family + promote to owner (mirror test_ai_report)."""
    from apps.backend.app.models.ai_provider_config import AIProviderConfig

    me = client.get("/api/v1/auth/me", headers=auth_headers).json()
    family_id = me["data"]["family_id"]
    family = db.query(Family).filter_by(id=family_id).first()
    family.ai_enabled = True
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


def _make_fake_task():
    """Create a mock AITask for testing."""
    from datetime import UTC, datetime

    class _FakeTask:
        id = 12345
        family_id = 1
        skill_id = "coach"
        status = "running"
        session_id = "test-session-123"
        started_at = datetime.now(UTC)
        completed_at = None
        queue_position = None
    return _FakeTask()


def test_generate_returns_cached_when_fresh(client, auth_headers, db_session):
    """A cached finance_coach row younger than 8h is returned as JSON (non-stream)."""
    from apps.backend.app.services.finance_coach_cache import upsert_skill_result

    family_id = _enable_ai(db_session, auth_headers, client)
    upsert_skill_result(
        db_session, family_id, "finance_coach",
        {"suggestions": [{"id": "s1", "severity": "high", "title": "x", "action": "y",
                          "target_type": "liability", "target_id": "1", "cta_label": "去"}]},
    )
    db_session.commit()

    with patch("apps.backend.app.routers.ai_finance_coach.check_circuit_blocked", return_value=None):
        resp = client.post("/api/v1/ai/finance-coach/generate", headers=auth_headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "cached"
    assert body["report"]["suggestions"][0]["id"] == "s1"


def test_generate_force_bypasses_cache(client, auth_headers, db_session):
    """force=true skips the cache and regenerates (AITask-tracked bridge consumer)."""
    from apps.backend.app.services.finance_coach_cache import upsert_skill_result

    family_id = _enable_ai(db_session, auth_headers, client)
    upsert_skill_result(db_session, family_id, "finance_coach", {"suggestions": []})
    db_session.commit()

    async def _fake_stream(*args, **kwargs):
        yield "event: custom\ndata: {}\n\n"
        yield "event: end\ndata: null\n\n"

    class _FakeSession:
        id = "test-session-123"

    with patch("apps.backend.app.routers.ai_finance_coach.check_circuit_blocked", return_value=None), \
         patch("apps.backend.app.routers.ai_finance_coach.AITaskService") as task_svc, \
         patch("apps.backend.app.routers.ai_finance_coach.ChatSessionService") as sess_svc, \
         patch("apps.backend.app.routers.ai_finance_coach.AgentClient") as agent_cls, \
         patch("apps.backend.app.routers.ai_finance_coach.consume_task_stream", side_effect=_fake_stream):
        task_svc.get_running_task.return_value = None
        task_svc.get_any_running_task.return_value = None
        task_svc.create_task.return_value = _make_fake_task()

        async def _fake_create_session(*a, **kw):
            return _FakeSession()

        sess_svc.create_session = _fake_create_session
        agent_instance = agent_cls.return_value

        async def _fake_post(*a, **kw):
            class _R:
                status_code = 200
                text = "ok"
                headers = {"Content-Location": "/internal/gateway/runs/finance-coach/t/run-123"}
            return _R()

        agent_instance.post = _fake_post
        resp = client.post(
            "/api/v1/ai/finance-coach/generate?force=true", headers=auth_headers
        )
    # force path streams (StreamingResponse 200)
    assert resp.status_code == 200
    # consume the streamed body so the generator completes
    _ = resp.content


def test_generate_blocked_by_circuit_breaker(client, auth_headers, db_session):
    """When the circuit breaker is open, returns the blocked response."""
    _enable_ai(db_session, auth_headers, client)
    blocked = {"status": "circuit_open", "message": "熔断中", "retry_after": 60}
    with patch("apps.backend.app.routers.ai_finance_coach.check_circuit_blocked", return_value=blocked):
        resp = client.post("/api/v1/ai/finance-coach/generate", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    # The backend response envelope wraps the dict in {"data": {...}}.
    data = body.get("data", body)
    assert data["status"] == "circuit_open"
