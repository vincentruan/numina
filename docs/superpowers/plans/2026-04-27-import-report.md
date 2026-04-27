# Phase 5 金融文档智能导入 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 支持上传金融 PDF 账单，通过 LLM 提取持仓快照，预览确认后更新 Numina 资产数据。

**Architecture:** Frontend 上传 PDF → Backend 用 pdfplumber 提取文本 → 调用 Agent 微服务 LLM 解析 → 返回预览 → 用户确认 → Backend 执行资产匹配+更新/创建。Backend 新增两个端点（parse/confirm），Agent 新增一个内部端点（import/parse），Frontend 新增 ImportReportPage.vue。

**Tech Stack:** pdfplumber（PDF 文本提取）、httpx（Backend→Agent 调用）、FastAPI、Pydantic v2、Vue 3 + Vant 4

---

## 文件清单

| 操作 | 路径 | 职责 |
|------|------|------|
| 新建 | `agent/routers/import_parse.py` | Agent 侧 LLM 解析端点 |
| 修改 | `agent/app/main.py` | 注册 import_parse router |
| 新建 | `backend/app/routers/import_report.py` | Backend parse + confirm 端点 |
| 修改 | `backend/app/main.py` | 注册 import_report router |
| 修改 | `backend/app/errors/codes.py` | 新增 IMPORT_* ErrorCode |
| 新建 | `frontend/src/pages/ImportReportPage.vue` | 上传+预览+确认页面 |
| 修改 | `frontend/src/api/import.ts` | 新增 parseReport / confirmImport API |
| 修改 | `frontend/src/router/index.ts` | 注册 /import-report 路由 |
| 修改 | `frontend/src/pages/SettingsPage.vue` | 添加"导入账单"入口 |
| 新建 | `agent/tests/unit/test_import_parse.py` | Agent 解析单元测试 |
| 新建 | `backend/tests/test_import_report.py` | Backend 路由测试 |

---

## Task 1: Agent — import_parse 路由

**Files:**
- Create: `agent/routers/import_parse.py`
- Modify: `agent/app/main.py`
- Test: `agent/tests/unit/test_import_parse.py`

- [ ] **Step 1: 写失败测试**

```python
# agent/tests/unit/test_import_parse.py
import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from agent.app.main import app  # adjust import if needed

VALID_TOKEN = "test-token"

@pytest.fixture(autouse=True)
def patch_token(monkeypatch):
    monkeypatch.setenv("AGENT_INTERNAL_TOKEN", VALID_TOKEN)

def test_parse_returns_structured_items():
    mock_response = {
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
        "routers.import_parse.orchestrator.dispatch",
        new=AsyncMock(return_value=type("R", (), {"model_dump": lambda self: mock_response})()),
    ):
        client = TestClient(app)
        resp = client.post(
            "/import/parse",
            json={"text": "贵州茅台 600519 100股 市值158000元"},
            headers={"X-Agent-Token": VALID_TOKEN, "X-Family-Id": "fam1"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"][0]["name"] == "贵州茅台"
    assert data["items"][0]["current_value"] == 158000.0

def test_parse_rejects_invalid_token():
    client = TestClient(app)
    resp = client.post(
        "/import/parse",
        json={"text": "some text"},
        headers={"X-Agent-Token": "wrong", "X-Family-Id": "fam1"},
    )
    assert resp.status_code == 401

def test_parse_returns_empty_items_when_llm_finds_nothing():
    empty_response = {"source": "", "report_date": None, "items": []}
    with patch(
        "routers.import_parse.orchestrator.dispatch",
        new=AsyncMock(return_value=type("R", (), {"model_dump": lambda self: empty_response})()),
    ):
        client = TestClient(app)
        resp = client.post(
            "/import/parse",
            json={"text": "这不是金融文档"},
            headers={"X-Agent-Token": VALID_TOKEN, "X-Family-Id": "fam1"},
        )
    assert resp.status_code == 200
    assert resp.json()["items"] == []
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd agent && uv run pytest tests/unit/test_import_parse.py -v
```

期望：FAIL（`routers.import_parse` 不存在）

