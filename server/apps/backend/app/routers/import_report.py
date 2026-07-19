"""金融文档智能导入端点。

- POST /api/v1/import/parse-pdf  — 上传 PDF，返回持仓预览
- POST /api/v1/import/confirm    — 确认导入，执行资产匹配+更新/创建
"""

import io
import logging
import uuid
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
from apps.backend.app.models.user import User
from apps.backend.app.services.agent_client import AgentClient

router = APIRouter(prefix="/import", tags=["import"])
logger = logging.getLogger(__name__)

_MAX_PDF_BYTES = 10 * 1024 * 1024  # 10 MB

# Image-based PDF detection threshold (chars/page). Mirrors DeerFlow's
# file_conversion._MIN_CHARS_PER_PAGE: normal text PDFs yield 200-2000
# chars/page; image-based (scanned) PDFs yield close to 0. Below this
# threshold → render pages to PNG and let the agent's vision model read
# them via view_image (Q1-A decision: DeerFlow sparse-detection pattern).
_MIN_CHARS_PER_PAGE_FOR_VISION = 50
# Cap on rendered pages to bound token cost (Q2-B decision). Pages beyond
# this are dropped with a warning; the agent parses what it can.
_MAX_RENDERED_PAGES = 10


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


def _is_image_based_pdf(data: bytes, text: str) -> bool:
    """检测 PDF 是否为图片型（扫描件）。

    Q1-A 决策（复刻 DeerFlow file_conversion._pymupdf_output_too_sparse）：
    用 chars/page < 阈值判定。正常文本 PDF 每页 200-2000 字符，图片型接近 0。
    页数不可得时退化为绝对 200 字符阈值。
    """
    if text and len(text.strip()) >= 200:
        # 文本足够，先用 pymupdf 确认页数算 chars/page
        try:
            with pymupdf.open(stream=data, filetype="pdf") as doc:
                page_count = doc.page_count or 1
            return len(text.strip()) / page_count < _MIN_CHARS_PER_PAGE_FOR_VISION
        except Exception:
            return False
    # 文本稀疏（< 200 绝对字符）→ 图片型
    return True


def _render_pdf_pages_to_sandbox(
    data: bytes, family_id: str, thread_id: str
) -> list[str]:
    """渲染 PDF 每页为 PNG，落 family-scoped 沙箱 uploads 目录。

    Q2-B 决策：最多渲染 _MAX_RENDERED_PAGES 页（token 成本控制）。
    路径 = AGENT_DATA_DIR/{family_id}/sandboxes/{thread_id}/uploads/page_{n}.png
    （backend/agent 共享 /app/.numina/data/workspaces 文件系统，见 ai_chat.py:579 先例）。
    agent 的 NuminaLocalSandboxProvider 把 /mnt/user-data/uploads 映射到该目录，
    故 agent 调 view_image("/mnt/user-data/uploads/page_1.png") 即可读取。

    返回容器虚拟路径列表（供 agent view_image 使用）。
    """
    data_root = Path(settings.DATA_ROOT).expanduser() if hasattr(settings, "DATA_ROOT") else Path.home() / ".numina" / "data"
    uploads_dir = data_root / "workspaces" / str(family_id) / "sandboxes" / thread_id / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)

    virtual_paths: list[str] = []
    try:
        with pymupdf.open(stream=data, filetype="pdf") as doc:
            page_count = min(doc.page_count, _MAX_RENDERED_PAGES)
            if doc.page_count > _MAX_RENDERED_PAGES:
                logger.warning(
                    "[parse_pdf] PDF has %d pages, rendering only first %d family=%s",
                    doc.page_count, _MAX_RENDERED_PAGES, family_id,
                )
            for i in range(page_count):
                page = doc[i]
                # 2x zoom for OCR readability (default 72 DPI too low for dense tables)
                pix = page.get_pixmap(matrix=pymupdf.Matrix(2, 2))
                filename = f"page_{i + 1}.png"
                pix.save(str(uploads_dir / filename))
                virtual_paths.append(f"/mnt/user-data/uploads/{filename}")
    except Exception as e:
        logger.error("[parse_pdf] PDF page render failed family=%s err=%s", family_id, e)
        return []
    return virtual_paths


async def _call_agent_parse(
    text: str, family_id: str, thread_id: str | None = None, image_paths: list[str] | None = None
) -> dict:
    """调用 Agent 微服务解析文本，返回原始 dict。

    U8: agent /import/parse 现在内联运行 ``app="import-parse"`` stream_run agent
    （单次 LLM 解析），不再是 dispatch 即返；timeout 提至 120s 以容纳 agent run。

    C 方案（vision）：当 backend 渲染了 PDF 页图，传 thread_id + image_paths 给
    agent——thread_id 让 agent 用同一沙箱（PNG 已落 uploads/），image_paths 告知
    agent 用 view_image 读取这些图片。纯文本解析时不传这两项（向后兼容）。
    """
    agent_client = AgentClient(family_id, timeout=120.0)
    payload: dict = {"text": text}
    if thread_id:
        payload["thread_id"] = thread_id
    if image_paths:
        payload["image_paths"] = image_paths
    resp = await agent_client.post(
        "/import/parse",
        json=payload,
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
    """上传 PDF，提取文本，调用 Agent 解析，返回持仓预览。

    C 方案（vision）：PDF 文本足够时走纯文本路径；检测为图片型（扫描件）时，
    渲染每页 PNG 到 family-scoped 沙箱，传 thread_id + image_paths 给 agent，
    agent 用 view_image 读图 + vision 模型解析（Q1-A 稀疏检测 + Q2-B 限页）。
    """
    raw = await file.read()
    if len(raw) > _MAX_PDF_BYTES:
        raise AppError(ErrorCode.IMPORT_PDF_UNREADABLE)

    family_id = str(current_user.family_id)
    text = _extract_pdf_text(raw)

    # 预生成 thread_id（vision 路径需 backend 提前渲染 PNG 到该 thread 的沙箱）
    thread_id = f"importparse-thread-{uuid.uuid4().hex[:12]}"
    image_paths: list[str] = []

    # 图片型 PDF → 渲染页图走 vision；文本型 → 纯文本路径
    if _is_image_based_pdf(raw, text):
        image_paths = _render_pdf_pages_to_sandbox(raw, family_id, thread_id)
        if not image_paths:
            # 渲染失败 → 文本也提取不到 → 无法解析
            raise AppError(ErrorCode.IMPORT_PDF_UNREADABLE)
        # 图片型 PDF 不依赖 text（可能为空），agent 走 view_image 路径
        text = text or ""

    if not text and not image_paths:
        # 纯文本路径且文本为空 → 无法解析
        raise AppError(ErrorCode.IMPORT_PDF_UNREADABLE)

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
            matched_asset_id=matched.id if matched else None,
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
