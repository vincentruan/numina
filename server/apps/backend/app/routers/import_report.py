"""Multi-format intelligent import endpoints.

- POST /api/v1/import/parse        — Upload any supported file, returns preview
- POST /api/v1/import/confirm      — Confirm import (multi-model: Asset + Liability)
- POST /api/v1/import/confirm-via-agent — Confirm via MCP batch tools (legacy)
- GET  /api/v1/import/history      — Recent import history
- POST /api/v1/import/rollback/{id} — Rollback a committed import
"""

import csv
import hashlib
import io
import logging
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import httpx
import pdfplumber
import pymupdf
from fastapi import APIRouter, Depends, File, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from apps.backend.app.auth.deps import require_adult
from apps.backend.app.config import settings
from apps.backend.app.database import get_db
from apps.backend.app.errors import AppError, ErrorCode
from apps.backend.app.models.asset import Asset
from apps.backend.app.models.category import Category
from apps.backend.app.models.draft_import import DraftImport
from apps.backend.app.models.liability import Liability
from apps.backend.app.models.user import User
from apps.backend.app.services.agent_client import AgentClient

router = APIRouter(prefix="/import", tags=["import"])
logger = logging.getLogger(__name__)

# R1 / KTD5: split file size limits by type.
_MAX_IMAGE_BYTES = 25 * 1024 * 1024  # 25 MB for images (phone photos can be 5-15 MB)
_MAX_EXCEL_BYTES = 10 * 1024 * 1024  # 10 MB for Excel/CSV (typically <1 MB)

# Image-based PDF detection threshold (chars/page).
_MIN_CHARS_PER_PAGE_FOR_VISION = 50
_MAX_RENDERED_PAGES = 10

# Supported MIME types (R1).
_SUPPORTED_IMAGE_TYPES = {"image/png", "image/jpeg"}
_SUPPORTED_PDF_TYPES = {"application/pdf"}
_SUPPORTED_EXCEL_TYPES = {
    "application/vnd.openxmlformats-officedocument.spreadsheetml.xlsx",
    "application/vnd.ms-excel",
    "text/csv",
}
# Extension fallback when content-type is unreliable.
_EXCEL_EXTENSIONS = {".xlsx", ".xls", ".csv"}

# Rollback window (R24).
_ROLLBACK_WINDOW_DAYS = 30


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _detect_format(filename: str | None, content_type: str | None) -> str:
    """Detect file format from content-type with extension fallback.

    Returns one of: "image", "pdf", "excel", "csv".
    Raises IMPORT_PDF_UNREADABLE if format is unsupported.
    """
    if content_type in _SUPPORTED_IMAGE_TYPES:
        return "image"
    if content_type in _SUPPORTED_PDF_TYPES:
        return "pdf"
    if content_type in _SUPPORTED_EXCEL_TYPES:
        if content_type == "text/csv":
            return "csv"
        return "excel"

    # Fallback: check file extension.
    ext = Path(filename or "").suffix.lower()
    if ext in {".png", ".jpg", ".jpeg"}:
        return "image"
    if ext == ".pdf":
        return "pdf"
    if ext == ".csv":
        return "csv"
    if ext in _EXCEL_EXTENSIONS:
        return "excel"

    raise AppError(ErrorCode.IMPORT_PDF_UNREADABLE)


def _compute_file_hash(data: bytes) -> str:
    """Compute SHA-256 hash for duplicate detection (R13, R21)."""
    return hashlib.sha256(data).hexdigest()


def _validate_file_size(data: bytes, fmt: str) -> None:
    """Validate file size against format-specific limits (R1, KTD5)."""
    limit = _MAX_EXCEL_BYTES if fmt in ("excel", "csv") else _MAX_IMAGE_BYTES
    if len(data) > limit:
        raise AppError(ErrorCode.IMPORT_FILE_TOO_LARGE)


# Magic bytes for format validation (P1-9 security hardening).
_MAGIC_BYTES = {
    "image": [b"\x89PNG", b"\xff\xd8\xff"],  # PNG, JPEG
    "pdf": [b"%PDF"],
}