- [ ] **Step 3: 实现 agent/routers/import_parse.py**

```python
"""金融文档持仓解析端点（由 backend 调用）。"""

import json
import logging

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from app.config import settings
from services.orchestrator import orchestrator

router = APIRouter(prefix="/import", tags=["import"])
logger = logging.getLogger(__name__)


class ImportParseRequest(BaseModel):
    text: str


@router.post("/parse")
async def parse_import(
    body: ImportParseRequest,
    x_family_id: str = Header(..., alias="X-Family-Id"),
    x_agent_token: str = Header(..., alias="X-Agent-Token"),
    x_user_id: str = Header(None, alias="X-User-Id"),
):
    """解析金融文档文本，提取持仓快照（由 backend 调用）。"""
    if x_agent_token != settings.AGENT_INTERNAL_TOKEN:
        raise HTTPException(status_code=401, detail="invalid token")

    free_text = json.dumps({"text": body.text}, ensure_ascii=False)
    response = await orchestrator.dispatch(
        capability="import_parse",
        family_id=x_family_id,
        user_id=x_user_id,
        free_text=free_text,
    )
    return response.model_dump()
```

- [ ] **Step 4: 在 agent/app/main.py 注册路由**

在现有 `from routers import time_machine as time_machine_router` 后添加：

```python
from routers import import_parse as import_parse_router
```

在 `app.include_router(time_machine_router.router)` 后添加：

```python
app.include_router(import_parse_router.router)
```

- [ ] **Step 5: 运行测试确认通过**

```bash
cd agent && uv run pytest tests/unit/test_import_parse.py -v
```

期望：3 PASSED

- [ ] **Step 6: Commit**

```bash
git add agent/routers/import_parse.py agent/app/main.py agent/tests/unit/test_import_parse.py
git commit -m "feat(phase5): add agent import_parse router for LLM-based PDF holdings extraction"
```

---

## Task 2: Agent — orchestrator capability "import_parse"

**Files:**
- Modify: `agent/services/orchestrator.py` 或 fallback_engine（视现有实现而定）

- [ ] **Step 1: 查看 orchestrator 如何注册 capability**

```bash
grep -n "capability\|\"report\"\|\"suggest\"\|dispatch" agent/services/orchestrator.py | head -40
```

- [ ] **Step 2: 写失败测试（验证 import_parse capability 存在）**

```python
# 在 agent/tests/unit/test_import_parse.py 追加：
@pytest.mark.asyncio
async def test_orchestrator_import_parse_capability():
    from services.orchestrator import orchestrator
    # Should not raise KeyError / capability not found
    with patch("services.orchestrator.fallback_engine.run", new=AsyncMock(return_value={"items": []})):
        result = await orchestrator.dispatch(
            capability="import_parse",
            family_id="fam1",
            user_id="user1",
            free_text='{"text": "贵州茅台 100股"}',
        )
    assert hasattr(result, "model_dump")
```

- [ ] **Step 3: 运行测试确认失败**

```bash
cd agent && uv run pytest tests/unit/test_import_parse.py::test_orchestrator_import_parse_capability -v
```

- [ ] **Step 4: 在 orchestrator/fallback_engine 注册 import_parse capability**

根据 Step 1 的输出，按现有模式添加 `import_parse` capability。LLM prompt 要点：

```python
IMPORT_PARSE_PROMPT = """你是一个金融文档解析助手。
从以下文本中提取持仓/资产信息，输出严格 JSON，不输出任何解释文字。

输出格式：
{
  "source": "机构名称或空字符串",
  "report_date": "YYYY-MM-DD 或 null",
  "items": [
    {
      "name": "资产名称",
      "asset_type": "financial",
      "category_hint": "股票|基金|债券|存款|理财产品|数字货币|其他",
      "current_value": 数字,
      "currency": "CNY",
      "quantity": 数字或null
    }
  ]
}

规则：
- 只提取持仓/资产信息，忽略交易流水、消费记录
- 识别不到任何资产时返回 {"source": "", "report_date": null, "items": []}
- current_value 必须是数字，不能是字符串

文档内容：
{text}
"""
```

