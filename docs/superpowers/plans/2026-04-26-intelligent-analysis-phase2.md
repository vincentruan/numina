# 智能分析 Phase 2 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现消费漏洞检测、购买 vs 租赁计算器、消费等价换算三个智能分析功能

**Architecture:** 消费漏洞检测走 backend→agent orchestrator 管道，结果持久化到新表 `ai_spending_leaks`；买租计算器和消费等价换算为纯计算端点，无 DB 存储，无 LLM 调用。前端：漏洞检测放 AI 页面，另两个放资产详情页。

**Tech Stack:** Python 3.11 + FastAPI + SQLAlchemy (backend)；FastAPI (agent)；Vue 3 + TypeScript + Vant 4 (frontend)

---

## 文件变更清单

### Backend（新建）
- `backend/app/models/ai_spending_leak.py`
- `backend/app/routers/ai_spending_leaks.py`
- `backend/app/routers/assets_analysis.py`
- `backend/tests/test_ai_spending_leaks.py`
- `backend/tests/test_assets_analysis.py`

### Backend（修改）
- `backend/app/errors/codes.py` — 新增 `AI_SPENDING_LEAK_NOT_FOUND`
- `backend/app/main.py` — 注册两个新 router + import 新模型

### Agent（新建）
- `agent/routers/spending_leak.py`

### Agent（修改）
- `agent/app/main.py` — 注册新 router
- `agent/services/fallback_engine.py` — 新增 `spending_leak` case

### Frontend（新建）
- `frontend/src/api/aiSpendingLeaks.ts`
- `frontend/src/api/assetsAnalysis.ts`
- `frontend/src/views/ai/SpendingLeaksCard.vue`
- `frontend/src/views/assets/components/BuyVsRentCalculator.vue`
- `frontend/src/views/assets/components/CostEquivalenceCard.vue`

### Frontend（修改）
- `frontend/src/views/ai/AIPage.vue` — 嵌入 SpendingLeaksCard
- `frontend/src/views/assets/AssetDetailPage.vue` — 嵌入两个新组件

---
## Task 1: 数据库模型 + ErrorCode

**Files:**
- Create: `backend/app/models/ai_spending_leak.py`
- Modify: `backend/app/errors/codes.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: 新建模型文件**

```python
# backend/app/models/ai_spending_leak.py
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.utils.snowflake import next_id


class AISpendingLeak(Base):
    __tablename__ = "ai_spending_leaks"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    family_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("families.id"), nullable=False, index=True)
    asset_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("assets.id"), nullable=False)
    asset_name: Mapped[str] = mapped_column(String(200), nullable=False)
    leak_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # leak_type: high_idle_cost | redundant | high_maintenance
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="medium")
    # severity: low | medium | high
    estimated_annual_waste: Mapped[float | None] = mapped_column(Float, nullable=True)
    suggestion: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_dismissed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=func.now())
    dismissed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
```

- [ ] **Step 2: 新增 ErrorCode**

在 `backend/app/errors/codes.py` 的 AI 区块末尾（`AI_QUESTION_EMPTY` 之后）添加：

```python
    AI_SPENDING_LEAK_NOT_FOUND = "AI_SPENDING_LEAK_NOT_FOUND"
```

在同文件 `ERROR_META` 字典中（`AI_QUESTION_EMPTY: 422` 之后）添加：

```python
    ErrorCode.AI_SPENDING_LEAK_NOT_FOUND: 404,
```

- [ ] **Step 3: 在 main.py 注册模型 import**

在 `backend/app/main.py` 的模型 import 区块（`from app.models.ai_ws_ticket import AIWsTicket` 附近）添加：

```python
from app.models.ai_spending_leak import AISpendingLeak  # noqa: F401
```

- [ ] **Step 4: 验证表会被自动创建**

```bash
cd backend && uv run python -c "from app.models.ai_spending_leak import AISpendingLeak; print('OK', AISpendingLeak.__tablename__)"
```

Expected: `OK ai_spending_leaks`

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/ai_spending_leak.py backend/app/errors/codes.py backend/app/main.py
git commit -m "feat(model): add AISpendingLeak model and error code"
```

---

## Task 2: Backend Router — ai_spending_leaks

**Files:**
- Create: `backend/app/routers/ai_spending_leaks.py`
- Create: `backend/tests/test_ai_spending_leaks.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_ai_spending_leaks.py
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

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
    """GET /ai/spending-leaks returns empty list when no leaks."""
    resp = client.get("/api/v1/ai/spending-leaks", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["data"] == []


def test_get_spending_leaks_returns_undismissed(client, auth_headers, db):
    """GET /ai/spending-leaks returns only undismissed leaks for the family."""
    me = client.get("/api/v1/auth/me", headers=auth_headers).json()
    family_id = me["data"]["family_id"]

    # Seed one active and one dismissed leak
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
    """POST /ai/spending-leaks/{id}/dismiss marks leak as dismissed."""
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
    """POST /ai/spending-leaks/99999/dismiss returns 404."""
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
    """POST /ai/spending-leaks/refresh calls agent and writes results."""
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
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd backend && uv run pytest tests/test_ai_spending_leaks.py -v 2>&1 | head -30
```

Expected: ImportError or 404 (router not registered yet)