def _validate_magic_bytes(data: bytes, fmt: str) -> None:
    """Validate file magic bytes match the claimed format.

    Raises IMPORT_PDF_UNREADABLE if the file content doesn't match the expected format.
    Excel/CSV are not validated (ZIP/XML structures are complex to check via magic bytes).
    """
    if fmt not in _MAGIC_BYTES:
        return  # No magic byte check for excel/csv
    if len(data) < 4:
        raise AppError(ErrorCode.IMPORT_PDF_UNREADABLE)
    if not any(data.startswith(magic) for magic in _MAGIC_BYTES[fmt]):
        raise AppError(ErrorCode.IMPORT_PDF_UNREADABLE)


def _save_image_to_sandbox(
    data: bytes, family_id: str, thread_id: str, filename: str = "upload.png"
) -> str:
    """Save uploaded image to family-scoped sandbox for agent view_image.

    Returns the virtual path for agent's view_image tool.
    """
    data_root = Path(settings.DATA_ROOT).expanduser() if hasattr(settings, "DATA_ROOT") else Path.home() / ".numina" / "data"
    uploads_dir = (
        data_root / "workspaces" / "users" / str(family_id)
        / "threads" / thread_id / "user-data" / "uploads"
    )
    uploads_dir.mkdir(parents=True, exist_ok=True)

    # Determine extension from content — whitelist to prevent unexpected file types.
    ext = Path(filename).suffix.lower()
    if ext not in {".png", ".jpg", ".jpeg"}:
        ext = ".png"
    save_path = uploads_dir / f"upload{ext}"
    save_path.write_bytes(data)
    return f"/mnt/user-data/uploads/upload{ext}"


def _extract_excel_to_text(data: bytes, fmt: str) -> str:
    """Extract rows from Excel/CSV and serialize to structured text.

    Each row becomes a JSON-like line: {"col_a": val1, "col_b": val2, ...}.
    The agent classifies columns by content heuristics.
    """
    if fmt == "csv":
        text_data = data.decode("utf-8-sig", errors="replace")
        reader = csv.DictReader(io.StringIO(text_data))
        import itertools
        rows = list(itertools.islice(reader, 200))
    else:
        import openpyxl

        wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        try:
            ws = wb.active
            if ws is None:
                return ""
            rows_list = list(ws.iter_rows(values_only=True))
            if not rows_list:
                return ""
            headers = [str(c) if c is not None else f"col_{i}" for i, c in enumerate(rows_list[0])]
            rows = []
            for row in rows_list[1:]:
                rows.append(dict(zip(headers, row, strict=False)))
        finally:
            wb.close()

    if not rows:
        return ""

    import json
    lines = [json.dumps(row, ensure_ascii=False, default=str) for row in rows[:200]]
    return "\n".join(lines)


def _extract_pdf_text(data: bytes) -> str:
    """从 PDF 字节提取纯文本；扫描件/图片 PDF 返回空字符串。"""
    try:
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            pages = [page.extract_text() or "" for page in pdf.pages]
        return "\n".join(pages).strip()
    except Exception:
        return ""


def _is_image_based_pdf(data: bytes, text: str) -> bool:
    """检测 PDF 是否为图片型（扫描件）。"""
    if text and len(text.strip()) >= 200:
        try:
            with pymupdf.open(stream=data, filetype="pdf") as doc:
                page_count = doc.page_count or 1
            return len(text.strip()) / page_count < _MIN_CHARS_PER_PAGE_FOR_VISION
        except Exception:
            return False
    return True


def _render_pdf_pages_to_sandbox(
    data: bytes, family_id: str, thread_id: str
) -> list[str]:
    """渲染 PDF 每页为 PNG，落 family-scoped 沙箱 uploads 目录。"""
    data_root = Path(settings.DATA_ROOT).expanduser() if hasattr(settings, "DATA_ROOT") else Path.home() / ".numina" / "data"
    uploads_dir = (
        data_root / "workspaces" / "users" / str(family_id)
        / "threads" / thread_id / "user-data" / "uploads"
    )
    uploads_dir.mkdir(parents=True, exist_ok=True)

    virtual_paths: list[str] = []
    try:
        with pymupdf.open(stream=data, filetype="pdf") as doc:
            page_count = min(doc.page_count, _MAX_RENDERED_PAGES)
            if doc.page_count > _MAX_RENDERED_PAGES:
                logger.warning(
                    "[parse] PDF has %d pages, rendering only first %d family=%s",
                    doc.page_count, _MAX_RENDERED_PAGES, family_id,
                )
            for i in range(page_count):
                page = doc[i]
                pix = page.get_pixmap(matrix=pymupdf.Matrix(2, 2))
                filename = f"page_{i + 1}.png"
                pix.save(str(uploads_dir / filename))
                virtual_paths.append(f"/mnt/user-data/uploads/{filename}")
    except Exception as e:
        logger.error("[parse] PDF page render failed family=%s err=%s", family_id, e, exc_info=True)
        return []
    return virtual_paths