- [ ] **Step 5: 运行测试确认通过**

```bash
cd agent && uv run pytest tests/unit/test_import_parse.py -v
```

- [ ] **Step 6: Commit**

```bash
git add agent/services/
git commit -m "feat(phase5): register import_parse capability in agent orchestrator"
```

---

## Task 3: Backend — ErrorCode 新增 + pdfplumber 依赖

**Files:**
- Modify: `backend/app/errors/codes.py`
- Modify: `backend/pyproject.toml`

- [ ] **Step 1: 在 backend/app/errors/codes.py 新增 ErrorCode**

找到 `AI_SERVICE_UNAVAILABLE` 附近，添加：

```python
IMPORT_PDF_UNREADABLE = "IMPORT_PDF_UNREADABLE"
IMPORT_NO_ASSETS_FOUND = "IMPORT_NO_ASSETS_FOUND"
IMPORT_AGENT_TIMEOUT = "IMPORT_AGENT_TIMEOUT"
```

在 `ERROR_CODE_HTTP_STATUS` 字典中添加对应 HTTP 状态码：

```python
ErrorCode.IMPORT_PDF_UNREADABLE: 400,
ErrorCode.IMPORT_NO_ASSETS_FOUND: 422,
ErrorCode.IMPORT_AGENT_TIMEOUT: 504,
```

- [ ] **Step 2: 确认 pdfplumber 已在依赖中**

```bash
grep "pdfplumber" backend/pyproject.toml
```

若无输出，在 `[project] dependencies` 中添加：

```toml
"pdfplumber>=0.11",
```

然后安装：

```bash
cd backend && uv sync
```

- [ ] **Step 3: 验证 ErrorCode 可导入**

```bash
cd backend && python -c "from app.errors.codes import ErrorCode; print(ErrorCode.IMPORT_PDF_UNREADABLE)"
```

期望输出：`IMPORT_PDF_UNREADABLE`

- [ ] **Step 4: Commit**

```bash
git add backend/app/errors/codes.py backend/pyproject.toml
git commit -m "feat(phase5): add IMPORT_* error codes and pdfplumber dependency"
```

---

## Task 4: Backend — import_report 路由（parse 端点）

**Files:**
- Create: `backend/app/routers/import_report.py`
- Test: `backend/tests/test_import_report.py`

- [ ] **Step 1: 写失败测试（parse 端点）**

```python
# backend/tests/test_import_report.py
import io
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import auth_headers  # 复用现有 fixture


def _make_pdf_bytes(text: str = "贵州茅台 100股 市值158000") -> bytes:
    """生成最小合法 PDF 字节（用于测试，pdfplumber 可读取）。"""
    import pdfplumber, io as _io
    # 直接用 reportlab 生成最小 PDF
    try:
        from reportlab.pdfgen import canvas as rl_canvas
        buf = _io.BytesIO()
        c = rl_canvas.Canvas(buf)
        c.drawString(100, 750, text)
        c.save()
        return buf.getvalue()
    except ImportError:
        # fallback: 返回空字节，测试 pdfplumber 空文本路径
        return b"%PDF-1.4\n%%EOF"


def test_parse_returns_preview(client, adult_token_headers):
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
    with patch("app.routers.import_report._call_agent_parse", new=AsyncMock(return_value=mock_agent_resp)):
        with patch("app.routers.import_report._extract_pdf_text", return_value="贵州茅台 100股"):
            resp = client.post(
                "/api/v1/import/parse-pdf",
                files={"file": ("test.pdf", b"fake-pdf", "application/pdf")},
                headers=adult_token_headers,
            )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["name"] == "贵州茅台"
    assert data["items"][0]["action"] in ("update", "create")


def test_parse_returns_400_for_empty_pdf(client, adult_token_headers):
    with patch("app.routers.import_report._extract_pdf_text", return_value=""):
        resp = client.post(
            "/api/v1/import/parse-pdf",
            files={"file": ("scan.pdf", b"fake-pdf", "application/pdf")},
            headers=adult_token_headers,
        )
    assert resp.status_code == 400


def test_parse_returns_422_when_agent_finds_nothing(client, adult_token_headers):
    empty = {"source": "", "report_date": None, "items": []}
    with patch("app.routers.import_report._call_agent_parse", new=AsyncMock(return_value=empty)):
        with patch("app.routers.import_report._extract_pdf_text", return_value="这不是金融文档"):
            resp = client.post(
                "/api/v1/import/parse-pdf",
                files={"file": ("other.pdf", b"fake-pdf", "application/pdf")},
                headers=adult_token_headers,
            )
    assert resp.status_code == 422
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd backend && uv run pytest tests/test_import_report.py -v
```

