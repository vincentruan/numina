"""Tests for multi-format import endpoints — U2 verification."""

import io
from datetime import UTC, datetime
from unittest.mock import patch

from apps.backend.app.models.draft_import import DraftImport


def _unwrap(resp_json: dict) -> dict | list:
    """Unwrap the API envelope: {"code": "OK", "data": ...} → data."""
    if "data" in resp_json:
        return resp_json["data"]  # type: ignore[no-any-return]
    return resp_json


def _mock_agent_parse(items: list[dict] | None = None) -> dict:
    """Default agent parse response with mixed asset + liability items."""
    if items is None:
        items = [
            {
                "name": "招商银行储蓄",
                "target_model": "asset",
                "asset_type": "financial",
                "category_hint": "银行存款",
                "current_value": 50000,
                "currency": "CNY",
                "confidence": 0.92,
            },
            {
                "name": "信用卡欠款",
                "target_model": "liability",
                "category": "credit_card",
                "original_amount": 30000,
                "remaining_amount": 15000,
                "monthly_payment": 3000,
                "currency": "CNY",
                "confidence": 0.85,
            },
        ]
    return {"source": "test", "report_date": "2026-08-03", "items": items}


# ---------------------------------------------------------------------------
# Tests: /parse endpoint
# ---------------------------------------------------------------------------