async def _call_agent_parse(
    text: str, family_id: str, thread_id: str | None = None, image_paths: list[str] | None = None
) -> dict:
    """调用 Agent 微服务解析文本/图片，返回原始 dict。"""
    agent_client = AgentClient(family_id, timeout=120.0)
    payload: dict = {"text": text}
    if thread_id:
        payload["thread_id"] = thread_id
    if image_paths:
        payload["image_paths"] = image_paths
    resp = await agent_client.post("/import/parse", json=payload)
    resp.raise_for_status()
    return resp.json()


def _match_asset(name: str, family_id: str, db: Session) -> Asset | None:
    """按名称匹配现有资产（精确 > 模糊，同家庭内）。"""
    asset = (
        db.query(Asset)
        .filter(
            Asset.family_id == family_id,
            Asset.name == name,
            Asset.is_archived.is_(False),
        )
        .first()
    )
    if asset:
        return asset
    assets = (
        db.query(Asset)
        .filter(Asset.family_id == family_id, Asset.is_archived.is_(False))
        .all()
    )
    for a in assets:
        if name in a.name or a.name in name:
            return a
    return None


def _resolve_category_id(category_hint: str, db: Session) -> str | None:
    """按 category_hint 查找系统分类 ID。"""
    cat = db.query(Category).filter(Category.name == category_hint).first()
    return str(cat.id) if cat else None


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class ImportPreviewItem(BaseModel):
    temp_id: str
    name: str
    target_model: str = "asset"  # "asset" | "liability" (R5)
    asset_type: str = "financial"
    category_hint: str = ""
    current_value: float | None = None
    currency: str = "CNY"
    quantity: float | None = None
    notes: str | None = None
    matched_asset_id: str | None = None
    matched_asset_name: str | None = None
    action: str = "create"  # "update" | "create"
    warning: str | None = None
    confidence: float | None = None  # R7: 0.0–1.0
    # Liability-specific fields (R6)
    original_amount: float | None = None
    remaining_amount: float | None = None
    monthly_payment: float | None = None
    interest_rate: float | None = None
    liability_category: str | None = None  # mortgage/car_loan/credit_card/other


class ImportPreview(BaseModel):
    source: str
    report_date: str | None
    items: list[ImportPreviewItem]
    message: str | None = None  # R7a: guidance when zero items
    draft_id: str | None = None  # Draft import ID for tracking


class ConfirmItem(BaseModel):
    temp_id: str
    name: str
    target_model: str = "asset"  # "asset" | "liability"
    asset_type: str = "financial"
    category_hint: str = ""
    current_value: float | None = None
    currency: str = "CNY"
    quantity: float | None = None
    notes: str | None = None
    matched_asset_id: str | None = None
    action: str = "create"  # "update" | "create"
    # Liability-specific fields (R6)
    original_amount: float | None = None
    remaining_amount: float | None = None
    monthly_payment: float | None = None
    interest_rate: float | None = None
    liability_category: str | None = None


class ConfirmRequest(BaseModel):
    items: list[ConfirmItem]
    draft_id: str | None = None  # Link back to draft_imports record


class ConfirmResultItem(BaseModel):
    temp_id: str
    status: str  # "created" | "updated" | "skipped" | "error"
    id: str | None = None
    name: str | None = None
    error: str | None = None


class ConfirmResponse(BaseModel):
    updated: int = 0
    created: int = 0
    skipped: int = 0
    items: list[ConfirmResultItem] = []


