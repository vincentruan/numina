"""Tests for import_report router (parse + confirm endpoints)."""
from unittest.mock import AsyncMock, patch

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
        "apps.backend.app.routers.import_report._call_agent_parse",
        new=AsyncMock(return_value=mock_agent_resp),
    ), patch(
        "apps.backend.app.routers.import_report._extract_pdf_text",
        return_value="贵州茅台 100股",
    ), patch(
        # C 方案：纯文本路径测试，mock 为非图片型 PDF（跳过 vision 渲染分流）
        "apps.backend.app.routers.import_report._is_image_based_pdf",
        return_value=False,
    ):
        resp = client.post(
            "/api/v1/import/parse-pdf",
            files={"file": ("test.pdf", b"%PDF-1.4 fake content", "application/pdf")},
            headers=auth_headers,
        )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data["items"]) == 1
    assert data["items"][0]["name"] == "贵州茅台"
    assert data["items"][0]["action"] in ("update", "create")


def test_parse_returns_400_for_empty_pdf(client, auth_headers):
    with patch(
        "apps.backend.app.routers.import_report._extract_pdf_text",
        return_value="",
    ):
        resp = client.post(
            "/api/v1/import/parse-pdf",
            files={"file": ("scan.pdf", b"%PDF-1.4 fake scan", "application/pdf")},
            headers=auth_headers,
        )
    assert resp.status_code == 400


def test_parse_returns_200_with_guidance_when_agent_finds_nothing(client, auth_headers):
    """R7a: agent returns zero items → 200 with empty items + guidance message."""
    empty = {"source": "", "report_date": None, "items": []}
    with patch(
        "apps.backend.app.routers.import_report._call_agent_parse",
        new=AsyncMock(return_value=empty),
    ), patch(
        "apps.backend.app.routers.import_report._extract_pdf_text",
        return_value="这不是金融文档",
    ), patch(
        # C 方案：纯文本路径测试，mock 为非图片型 PDF
        "apps.backend.app.routers.import_report._is_image_based_pdf",
        return_value=False,
    ):
        resp = client.post(
            "/api/v1/import/parse-pdf",
            files={"file": ("other.pdf", b"%PDF-1.4 other content", "application/pdf")},
            headers=auth_headers,
        )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["items"] == []
    assert data["message"] is not None


def test_parse_image_based_pdf_passes_thread_id_and_image_paths(client, auth_headers):
    """C 方案（vision）：图片型 PDF → 渲染页图 → 传 thread_id + image_paths 给 agent。

    验证 backend 把 vision 路径所需的契约传给 agent：thread_id（让 agent 用
    同一沙箱，PNG 已落 uploads/）+ image_paths（容器虚拟路径列表）。
    """
    mock_agent_resp = {"source": "", "report_date": None, "items": []}
    captured: dict = {}

    async def _capture_call(text, family_id, thread_id=None, image_paths=None):
        captured["text"] = text
        captured["thread_id"] = thread_id
        captured["image_paths"] = image_paths
        return mock_agent_resp

    with patch(
        "apps.backend.app.routers.import_report._call_agent_parse",
        new=AsyncMock(side_effect=_capture_call),
    ), patch(
        "apps.backend.app.routers.import_report._extract_pdf_text",
        return_value="",  # 图片型 PDF 文本通常为空
    ), patch(
        "apps.backend.app.routers.import_report._is_image_based_pdf",
        return_value=True,
    ), patch(
        "apps.backend.app.routers.import_report._render_pdf_pages_to_sandbox",
        return_value=["/mnt/user-data/uploads/page_1.png", "/mnt/user-data/uploads/page_2.png"],
    ):
        resp = client.post(
            "/api/v1/import/parse-pdf",
            files={"file": ("scan.pdf", b"%PDF-1.4 fake scan", "application/pdf")},
            headers=auth_headers,
        )
    assert resp.status_code == 200  # R7a: agent 返空 items → 200 + message
    # thread_id + image_paths 必须传给 agent
    assert captured["thread_id"] is not None
    assert captured["thread_id"].startswith("importparse-thread-")
    assert captured["image_paths"] == [
        "/mnt/user-data/uploads/page_1.png",
        "/mnt/user-data/uploads/page_2.png",
    ]


def test_parse_text_pdf_does_not_pass_image_paths(client, auth_headers):
    """C 方案：文本型 PDF 走纯文本路径，不传 thread_id/image_paths（向后兼容）。"""
    mock_agent_resp = {"source": "", "report_date": None, "items": []}
    captured: dict = {}

    async def _capture_call(text, family_id, thread_id=None, image_paths=None):
        captured["thread_id"] = thread_id
        captured["image_paths"] = image_paths
        return mock_agent_resp

    with patch(
        "apps.backend.app.routers.import_report._call_agent_parse",
        new=AsyncMock(side_effect=_capture_call),
    ), patch(
        "apps.backend.app.routers.import_report._extract_pdf_text",
        return_value="贵州茅台 100股 市值158000",
    ), patch(
        "apps.backend.app.routers.import_report._is_image_based_pdf",
        return_value=False,
    ):
        resp = client.post(
            "/api/v1/import/parse-pdf",
            files={"file": ("text.pdf", b"%PDF-1.4 fake text", "application/pdf")},
            headers=auth_headers,
        )
    assert resp.status_code == 200  # R7a: agent 返空 items → 200 + message
    # 纯文本路径不传 vision 契约
    assert captured["thread_id"] is None
    assert captured["image_paths"] is None


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
    from apps.backend.app.models.asset import Asset
    from apps.backend.app.models.category import Category
    from apps.backend.app.models.user import User

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
    """matched_asset_id 属于其他家庭时，应跳过并返回错误。"""
    from apps.backend.app.models.asset import Asset
    from apps.backend.app.models.category import Category
    from apps.backend.app.models.user import User

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
                "target_model": "asset",
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
    data = resp.json()["data"]
    # Cross-family asset cannot be updated — returns error, not fallback create
    assert data["updated"] == 0
    assert data["skipped"] == 1
    assert data["items"][0]["status"] == "error"
