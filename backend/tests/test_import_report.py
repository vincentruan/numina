"""Tests for import_report router (parse + confirm endpoints)."""
from unittest.mock import AsyncMock, patch

import pytest


# ---------------------------------------------------------------------------
# Parse endpoint tests
# ---------------------------------------------------------------------------

def test_parse_returns_preview(client, auth_headers, db):
    mock_agent_resp = {
        "source": "华泰证券",
        "report_date": "2026-04-01",
        "items": [
            {
                "name": "贵州茅台",
                "asset_type": "financial",
                "category_hint": "股票",
                "current_value": 158000.0,
                "currency": "CNY",
                "quantity": 100,
            }
        ],
    }
    with patch(
        "app.routers.import_report._call_agent_parse",
        new=AsyncMock(return_value=mock_agent_resp),
    ):
        with patch(
            "app.routers.import_report._extract_pdf_text",
            return_value="贵州茅台 100股",
        ):
            resp = client.post(
                "/api/v1/import/parse-pdf",
                files={"file": ("test.pdf", b"fake-pdf", "application/pdf")},
                headers=auth_headers,
            )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data["items"]) == 1
    assert data["items"][0]["name"] == "贵州茅台"
    assert data["items"][0]["action"] in ("update", "create")


def test_parse_returns_400_for_empty_pdf(client, auth_headers):
    with patch(
        "app.routers.import_report._extract_pdf_text",
        return_value="",
    ):
        resp = client.post(
            "/api/v1/import/parse-pdf",
            files={"file": ("scan.pdf", b"fake-pdf", "application/pdf")},
            headers=auth_headers,
        )
    assert resp.status_code == 400


def test_parse_returns_422_when_agent_finds_nothing(client, auth_headers):
    empty = {"source": "", "report_date": None, "items": []}
    with patch(
        "app.routers.import_report._call_agent_parse",
        new=AsyncMock(return_value=empty),
    ):
        with patch(
            "app.routers.import_report._extract_pdf_text",
            return_value="这不是金融文档",
        ):
            resp = client.post(
                "/api/v1/import/parse-pdf",
                files={"file": ("other.pdf", b"fake-pdf", "application/pdf")},
                headers=auth_headers,
            )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Confirm endpoint tests
# ---------------------------------------------------------------------------

def test_confirm_creates_new_asset(client, auth_headers):
    payload = {
        "items": [
            {
                "temp_id": "tmp_002",
                "name": "新能源ETF",
                "asset_type": "financial",
                "category_hint": "基金",
                "current_value": 50000.0,
                "currency": "CNY",
                "quantity": None,
                "notes": None,
                "matched_asset_id": None,
                "action": "create",
            }
        ]
    }
    resp = client.post("/api/v1/import/confirm", json=payload, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["created"] == 1
    assert data["updated"] == 0


def test_confirm_updates_existing_asset(client, auth_headers, db):
    from app.models.asset import Asset
    from app.models.user import User
    from app.models.category import Category

    # Get the registered user and a category
    user = db.query(User).filter(User.username == "testuser").first()
    category = db.query(Category).first()

    # Seed an existing asset
    existing = Asset(
        user_id=user.id,
        family_id=user.family_id,
        category_id=category.id,
        name="贵州茅台",
        asset_type="financial",
        purchase_price=150000.0,
        current_value=150000.0,
        currency="CNY",
        status="in_use",
    )
    db.add(existing)
    db.commit()
    db.refresh(existing)

    payload = {
        "items": [
            {
                "temp_id": "tmp_001",
                "name": "贵州茅台",
                "asset_type": "financial",
                "category_hint": "股票",
                "current_value": 168000.0,
                "currency": "CNY",
                "quantity": None,
                "notes": None,
                "matched_asset_id": str(existing.id),
                "action": "update",
            }
        ]
    }
    resp = client.post("/api/v1/import/confirm", json=payload, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["updated"] == 1
    assert data["created"] == 0

    db.refresh(existing)
    assert existing.current_value == 168000.0


def test_confirm_skips_cross_family_asset(client, auth_headers, second_user_headers, db):
    """matched_asset_id 属于其他家庭时，应降级为 create。"""
    from app.models.asset import Asset
    from app.models.user import User
    from app.models.category import Category

    # Get second user (different family) and seed an asset for them
    other_user = db.query(User).filter(User.username == "testuser2").first()
    category = db.query(Category).first()

    other_asset = Asset(
        user_id=other_user.id,
        family_id=other_user.family_id,
        category_id=category.id,
        name="贵州茅台",
        asset_type="financial",
        purchase_price=150000.0,
        current_value=150000.0,
        currency="CNY",
        status="in_use",
    )
    db.add(other_asset)
    db.commit()
    db.refresh(other_asset)

    payload = {
        "items": [
            {
                "temp_id": "tmp_003",
                "name": "贵州茅台",
                "asset_type": "financial",
                "category_hint": "股票",
                "current_value": 168000.0,
                "currency": "CNY",
                "quantity": None,
                "notes": None,
                "matched_asset_id": str(other_asset.id),
                "action": "update",
            }
        ]
    }
    resp = client.post("/api/v1/import/confirm", json=payload, headers=auth_headers)
    assert resp.status_code == 200
    # Cross-family asset cannot be updated — should fall back to create
    assert resp.json()["data"]["created"] == 1
    assert resp.json()["data"]["updated"] == 0