class HistoryItem(BaseModel):
    id: str
    source_filename: str
    source_format: str
    status: str
    item_count: int
    created_at: str
    can_rollback: bool = False


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/parse", response_model=ImportPreview)
async def parse_file(
    file: UploadFile = File(...),
    current_user: User = Depends(require_adult),
    db: Session = Depends(get_db),
):
    """Upload any supported file, extract content, call agent, return preview.

    R3: single unified /parse endpoint. Server-side format detection (R4).
    Creates a DraftImport record for tracking (R21).
    """
    family_id = str(current_user.family_id)
    filename = file.filename or "upload"

    # Detect format first (R4: conditional dispatch) — only needs metadata, not bytes.
    fmt = _detect_format(filename, file.content_type)

    # Check size before reading full content to avoid OOM on large uploads.
    limit = _MAX_EXCEL_BYTES if fmt in ("excel", "csv") else _MAX_IMAGE_BYTES
    if file.size is not None and file.size > limit:
        raise AppError(ErrorCode.IMPORT_FILE_TOO_LARGE)

    raw = await file.read()
    _validate_file_size(raw, fmt)
    _validate_magic_bytes(raw, fmt)
    file_hash = _compute_file_hash(raw)

    # Pre-generate thread_id for sandbox path.
    thread_id = f"importparse-thread-{uuid.uuid4().hex[:12]}"
    text = ""
    image_paths: list[str] = []

    # --- Format-specific extraction (KTD2: conditional dispatch) ---
    if fmt == "image":
        # Image: save to sandbox, agent reads via view_image.
        vpath = _save_image_to_sandbox(raw, family_id, thread_id, filename)
        image_paths = [vpath]

    elif fmt == "pdf":
        # PDF: reuse existing extraction pipeline.
        text = _extract_pdf_text(raw)
        if _is_image_based_pdf(raw, text):
            image_paths = _render_pdf_pages_to_sandbox(raw, family_id, thread_id)
            if not image_paths:
                raise AppError(ErrorCode.IMPORT_PDF_UNREADABLE)
            text = text or ""
        if not text and not image_paths:
            raise AppError(ErrorCode.IMPORT_PDF_UNREADABLE)

    elif fmt in ("excel", "csv"):
        # Excel/CSV: serialize rows to structured text.
        text = _extract_excel_to_text(raw, fmt)
        if not text:
            raise AppError(ErrorCode.IMPORT_NO_ASSETS_FOUND)

    # --- Call agent ---
    try:
        agent_result = await _call_agent_parse(
            text,
            family_id,
            thread_id=thread_id if image_paths else None,
            image_paths=image_paths or None,
        )
    except httpx.TimeoutException as e:
        raise AppError(ErrorCode.IMPORT_AGENT_TIMEOUT) from e
    except Exception as e:
        logger.error("Agent parse failed: %s", e)
        raise AppError(ErrorCode.AI_SERVICE_UNAVAILABLE) from e

    raw_items: list[dict] = agent_result.get("items", [])

    # Build preview items with target_model + confidence.
    preview_items: list[ImportPreviewItem] = []
    for raw_item in raw_items:
        item_name = raw_item.get("name") or raw_item.get("code") or raw_item.get("asset_name")
        if not item_name:
            continue

        target_model = raw_item.get("target_model", "asset")
        confidence = raw_item.get("confidence")
        current_value = raw_item.get("current_value") or raw_item.get("market_value")

        # Asset matching (only for target_model=asset).
        matched_asset_id = None
        matched_asset_name = None
        action = "create"
        warning = None

        if target_model == "asset":
            matched = _match_asset(item_name, str(current_user.family_id), db)
            if matched:
                matched_asset_id = str(matched.id)
                matched_asset_name = matched.name
                action = "update"
            if current_value is None:
                warning = "amount_not_recognized"

        preview_items.append(ImportPreviewItem(
            temp_id=f"tmp_{uuid.uuid4().hex[:8]}",
            name=item_name,
            target_model=target_model,
            asset_type=raw_item.get("asset_type", "financial"),
            category_hint=raw_item.get("category_hint", ""),
            current_value=current_value,
            currency=raw_item.get("currency", "CNY"),
            quantity=raw_item.get("quantity"),
            notes=raw_item.get("notes"),
            matched_asset_id=matched_asset_id,
            matched_asset_name=matched_asset_name,
            action=action,
            warning=warning,
            confidence=confidence,
            # Liability fields (R6).
            original_amount=raw_item.get("original_amount"),
            remaining_amount=raw_item.get("remaining_amount"),
            monthly_payment=raw_item.get("monthly_payment"),
            interest_rate=raw_item.get("interest_rate"),
            liability_category=raw_item.get("category") or raw_item.get("liability_category"),
        ))

    # R7a: zero items → return with guidance message (not an error).
    message = None
    if not preview_items:
        message = "未在文件中识别到财务数据，请确认文件格式正确（支持 PDF、截图、Excel、CSV）"

    # R21: create DraftImport record.
    draft = DraftImport(
        family_id=current_user.family_id,
        user_id=current_user.id,
        source_filename=filename,
        source_format=fmt,
        file_hash=file_hash,
        status="pending",
    )
    draft.set_parsed_items([item.model_dump() for item in preview_items])
    db.add(draft)
    db.flush()  # Get the draft.id.

    return ImportPreview(
        source=agent_result.get("source", ""),
        report_date=agent_result.get("report_date"),
        items=preview_items,
        message=message,
        draft_id=str(draft.id),
    )