class TestParseEndpoint:
    """POST /import/parse tests."""

    @patch("apps.backend.app.routers.import_report._is_image_based_pdf", return_value=False)
    @patch("apps.backend.app.routers.import_report._extract_pdf_text", return_value="Some bank statement text " * 20)
    @patch("apps.backend.app.routers.import_report._call_agent_parse")
    def test_parse_pdf_creates_draft(self, mock_agent, mock_extract, mock_is_img, client, auth_headers, db):
        """POST /parse with PDF creates draft_import with status=pending."""
        mock_agent.return_value = _mock_agent_parse()

        pdf_content = b"%PDF-1.4 fake pdf content"
        resp = client.post(
            "/api/v1/import/parse",
            files={"file": ("statement.pdf", pdf_content, "application/pdf")},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = _unwrap(resp.json())
        assert "items" in data
        assert data["draft_id"] is not None

        # Verify draft record created.
        draft = db.query(DraftImport).filter_by(id=data["draft_id"]).first()
        assert draft is not None
        assert draft.status == "pending"
        assert draft.source_format == "pdf"
        assert draft.file_hash is not None
        assert len(draft.get_parsed_items()) == len(data["items"])

    @patch("apps.backend.app.routers.import_report._save_image_to_sandbox")
    @patch("apps.backend.app.routers.import_report._call_agent_parse")
    def test_parse_image(self, mock_agent, mock_save, client, auth_headers, db):
        """POST /parse with PNG image creates draft and returns items."""
        mock_agent.return_value = _mock_agent_parse()
        mock_save.return_value = "/mnt/user-data/uploads/upload.png"

        png_header = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        resp = client.post(
            "/api/v1/import/parse",
            files={"file": ("screenshot.png", png_header, "image/png")},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = _unwrap(resp.json())
        assert data["draft_id"] is not None
        assert any(i["target_model"] == "asset" for i in data["items"])
        assert any(i["target_model"] == "liability" for i in data["items"])

    @patch("apps.backend.app.routers.import_report._call_agent_parse")
    def test_parse_csv(self, mock_agent, client, auth_headers, db):
        """POST /parse with CSV creates draft from tabular extraction."""
        mock_agent.return_value = _mock_agent_parse()

        csv_content = "name,value,type\nTest Asset,1000,financial\n"
        resp = client.post(
            "/api/v1/import/parse",
            files={"file": ("data.csv", csv_content.encode(), "text/csv")},
            headers=auth_headers,
        )
        assert resp.status_code == 200

    @patch("apps.backend.app.routers.import_report._is_image_based_pdf", return_value=False)
    @patch("apps.backend.app.routers.import_report._extract_pdf_text", return_value="Some text " * 30)
    @patch("apps.backend.app.routers.import_report._call_agent_parse")
    def test_parse_zero_items_returns_message(self, mock_agent, mock_extract, mock_is_img, client, auth_headers, db):
        """POST /parse with unrecognizable file returns empty items + message (R7a)."""
        mock_agent.return_value = {"source": "", "report_date": None, "items": []}

        pdf_content = b"%PDF-1.4 empty content " + b"x" * 300
        resp = client.post(
            "/api/v1/import/parse",
            files={"file": ("garbage.pdf", pdf_content, "application/pdf")},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = _unwrap(resp.json())
        assert data["items"] == []
        assert data["message"] is not None
        assert "未在文件中识别到财务数据" in data["message"]

    def test_parse_file_too_large(self, client, auth_headers, db):
        """POST /parse with oversized Excel returns 413."""
        big_content = b"\x00" * (11 * 1024 * 1024)
        resp = client.post(
            "/api/v1/import/parse",
            files={"file": ("big.xlsx", big_content, "application/vnd.openxmlformats-officedocument.spreadsheetml.xlsx")},
            headers=auth_headers,
        )
        assert resp.status_code == 413

    def test_parse_unsupported_format(self, client, auth_headers, db):
        """POST /parse with unsupported file type returns error."""
        resp = client.post(
            "/api/v1/import/parse",
            files={"file": ("doc.zip", b"PK\x03\x04fake", "application/zip")},
            headers=auth_headers,
        )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Tests: /confirm endpoint
# ---------------------------------------------------------------------------

class TestConfirmEndpoint:
    """POST /import/confirm tests."""

    def test_confirm_mixed_assets_liabilities(self, client, auth_headers, db):
        """POST /confirm with mixed items creates records in both models."""
        from apps.backend.app.models.category import Category

        # Get a valid category from seeded data.
        cat = db.query(Category).first()
        cat_name = cat.name if cat else ""

        me_resp = client.get("/api/v1/auth/me", headers=auth_headers)
        user_data = me_resp.json().get("data", me_resp.json())
        family_id = int(user_data["family_id"])
        user_id = int(user_data["id"])

        # Create a draft first.
        draft = DraftImport(
            family_id=family_id,
            user_id=user_id,
            source_filename="test.pdf",
            source_format="pdf",
            status="pending",
        )
        draft.set_parsed_items([])
        db.add(draft)
        db.flush()

        resp = client.post(
            "/api/v1/import/confirm",
            json={
                "draft_id": str(draft.id),
                "items": [
                    {
                        "temp_id": "tmp_1",
                        "name": "测试资产",
                        "target_model": "asset",
                        "asset_type": "financial",
                        "category_hint": cat_name,
                        "current_value": 10000,
                        "currency": "CNY",
                        "action": "create",
                    },
                    {
                        "temp_id": "tmp_2",
                        "name": "测试负债",
                        "target_model": "liability",
                        "liability_category": "credit_card",
                        "original_amount": 5000,
                        "remaining_amount": 3000,
                        "currency": "CNY",
                        "action": "create",
                    },
                ],
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = _unwrap(resp.json())
        assert data["created"] == 2
        assert len(data["items"]) == 2

        # Verify draft status updated.
        db.refresh(draft)
        assert draft.status == "committed"
        assert len(draft.get_committed_record_ids()) == 2


# ---------------------------------------------------------------------------
# Tests: /history endpoint
# ---------------------------------------------------------------------------

class TestHistoryEndpoint:
    """GET /import/history tests."""

    def test_history_returns_records(self, client, auth_headers, db):
        """GET /history returns last 20 records with correct metadata."""
        me_resp = client.get("/api/v1/auth/me", headers=auth_headers)
        user_data = me_resp.json().get("data", me_resp.json())
        family_id = int(user_data["family_id"])
        user_id = int(user_data["id"])

        for i in range(3):
            d = DraftImport(
                family_id=family_id,
                user_id=user_id,
                source_filename=f"file_{i}.pdf",
                source_format="pdf",
                status="committed" if i < 2 else "pending",
            )
            # Stagger created_at to avoid SQLite second-precision ties.
            d.created_at = datetime(2026, 8, 3, 12, 0, i, tzinfo=UTC)
            d.set_parsed_items([{"name": f"item_{j}"} for j in range(i + 1)])
            db.add(d)
        db.flush()

        resp = client.get("/api/v1/import/history", headers=auth_headers)
        assert resp.status_code == 200
        data = _unwrap(resp.json())
        assert len(data) == 3
        assert data[0]["source_filename"] == "file_2.pdf"  # Most recent first.
        assert data[0]["status"] == "pending"


# ---------------------------------------------------------------------------
# Tests: /rollback endpoint
# ---------------------------------------------------------------------------

class TestRollbackEndpoint:
    """POST /import/rollback/{draft_id} tests."""

    def test_rollback_sets_archived(self, client, auth_headers, db):
        """POST /rollback sets is_archived=True and updates status."""
        from apps.backend.app.models.asset import Asset
        from apps.backend.app.models.category import Category
        from apps.backend.app.models.user import User
        from apps.backend.app.utils.snowflake import next_id

        me_resp = client.get("/api/v1/auth/me", headers=auth_headers)
        user_data = me_resp.json().get("data", me_resp.json())
        family_id = int(user_data["family_id"])
        user_id = int(user_data["id"])

        category = db.query(Category).first()

        asset = Asset(
            id=next_id(),
            user_id=user_id,
            family_id=family_id,
            category_id=category.id,
            name="Rollback Test Asset",
            asset_type="financial",
            current_value=10000,
            status="in_use",
        )
        db.add(asset)
        db.flush()

        draft = DraftImport(
            family_id=family_id,
            user_id=user_id,
            source_filename="rollback_test.pdf",
            source_format="pdf",
            status="committed",
        )
        draft.set_parsed_items([])
        draft.set_committed_record_ids([str(asset.id)])
        db.add(draft)
        db.flush()

        resp = client.post(
            f"/api/v1/import/rollback/{draft.id}",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = _unwrap(resp.json())
        assert data["status"] == "rolled_back"
        assert data["archived_count"] == 1

        db.refresh(asset)
        assert asset.is_archived is True

        db.refresh(draft)
        assert draft.status == "rolled_back"

    def test_rollback_not_found(self, client, auth_headers, db):
        """POST /rollback with invalid ID returns 404."""
        resp = client.post(
            "/api/v1/import/rollback/999999999999",
            headers=auth_headers,
        )
        assert resp.status_code == 404

    def test_rollback_wrong_status(self, client, auth_headers, db):
        """POST /rollback with pending status returns 409."""
        me_resp = client.get("/api/v1/auth/me", headers=auth_headers)
        user_data = me_resp.json().get("data", me_resp.json())
        family_id = int(user_data["family_id"])
        user_id = int(user_data["id"])

        draft = DraftImport(
            family_id=family_id,
            user_id=user_id,
            source_filename="pending.pdf",
            source_format="pdf",
            status="pending",
        )
        draft.set_parsed_items([])
        db.add(draft)
        db.flush()

        resp = client.post(
            f"/api/v1/import/rollback/{draft.id}",
            headers=auth_headers,
        )
        assert resp.status_code == 409


# ---------------------------------------------------------------------------
# Tests: extraction helpers (no auth needed)
# ---------------------------------------------------------------------------

class TestExtractionHelpers:
    """Multi-format extraction helper tests."""

    def test_excel_extraction(self):
        """Excel upload produces structured text."""
        import openpyxl
        from apps.backend.app.routers.import_report import _extract_excel_to_text

        wb = openpyxl.Workbook()
        ws = wb.active
        assert ws is not None
        ws.append(["name", "value", "type"])
        ws.append(["Test Asset", 1000, "financial"])
        ws.append(["Test Liability", 500, "loan"])
        buf = io.BytesIO()
        wb.save(buf)
        wb.close()

        text = _extract_excel_to_text(buf.getvalue(), "excel")
        assert "Test Asset" in text
        assert "Test Liability" in text

    def test_csv_extraction(self):
        """CSV upload produces structured text."""
        from apps.backend.app.routers.import_report import _extract_excel_to_text

        csv_bytes = "name,value\nAsset A,1000\nAsset B,2000\n".encode("utf-8")
        text = _extract_excel_to_text(csv_bytes, "csv")
        assert "Asset A" in text
        assert "Asset B" in text

    def test_file_hash_deterministic(self):
        """SHA-256 hash is deterministic."""
        from apps.backend.app.routers.import_report import _compute_file_hash

        data = b"test data for hashing"
        h1 = _compute_file_hash(data)
        h2 = _compute_file_hash(data)
        assert h1 == h2
        assert len(h1) == 64

    def test_detect_format_by_extension(self):
        """Format detection falls back to extension."""
        from apps.backend.app.routers.import_report import _detect_format

        assert _detect_format("photo.png", "application/octet-stream") == "image"
        assert _detect_format("data.csv", "text/plain") == "csv"
        assert _detect_format("report.xlsx", "application/octet-stream") == "excel"