期望：FAIL（`app.routers.import_report` 不存在）

- [ ] **Step 3: 实现 backend/app/routers/import_report.py（parse 端点）**

```python
"""金融文档智能导入端点。

- POST /api/v1/import/parse-pdf  — 上传 PDF，返回持仓预览
- POST /api/v1/import/confirm    — 确认导入，执行资产匹配+更新/创建
"""

import io
import logging
import uuid
from decimal import Decimal

import httpx
import pdfplumber
from fastapi import APIRouter, Depends, UploadFile, File
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
        .filter(Asset.family_id == family_id, Asset.name == name, Asset.is_archived == False)
        .first()
    )
    if asset:
        return asset
    # 模糊匹配：名称包含关系
    assets = (
        db.query(Asset)
        .filter(Asset.family_id == family_id, Asset.is_archived == False)
        .all()
    )
    for a in assets:
        if name in a.name or a.name in name:
            return a
    return None


def _resolve_category_id(category_hint: str, asset_type: str, db: Session) -> str | None:
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
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd backend && uv run pytest tests/test_import_report.py::test_parse_returns_preview tests/test_import_report.py::test_parse_returns_400_for_empty_pdf tests/test_import_report.py::test_parse_returns_422_when_agent_finds_nothing -v
```

期望：3 PASSED

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/import_report.py backend/tests/test_import_report.py
git commit -m "feat(phase5): add backend import parse-pdf endpoint with pdfplumber + agent call"
```

---

## Task 5: Backend — confirm 端点

**Files:**
- Modify: `backend/app/routers/import_report.py`（追加 confirm 端点）
- Modify: `backend/tests/test_import_report.py`（追加 confirm 测试）

- [ ] **Step 1: 写失败测试（confirm 端点）**

在 `backend/tests/test_import_report.py` 追加：

```python
def test_confirm_updates_existing_asset(client, adult_token_headers, db_session, seed_asset):
    """seed_asset 是已存在的"贵州茅台"资产 fixture。"""
    payload = {
        "items": [
            {
                "temp_id": "tmp_001",
                "name": "贵州茅台",
                "asset_type": "financial",
                "category_hint": "股票",
                "current_value": 168000.0,
                "currency": "CNY",
                "quantity": 100,
                "notes": None,
                "matched_asset_id": str(seed_asset.id),
                "action": "update",
            }
        ]
    }
    resp = client.post("/api/v1/import/confirm", json=payload, headers=adult_token_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["updated"] == 1
    assert data["created"] == 0
    # 验证数据库已更新
    db_session.refresh(seed_asset)
    assert seed_asset.current_value == 168000.0


def test_confirm_creates_new_asset(client, adult_token_headers):
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
    resp = client.post("/api/v1/import/confirm", json=payload, headers=adult_token_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["created"] == 1
    assert data["updated"] == 0


def test_confirm_skips_cross_family_asset(client, adult_token_headers, other_family_asset):
    """matched_asset_id 属于其他家庭时，应拒绝更新（降级为 create）。"""
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
                "matched_asset_id": str(other_family_asset.id),
                "action": "update",
            }
        ]
    }
    resp = client.post("/api/v1/import/confirm", json=payload, headers=adult_token_headers)
    assert resp.status_code == 200
    # 跨家庭资产不能被更新，应降级为 create
    assert resp.json()["created"] == 1
    assert resp.json()["updated"] == 0
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd backend && uv run pytest tests/test_import_report.py::test_confirm_updates_existing_asset tests/test_import_report.py::test_confirm_creates_new_asset -v
```

期望：FAIL（confirm 端点不存在）

- [ ] **Step 3: 在 import_report.py 追加 confirm 端点**

```python
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
        category_id = _resolve_category_id(item.category_hint, item.asset_type, db)
        new_asset = Asset(
            user_id=current_user.id,
            family_id=current_user.family_id,
            category_id=category_id,
            name=item.name,
            asset_type=item.asset_type,
            current_value=item.current_value,
            purchase_price=item.current_value,  # 无历史数据时以当前市值作为购入价
            currency=item.currency,
            notes=item.notes,
            status="in_use",
        )
        db.add(new_asset)
        stats["created"] += 1

    db.commit()
    return stats