- [ ] **Step 3: 实现 router**

```python
# backend/app/routers/ai_spending_leaks.py
"""AI 消费漏洞检测端点。"""

import logging
from datetime import datetime

import httpx
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.ai_deps import require_ai_enabled
from app.auth.deps import require_adult
from app.config import settings
from app.database import get_db
from app.errors import AppError, ErrorCode
from app.models.ai_spending_leak import AISpendingLeak
from app.models.user import User

router = APIRouter(prefix="/ai/spending-leaks", tags=["ai-spending-leaks"])
logger = logging.getLogger(__name__)


@router.get("")
def get_leaks(
    current_user: User = Depends(require_adult),
    db: Session = Depends(get_db),
):
    leaks = (
        db.query(AISpendingLeak)
        .filter(
            AISpendingLeak.family_id == current_user.family_id,
            AISpendingLeak.is_dismissed == False,
        )
        .order_by(AISpendingLeak.created_at.desc())
        .all()
    )
    return [
        {
            "id": l.id,
            "asset_id": l.asset_id,
            "asset_name": l.asset_name,
            "leak_type": l.leak_type,
            "severity": l.severity,
            "estimated_annual_waste": l.estimated_annual_waste,
            "suggestion": l.suggestion,
            "created_at": l.created_at.isoformat(),
        }
        for l in leaks
    ]


@router.post("/refresh")
async def refresh_leaks(
    current_user: User = Depends(require_adult),
    _ai: None = Depends(require_ai_enabled),
    db: Session = Depends(get_db),
):
    """触发 agent 扫描并刷新消费漏洞（清除旧记录，写入新记录）。"""
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{settings.AGENT_BASE_URL}/spending-leak",
                headers={
                    "X-Family-Id": str(current_user.family_id),
                    "X-Agent-Token": settings.AGENT_INTERNAL_TOKEN,
                },
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        logger.error(f"调用 agent spending-leak 失败: {e}")
        raise AppError(ErrorCode.AI_SERVICE_UNAVAILABLE)

    raw_leaks = data.get("leaks", [])

    try:
        db.query(AISpendingLeak).filter(
            AISpendingLeak.family_id == current_user.family_id,
            AISpendingLeak.is_dismissed == False,
        ).delete()

        for leak in raw_leaks:
            db.add(AISpendingLeak(
                family_id=current_user.family_id,
                asset_id=leak["asset_id"],
                asset_name=leak["asset_name"],
                leak_type=leak["leak_type"],
                severity=leak["severity"],
                estimated_annual_waste=leak.get("estimated_annual_waste"),
                suggestion=leak.get("suggestion"),
            ))
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"写入消费漏洞数据失败: {e}")
        raise AppError(ErrorCode.AI_DATA_WRITE_FAILED)

    return {"refreshed": len(raw_leaks)}


@router.post("/{leak_id}/dismiss")
def dismiss_leak(
    leak_id: int,
    current_user: User = Depends(require_adult),
    db: Session = Depends(get_db),
):
    leak = db.query(AISpendingLeak).filter(
        AISpendingLeak.id == leak_id,
        AISpendingLeak.family_id == current_user.family_id,
    ).first()
    if not leak:
        raise AppError(ErrorCode.AI_SPENDING_LEAK_NOT_FOUND)
    leak.is_dismissed = True
    leak.dismissed_at = datetime.utcnow()
    db.commit()
    return {"ok": True}
```

- [ ] **Step 4: 在 main.py 注册 router**

在 `backend/app/main.py` 的 router import 区块（`ai_alerts_router` 附近）添加：

```python
from app.routers import ai_spending_leaks as ai_spending_leaks_router
```

在 router 注册区块（`app.include_router(ai_alerts_router.router, ...)` 之后）添加：

```python
app.include_router(ai_spending_leaks_router.router, prefix="/api/v1")
```

- [ ] **Step 5: 运行测试确认通过**

```bash
cd backend && uv run pytest tests/test_ai_spending_leaks.py -v
```

Expected: 5 tests PASSED

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/ai_spending_leaks.py backend/tests/test_ai_spending_leaks.py backend/app/main.py
git commit -m "feat(api): add ai/spending-leaks endpoints"
```

---
## Task 3: Backend Router — assets_analysis (买租计算器 + 等价换算)

**Files:**
- Create: `backend/app/routers/assets_analysis.py`
- Create: `backend/tests/test_assets_analysis.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_assets_analysis.py
import pytest


