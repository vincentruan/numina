from unittest.mock import AsyncMock, MagicMock, patch

from app.models.ai_spending_leak import AISpendingLeak
from app.models.family import Family


def _enable_ai(db, auth_headers, client):
    me = client.get("/api/v1/auth/me", headers=auth_headers).json()
    family_id = me["data"]["family_id"]
    family = db.query(Family).filter_by(id=family_id).first()
    family.ai_enabled = True
    db.commit()
    return family_id


def test_get_spending_leaks_empty(client, auth_headers, db):
    resp = client.get("/api/v1/ai/spending-leaks", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["data"] == []


def test_get_spending_leaks_returns_undismissed(client, auth_headers, db):
    me = client.get("/api/v1/auth/me", headers=auth_headers).json()
    family_id = me["data"]["family_id"]

    from app.models.asset import Asset
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

    from app.models.asset import Asset
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


def _mock_agent_response(leaks: list):
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {"leaks": leaks}
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_resp)
    return mock_client


def test_refresh_spending_leaks(client, auth_headers, db):
    family_id = _enable_ai(db, auth_headers, client)

    from app.models.asset import Asset
    asset = db.query(Asset).filter_by(family_id=family_id).first()
    asset_id = asset.id if asset else 1

    fake_leaks = [{
        "asset_id": asset_id,
        "asset_name": "跑步机",
        "leak_type": "high_idle_cost",
        "severity": "high",
        "estimated_annual_waste": 2400.0,
        "suggestion": "建议出售",
    }]

    with patch("httpx.AsyncClient", return_value=_mock_agent_response(fake_leaks)):
        resp = client.post("/api/v1/ai/spending-leaks/refresh", headers=auth_headers)

    assert resp.status_code == 200
    assert resp.json()["data"]["refreshed"] == 1

    leaks = db.query(AISpendingLeak).filter_by(family_id=family_id, is_dismissed=False).all()
    assert len(leaks) == 1
    assert leaks[0].asset_name == "跑步机"