```

- [ ] **Step 4: 运行全部 confirm 测试**

```bash
cd backend && uv run pytest tests/test_import_report.py -v
```

期望：全部 PASSED

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/import_report.py backend/tests/test_import_report.py
git commit -m "feat(phase5): add backend import confirm endpoint with asset match/update/create"
```

---

## Task 6: Backend — 注册路由

**Files:**
- Modify: `backend/app/main.py`

- [ ] **Step 1: 在 main.py 注册 import_report router**

找到 `from app.routers import import_ as import_router` 这行，在其后添加：

```python
from app.routers import import_report as import_report_router
```

找到 `app.include_router(import_router.router, prefix="/api/v1")` 附近，添加：

```python
app.include_router(import_report_router.router, prefix="/api/v1")
```

- [ ] **Step 2: 验证路由已注册**

```bash
cd backend && python -c "
from app.main import app
routes = [r.path for r in app.routes]
assert any('/import/parse-pdf' in r for r in routes), f'route missing, got: {routes}'
assert any('/import/confirm' in r for r in routes), f'route missing, got: {routes}'
print('OK: routes registered')
"
```

- [ ] **Step 3: 运行全量 backend 测试确认无回归**

```bash
cd backend && uv run pytest tests/ -v --tb=short -q
```

期望：全部通过（含新增测试）

- [ ] **Step 4: Commit**

```bash
git add backend/app/main.py
git commit -m "feat(phase5): register import_report router in backend main"
```

---

## Task 7: Frontend — API 层

**Files:**
- Modify: `frontend/src/api/import.ts`

先看现有 import.ts 内容：

- [ ] **Step 1: 查看现有 import.ts**

```bash
cat frontend/src/api/import.ts
```

- [ ] **Step 2: 追加 parseReport 和 confirmImport 函数**

在 `frontend/src/api/import.ts` 末尾追加：

```typescript
export interface ImportPreviewItem {
  temp_id: string
  name: string
  asset_type: string
  category_hint: string
  current_value: number | null
  currency: string
  quantity: number | null
  notes: string | null
  matched_asset_id: string | null
  matched_asset_name: string | null
  action: 'update' | 'create'
  warning: string | null
}

export interface ImportPreview {
  source: string
  report_date: string | null
  items: ImportPreviewItem[]
}

export interface ImportConfirmResult {
  updated: number
  created: number
  skipped: number
}

export async function parseReport(file: File): Promise<ImportPreview> {
  const form = new FormData()
  form.append('file', file)
  const resp = await apiClient.post<ImportPreview>('/import/parse-pdf', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return resp.data
}

export async function confirmImport(items: ImportPreviewItem[]): Promise<ImportConfirmResult> {
  const resp = await apiClient.post<ImportConfirmResult>('/import/confirm', { items })
  return resp.data
}
```

- [ ] **Step 3: 类型检查**

```bash
cd frontend && npm run typecheck
```

期望：无新增错误

- [ ] **Step 4: Commit**

```bash
git add frontend/src/api/import.ts
git commit -m "feat(phase5): add parseReport and confirmImport API functions"
```

---

## Task 8: Frontend — ImportReportPage.vue

**Files:**
- Create: `frontend/src/pages/ImportReportPage.vue`

- [ ] **Step 1: 查看现有页面结构参考**

```bash
head -60 frontend/src/pages/SettingsPage.vue
```

