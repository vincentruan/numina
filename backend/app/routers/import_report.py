"""金融文档智能导入端点。

- POST /api/v1/import/parse-pdf  — 上传 PDF，返回持仓预览
- POST /api/v1/import/confirm    — 确认导入，执行资产匹配+更新/创建
"""

import io
import logging
import uuid

import httpx
import pdfplumber
from fastapi import APIRouter, Depends, File, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.deps import require_adult
from app.config import settings
from app.database import get_db
from app.errors import AppError, ErrorCode
from app.models.asset import Asset
from app.models.category import Category
from app.models.user import User

router = APIRouter(prefix="/import", tags=["import"])
logger = logging.getLogger(__name__)

_MAX_PDF_BYTES = 10 * 1024 * 1024  # 10 MB


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_pdf_text(data: bytes) -> str:
    """从 PDF 字节提取纯文本；扫描件/图片 PDF 返回空字符串。"""
    try:
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            pages = [page.extract_text() or "" for page in pdf.pages]
        return "\n".join(pages).strip()
    except Exception:
        return ""


async def _call_agent_parse(text: str, family_id: str) -> dict:
    """调用 Agent 微服务解析文本，返回原始 dict。"""
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{settings.AGENT_BASE_URL}/import/parse",
            json={"text": text},
            headers={
                "X-Family-Id": family_id,
                "X-Agent-Token": settings.AGENT_INTERNAL_TOKEN,
            },
        )
        resp.raise_for_status()
        return resp.json()


def _match_asset(name: str, family_id: str, db: Session) -> Asset | None:
    """按名称匹配现有资产（精确 > 模糊，同家庭内）。"""
    # 精确匹配
    asset = (
        db.query(Asset)
        .filter(
            Asset.family_id == family_id,
            Asset.name == name,
            Asset.is_archived == False,  # noqa: E712
        )
        .first()
    )
    if asset:
        return asset
    # 模糊匹配：名称包含关系
    assets = (
        db.query(Asset)
        .filter(Asset.family_id == family_id, Asset.is_archived == False)  # noqa: E712
        .all()
    )
    for a in assets:
        if name in a.name or a.name in name:
            return a
    return None


def _resolve_category_id(category_hint: str, db: Session) -> str | None:
    """按 category_hint 查找系统分类 ID。"""
    cat = db.query(Category).filter(Category.name == category_hint).first()
    return cat.id if cat else None


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class ImportPreviewItem(BaseModel):
    temp_id: str
    name: str
    asset_type: str
    category_hint: str
    current_value: float | None
    currency: str = "CNY"
    quantity: float | None = None
    notes: str | None = None
    matched_asset_id: str | None = None
    matched_asset_name: str | None = None
    action: str  # "update" | "create"
    warning: str | None = None


class ImportPreview(BaseModel):
    source: str
    report_date: str | None
    items: list[ImportPreviewItem]


class ConfirmItem(BaseModel):
    temp_id: str
    name: str
    asset_type: str
    category_hint: str
    current_value: float | None
    currency: str = "CNY"
    quantity: float | None = None
    notes: str | None = None
    matched_asset_id: str | None = None
    action: str  # "update" | "create"


class ConfirmRequest(BaseModel):
    items: list[ConfirmItem]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/parse-pdf", response_model=ImportPreview)
async def parse_pdf(
    file: UploadFile = File(...),
    current_user: User = Depends(require_adult),
    db: Session = Depends(get_db),
):
    """上传 PDF，提取文本，调用 Agent 解析，返回持仓预览。"""
    raw = await file.read()
    if len(raw) > _MAX_PDF_BYTES:
        raise AppError(ErrorCode.IMPORT_PDF_UNREADABLE)

    text = _extract_pdf_text(raw)
    if not text:
        raise AppError(ErrorCode.IMPORT_PDF_UNREADABLE)

    try:
        agent_result = await _call_agent_parse(text, str(current_user.family_id))
    except httpx.TimeoutException as e:
        raise AppError(ErrorCode.IMPORT_AGENT_TIMEOUT) from e
    except Exception as e:
        logger.error(f"Agent parse failed: {e}")
        raise AppError(ErrorCode.AI_SERVICE_UNAVAILABLE) from e

    raw_items: list[dict] = agent_result.get("items", [])
    if not raw_items:
        raise AppError(ErrorCode.IMPORT_NO_ASSETS_FOUND)

    preview_items: list[ImportPreviewItem] = []
    for raw_item in raw_items:
        matched = _match_asset(raw_item["name"], str(current_user.family_id), db)
        warning = None
        if raw_item.get("current_value") is None:
            warning = "金额未识别，请手动补充"

        preview_items.append(ImportPreviewItem(
            temp_id=f"tmp_{uuid.uuid4().hex[:8]}",
            name=raw_item["name"],
            asset_type=raw_item.get("asset_type", "financial"),
            category_hint=raw_item.get("category_hint", ""),
            current_value=raw_item.get("current_value"),
            currency=raw_item.get("currency", "CNY"),
            quantity=raw_item.get("quantity"),
            matched_asset_id=str(matched.id) if matched else None,
            matched_asset_name=matched.name if matched else None,
            action="update" if matched else "create",
            warning=warning,
        ))

    return ImportPreview(
        source=agent_result.get("source", ""),
        report_date=agent_result.get("report_date"),
        items=preview_items,
    )


@router.post("/confirm")
def confirm_import(
    req: ConfirmRequest,
    current_user: User = Depends(require_adult),
    db: Session = Depends(get_db),
):
    """用户确认后执行资产匹配+更新/创建。"""
    stats = {"updated": 0, "created": 0, "skipped": 0}

    for item in req.items:
        if item.action == "update" and item.matched_asset_id:
            # 验证资产属于当前家庭
            asset = (
                db.query(Asset)
                .filter(
                    Asset.id == item.matched_asset_id,
                    Asset.family_id == current_user.family_id,
                )
                .first()
            )
            if asset:
                asset.current_value = item.current_value
                if item.currency:
                    asset.currency = item.currency
                if item.notes:
                    asset.notes = item.notes
                stats["updated"] += 1
                continue
            # 跨家庭资产降级为 create

        # create 路径
        category_id = _resolve_category_id(item.category_hint, db)
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
        stats["created"] += 1

    db.commit()
    return stats
