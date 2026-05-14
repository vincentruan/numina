from unittest.mock import AsyncMock, MagicMock, patch

from apps.backend.app.models.ai_spending_leak import AISpendingLeak


def _enable_ai(db, auth_headers, client):
    me = client.get("/api/v1/auth/me", headers=auth_headers).json()
    family_id = me["data"]["family_id"]
    from apps.backend.app.models.ai_provider_config import AIProviderConfig
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


def _mock_streaming_client(chunks: list[str] | None = None):
    """Create a mock httpx client that supports async streaming."""
    if chunks is None:
        chunks = ["分析完成。"]

    async def _aiter_text():
        for chunk in chunks:
            yield chunk

    mock_resp = AsyncMock()
    mock_resp.aiter_text = _aiter_text
    mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_resp.__aexit__ = AsyncMock(return_value=False)

    mock_stream_ctx = AsyncMock()
    mock_stream_ctx.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_stream_ctx.__aexit__ = AsyncMock(return_value=False)

    mock_client = AsyncMock()
    mock_client.stream = MagicMock(return_value=mock_stream_ctx)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    mock_cls = MagicMock(return_value=mock_client)
    mock_cls.__aenter__ = AsyncMock(return_value=mock_client)
    mock_cls.__aexit__ = AsyncMock(return_value=False)
    return mock_cls


def test_get_spending_leaks_empty(client, auth_headers, db):
    resp = client.get("/api/v1/ai/spending-leaks", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["data"] == []


def test_get_spending_leaks_returns_undismissed(client, auth_headers, db):
    me = client.get("/api/v1/auth/me", headers=auth_headers).json()
    family_id = me["data"]["family_id"]

    from apps.backend.app.models.asset import Asset
    asset = db.query(Asset).filter_by(family_id=family_id).first()
    asset_id = asset.id if asset else 1

    active = AISpendingLeak(
        family_id=family_id, asset_id=asset_id, asset_name="测试资产",
        leak_type="high_idle_cost", severity="medium",
        estimated_annual_waste=1200.0, suggestion="建议出售",
    )
    dismissed = AISpendingLeak(
        family_id=family_id, asset_id=asset_id, asset_name="旧资产",
        leak_type="redundant", severity="low",
        estimated_annual_waste=500.0, suggestion="建议整合",
        is_dismissed=True,
    )
    db.add_all([active, dismissed])
    db.commit()

    resp = client.get("/api/v1/ai/spending-leaks", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) == 1
    assert data[0]["asset_name"] == "测试资产"


def test_dismiss_leak(client, auth_headers, db):
    me = client.get("/api/v1/auth/me", headers=auth_headers).json()
    family_id = me["data"]["family_id"]

    from apps.backend.app.models.asset import Asset
    asset = db.query(Asset).filter_by(family_id=family_id).first()
    asset_id = asset.id if asset else 1

    leak = AISpendingLeak(
        family_id=family_id, asset_id=asset_id, asset_name="待关闭",
        leak_type="high_maintenance", severity="high",
        estimated_annual_waste=3000.0, suggestion="建议减少维护",
    )
    db.add(leak)
    db.commit()
    db.refresh(leak)

    resp = client.post(f"/api/v1/ai/spending-leaks/{leak.id}/dismiss", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["ok"] is True

    db.refresh(leak)
    assert leak.is_dismissed is True


def test_dismiss_nonexistent_leak_returns_404(client, auth_headers, db):
    resp = client.post("/api/v1/ai/spending-leaks/99999/dismiss", headers=auth_headers)
    assert resp.status_code == 404


def test_refresh_spending_leaks(client, auth_headers, db):
    """POST /refresh streams response and creates a completed AITask."""
    from apps.backend.app.models.ai_task import AITask

    family_id = _enable_ai(db, auth_headers, client)

    with patch("httpx.AsyncClient", new=_mock_streaming_client()):
        resp = client.post("/api/v1/ai/spending-leaks/refresh", headers=auth_headers)

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/plain")

    db.expire_all()
    task = db.query(AITask).filter_by(family_id=family_id, capability="spending_leak").first()
    assert task is not None
    assert task.status == "completed"


def test_refresh_spending_leaks_409_when_in_progress(client, auth_headers, db):
    """POST /refresh returns 409 if a task is already running."""
    from datetime import datetime

    from apps.backend.app.models.ai_task import AITask

    family_id = _enable_ai(db, auth_headers, client)

    task = AITask(
        family_id=family_id,
        capability="spending_leak",
        status="running",
        started_at=datetime.utcnow(),
    )
    db.add(task)
    db.commit()

    resp = client.post("/api/v1/ai/spending-leaks/refresh", headers=auth_headers)
    assert resp.status_code == 409