- [ ] **Step 2: 创建 ImportReportPage.vue**

```vue
<template>
  <div class="import-report-page">
    <van-nav-bar title="导入账单" left-arrow @click-left="router.back()" />

    <!-- 上传区域 -->
    <div v-if="step === 'upload'" class="upload-section">
      <van-cell-group inset class="upload-card">
        <div class="upload-hint">
          <p class="hint-title">上传金融账单 PDF</p>
          <p class="hint-desc">支持券商日结单、银行账单等金融文档，系统将自动识别持仓信息</p>
        </div>
        <van-uploader
          :after-read="handleFileRead"
          accept="application/pdf"
          :max-size="10 * 1024 * 1024"
          @oversize="showToast('文件不能超过 10MB')"
        >
          <van-button icon="plus" type="primary" block>选择 PDF 文件</van-button>
        </van-uploader>
      </van-cell-group>
    </div>

    <!-- 解析中 -->
    <div v-if="step === 'parsing'" class="parsing-section">
      <van-loading size="48px" vertical>正在解析中...</van-loading>
    </div>

    <!-- 预览确认 -->
    <div v-if="step === 'preview'" class="preview-section">
      <van-cell-group inset>
        <van-cell title="来源" :value="preview!.source || '未识别'" />
        <van-cell title="账单日期" :value="preview!.report_date || '未识别'" />
      </van-cell-group>

      <div class="preview-summary">
        将更新 <strong>{{ updateCount }}</strong> 条，新建 <strong>{{ createCount }}</strong> 条
      </div>

      <van-cell-group inset class="preview-list">
        <div
          v-for="item in editableItems"
          :key="item.temp_id"
          :class="['preview-item', item.warning ? 'has-warning' : '']"
        >
          <div class="item-row">
            <van-field
              v-model="item.name"
              label="名称"
              placeholder="资产名称"
              size="small"
            />
            <van-field
              v-model.number="item.current_value"
              label="市值"
              type="number"
              placeholder="请输入"
              size="small"
            />
          </div>
          <div class="item-meta">
            <van-tag :type="item.action === 'update' ? 'primary' : 'success'">
              {{ item.action === 'update' ? '更新' : '新建' }}
            </van-tag>
            <span v-if="item.matched_asset_name" class="matched-name">
              → {{ item.matched_asset_name }}
            </span>
            <span v-if="item.warning" class="warning-text">⚠ {{ item.warning }}</span>
          </div>
        </div>
      </van-cell-group>

      <div class="action-bar">
        <van-button plain @click="step = 'upload'">重新上传</van-button>
        <van-button type="primary" :loading="confirming" @click="handleConfirm">
          确认导入
        </van-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { showToast, showSuccessToast, showFailToast } from 'vant'
import { parseReport, confirmImport, type ImportPreview, type ImportPreviewItem } from '@/api/import'

const router = useRouter()
const step = ref<'upload' | 'parsing' | 'preview'>('upload')
const preview = ref<ImportPreview | null>(null)
const editableItems = ref<ImportPreviewItem[]>([])
const confirming = ref(false)

const updateCount = computed(() => editableItems.value.filter(i => i.action === 'update').length)
const createCount = computed(() => editableItems.value.filter(i => i.action === 'create').length)

async function handleFileRead(file: { file: File }) {
  step.value = 'parsing'
  try {
    const result = await parseReport(file.file)
    preview.value = result
    editableItems.value = result.items.map(i => ({ ...i }))
    step.value = 'preview'
  } catch (err: any) {
    step.value = 'upload'
    const msg = err?.response?.data?.detail || '解析失败，请检查文件是否为金融账单'
    showFailToast(msg)
  }
}

async function handleConfirm() {
  confirming.value = true
  try {
    const result = await confirmImport(editableItems.value)
    showSuccessToast(`导入完成：更新 ${result.updated} 条，新建 ${result.created} 条`)
    router.back()
  } catch {
    showFailToast('导入失败，请稍后重试')
  } finally {
    confirming.value = false
  }
}
</script>

<style scoped>
.import-report-page {
  min-height: 100vh;
  background: var(--van-background);
}
.upload-section,
.parsing-section,
.preview-section {
  padding: 16px;
}
.upload-card {
  padding: 24px 16px;
}
.upload-hint {
  text-align: center;
  margin-bottom: 20px;
}
.hint-title {
  font-size: 16px;
  font-weight: 600;
  margin-bottom: 8px;
}
.hint-desc {
  font-size: 13px;
  color: var(--van-text-color-2);
  line-height: 1.5;
}
.parsing-section {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 60vh;
}
.preview-summary {
  padding: 12px 16px;
  font-size: 14px;
  color: var(--van-text-color-2);
}
.preview-item {
  padding: 12px 16px;
  border-bottom: 1px solid var(--van-border-color);
}
.preview-item.has-warning {
  background: #fffbe6;
}
.item-row {
  display: flex;
  gap: 8px;
}
.item-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 6px;
  font-size: 12px;
}
.matched-name {
  color: var(--van-text-color-2);
}
.warning-text {
  color: #ff976a;
}
.action-bar {
  display: flex;
  gap: 12px;
  padding: 16px;
  position: sticky;
  bottom: 0;
  background: var(--van-background);
}
.action-bar .van-button {
  flex: 1;
}
</style>
```