# Keep backward-compatible alias for any callers still hitting /parse-pdf.
@router.post("/parse-pdf", response_model=ImportPreview)
async def parse_pdf_compat(
    file: UploadFile = File(...),
    current_user: User = Depends(require_adult),
    db: Session = Depends(get_db),
):
    """Backward-compatible alias for /parse (PDF only)."""
    return await parse_file(file=file, current_user=current_user, db=db)


@router.post("/confirm", response_model=ConfirmResponse)
def confirm_import(
    req: ConfirmRequest,
    current_user: User = Depends(require_adult),
    db: Session = Depends(get_db),
):
    """Confirm import: create/update Assets and Liabilities, update draft.

    R13: routes creates through MCP batch tools, updates through direct DB.
    R15: returns per-item results.
    R22: updates draft_import status to "committed".
    """
    result_items: list[ConfirmResultItem] = []
    stats = {"updated": 0, "created": 0, "skipped": 0}

    # Split items by target_model and action.
    asset_creates = [i for i in req.items if i.target_model == "asset" and i.action == "create"]
    liability_creates = [i for i in req.items if i.target_model == "liability" and i.action == "create"]
    # Only asset updates are supported (liability matching is not implemented in /parse).
    updates = [i for i in req.items if i.target_model == "asset" and i.action == "update" and i.matched_asset_id]

    # --- Asset updates (direct DB write) ---
    for item in updates:
        # Asset update.
        asset = (
            db.query(Asset)
            .filter(
                Asset.id == item.matched_asset_id,
                Asset.family_id == current_user.family_id,
            )
            .first()
        )
        if asset:
            asset.current_value = Decimal(str(item.current_value)) if item.current_value is not None else None
            if item.currency:
                asset.currency = item.currency
            if item.notes:
                asset.notes = item.notes
            stats["updated"] += 1
            result_items.append(ConfirmResultItem(
                temp_id=item.temp_id, status="updated",
                id=str(asset.id), name=asset.name,
            ))
        else:
            stats["skipped"] += 1
            result_items.append(ConfirmResultItem(
                temp_id=item.temp_id, status="error",
                error="资产记录不存在",
            ))

    # --- Asset creates (direct DB write via _resolve_category_id) ---
    created_asset_ids: list[str] = []
    for item in asset_creates:
        try:
            category_id = _resolve_category_id(item.category_hint, db)
            if category_id is None:
                stats["skipped"] += 1
                result_items.append(ConfirmResultItem(
                    temp_id=item.temp_id, status="skipped",
                    error=f"未知分类: {item.category_hint}",
                ))
                continue
            new_asset = Asset(
                user_id=current_user.id,
                family_id=current_user.family_id,
                category_id=category_id,
                name=item.name,
                asset_type=item.asset_type,
                current_value=item.current_value,
                purchase_price=item.current_value,
                currency=item.currency,
                notes=item.notes,
                status="in_use",
            )
            db.add(new_asset)
            db.flush()
            created_asset_ids.append(str(new_asset.id))
            stats["created"] += 1
            result_items.append(ConfirmResultItem(
                temp_id=item.temp_id, status="created",
                id=str(new_asset.id), name=new_asset.name,
            ))
        except Exception as e:
            stats["skipped"] += 1
            result_items.append(ConfirmResultItem(
                temp_id=item.temp_id, status="error",
                error=str(e),
            ))

    # --- Liability creates (direct DB write) ---
    created_liability_ids: list[str] = []
    for item in liability_creates:
        try:
            new_liability = Liability(
                user_id=current_user.id,
                family_id=current_user.family_id,
                category=item.liability_category or "other",
                name=item.name,
                original_amount=Decimal(str(item.original_amount)) if item.original_amount is not None else Decimal("0"),
                remaining_amount=Decimal(str(item.remaining_amount)) if item.remaining_amount is not None else Decimal("0"),
                monthly_payment=Decimal(str(item.monthly_payment)) if item.monthly_payment is not None else None,
                interest_rate=item.interest_rate,
                currency=item.currency,
                notes=item.notes,
            )
            db.add(new_liability)
            db.flush()
            created_liability_ids.append(str(new_liability.id))
            stats["created"] += 1
            result_items.append(ConfirmResultItem(
                temp_id=item.temp_id, status="created",
                id=str(new_liability.id), name=new_liability.name,
            ))
        except Exception as e:
            stats["skipped"] += 1
            result_items.append(ConfirmResultItem(
                temp_id=item.temp_id, status="error",
                error=str(e),
            ))

    db.commit()

    # R22: update DraftImport status to "committed".
    if req.draft_id:
        try:
            draft_id_int = int(req.draft_id)
        except ValueError:
            draft_id_int = None
        if draft_id_int is not None:
            draft = db.query(DraftImport).filter(
                DraftImport.id == draft_id_int,
                DraftImport.family_id == current_user.family_id,
            ).first()
            if draft:
                draft.status = "committed"
                all_ids = created_asset_ids + created_liability_ids
                draft.set_committed_record_ids(all_ids)
                db.commit()

    return ConfirmResponse(
        updated=stats["updated"],
        created=stats["created"],
        skipped=stats["skipped"],
        items=result_items,
    )