def test_buy_vs_rent_buy_cheaper(client, auth_headers):
    """买入总成本 < 租赁总成本时推荐购买。"""
    resp = client.post(
        "/api/v1/assets/buy-vs-rent",
        json={
            "purchase_price": 5000.0,
            "monthly_rent": 500.0,
            "usage_months": 24,
            "annual_maintenance_cost": 200.0,
            "depreciation_years": 10,
            "residual_value_rate": 0.1,
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["buy_total"] < data["rent_total"]
    assert data["recommendation"] == "购买更划算"
    assert data["breakeven_months"] is not None


def test_buy_vs_rent_rent_cheaper(client, auth_headers):
    """租赁总成本 < 买入总成本时推荐租赁。"""
    resp = client.post(
        "/api/v1/assets/buy-vs-rent",
        json={
            "purchase_price": 50000.0,
            "monthly_rent": 200.0,
            "usage_months": 12,
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["rent_total"] < data["buy_total"]
    assert data["recommendation"] == "租赁更划算"


def test_buy_vs_rent_breakeven_null_when_rent_le_maintenance(client, auth_headers):
    """月租 <= 月均维护费时 breakeven_months 为 null。"""
    resp = client.post(
        "/api/v1/assets/buy-vs-rent",
        json={
            "purchase_price": 10000.0,
            "monthly_rent": 50.0,
            "usage_months": 12,
            "annual_maintenance_cost": 1200.0,  # 月均 100 > 月租 50
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["breakeven_months"] is None


def test_buy_vs_rent_validation(client, auth_headers):
    """缺少必填字段返回 422。"""
    resp = client.post(
        "/api/v1/assets/buy-vs-rent",
        json={"purchase_price": 1000.0},
        headers=auth_headers,
    )
    assert resp.status_code == 422


def test_cost_equivalence_full(client, auth_headers, db):
    """GET /assets/{id}/cost-equivalence 返回三种换算结果。"""
    from datetime import date, timedelta
    from app.models.asset import Asset
    from app.models.category import Category

    me = client.get("/api/v1/auth/me", headers=auth_headers).json()
    family_id = me["data"]["family_id"]
    user_id = me["data"]["id"]

    cat = db.query(Category).filter_by(asset_type="physical").first()
    asset = Asset(
        user_id=user_id,
        family_id=family_id,
        category_id=cat.id,
        name="测试笔记本",
        asset_type="physical",
        purchase_price=8000.0,
        annual_maintenance_cost=400.0,
        purchase_date=date.today() - timedelta(days=365),
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)

    resp = client.get(
        f"/api/v1/assets/{asset.id}/cost-equivalence",
        params={"hourly_wage": 100.0, "yield_rate": 0.05, "years": 5},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["held_days"] == 365
    assert data["total_held_cost"] == pytest.approx(8400.0, rel=0.01)
    assert data["daily_cost"] == pytest.approx(8400.0 / 365, rel=0.01)
    assert data["time_cost_hours"] == pytest.approx(8400.0 / 100.0, rel=0.01)
    assert data["opportunity_cost"] == pytest.approx(8400.0 * (1.05 ** 5) - 8400.0, rel=0.01)


def test_cost_equivalence_null_when_no_purchase_price(client, auth_headers, db):
    """资产无 purchase_price 时返回 null 字段，不报错。"""
    from app.models.asset import Asset
    from app.models.category import Category

    me = client.get("/api/v1/auth/me", headers=auth_headers).json()
    family_id = me["data"]["family_id"]
    user_id = me["data"]["id"]

    cat = db.query(Category).filter_by(asset_type="physical").first()
    asset = Asset(
        user_id=user_id,
        family_id=family_id,
        category_id=cat.id,
        name="无价格资产",
        asset_type="physical",
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)

    resp = client.get(
        f"/api/v1/assets/{asset.id}/cost-equivalence",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["daily_cost"] is None
    assert data["time_cost_hours"] is None
    assert data["opportunity_cost"] is None


def test_cost_equivalence_asset_not_found(client, auth_headers):
    """不存在的资产返回 404。"""
    resp = client.get("/api/v1/assets/99999/cost-equivalence", headers=auth_headers)
    assert resp.status_code == 404
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd backend && uv run pytest tests/test_assets_analysis.py -v 2>&1 | head -20
```

Expected: 404 or ImportError (router not registered)

- [ ] **Step 3: 实现 router**

```python
# backend/app/routers/assets_analysis.py
"""资产分析工具端点 — 买租计算器、消费等价换算（纯计算，无 LLM）。"""

from datetime import date

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy.orm import Session

from app.auth.deps import require_adult
from app.database import get_db
from app.errors import AppError, ErrorCode
from app.models.asset import Asset
from app.models.user import User

router = APIRouter(tags=["assets-analysis"])


class BuyVsRentRequest(BaseModel):
    purchase_price: float
    monthly_rent: float
    usage_months: int
    annual_maintenance_cost: float = 0.0
    depreciation_years: int = 10
    residual_value_rate: float = 0.1

    @field_validator("usage_months")
    @classmethod
    def validate_usage_months(cls, v: int) -> int:
        if not (1 <= v <= 600):
            raise ValueError("usage_months 必须在 1-600 之间")
        return v

    @field_validator("residual_value_rate")
    @classmethod
    def validate_residual_rate(cls, v: float) -> float:
        if not (0.0 <= v <= 1.0):
            raise ValueError("residual_value_rate 必须在 0-1 之间")
        return v


class BuyVsRentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    buy_total: float
    rent_total: float
    breakeven_months: float | None
    recommendation: str
    buy_advantage_pct: float


@router.post("/assets/buy-vs-rent", response_model=BuyVsRentResponse)
def calculate_buy_vs_rent(
    body: BuyVsRentRequest,
    user: User = Depends(require_adult),
):
    usage_years = body.usage_months / 12.0
    total_maintenance = body.annual_maintenance_cost * usage_years
    residual_value = body.purchase_price * body.residual_value_rate * max(
        0.0, 1.0 - usage_years / body.depreciation_years
    )
    buy_total = body.purchase_price + total_maintenance - residual_value
    rent_total = body.monthly_rent * body.usage_months

    monthly_maintenance = body.annual_maintenance_cost / 12.0
    if body.monthly_rent > monthly_maintenance:
        breakeven_months: float | None = body.purchase_price / (body.monthly_rent - monthly_maintenance)
    else:
        breakeven_months = None

    diff_pct = (rent_total - buy_total) / rent_total * 100 if rent_total else 0.0
    if abs(diff_pct) < 10.0:
        recommendation = "两者相近，建议租赁以保持灵活性"
    elif buy_total < rent_total:
        recommendation = "购买更划算"
    else:
        recommendation = "租赁更划算"

    return BuyVsRentResponse(
        buy_total=round(buy_total, 2),
        rent_total=round(rent_total, 2),
        breakeven_months=round(breakeven_months, 1) if breakeven_months is not None else None,
        recommendation=recommendation,
        buy_advantage_pct=round(diff_pct, 1),
    )


@router.get("/assets/{asset_id}/cost-equivalence")
def get_cost_equivalence(
    asset_id: int,
    hourly_wage: float = Query(50.0, gt=0),
    yield_rate: float = Query(0.05, ge=0, le=1),
    years: int = Query(10, ge=1, le=30),
    user: User = Depends(require_adult),
    db: Session = Depends(get_db),
):
    asset = db.query(Asset).filter(
        Asset.id == asset_id,
        Asset.family_id == user.family_id,
        Asset.is_archived == False,
    ).first()
    if not asset:
        raise AppError(ErrorCode.ASSET_NOT_FOUND)

    if asset.purchase_price is None or asset.purchase_date is None:
        return {
            "asset_id": asset.id,
            "asset_name": asset.name,
            "held_days": None,
            "total_held_cost": None,
            "daily_cost": None,
            "time_cost_hours": None,
            "opportunity_cost": None,
        }

    today = date.today()
    held_days = (today - asset.purchase_date).days
    if held_days <= 0:
        held_days = 1

    annual_maintenance = asset.annual_maintenance_cost or 0.0
    total_held_cost = asset.purchase_price + annual_maintenance * (held_days / 365.0)
    daily_cost = total_held_cost / held_days
    time_cost_hours = total_held_cost / hourly_wage
    opportunity_cost = total_held_cost * ((1 + yield_rate) ** years) - total_held_cost

    return {
        "asset_id": asset.id,
        "asset_name": asset.name,
        "held_days": held_days,
        "total_held_cost": round(total_held_cost, 2),
        "daily_cost": round(daily_cost, 4),
        "time_cost_hours": round(time_cost_hours, 2),
        "opportunity_cost": round(opportunity_cost, 2),
    }
```

- [ ] **Step 4: 在 main.py 注册 router**

在 `backend/app/main.py` 的 router import 区块添加：

```python
from app.routers import assets_analysis as assets_analysis_router
```

在 router 注册区块（`app.include_router(assets.router, ...)` 之后）添加：

```python
app.include_router(assets_analysis_router.router, prefix="/api/v1")
```

- [ ] **Step 5: 运行测试确认通过**

```bash
cd backend && uv run pytest tests/test_assets_analysis.py -v
```

Expected: 7 tests PASSED

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/assets_analysis.py backend/tests/test_assets_analysis.py backend/app/main.py
git commit -m "feat(api): add buy-vs-rent and cost-equivalence endpoints"
```

---
## Task 4: Agent — spending_leak capability

**Files:**
- Create: `agent/routers/spending_leak.py`
- Modify: `agent/app/main.py`
- Modify: `agent/services/fallback_engine.py`

- [ ] **Step 1: 新建 agent router**

```python
# agent/routers/spending_leak.py
"""消费漏洞检测 agent 路由。"""

import logging

from fastapi import APIRouter, Header, HTTPException

from app.config import settings
from services.orchestrator import orchestrator

router = APIRouter(prefix="/spending-leak", tags=["spending-leak"])
logger = logging.getLogger(__name__)


@router.post("")
async def analyze_spending_leaks(
    x_family_id: str = Header(..., alias="X-Family-Id"),
    x_agent_token: str = Header(..., alias="X-Agent-Token"),
    x_user_id: str = Header(None, alias="X-User-Id"),
):
    """分析家庭消费漏洞（由 backend 调用）。"""
    if x_agent_token != settings.AGENT_INTERNAL_TOKEN:
        raise HTTPException(status_code=401, detail="invalid token")

    response = await orchestrator.dispatch(
        capability="spending_leak",
        family_id=x_family_id,
        user_id=x_user_id,
    )
    return response.model_dump()
```

- [ ] **Step 2: 在 agent/app/main.py 注册 router**

在 `agent/app/main.py` 的 router import 区块（`from routers import allocation as allocation_router` 附近）添加：

```python
from routers import spending_leak as spending_leak_router
```

在 `app.include_router(allocation_router.router)` 之后添加：

```python
app.include_router(spending_leak_router.router)
```

- [ ] **Step 3: 在 fallback_engine.py 新增 spending_leak case**

在 `agent/services/fallback_engine.py` 的 `_run_legacy` 方法中，`elif capability == "chat":` 之前添加：

```python
        elif capability == "spending_leak":
            from services.spending_leak import scan_spending_leaks
            leaks = await scan_spending_leaks(family_id=family_id, llm=llm, ctx=ctx)
            return {"leaks": leaks, "summary": f"发现 {len(leaks)} 条消费漏洞"}
```

- [ ] **Step 4: 新建 spending_leak service**

```python
# agent/services/spending_leak.py
"""消费漏洞检测服务。

规则层（无需 LLM）：
- high_idle_cost: usage_frequency in (rarely, idle) 且 daily_cost > 5
- redundant: 同 category_id 下 >= 2 个 in_use 资产
- high_maintenance: annual_maintenance_cost / current_value > 0.15

LLM 层：为每条漏洞生成建议文本。
"""

import logging
from collections import defaultdict

from core.backend_client import BackendClient
from core.llm import LLMClient
from schemas.context import RedactedContext

logger = logging.getLogger(__name__)

SUGGEST_PROMPT = """你是家庭资产管理顾问。以下是一项资产的消费漏洞信息，请用一句话（30字以内）给出具体建议。

资产名称：{name}
漏洞类型：{leak_type_label}
年度估算浪费：{waste}元

只输出建议文本，不要任何前缀或解释。"""

LEAK_TYPE_LABELS = {
    "high_idle_cost": "高闲置成本",
    "redundant": "冗余持有",
    "high_maintenance": "高维护负担",
}


async def scan_spending_leaks(family_id: str, llm: LLMClient, ctx: RedactedContext) -> list[dict]:
    """扫描家庭资产，返回消费漏洞列表。"""
    client = BackendClient(family_id=family_id)

    try:
        low_usage = await client.get_dashboard_low_usage()
        daily_cost_ranking = await client.get_dashboard_daily_cost()
    except Exception as e:
        logger.error(f"[spending_leak] 拉取数据失败 family={family_id}: {e}")
        raise

    leaks: list[dict] = []
    seen_asset_ids: set = set()

    # ── high_idle_cost: 低频 + 日均成本 > 5 ──────────────────────────
    for asset in low_usage:
        freq = asset.get("usage_frequency", "")
        daily_cost = asset.get("daily_cost") or 0.0
        if freq not in ("rarely", "idle") or daily_cost <= 5.0:
            continue
        asset_id = asset.get("id")
        seen_asset_ids.add(asset_id)
        annual_waste = round(daily_cost * 365, 2)
        severity = "high" if daily_cost > 30 else "medium"
        suggestion = await _get_suggestion(
            llm=llm,
            name=asset.get("name", ""),
            leak_type_label=LEAK_TYPE_LABELS["high_idle_cost"],
            waste=annual_waste,
        )
        leaks.append({
            "asset_id": asset_id,
            "asset_name": asset.get("name", ""),
            "leak_type": "high_idle_cost",
            "severity": severity,
            "estimated_annual_waste": annual_waste,
            "suggestion": suggestion,
        })

    # ── redundant: 同类别 >= 2 个 in_use 资产 ────────────────────────
    # daily_cost_ranking contains in_use assets with cost data
    category_assets: dict[str, list[dict]] = defaultdict(list)
    for asset in daily_cost_ranking:
        cat = str(asset.get("category_id") or asset.get("category_name", ""))
        if cat:
            category_assets[cat].append(asset)

    for cat, assets in category_assets.items():
        if len(assets) < 2:
            continue
        # Flag all but the highest-value asset as redundant
        sorted_assets = sorted(assets, key=lambda a: a.get("current_value") or 0, reverse=True)
        for asset in sorted_assets[1:]:
            asset_id = asset.get("id")
            if asset_id in seen_asset_ids:
                continue
            seen_asset_ids.add(asset_id)
            daily_cost = asset.get("daily_cost") or 0.0
            annual_waste = round(daily_cost * 365, 2)
            suggestion = await _get_suggestion(
                llm=llm,
                name=asset.get("name", ""),
                leak_type_label=LEAK_TYPE_LABELS["redundant"],
                waste=annual_waste,
            )
            leaks.append({
                "asset_id": asset_id,
                "asset_name": asset.get("name", ""),
                "leak_type": "redundant",
                "severity": "low",
                "estimated_annual_waste": annual_waste,
                "suggestion": suggestion,
            })

    # ── high_maintenance: 年维护费 / 当前价值 > 15% ───────────────────
    for asset in daily_cost_ranking:
        asset_id = asset.get("id")
        if asset_id in seen_asset_ids:
            continue
        maintenance = asset.get("annual_maintenance_cost") or 0.0
        value = asset.get("current_value") or 0.0
        if value <= 0 or maintenance / value <= 0.15:
            continue
        seen_asset_ids.add(asset_id)
        annual_waste = round(maintenance, 2)
        suggestion = await _get_suggestion(
            llm=llm,
            name=asset.get("name", ""),
            leak_type_label=LEAK_TYPE_LABELS["high_maintenance"],
            waste=annual_waste,
        )
        leaks.append({
            "asset_id": asset_id,
            "asset_name": asset.get("name", ""),
            "leak_type": "high_maintenance",
            "severity": "high" if maintenance / value > 0.30 else "medium",
            "estimated_annual_waste": annual_waste,
            "suggestion": suggestion,
        })

    return leaks


async def _get_suggestion(llm: LLMClient, name: str, leak_type_label: str, waste: float) -> str:
    try:
        prompt = SUGGEST_PROMPT.format(
            name=name,
            leak_type_label=leak_type_label,
            waste=waste,
        )
        return (await llm.complete(prompt, max_tokens=60)).strip()
    except Exception as e:
        logger.warning(f"[spending_leak] LLM 建议生成失败: {e}")
        return ""
```

- [ ] **Step 5: 验证 agent 语法**

```bash
cd agent && uv run python -c "from routers.spending_leak import router; print('OK')"
```

Expected: `OK`

```bash
cd agent && uv run python -c "from services.spending_leak import scan_spending_leaks; print('OK')"
```

Expected: `OK`

- [ ] **Step 6: Commit**

```bash
git add agent/routers/spending_leak.py agent/services/spending_leak.py agent/app/main.py agent/services/fallback_engine.py
git commit -m "feat(agent): add spending_leak capability"
```

---
## Task 5: Frontend API 层

**Files:**
- Create: `frontend/src/api/aiSpendingLeaks.ts`
- Create: `frontend/src/api/assetsAnalysis.ts`

先看现有 API 文件的 import 模式，确保一致。

- [ ] **Step 1: 查看现有 API 文件模式**

```bash
head -10 frontend/src/api/assets.ts
```

- [ ] **Step 2: 新建 aiSpendingLeaks.ts**

```typescript
// frontend/src/api/aiSpendingLeaks.ts
import { useHttp } from '@/composables/useHttp'

export interface SpendingLeakItem {
  id: number
  asset_id: number
  asset_name: string
  leak_type: 'high_idle_cost' | 'redundant' | 'high_maintenance'
  severity: 'low' | 'medium' | 'high'
  estimated_annual_waste: number | null
  suggestion: string | null
  created_at: string
}

export function useAiSpendingLeaksApi() {
  const http = useHttp()

  const getLeaks = (): Promise<SpendingLeakItem[]> =>
    http.get('/api/v1/ai/spending-leaks')

  const refreshLeaks = (): Promise<{ refreshed: number }> =>
    http.post('/api/v1/ai/spending-leaks/refresh')

  const dismissLeak = (id: number): Promise<{ ok: boolean }> =>
    http.post(`/api/v1/ai/spending-leaks/${id}/dismiss`)

  return { getLeaks, refreshLeaks, dismissLeak }
}
```

> 注意：如果项目使用 axios 直接调用而非 composable，参考 `frontend/src/api/assets.ts` 的实际模式调整。

- [ ] **Step 3: 新建 assetsAnalysis.ts**

```typescript
// frontend/src/api/assetsAnalysis.ts
import { useHttp } from '@/composables/useHttp'

export interface BuyVsRentParams {
  purchase_price: number
  monthly_rent: number
  usage_months: number
  annual_maintenance_cost?: number
  depreciation_years?: number
  residual_value_rate?: number
}

export interface BuyVsRentResult {
  buy_total: number
  rent_total: number
  breakeven_months: number | null
  recommendation: string
  buy_advantage_pct: number
}

export interface CostEquivalenceResult {
  asset_id: number
  asset_name: string
  held_days: number | null
  total_held_cost: number | null
  daily_cost: number | null
  time_cost_hours: number | null
  opportunity_cost: number | null
}

export function useAssetsAnalysisApi() {
  const http = useHttp()

  const calculateBuyVsRent = (params: BuyVsRentParams): Promise<BuyVsRentResult> =>
    http.post('/api/v1/assets/buy-vs-rent', params)

  const getCostEquivalence = (
    assetId: number,
    params?: { hourly_wage?: number; yield_rate?: number; years?: number },
  ): Promise<CostEquivalenceResult> =>
    http.get(`/api/v1/assets/${assetId}/cost-equivalence`, { params })

  return { calculateBuyVsRent, getCostEquivalence }
}
```

- [ ] **Step 4: 运行 typecheck 确认无类型错误**

```bash
cd frontend && npm run typecheck 2>&1 | grep -E "error|Error" | head -20
```

Expected: 无新增错误

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/aiSpendingLeaks.ts frontend/src/api/assetsAnalysis.ts
git commit -m "feat(api): add frontend API types for spending leaks and asset analysis"
```

---

## Task 6: Frontend UI — SpendingLeaksCard (AI 页面)

**Files:**
- Create: `frontend/src/views/ai/SpendingLeaksCard.vue`
- Modify: `frontend/src/views/ai/AIPage.vue` (或实际 AI 页面路径)

- [ ] **Step 1: 确认 AI 页面路径**

```bash
find frontend/src/views -name "*.vue" | xargs grep -l "ai_report\|AIReport\|体检报告" | head -5
```

- [ ] **Step 2: 新建 SpendingLeaksCard.vue**

```vue
<!-- frontend/src/views/ai/SpendingLeaksCard.vue -->
<template>
  <div class="spending-leaks-card">
    <div class="card-header">
      <span class="card-title">消费漏洞检测</span>
      <van-button
        size="small"
        :loading="refreshing"
        @click="handleRefresh"
      >重新分析</van-button>
    </div>

    <van-loading v-if="loading" class="loading-center" />

    <van-empty v-else-if="leaks.length === 0" description="暂无消费漏洞" />

    <div v-else class="leak-list">
      <div
        v-for="leak in leaks"
        :key="leak.id"
        :class="['leak-item', `severity-${leak.severity}`]"
      >
        <div class="leak-header">
          <span class="leak-name">{{ leak.asset_name }}</span>
          <van-tag :type="severityTagType(leak.severity)">{{ severityLabel(leak.severity) }}</van-tag>
        </div>
        <p class="leak-suggestion">{{ leak.suggestion }}</p>
        <div class="leak-footer">
          <span class="waste-amount">年浪费约 ¥{{ formatAmount(leak.estimated_annual_waste) }}</span>
          <van-button size="mini" plain @click="handleDismiss(leak.id)">忽略</van-button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { showToast } from 'vant'
import { useAiSpendingLeaksApi, type SpendingLeakItem } from '@/api/aiSpendingLeaks'

const { getLeaks, refreshLeaks, dismissLeak } = useAiSpendingLeaksApi()

const leaks = ref<SpendingLeakItem[]>([])
const loading = ref(false)
const refreshing = ref(false)

const loadLeaks = async () => {
  loading.value = true
  try {
    leaks.value = await getLeaks()
  } finally {
    loading.value = false
  }
}

const handleRefresh = async () => {
  refreshing.value = true
  try {
    const result = await refreshLeaks()
    showToast(`分析完成，发现 ${result.refreshed} 条漏洞`)
    await loadLeaks()
  } catch {
    showToast('分析失败，请稍后重试')
  } finally {
    refreshing.value = false
  }
}

const handleDismiss = async (id: number) => {
  await dismissLeak(id)
  leaks.value = leaks.value.filter(l => l.id !== id)
}

const severityTagType = (severity: string) => {
  return { high: 'danger', medium: 'warning', low: 'primary' }[severity] ?? 'default'
}

const severityLabel = (severity: string) => {
  return { high: '高', medium: '中', low: '低' }[severity] ?? severity
}

const formatAmount = (amount: number | null) => {
  if (amount == null) return '--'
  return amount.toFixed(0)
}

onMounted(loadLeaks)
</script>
```

- [ ] **Step 3: 在 AI 页面嵌入 SpendingLeaksCard**

在 AI 页面（Step 1 找到的文件）中，在体检报告卡片或老化预警卡片附近添加：

```vue
<SpendingLeaksCard />
```

并在 `<script setup>` 中添加 import：

```typescript
import SpendingLeaksCard from './SpendingLeaksCard.vue'
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/views/ai/SpendingLeaksCard.vue
git commit -m "feat(ui): add SpendingLeaksCard to AI page"
```

---

## Task 7: Frontend UI — BuyVsRentCalculator + CostEquivalenceCard (资产详情页)

**Files:**
- Create: `frontend/src/views/assets/components/BuyVsRentCalculator.vue`
- Create: `frontend/src/views/assets/components/CostEquivalenceCard.vue`
- Modify: `frontend/src/views/assets/AssetDetailPage.vue` (或实际资产详情页路径)

- [ ] **Step 1: 确认资产详情页路径**

```bash
find frontend/src/views -name "*.vue" | xargs grep -l "purchase_price\|AssetDetail" | head -5
```

- [ ] **Step 2: 新建 BuyVsRentCalculator.vue**

```vue
<!-- frontend/src/views/assets/components/BuyVsRentCalculator.vue -->
<template>
  <div class="buy-vs-rent-calculator">
    <div class="section-title">买 vs 租计算器</div>

    <van-cell-group inset>
      <van-field
        v-model.number="form.purchase_price"
        label="购买价格 (¥)"
        type="number"
        placeholder="输入购买价格"
      />
      <van-field
        v-model.number="form.monthly_rent"
        label="月租金 (¥)"
        type="number"
        placeholder="输入月租金"
      />
      <van-field
        v-model.number="form.usage_months"
        label="使用月数"
        type="number"
        placeholder="计划使用多少个月"
      />
      <van-field
        v-model.number="form.annual_maintenance_cost"
        label="年维护费 (¥)"
        type="number"
        placeholder="可选，默认 0"
      />
    </van-cell-group>

    <div class="calc-btn-row">
      <van-button block type="primary" :loading="loading" @click="calculate">计算</van-button>
    </div>

    <div v-if="result" class="result-card">
      <div class="result-row">
        <span>买入总成本</span>
        <span class="amount">¥{{ result.buy_total.toFixed(2) }}</span>
      </div>
      <div class="result-row">
        <span>租赁总成本</span>
        <span class="amount">¥{{ result.rent_total.toFixed(2) }}</span>
      </div>
      <div class="result-row">
        <span>盈亏平衡点</span>
        <span>{{ result.breakeven_months != null ? result.breakeven_months.toFixed(1) + ' 个月' : '不适用' }}</span>
      </div>
      <div class="recommendation">{{ result.recommendation }}</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useAssetsAnalysisApi, type BuyVsRentResult } from '@/api/assetsAnalysis'

const props = defineProps<{ initialPrice?: number }>()

const { calculateBuyVsRent } = useAssetsAnalysisApi()

const form = reactive({
  purchase_price: props.initialPrice ?? 0,
  monthly_rent: 0,
  usage_months: 12,
  annual_maintenance_cost: 0,
})

const result = ref<BuyVsRentResult | null>(null)
const loading = ref(false)

const calculate = async () => {
  if (!form.purchase_price || !form.monthly_rent || !form.usage_months) return
  loading.value = true
  try {
    result.value = await calculateBuyVsRent(form)
  } finally {
    loading.value = false
  }
}
</script>
```

- [ ] **Step 3: 新建 CostEquivalenceCard.vue**

```vue
<!-- frontend/src/views/assets/components/CostEquivalenceCard.vue -->
<template>
  <div class="cost-equivalence-card">
    <div class="section-title">消费等价换算</div>

    <van-loading v-if="loading" class="loading-center" />

    <div v-else-if="data">
      <van-cell-group inset>
        <van-cell title="日均成本" :value="data.daily_cost != null ? `¥${data.daily_cost.toFixed(2)}` : '--'" />
        <van-cell
          title="时间成本"
          :value="data.time_cost_hours != null ? `${data.time_cost_hours.toFixed(1)} 小时` : '--'"
          label="按时薪 ¥50/小时换算"
        />
        <van-cell
          title="机会成本 (10年)"
          :value="data.opportunity_cost != null ? `¥${data.opportunity_cost.toFixed(0)}` : '--'"
          label="按年化 5% 计算"
        />
        <van-cell title="持有天数" :value="data.held_days != null ? `${data.held_days} 天` : '--'" />
      </van-cell-group>
    </div>

    <van-empty v-else description="数据不足，无法换算" />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useAssetsAnalysisApi, type CostEquivalenceResult } from '@/api/assetsAnalysis'

const props = defineProps<{ assetId: number }>()

const { getCostEquivalence } = useAssetsAnalysisApi()

const data = ref<CostEquivalenceResult | null>(null)
const loading = ref(false)

onMounted(async () => {
  loading.value = true
  try {
    data.value = await getCostEquivalence(props.assetId)
  } finally {
    loading.value = false
  }
})
</script>
```

- [ ] **Step 4: 在资产详情页嵌入两个组件**

在资产详情页（Step 1 找到的文件）中，在适当位置（如资产信息卡片下方）添加：

```vue
<BuyVsRentCalculator :initial-price="asset.purchase_price ?? undefined" />
<CostEquivalenceCard :asset-id="asset.id" />
```

并在 `<script setup>` 中添加 imports：

```typescript
import BuyVsRentCalculator from './components/BuyVsRentCalculator.vue'
import CostEquivalenceCard from './components/CostEquivalenceCard.vue'
```

- [ ] **Step 5: 运行 typecheck**

```bash
cd frontend && npm run typecheck 2>&1 | grep -E "error|Error" | head -20
```

Expected: 无新增错误

- [ ] **Step 6: Commit**

```bash
git add frontend/src/views/assets/components/BuyVsRentCalculator.vue frontend/src/views/assets/components/CostEquivalenceCard.vue
git commit -m "feat(ui): add BuyVsRentCalculator and CostEquivalenceCard to asset detail page"
```

---

## Task 8: 全量验证

- [ ] **Step 1: 运行所有 backend 测试**

```bash
cd backend && uv run pytest tests/test_ai_spending_leaks.py tests/test_assets_analysis.py -v
```

Expected: 12 tests PASSED

- [ ] **Step 2: 运行完整 backend 测试套件（回归检查）**

```bash
cd backend && uv run pytest tests/ -q --tb=short 2>&1 | tail -20
```

Expected: 无新增失败

- [ ] **Step 3: Frontend typecheck**

```bash
cd frontend && npm run typecheck
```

Expected: 无错误

- [ ] **Step 4: Agent 语法检查**

```bash
cd agent && uv run ruff check routers/spending_leak.py services/spending_leak.py
```

Expected: All checks passed

- [ ] **Step 5: Backend lint**

```bash
cd backend && uv run ruff check app/routers/ai_spending_leaks.py app/routers/assets_analysis.py app/models/ai_spending_leak.py
```

Expected: All checks passed

- [ ] **Step 6: Final commit**

```bash
git add -A
git commit -m "feat: 智能分析 Phase 2 — 消费漏洞检测、买租计算器、消费等价换算"
```

---

## 注意事项

1. **API 调用模式**：`frontend/src/api/` 中的实际 HTTP 调用模式（axios/fetch/composable）以现有文件为准，Task 5 Step 1 先确认再写代码。

2. **资产详情页路径**：Task 7 Step 1 先 `find` 确认实际文件路径，不要假设。

3. **agent/services/fallback_engine.py 修改位置**：新增 `spending_leak` case 必须在 `else:` 分支之前，即 `elif capability == "chat":` 之前。

4. **表自动创建**：项目使用 `run_schema_migration` 自动对齐表结构（见 `backend/app/services/db_migrate.py`），不需要手动运行 alembic。新模型 import 到 `main.py` 后重启即可创建表。