- [ ] **Step 3: 类型检查**

```bash
cd frontend && npm run typecheck
```

期望：无新增错误

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/ImportReportPage.vue
git commit -m "feat(phase5): add ImportReportPage with upload, preview, and confirm flow"
```

---

## Task 9: Frontend — 路由注册 + 设置页入口

**Files:**
- Modify: `frontend/src/router/index.ts`
- Modify: `frontend/src/pages/SettingsPage.vue`

- [ ] **Step 1: 在 router/index.ts 注册路由**

找到现有路由列表，添加：

```typescript
{
  path: '/import-report',
  component: () => import('@/pages/ImportReportPage.vue'),
  meta: { requiresAuth: true },
},
```

- [ ] **Step 2: 在 SettingsPage.vue 添加入口**

找到"数据管理"相关的 cell-group（或导出/导入附近），添加：

```vue
<van-cell
  title="导入账单"
  label="从 PDF 账单智能导入持仓数据"
  is-link
  @click="router.push('/import-report')"
/>
```

- [ ] **Step 3: 类型检查**

```bash
cd frontend && npm run typecheck
```

期望：无新增错误

- [ ] **Step 4: Commit**

```bash
git add frontend/src/router/index.ts frontend/src/pages/SettingsPage.vue
git commit -m "feat(phase5): register import-report route and add settings entry"
```

---

## 自检：Spec 覆盖验证

| Spec 要求 | 对应 Task |
|-----------|-----------|
| PDF 上传 → pdfplumber 提取文本 | Task 4（`_extract_pdf_text`） |
| 调用 Agent 微服务 LLM 解析 | Task 1-2（agent router + capability） |
| 返回 ImportPreview（含 matched_asset） | Task 4（parse 端点） |
| 用户预览可编辑 | Task 8（ImportReportPage.vue） |
| 确认后 update/create 资产 | Task 5（confirm 端点） |
| 精确+模糊资产匹配 | Task 5（`_match_asset`） |
| 跨家庭资产不可更新 | Task 5（confirm 测试 `test_confirm_skips_cross_family_asset`） |
| 扫描件 PDF → 400 | Task 4（`_extract_pdf_text` 返回空 → AppError） |
| LLM 未识别 → 422 | Task 4（`items` 为空 → AppError） |
| Agent 超时 → 504 | Task 4（`httpx.TimeoutException`） |
| 部分字段缺失 → warning | Task 4（`warning` 字段） |
| ErrorCode 新增 | Task 3 |
| 前端错误提示中文 | Task 8（`showFailToast` 中文消息） |
| 设置页入口 | Task 9 |
| Agent 测试 | Task 1-2 |
| Backend 路由测试 | Task 4-5 |
| 资产匹配逻辑测试 | Task 5 |

所有 Spec 要求均有对应 Task，无遗漏。