@router.post("/confirm-via-agent")
async def confirm_import_via_agent(
    req: ConfirmRequest,
    current_user: User = Depends(require_adult),
):
    """C1 直接写入流程（legacy）：用户确认后由 agent 调 import_assets_batch MCP 工具写库。"""
    from apps.backend.app.database import SessionLocal

    updated = 0
    update_items = [item for item in req.items if item.action == "update" and item.matched_asset_id]
    if update_items:
        with SessionLocal() as db:
            for item in update_items:
                asset = (
                    db.query(Asset)
                    .filter(
                        Asset.id == item.matched_asset_id,
                        Asset.family_id == current_user.family_id,
                    )
                    .first()
                )
                if asset:
                    asset.current_value = Decimal(str(item.current_value)) if item.current_value is not None else None
                    if item.currency:
                        asset.currency = item.currency
                    if item.notes:
                        asset.notes = item.notes
                    updated += 1
            db.commit()

    create_items = [
        {
            "temp_id": item.temp_id,
            "name": item.name,
            "asset_type": item.asset_type,
            "category_hint": item.category_hint,
            "current_value": item.current_value,
            "currency": item.currency,
            "quantity": item.quantity,
            "notes": item.notes,
        }
        for item in req.items
        if item.action == "create"
    ]
    write_result: dict = {"created": 0, "skipped": 0, "items": []}
    if create_items:
        try:
            agent_client = AgentClient(
                str(current_user.family_id),
                user_id=str(current_user.id),
                timeout=120.0,
            )
            resp = await agent_client.post(
                "/import/parse",
                json={"text": "", "confirm_items": create_items},
            )
            resp.raise_for_status()
            agent_data = resp.json()
            wr = agent_data.get("write_result")
            if isinstance(wr, dict):
                write_result = wr
        except httpx.TimeoutException as e:
            raise AppError(ErrorCode.IMPORT_AGENT_TIMEOUT) from e
        except Exception as e:
            logger.error("Agent confirm-via-agent failed: %s", e)
            raise AppError(ErrorCode.AI_SERVICE_UNAVAILABLE) from e

    return {
        "updated": updated,
        "created": write_result.get("created", 0),
        "skipped": write_result.get("skipped", 0),
        "items": write_result.get("items", []),
    }


@router.get("/history", response_model=list[HistoryItem])
def import_history(
    current_user: User = Depends(require_adult),
    db: Session = Depends(get_db),
):
    """R23: return last 20 draft_imports records for the family."""
    drafts = (
        db.query(DraftImport)
        .filter(DraftImport.family_id == current_user.family_id)
        .order_by(DraftImport.created_at.desc())
        .limit(20)
        .all()
    )

    now = datetime.now(UTC)
    cutoff = now - timedelta(days=_ROLLBACK_WINDOW_DAYS)

    items: list[HistoryItem] = []
    for d in drafts:
        parsed = d.get_parsed_items()
        can_rollback = (
            d.status == "committed"
            and d.created_at is not None
            and d.created_at.replace(tzinfo=UTC) > cutoff
        )
        items.append(HistoryItem(
            id=str(d.id),
            source_filename=d.source_filename,
            source_format=d.source_format,
            status=d.status,
            item_count=len(parsed),
            created_at=d.created_at.isoformat() if d.created_at else "",
            can_rollback=can_rollback,
        ))
    return items


@router.post("/rollback/{draft_id}")
def rollback_import(
    draft_id: str,
    current_user: User = Depends(require_adult),
    db: Session = Depends(get_db),
):
    """R22/R24: rollback a committed import within 30 days.

    Sets is_archived=True on all imported records.
    Checks for cross-references before rollback.
    """
    try:
        draft_id_int = int(draft_id)
    except ValueError:
        raise AppError(ErrorCode.IMPORT_DRAFT_NOT_FOUND) from None
    draft = db.query(DraftImport).filter(DraftImport.id == draft_id_int).first()
    if not draft:
        raise AppError(ErrorCode.IMPORT_DRAFT_NOT_FOUND)

    # Verify ownership.
    if draft.family_id != current_user.family_id:
        raise AppError(ErrorCode.IMPORT_DRAFT_NOT_FOUND)

    # Verify status.
    if draft.status != "committed":
        raise AppError(ErrorCode.IMPORT_ROLLBACK_EXPIRED)

    # Verify within 30-day window (R24).
    now = datetime.now(UTC)
    cutoff = now - timedelta(days=_ROLLBACK_WINDOW_DAYS)
    if draft.created_at is None or draft.created_at.replace(tzinfo=UTC) <= cutoff:
        raise AppError(ErrorCode.IMPORT_ROLLBACK_EXPIRED)

    # Get committed record IDs.
    record_ids = draft.get_committed_record_ids()
    if not record_ids:
        raise AppError(ErrorCode.IMPORT_DRAFT_NOT_FOUND)

    # Check for cross-references (R22): linked_asset_id on liabilities.
    for rid in record_ids:
        # Check if this asset is referenced by any liability.
        linked = db.query(Liability).filter(
            Liability.linked_asset_id == rid,
            Liability.is_archived.is_(False),
        ).first()
        if linked:
            raise AppError(ErrorCode.IMPORT_ROLLBACK_REFERENCED)

    # Soft-delete all committed records.
    archived_count = 0
    for rid in record_ids:
        # Try Asset first.
        asset = db.query(Asset).filter_by(id=rid).first()
        if asset and asset.family_id == current_user.family_id:
            asset.is_archived = True
            archived_count += 1
            continue
        # Try Liability.
        liability = db.query(Liability).filter_by(id=rid).first()
        if liability and liability.family_id == current_user.family_id:
            liability.is_archived = True
            archived_count += 1

    # Update draft status.
    draft.status = "rolled_back"
    draft.rolled_back_at = now
    db.commit()

    return {
        "status": "rolled_back",
        "archived_count": archived_count,
        "draft_id": draft_id,
    }
