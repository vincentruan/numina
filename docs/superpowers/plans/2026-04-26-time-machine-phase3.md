# 资产时光机 Phase 3 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现资产时光机三大功能：What-if 消费模拟器、财务推演、购买力时光机

**Architecture:** 纯计算引擎 + 可选 LLM 解读。后端新增 3 个 service（whatif / projection / purchasing_power）+ 1 个 router + 1 张种子数据表。Agent 新增 time_machine capability 用于生成自然语言解读。前端新增时光机页面（三 Tab）。

**Tech Stack:** Python 3.11+ / FastAPI / SQLAlchemy / Alembic / Vue 3 / TypeScript / Vant 4 / ECharts

---

## File Structure

### Backend — New Files

| File | Responsibility |
|------|---------------|
| `backend/app/constants/cpi.py` | 中国 CPI 年度常量数据 |
| `backend/app/models/category_financial_default.py` | 分类默认财务参数 ORM 模型 |
| `backend/app/seed/category_financial_defaults.py` | 种子数据（21 个分类的默认折旧率/收益率/寿命） |
| `backend/app/schemas/whatif.py` | What-if 请求/响应 Pydantic 模型 |
| `backend/app/schemas/projection.py` | 财务推演请求/响应 Pydantic 模型 |
| `backend/app/schemas/purchasing_power.py` | 购买力请求/响应 Pydantic 模型 |
| `backend/app/services/whatif.py` | What-if 计算引擎 |
| `backend/app/services/projection.py` | 财务推演计算引擎 |
| `backend/app/services/purchasing_power.py` | 购买力计算引擎 |
| `backend/app/routers/ai_time_machine.py` | 时光机 API 路由（3 个端点） |
| `backend/tests/test_purchasing_power.py` | 购买力计算测试 |
| `backend/tests/test_whatif.py` | What-if 模拟测试 |
| `backend/tests/test_projection.py` | 财务推演测试 |

### Backend — Modified Files

| File | Change |
|------|--------|
| `backend/app/main.py` | 注册 ai_time_machine router + import model |
| `backend/app/routers/assets_analysis.py` | 新增 `GET /assets/{id}/purchasing-power` 端点 |
| `backend/app/errors/codes.py` | （无需新增 — 复用 ASSET_NOT_FOUND） |

### Agent — New Files

| File | Responsibility |
|------|---------------|
| `agent/routers/time_machine.py` | 时光机 LLM 解读路由 |

### Agent — Modified Files

| File | Change |
|------|--------|
| `agent/app/main.py` | 注册 time_machine router |
| `agent/services/fallback_engine.py` | 新增 `time_machine` capability case |

### Frontend — New Files

| File | Responsibility |
|------|---------------|
| `frontend/src/api/timeMachine.ts` | API 调用封装 |
| `frontend/src/pages/AITimeMachinePage.vue` | 时光机主页面（三 Tab） |
| `frontend/src/components/ai/WhatIfSimulator.vue` | What-if 模拟器组件 |
| `frontend/src/components/ai/ProjectionChart.vue` | 财务推演图表组件 |
| `frontend/src/components/ai/PurchasingPowerCalc.vue` | 购买力计算器组件 |

### Frontend — Modified Files

| File | Change |
|------|--------|
| `frontend/src/pages/AIHubPage.vue` | 新增时光机入口卡片 |
| `frontend/src/router/index.ts` | 新增 `/ai/time-machine` 路由 |
| `frontend/src/i18n/locales/zh-CN.ts` | 新增时光机相关文案 |
| `frontend/src/i18n/locales/en-US.ts` | 新增时光机相关文案 |

---

## Tasks

### Task 1: CPI 常量数据 + 购买力计算 Service

**Files:**
- Create: `backend/app/constants/cpi.py`
- Create: `backend/app/schemas/purchasing_power.py`
- Create: `backend/app/services/purchasing_power.py`
- Test: `backend/tests/test_purchasing_power.py`

- [ ] **Step 1: Write the failing test for purchasing power lookback**

```python
# backend/tests/test_purchasing_power.py
from app.services.purchasing_power import calculate_purchasing_power


def test_lookback_2015_to_2025():
    """2015年的10万元，到2025年应该增值（通胀侵蚀购买力）。"""
    result = calculate_purchasing_power(
        amount=100000.0, from_year=2015, to_year=2025
    )
    assert result["original_amount"] == 100000.0
    assert result["adjusted_amount"] > 100000.0  # 通胀后等价金额更高
    assert result["cumulative_inflation"] > 0
    assert result["from_year"] == 2015
    assert result["to_year"] == 2025
    assert "explanation" in result
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_purchasing_power.py::test_lookback_2015_to_2025 -v`
Expected: FAIL with "ModuleNotFoundError"

- [ ] **Step 3: Create CPI constants**

```python
# backend/app/constants/cpi.py
"""中国 CPI 年度涨幅数据（%）。来源：国家统计局。"""

CHINA_CPI_ANNUAL: dict[int, float] = {
    2005: 1.8, 2006: 1.5, 2007: 4.8, 2008: 5.9,
    2009: -0.7, 2010: 3.3, 2011: 5.4, 2012: 2.6,
    2013: 2.6, 2014: 2.0, 2015: 1.4, 2016: 2.0,
    2017: 1.6, 2018: 2.1, 2019: 2.9, 2020: 2.5,
    2021: 0.9, 2022: 2.0, 2023: 0.2, 2024: 0.2,
    2025: 0.5,
}

DEFAULT_INFLATION_RATE = 0.03  # 3% 默认通胀率（用于前看/超出 CPI 数据范围）
```

- [ ] **Step 4: Create purchasing power schemas**

```python
# backend/app/schemas/purchasing_power.py
from pydantic import BaseModel, ConfigDict, field_validator


class PurchasingPowerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    original_amount: float
    adjusted_amount: float
    from_year: int
    to_year: int
    cumulative_inflation: float
    annual_avg_inflation: float
    explanation: str
```

- [ ] **Step 5: Implement purchasing power service**

```python
# backend/app/services/purchasing_power.py
from app.constants.cpi import CHINA_CPI_ANNUAL, DEFAULT_INFLATION_RATE


def calculate_purchasing_power(
    amount: float,
    from_year: int,
    to_year: int,
    custom_inflation_rate: float | None = None,
) -> dict:
    if from_year > to_year:
        from_year, to_year = to_year, from_year

    years = to_year - from_year
    if years == 0:
        return {
            "original_amount": amount,
            "adjusted_amount": amount,
            "from_year": from_year,
            "to_year": to_year,
            "cumulative_inflation": 0.0,
            "annual_avg_inflation": 0.0,
            "explanation": f"{from_year}年的{amount:.0f}元，仍然是{amount:.0f}元",
        }

    # 逐年复合计算
    factor = 1.0
    for y in range(from_year, to_year):
        if custom_inflation_rate is not None:
            rate = custom_inflation_rate
        else:
            rate = CHINA_CPI_ANNUAL.get(y, DEFAULT_INFLATION_RATE * 100) / 100.0
        factor *= (1 + rate)

    adjusted = round(amount * factor, 2)
    cumulative = round((factor - 1) * 100, 2)
    annual_avg = round(((factor ** (1.0 / years)) - 1) * 100, 2) if years > 0 else 0.0

    explanation = f"{from_year}年的{amount:.0f}元，相当于{to_year}年的{adjusted:.0f}元"

    return {
        "original_amount": amount,
        "adjusted_amount": adjusted,
        "from_year": from_year,
        "to_year": to_year,
        "cumulative_inflation": cumulative,
        "annual_avg_inflation": annual_avg,
        "explanation": explanation,
    }
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_purchasing_power.py -v`
Expected: PASS

- [ ] **Step 7: Add more tests**

```python
# Append to backend/tests/test_purchasing_power.py

def test_lookback_same_year():
    result = calculate_purchasing_power(amount=50000.0, from_year=2020, to_year=2020)
    assert result["adjusted_amount"] == 50000.0
    assert result["cumulative_inflation"] == 0.0


def test_custom_inflation_rate():
    result = calculate_purchasing_power(
        amount=100000.0, from_year=2020, to_year=2025, custom_inflation_rate=0.05
    )
    expected = round(100000.0 * (1.05 ** 5), 2)
    assert abs(result["adjusted_amount"] - expected) < 0.01


def test_auto_swap_years():
    """from_year > to_year 时自动交换。"""
    result = calculate_purchasing_power(amount=10000.0, from_year=2025, to_year=2015)
    assert result["from_year"] == 2015
    assert result["to_year"] == 2025
    assert result["adjusted_amount"] > 10000.0
```

- [ ] **Step 8: Run all purchasing power tests**

Run: `cd backend && uv run pytest tests/test_purchasing_power.py -v`
Expected: All PASS

- [ ] **Step 9: Commit**

```bash
cd backend
git add app/constants/cpi.py app/schemas/purchasing_power.py app/services/purchasing_power.py tests/test_purchasing_power.py
git commit -m "feat(backend): add purchasing power calculation service and CPI constants"
```

---

### Task 2: CategoryFinancialDefault 模型 + 种子数据

**Files:**
- Create: `backend/app/models/category_financial_default.py`
- Create: `backend/app/seed/category_financial_defaults.py`
- Modify: `backend/app/main.py`
- Modify: `backend/tests/conftest.py`

- [ ] **Step 1: Create the ORM model**

```python
# backend/app/models/category_financial_default.py
from sqlalchemy import BigInteger, Float, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.utils.snowflake import next_id


class CategoryFinancialDefault(Base):
    __tablename__ = "category_financial_defaults"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    category_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("categories.id"), nullable=False, unique=True
    )
    default_annual_depreciation: Mapped[float] = mapped_column(Float, default=0.1)
    default_annual_return: Mapped[float] = mapped_column(Float, default=0.0)
    default_lifespan_years: Mapped[int | None] = mapped_column(Integer, nullable=True, default=10)

    category = relationship("Category")
```

- [ ] **Step 2: Create seed data function**

```python
# backend/app/seed/category_financial_defaults.py
"""种子数据：每个系统分类的默认财务参数。"""

# category_name -> (annual_depreciation, annual_return, lifespan_years)
DEFAULTS: dict[str, tuple[float, float, int | None]] = {
    "房产": (0.02, 0.03, 50),
    "车辆": (0.15, 0.0, 10),
    "数码": (0.25, 0.0, 4),
    "家电": (0.10, 0.0, 10),
    "家具": (0.08, 0.0, 15),
    "珠宝": (0.01, 0.02, 50),
    "服饰": (0.30, 0.0, 3),
    "美妆": (0.50, 0.0, 2),
    "运动": (0.15, 0.0, 8),
    "玩具": (0.20, 0.0, 5),
    "宠物": (0.20, 0.0, 5),
    "乐器": (0.05, 0.0, 20),
    "箱包": (0.15, 0.0, 8),
    "存款": (0.0, 0.02, None),
    "基金": (0.0, 0.06, None),
    "股票": (0.0, 0.08, None),
    "债券": (0.0, 0.04, None),
    "保险": (0.0, 0.03, None),
    "理财产品": (0.0, 0.035, None),
    "数字货币": (0.0, 0.10, None),
    "其他金融": (0.0, 0.03, None),
}


def seed_category_financial_defaults(db):
    from app.models.category import Category
    from app.models.category_financial_default import CategoryFinancialDefault

    existing = db.query(CategoryFinancialDefault).first()
    if existing:
        return

    categories = db.query(Category).filter(Category.is_system == True).all()
    name_to_id = {c.name: c.id for c in categories}

    for name, (depreciation, annual_return, lifespan) in DEFAULTS.items():
        cat_id = name_to_id.get(name)
        if cat_id is None:
            continue
        db.add(CategoryFinancialDefault(
            category_id=cat_id,
            default_annual_depreciation=depreciation,
            default_annual_return=annual_return,
            default_lifespan_years=lifespan,
        ))
    db.commit()
```

- [ ] **Step 3: Register model import and seed in main.py**

Add to `backend/app/main.py` model imports section:
```python
from app.models.category_financial_default import CategoryFinancialDefault  # noqa: F401
```

Add to lifespan function after `seed_invitation_codes(db)`:
```python
from app.seed.category_financial_defaults import seed_category_financial_defaults
seed_category_financial_defaults(db)
```

- [ ] **Step 4: Import model in conftest.py**

Add to `backend/tests/conftest.py` model imports:
```python
from app.models.category_financial_default import CategoryFinancialDefault  # noqa: F401
```

- [ ] **Step 5: Run existing tests to verify no regression**

Run: `cd backend && uv run pytest tests/test_assets_analysis.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
cd backend
git add app/models/category_financial_default.py app/seed/category_financial_defaults.py
git add -p app/main.py tests/conftest.py
git commit -m "feat(backend): add CategoryFinancialDefault model and seed data"
```

---

### Task 3: 购买力 API 端点

**Files:**
- Create: `backend/app/routers/ai_time_machine.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/routers/assets_analysis.py`
- Test: `backend/tests/test_purchasing_power.py`

- [ ] **Step 1: Write failing API test**

```python
# Append to backend/tests/test_purchasing_power.py

def test_purchasing_power_api(client, auth_headers):
    resp = client.get(
        "/api/v1/ai/purchasing-power",
        params={"amount": 100000, "from_year": 2015, "to_year": 2025},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["original_amount"] == 100000.0
    assert data["adjusted_amount"] > 100000.0
    assert "explanation" in data
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_purchasing_power.py::test_purchasing_power_api -v`
Expected: FAIL with 404

- [ ] **Step 3: Create time machine router with purchasing-power endpoint**

```python
# backend/app/routers/ai_time_machine.py
"""资产时光机 API 端点 — What-if 模拟、财务推演、购买力计算。"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth.deps import require_adult
from app.database import get_db
from app.models.user import User
from app.schemas.purchasing_power import PurchasingPowerResponse
from app.services.purchasing_power import calculate_purchasing_power

router = APIRouter(prefix="/ai", tags=["ai-time-machine"])


@router.get("/purchasing-power", response_model=PurchasingPowerResponse)
def get_purchasing_power(
    amount: float = Query(..., gt=0),
    from_year: int = Query(..., ge=1990, le=2050),
    to_year: int = Query(..., ge=1990, le=2050),
    custom_inflation_rate: float | None = Query(None, ge=0, le=1),
    user: User = Depends(require_adult),
):
    return calculate_purchasing_power(
        amount=amount,
        from_year=from_year,
        to_year=to_year,
        custom_inflation_rate=custom_inflation_rate,
    )
```

- [ ] **Step 4: Register router in main.py**

Add import:
```python
from app.routers import ai_time_machine as ai_time_machine_router
```

Add include_router (after ai_chat_router):
```python
app.include_router(ai_time_machine_router.router, prefix="/api/v1")
```

- [ ] **Step 5: Add asset-level purchasing power endpoint**

Append to `backend/app/routers/assets_analysis.py`:
```python
from app.services.purchasing_power import calculate_purchasing_power as calc_pp


@router.get("/assets/{asset_id}/purchasing-power")
def get_asset_purchasing_power(
    asset_id: int,
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
            "original_amount": None, "adjusted_amount": None,
            "from_year": None, "to_year": None,
            "cumulative_inflation": None, "annual_avg_inflation": None,
            "explanation": None,
        }

    from datetime import date
    return calc_pp(
        amount=asset.purchase_price,
        from_year=asset.purchase_date.year,
        to_year=date.today().year,
    )
```

- [ ] **Step 6: Write asset-level API test**

```python
# Append to backend/tests/test_purchasing_power.py

def test_asset_purchasing_power(client, auth_headers, db):
    from datetime import date, timedelta
    from app.models.asset import Asset
    from app.models.category import Category

    me = client.get("/api/v1/auth/me", headers=auth_headers).json()
    family_id = me["data"]["family_id"]
    user_id = me["data"]["id"]

    cat = db.query(Category).filter_by(asset_type="physical").first()
    asset = Asset(
        user_id=user_id, family_id=family_id, category_id=cat.id,
        name="测试手机", asset_type="physical",
        purchase_price=5000.0, current_value=3000.0,
        purchase_date=date(2020, 1, 1),
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)

    resp = client.get(
        f"/api/v1/assets/{asset.id}/purchasing-power",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["original_amount"] == 5000.0
    assert data["from_year"] == 2020


def test_asset_purchasing_power_no_date(client, auth_headers, db):
    from app.models.asset import Asset
    from app.models.category import Category

    me = client.get("/api/v1/auth/me", headers=auth_headers).json()
    family_id = me["data"]["family_id"]
    user_id = me["data"]["id"]

    cat = db.query(Category).filter_by(asset_type="physical").first()
    asset = Asset(
        user_id=user_id, family_id=family_id, category_id=cat.id,
        name="无日期资产", asset_type="physical",
        purchase_price=None, current_value=1000.0,
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)

    resp = client.get(
        f"/api/v1/assets/{asset.id}/purchasing-power",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["original_amount"] is None
```

- [ ] **Step 7: Run all purchasing power tests**

Run: `cd backend && uv run pytest tests/test_purchasing_power.py -v`
Expected: All PASS

- [ ] **Step 8: Commit**

```bash
cd backend
git add app/routers/ai_time_machine.py
git add -p app/main.py app/routers/assets_analysis.py tests/test_purchasing_power.py
git commit -m "feat(api): add purchasing-power endpoints for time machine"
```

---

### Task 4: What-if 计算引擎

**Files:**
- Create: `backend/app/schemas/whatif.py`
- Create: `backend/app/services/whatif.py`
- Test: `backend/tests/test_whatif.py`

- [ ] **Step 1: Write failing test for basic sell scenario**

```python
# backend/tests/test_whatif.py
from app.services.whatif import calculate_whatif


def test_sell_asset_improves_net_worth():
    """卖掉高维护成本资产，长期净资产应该更高。"""
    result = calculate_whatif(
        current_net_worth=500000.0,
        assets=[{
            "id": 1, "current_value": 50000.0, "asset_type": "physical",
            "annual_depreciation": 0.15, "annual_maintenance_cost": 5000.0,
            "annual_return": 0.0,
        }],
        liabilities=[],
        actions=[{
            "action_type": "sell", "asset_id": 1, "liquidation_rate": 0.8,
        }],
        projection_years=10,
        inflation_rate=0.03,
    )
    assert len(result["projection"]) == 11  # year 0 through 10
    assert result["total_difference"] > 0  # selling is better long-term
    assert result["projection"][0]["difference"] == 0  # year 0 is same
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_whatif.py::test_sell_asset_improves_net_worth -v`
Expected: FAIL with "ModuleNotFoundError"

- [ ] **Step 3: Create whatif schemas**

```python
# backend/app/schemas/whatif.py
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator


class WhatIfAction(BaseModel):
    action_type: Literal["sell", "buy", "invest", "stop_expense"]
    asset_id: int | None = None
    amount: float | None = None
    annual_return_rate: float = 0.0
    annual_cost: float = 0.0
    liquidation_rate: float = 0.8

    @field_validator("liquidation_rate")
    @classmethod
    def validate_liquidation_rate(cls, v: float) -> float:
        if not (0.0 <= v <= 1.0):
            raise ValueError("liquidation_rate 必须在 0-1 之间")
        return v


class WhatIfRequest(BaseModel):
    actions: list[WhatIfAction]
    projection_years: int = 10
    inflation_rate: float = 0.03

    @field_validator("actions")
    @classmethod
    def validate_actions(cls, v: list) -> list:
        if len(v) < 1 or len(v) > 5:
            raise ValueError("actions 数量必须在 1-5 之间")
        return v

    @field_validator("projection_years")
    @classmethod
    def validate_years(cls, v: int) -> int:
        if not (1 <= v <= 30):
            raise ValueError("projection_years 必须在 1-30 之间")
        return v


class WhatIfYearPoint(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    year: int
    baseline_net_worth: float
    scenario_net_worth: float
    difference: float


class WhatIfResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    projection: list[WhatIfYearPoint]
    total_difference: float
    breakeven_year: int | None
    summary: str | None = None
```

- [ ] **Step 4: Implement whatif service**

```python
# backend/app/services/whatif.py
"""What-if 消费模拟计算引擎。"""


def calculate_whatif(
    current_net_worth: float,
    assets: list[dict],
    liabilities: list[dict],
    actions: list[dict],
    projection_years: int = 10,
    inflation_rate: float = 0.03,
) -> dict:
    asset_map = {a["id"]: a for a in assets}
    annual_liability_cost = sum(
        (li.get("monthly_payment") or 0) * 12 for li in liabilities
    )

    # Build baseline annual delta from all assets
    baseline_annual_gain = 0.0
    baseline_annual_loss = 0.0
    for a in assets:
        if a["asset_type"] == "financial":
            baseline_annual_gain += a["current_value"] * a.get("annual_return", 0)
        else:
            baseline_annual_loss += a["current_value"] * a.get("annual_depreciation", 0.1)
            baseline_annual_loss += a.get("annual_maintenance_cost", 0) or 0

    # Build scenario adjustments from actions
    scenario_year0_delta = 0.0  # one-time changes at year 0
    scenario_annual_gain_delta = 0.0
    scenario_annual_loss_delta = 0.0

    for act in actions:
        atype = act["action_type"]
        if atype == "sell":
            asset = asset_map.get(act.get("asset_id"))
            if asset:
                sell_income = asset["current_value"] * act.get("liquidation_rate", 0.8)
                scenario_year0_delta += sell_income
                # Remove this asset's ongoing costs from scenario
                if asset["asset_type"] == "physical":
                    scenario_annual_loss_delta -= asset["current_value"] * asset.get("annual_depreciation", 0.1)
                    scenario_annual_loss_delta -= asset.get("annual_maintenance_cost", 0) or 0
                else:
                    scenario_annual_gain_delta -= asset["current_value"] * asset.get("annual_return", 0)
        elif atype == "invest":
            amt = act.get("amount", 0) or 0
            scenario_year0_delta -= amt
            scenario_annual_gain_delta += amt * act.get("annual_return_rate", 0)
        elif atype == "buy":
            amt = act.get("amount", 0) or 0
            scenario_year0_delta -= amt
            scenario_annual_loss_delta += act.get("annual_cost", 0)
        elif atype == "stop_expense":
            asset = asset_map.get(act.get("asset_id"))
            saved = act.get("amount") or (asset.get("annual_maintenance_cost", 0) if asset else 0)
            scenario_annual_loss_delta -= saved or 0

    # Project year by year
    projection = []
    baseline = current_net_worth
    scenario = current_net_worth + scenario_year0_delta
    breakeven_year = None

    for y in range(projection_years + 1):
        diff = round(scenario - baseline, 2)
        projection.append({
            "year": y,
            "baseline_net_worth": round(baseline, 2),
            "scenario_net_worth": round(scenario, 2),
            "difference": diff,
        })
        if y > 0 and breakeven_year is None and diff > 0:
            breakeven_year = y

        if y < projection_years:
            baseline_delta = baseline_annual_gain - baseline_annual_loss - annual_liability_cost
            baseline += baseline_delta

            scenario_delta = (
                baseline_annual_gain + scenario_annual_gain_delta
                - baseline_annual_loss - scenario_annual_loss_delta
                - annual_liability_cost
            )
            scenario += scenario_delta

    return {
        "projection": projection,
        "total_difference": projection[-1]["difference"],
        "breakeven_year": breakeven_year,
        "summary": None,
    }
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_whatif.py -v`
Expected: PASS

- [ ] **Step 6: Add invest and stop_expense tests**

```python
# Append to backend/tests/test_whatif.py

def test_invest_scenario():
    """投资场景：初始减少现金，长期通过收益增长。"""
    result = calculate_whatif(
        current_net_worth=200000.0,
        assets=[],
        liabilities=[],
        actions=[{"action_type": "invest", "amount": 50000.0, "annual_return_rate": 0.08}],
        projection_years=5,
        inflation_rate=0.03,
    )
    # Year 0: scenario is 50k less
    assert result["projection"][0]["difference"] == 0
    assert result["projection"][1]["scenario_net_worth"] < result["projection"][1]["baseline_net_worth"]
    # Eventually should break even
    assert result["breakeven_year"] is not None or result["total_difference"] < 0


def test_empty_actions_validation():
    """actions 为空应该在 schema 层面被拒绝。"""
    from pydantic import ValidationError
    from app.schemas.whatif import WhatIfRequest
    import pytest

    with pytest.raises(ValidationError):
        WhatIfRequest(actions=[], projection_years=10)


def test_stop_expense():
    result = calculate_whatif(
        current_net_worth=100000.0,
        assets=[{
            "id": 1, "current_value": 10000.0, "asset_type": "physical",
            "annual_depreciation": 0.1, "annual_maintenance_cost": 2000.0,
            "annual_return": 0.0,
        }],
        liabilities=[],
        actions=[{"action_type": "stop_expense", "asset_id": 1}],
        projection_years=5,
        inflation_rate=0.03,
    )
    assert result["total_difference"] > 0  # saving maintenance cost
```

- [ ] **Step 7: Run all whatif tests**

Run: `cd backend && uv run pytest tests/test_whatif.py -v`
Expected: All PASS

- [ ] **Step 8: Commit**

```bash
cd backend
git add app/schemas/whatif.py app/services/whatif.py tests/test_whatif.py
git commit -m "feat(backend): add What-if simulation calculation engine"
```

---

### Task 5: What-if API 端点

**Files:**
- Modify: `backend/app/routers/ai_time_machine.py`
- Test: `backend/tests/test_whatif.py`

- [ ] **Step 1: Write failing API test**

```python
# Append to backend/tests/test_whatif.py

def test_whatif_api(client, auth_headers, db):
    from datetime import date
    from app.models.asset import Asset
    from app.models.category import Category

    me = client.get("/api/v1/auth/me", headers=auth_headers).json()
    family_id = me["data"]["family_id"]
    user_id = me["data"]["id"]

    cat = db.query(Category).filter_by(name="车辆").first()
    asset = Asset(
        user_id=user_id, family_id=family_id, category_id=cat.id,
        name="测试车", asset_type="physical",
        purchase_price=200000.0, current_value=150000.0,
        purchase_date=date(2022, 1, 1),
        annual_maintenance_cost=10000.0,
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)

    resp = client.post(
        "/api/v1/ai/whatif",
        json={
            "actions": [{"action_type": "sell", "asset_id": asset.id, "liquidation_rate": 0.7}],
            "projection_years": 5,
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data["projection"]) == 6
    assert "total_difference" in data


def test_whatif_api_validation(client, auth_headers):
    resp = client.post(
        "/api/v1/ai/whatif",
        json={"actions": [], "projection_years": 5},
        headers=auth_headers,
    )
    assert resp.status_code == 422
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_whatif.py::test_whatif_api -v`
Expected: FAIL with 404 or 405

- [ ] **Step 3: Add whatif endpoint to router**

Append to `backend/app/routers/ai_time_machine.py`:
```python
from app.errors import AppError, ErrorCode
from app.models.asset import Asset
from app.models.category_financial_default import CategoryFinancialDefault
from app.models.liability import Liability
from app.schemas.whatif import WhatIfRequest, WhatIfResponse
from app.services.whatif import calculate_whatif


@router.post("/ai/whatif", response_model=WhatIfResponse)
def run_whatif(
    body: WhatIfRequest,
    user: User = Depends(require_adult),
    db: Session = Depends(get_db),
):
    family_id = user.family_id

    # Load assets
    db_assets = (
        db.query(Asset)
        .filter(Asset.family_id == family_id, Asset.is_archived == False)
        .all()
    )
    # Load category defaults
    defaults = {
        d.category_id: d
        for d in db.query(CategoryFinancialDefault).all()
    }

    assets = []
    for a in db_assets:
        d = defaults.get(a.category_id)
        dep = d.default_annual_depreciation if d else 0.1
        ret = d.default_annual_return if d else 0.0
        assets.append({
            "id": a.id,
            "current_value": a.current_value or 0,
            "asset_type": a.asset_type,
            "annual_depreciation": dep,
            "annual_maintenance_cost": a.annual_maintenance_cost or 0,
            "annual_return": a.interest_rate or ret,
        })

    # Validate asset_ids in actions
    asset_ids = {a["id"] for a in assets}
    for act in body.actions:
        if act.asset_id is not None and act.asset_id not in asset_ids:
            raise AppError(ErrorCode.ASSET_NOT_FOUND)

    # Load liabilities
    db_liabilities = (
        db.query(Liability)
        .filter(Liability.family_id == family_id, Liability.is_active == True)
        .all()
    )
    liabilities = [
        {"monthly_payment": li.monthly_payment or 0}
        for li in db_liabilities
    ]

    # Calculate current net worth
    from app.services import dashboard as dashboard_service
    overview = dashboard_service.get_overview(db, user)
    current_net_worth = overview.net_worth

    result = calculate_whatif(
        current_net_worth=current_net_worth,
        assets=assets,
        liabilities=liabilities,
        actions=[a.model_dump() for a in body.actions],
        projection_years=body.projection_years,
        inflation_rate=body.inflation_rate,
    )
    return result
```

- [ ] **Step 4: Run all whatif tests**

Run: `cd backend && uv run pytest tests/test_whatif.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
cd backend
git add -p app/routers/ai_time_machine.py tests/test_whatif.py
git commit -m "feat(api): add POST /ai/whatif endpoint"
```

---

### Task 6: 财务推演计算引擎

**Files:**
- Create: `backend/app/schemas/projection.py`
- Create: `backend/app/services/projection.py`
- Test: `backend/tests/test_projection.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_projection.py
from app.services.projection import calculate_projection


def test_basic_projection():
    """基本推演：有资产和负债的家庭。"""
    result = calculate_projection(
        assets=[
            {"current_value": 100000.0, "asset_type": "physical",
             "annual_depreciation": 0.1, "annual_return": 0.0},
            {"current_value": 200000.0, "asset_type": "financial",
             "annual_depreciation": 0.0, "annual_return": 0.06},
        ],
        liabilities=[
            {"remaining_amount": 50000.0, "monthly_payment": 2000.0, "end_year": 2028},
        ],
        history_points=[],
        projection_years=5,
        inflation_rate=0.03,
        current_year=2026,
    )
    assert len(result["forecast"]) == 6  # year 0 through 5
    # Physical depreciates, financial grows
    assert result["forecast"][5]["total_assets"] > 0
    # Real net worth should be less than nominal
    assert result["forecast"][5]["real_net_worth"] < result["forecast"][5]["net_worth"]
    assert "assumptions" in result


def test_projection_empty_assets():
    result = calculate_projection(
        assets=[], liabilities=[], history_points=[],
        projection_years=3, inflation_rate=0.03, current_year=2026,
    )
    assert len(result["forecast"]) == 4
    for pt in result["forecast"]:
        assert pt["net_worth"] == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_projection.py::test_basic_projection -v`
Expected: FAIL with "ModuleNotFoundError"

- [ ] **Step 3: Create projection schemas**

```python
# backend/app/schemas/projection.py
from pydantic import BaseModel, ConfigDict, field_validator


class ProjectionRequest(BaseModel):
    projection_years: int = 5
    inflation_rate: float = 0.03
    custom_overrides: dict[int, float] | None = None

    @field_validator("projection_years")
    @classmethod
    def validate_years(cls, v: int) -> int:
        if not (1 <= v <= 30):
            raise ValueError("projection_years 必须在 1-30 之间")
        return v


class ProjectionYearPoint(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    year: int
    total_assets: float
    total_liabilities: float
    net_worth: float
    real_net_worth: float


class ProjectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    history: list[ProjectionYearPoint]
    forecast: list[ProjectionYearPoint]
    assumptions: dict
    summary: str | None = None
```

- [ ] **Step 4: Implement projection service**

```python
# backend/app/services/projection.py
"""财务推演计算引擎。"""

from datetime import date


def calculate_projection(
    assets: list[dict],
    liabilities: list[dict],
    history_points: list[dict],
    projection_years: int = 5,
    inflation_rate: float = 0.03,
    current_year: int | None = None,
    custom_overrides: dict[int, float] | None = None,
) -> dict:
    if current_year is None:
        current_year = date.today().year

    # Build per-asset projection parameters
    asset_projections = []
    for a in assets:
        asset_id = a.get("id")
        if custom_overrides and asset_id in custom_overrides:
            custom_rate = custom_overrides[asset_id]
            if a["asset_type"] == "financial":
                dep, ret = 0.0, custom_rate
            else:
                dep, ret = custom_rate, 0.0
        else:
            dep = a.get("annual_depreciation", 0.0)
            ret = a.get("annual_return", 0.0)
        asset_projections.append({
            "current_value": a.get("current_value", 0) or 0,
            "asset_type": a["asset_type"],
            "depreciation": dep,
            "annual_return": ret,
        })

    # Build liability projections
    liability_projections = []
    for li in liabilities:
        liability_projections.append({
            "remaining": li.get("remaining_amount", 0) or 0,
            "monthly_payment": li.get("monthly_payment", 0) or 0,
            "end_year": li.get("end_year"),
        })

    # Project year by year
    forecast = []
    for y in range(projection_years + 1):
        year = current_year + y
        total_assets = 0.0
        for ap in asset_projections:
            if ap["asset_type"] == "financial":
                val = ap["current_value"] * ((1 + ap["annual_return"]) ** y)
            else:
                val = ap["current_value"] * ((1 - ap["depreciation"]) ** y)
            total_assets += max(val, 0)

        total_liabilities = 0.0
        for lp in liability_projections:
            remaining = lp["remaining"] - lp["monthly_payment"] * 12 * y
            if lp["end_year"] and year > lp["end_year"]:
                remaining = 0
            total_liabilities += max(remaining, 0)

        net_worth = total_assets - total_liabilities
        real_net_worth = net_worth / ((1 + inflation_rate) ** y) if y > 0 else net_worth

        forecast.append({
            "year": year,
            "total_assets": round(total_assets, 2),
            "total_liabilities": round(total_liabilities, 2),
            "net_worth": round(net_worth, 2),
            "real_net_worth": round(real_net_worth, 2),
        })

    # Build assumptions dict
    assumptions = {
        "inflation_rate": inflation_rate,
        "projection_years": projection_years,
        "asset_count": len(assets),
        "liability_count": len(liabilities),
    }

    return {
        "history": history_points,
        "forecast": forecast,
        "assumptions": assumptions,
        "summary": None,
    }
```

- [ ] **Step 5: Run tests**

Run: `cd backend && uv run pytest tests/test_projection.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
cd backend
git add app/schemas/projection.py app/services/projection.py tests/test_projection.py
git commit -m "feat(backend): add financial projection calculation engine"
```

---

### Task 7: 财务推演 API 端点

**Files:**
- Modify: `backend/app/routers/ai_time_machine.py`
- Test: `backend/tests/test_projection.py`

- [ ] **Step 1: Write failing API test**

```python
# Append to backend/tests/test_projection.py

def test_projection_api(client, auth_headers, db):
    from datetime import date
    from app.models.asset import Asset
    from app.models.category import Category

    me = client.get("/api/v1/auth/me", headers=auth_headers).json()
    family_id = me["data"]["family_id"]
    user_id = me["data"]["id"]

    cat = db.query(Category).filter_by(name="存款").first()
    asset = Asset(
        user_id=user_id, family_id=family_id, category_id=cat.id,
        name="银行存款", asset_type="financial",
        purchase_price=100000.0, current_value=100000.0,
        purchase_date=date(2024, 1, 1),
    )
    db.add(asset)
    db.commit()

    resp = client.post(
        "/api/v1/ai/projection",
        json={"projection_years": 3, "inflation_rate": 0.03},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data["forecast"]) == 4
    assert data["forecast"][0]["total_assets"] > 0
    assert "assumptions" in data
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_projection.py::test_projection_api -v`
Expected: FAIL with 404

- [ ] **Step 3: Add projection endpoint to router**

Append to `backend/app/routers/ai_time_machine.py`:
```python
from app.models.snapshot import AssetSnapshot
from app.schemas.projection import ProjectionRequest, ProjectionResponse
from app.services.projection import calculate_projection


@router.post("/ai/projection", response_model=ProjectionResponse)
def run_projection(
    body: ProjectionRequest,
    user: User = Depends(require_adult),
    db: Session = Depends(get_db),
):
    family_id = user.family_id

    # Load assets with category defaults
    db_assets = (
        db.query(Asset)
        .filter(Asset.family_id == family_id, Asset.is_archived == False)
        .all()
    )
    defaults = {
        d.category_id: d
        for d in db.query(CategoryFinancialDefault).all()
    }

    assets = []
    for a in db_assets:
        d = defaults.get(a.category_id)
        dep = d.default_annual_depreciation if d else 0.1
        ret = d.default_annual_return if d else 0.0
        lifespan = d.default_lifespan_years if d else None
        # Use asset's own lifespan if available
        if a.expected_lifespan_days and a.expected_lifespan_days > 0:
            dep = 1.0 / (a.expected_lifespan_days / 365.0)
        assets.append({
            "id": a.id,
            "current_value": a.current_value or 0,
            "asset_type": a.asset_type,
            "annual_depreciation": dep,
            "annual_return": a.interest_rate or ret,
        })

    # Load liabilities
    from datetime import date as date_type
    db_liabilities = (
        db.query(Liability)
        .filter(Liability.family_id == family_id, Liability.is_active == True)
        .all()
    )
    liabilities = [
        {
            "remaining_amount": li.remaining_amount or 0,
            "monthly_payment": li.monthly_payment or 0,
            "end_year": li.end_date.year if li.end_date else None,
        }
        for li in db_liabilities
    ]

    # Load history from snapshots
    snapshots = (
        db.query(AssetSnapshot)
        .filter(
            AssetSnapshot.family_id == family_id,
            AssetSnapshot.user_id == None,
        )
        .order_by(AssetSnapshot.snapshot_date.asc())
        .all()
    )
    history = []
    seen_years = set()
    for s in snapshots:
        y = s.snapshot_date.year
        if y not in seen_years:
            seen_years.add(y)
            history.append({
                "year": y,
                "total_assets": s.total_assets or 0,
                "total_liabilities": s.total_liabilities or 0,
                "net_worth": s.net_worth or 0,
                "real_net_worth": s.net_worth or 0,
            })

    result = calculate_projection(
        assets=assets,
        liabilities=liabilities,
        history_points=history,
        projection_years=body.projection_years,
        inflation_rate=body.inflation_rate,
        custom_overrides=body.custom_overrides,
    )
    return result
```

- [ ] **Step 4: Run all projection tests**

Run: `cd backend && uv run pytest tests/test_projection.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
cd backend
git add -p app/routers/ai_time_machine.py tests/test_projection.py
git commit -m "feat(api): add POST /ai/projection endpoint"
```

---

### Task 8: Agent time_machine capability

**Files:**
- Create: `agent/routers/time_machine.py`
- Modify: `agent/app/main.py`
- Modify: `agent/services/fallback_engine.py`

- [ ] **Step 1: Create agent router**

```python
# agent/routers/time_machine.py
"""时光机 LLM 解读 agent 路由。"""

import logging

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from app.config import settings
from services.orchestrator import orchestrator

router = APIRouter(prefix="/time-machine", tags=["time-machine"])
logger = logging.getLogger(__name__)


class InterpretRequest(BaseModel):
    type: str  # "whatif" | "projection"
    data: dict
    family_context: dict | None = None


@router.post("/interpret")
async def interpret_time_machine(
    body: InterpretRequest,
    x_family_id: str = Header(..., alias="X-Family-Id"),
    x_agent_token: str = Header(..., alias="X-Agent-Token"),
):
    if x_agent_token != settings.AGENT_INTERNAL_TOKEN:
        raise HTTPException(status_code=401, detail="invalid token")

    import json
    free_text = json.dumps({
        "type": body.type,
        "data": body.data,
        "family_context": body.family_context,
    }, ensure_ascii=False)

    response = await orchestrator.dispatch(
        capability="time_machine",
        family_id=x_family_id,
        free_text=free_text,
    )
    return {"summary": response.summary}
```

- [ ] **Step 2: Register router in agent/app/main.py**

Add after `from routers import spending_leak as spending_leak_router`:
```python
from routers import time_machine as time_machine_router
```

Add after `app.include_router(spending_leak_router.router)`:
```python
app.include_router(time_machine_router.router)
```

- [ ] **Step 3: Add time_machine case to fallback_engine.py**

Add before the `else` clause in `_run_legacy`:
```python
        elif capability == "time_machine":
            import json
            payload = json.loads(ctx.free_text) if ctx.free_text else {}
            analysis_type = payload.get("type", "unknown")
            data = payload.get("data", {})
            family_context = payload.get("family_context", {})

            if analysis_type == "whatif":
                prompt = (
                    "你是家庭财务顾问。以下是用户的 What-if 消费模拟计算结果：\n"
                    f"{json.dumps(data, ensure_ascii=False)}\n\n"
                    f"家庭财务概况：{json.dumps(family_context, ensure_ascii=False)}\n\n"
                    "请用 2-3 句话总结关键发现，给出一个明确的建议。语气：温和、实用、不说教。"
                )
            elif analysis_type == "projection":
                prompt = (
                    "你是家庭财务顾问。以下是用户的财务推演计算结果：\n"
                    f"{json.dumps(data, ensure_ascii=False)}\n\n"
                    f"家庭财务概况：{json.dumps(family_context, ensure_ascii=False)}\n\n"
                    "请用 2-3 句话总结关键发现，给出一个明确的建议。语气：温和、实用、不说教。"
                )
            else:
                return {"summary": "未知的分析类型"}

            response = await llm.chat(prompt)
            return {"summary": response}
```

- [ ] **Step 4: Run agent tests to verify no regression**

Run: `cd agent && uv run pytest tests/ -v -k "not integration"`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
cd agent
git add routers/time_machine.py
git add -p app/main.py services/fallback_engine.py
git commit -m "feat(agent): add time_machine capability for LLM interpretation"
```

---

### Task 9: Frontend API 层 + 路由 + i18n

**Files:**
- Create: `frontend/src/api/timeMachine.ts`
- Modify: `frontend/src/router/index.ts`
- Modify: `frontend/src/i18n/locales/zh-CN.ts`
- Modify: `frontend/src/i18n/locales/en-US.ts`

- [ ] **Step 1: Create API module**

```typescript
// frontend/src/api/timeMachine.ts
import request from '@/utils/request'

export interface WhatIfAction {
  action_type: 'sell' | 'buy' | 'invest' | 'stop_expense'
  asset_id?: number
  amount?: number
  annual_return_rate?: number
  annual_cost?: number
  liquidation_rate?: number
}

export interface WhatIfRequest {
  actions: WhatIfAction[]
  projection_years?: number
  inflation_rate?: number
}

export interface WhatIfYearPoint {
  year: number
  baseline_net_worth: number
  scenario_net_worth: number
  difference: number
}

export interface WhatIfResponse {
  projection: WhatIfYearPoint[]
  total_difference: number
  breakeven_year: number | null
  summary: string | null
}

export interface ProjectionRequest {
  projection_years?: number
  inflation_rate?: number
  custom_overrides?: Record<number, number>
}

export interface ProjectionYearPoint {
  year: number
  total_assets: number
  total_liabilities: number
  net_worth: number
  real_net_worth: number
}

export interface ProjectionResponse {
  history: ProjectionYearPoint[]
  forecast: ProjectionYearPoint[]
  assumptions: Record<string, unknown>
  summary: string | null
}

export interface PurchasingPowerResponse {
  original_amount: number
  adjusted_amount: number
  from_year: number
  to_year: number
  cumulative_inflation: number
  annual_avg_inflation: number
  explanation: string
}

export function postWhatIf(data: WhatIfRequest) {
  return request.post<WhatIfResponse>('/ai/whatif', data)
}

export function postProjection(data: ProjectionRequest) {
  return request.post<ProjectionResponse>('/ai/projection', data)
}

export function getPurchasingPower(params: {
  amount: number
  from_year: number
  to_year: number
  custom_inflation_rate?: number
}) {
  return request.get<PurchasingPowerResponse>('/ai/purchasing-power', { params })
}

export function getAssetPurchasingPower(assetId: number) {
  return request.get<PurchasingPowerResponse>(`/assets/${assetId}/purchasing-power`)
}
```

- [ ] **Step 2: Add route**

Add to `frontend/src/router/index.ts` inside the MainLayout children, after the AI chat route:
```typescript
{
  path: 'ai/time-machine',
  name: 'AITimeMachine',
  component: () => import('@/pages/AITimeMachinePage.vue')
},
```

- [ ] **Step 3: Add i18n keys to zh-CN.ts**

Add under `toast` section:
```typescript
timeMachineLoading: '⏳ 正在计算…',
timeMachineError: '❌ 计算失败，请重试',
timeMachineSuccess: '✅ 计算完成',
```

Add a new `timeMachine` section:
```typescript
timeMachine: {
  title: '资产时光机',
  whatif: 'What-if 模拟',
  projection: '财务推演',
  purchasingPower: '购买力计算',
  addAction: '添加操作',
  sell: '卖出资产',
  buy: '购买资产',
  invest: '新增投资',
  stopExpense: '停止支出',
  projectionYears: '推演年数',
  inflationRate: '通胀率',
  calculate: '开始计算',
  baseline: '维持现状',
  scenario: '执行变更',
  breakeven: '盈亏平衡',
  totalDifference: '总差异',
  nominal: '名义值',
  realValue: '真实购买力',
  amount: '金额',
  fromYear: '起始年份',
  toYear: '目标年份',
  result: '换算结果',
  equivalent: '相当于',
  cumulativeInflation: '累计通胀',
  annualAvg: '年均通胀',
  myAssets: '我的资产购买力',
},
```

- [ ] **Step 4: Add i18n keys to en-US.ts**

Mirror the zh-CN keys with English translations.

- [ ] **Step 5: Run typecheck**

Run: `cd frontend && npm run typecheck`
Expected: No errors

- [ ] **Step 6: Commit**

```bash
cd frontend
git add src/api/timeMachine.ts
git add -p src/router/index.ts src/i18n/locales/zh-CN.ts src/i18n/locales/en-US.ts
git commit -m "feat(frontend): add time machine API, route, and i18n keys"
```

---

### Task 10: 购买力计算器组件

**Files:**
- Create: `frontend/src/components/ai/PurchasingPowerCalc.vue`

- [ ] **Step 1: Create the component**

```vue
<!-- frontend/src/components/ai/PurchasingPowerCalc.vue -->
<template>
  <div class="purchasing-power-calc">
    <van-form @submit="calculate">
      <van-cell-group inset>
        <van-field
          v-model.number="form.amount"
          type="number"
          :label="t('timeMachine.amount')"
          placeholder="100000"
          :rules="[{ required: true }]"
        />
        <van-field
          v-model.number="form.fromYear"
          type="number"
          :label="t('timeMachine.fromYear')"
          placeholder="2015"
          :rules="[{ required: true }]"
        />
        <van-field
          v-model.number="form.toYear"
          type="number"
          :label="t('timeMachine.toYear')"
          placeholder="2026"
          :rules="[{ required: true }]"
        />
      </van-cell-group>
      <div class="calc-btn-wrap">
        <van-button round block type="primary" native-type="submit" :loading="loading">
          {{ t('timeMachine.calculate') }}
        </van-button>
      </div>
    </van-form>

    <div v-if="result" class="result-card">
      <div class="result-main">
        <span class="result-original">{{ formatMoney(result.original_amount) }}</span>
        <span class="result-arrow">→</span>
        <span class="result-adjusted">{{ formatMoney(result.adjusted_amount) }}</span>
      </div>
      <p class="result-explanation">{{ result.explanation }}</p>
      <div class="result-meta">
        <span>{{ t('timeMachine.cumulativeInflation') }}: {{ result.cumulative_inflation }}%</span>
        <span>{{ t('timeMachine.annualAvg') }}: {{ result.annual_avg_inflation }}%</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { showToast } from 'vant'
import { getPurchasingPower, type PurchasingPowerResponse } from '@/api/timeMachine'

const { t } = useI18n()

const form = ref({ amount: 100000, fromYear: 2015, toYear: new Date().getFullYear() })
const loading = ref(false)
const result = ref<PurchasingPowerResponse | null>(null)

function formatMoney(v: number) {
  return `¥${v.toLocaleString('zh-CN', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`
}

async function calculate() {
  loading.value = true
  try {
    const res = await getPurchasingPower({
      amount: form.value.amount,
      from_year: form.value.fromYear,
      to_year: form.value.toYear,
    })
    result.value = res.data
  } catch {
    showToast(t('toast.timeMachineError'))
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.calc-btn-wrap { padding: 16px; }
.result-card {
  margin: 16px;
  padding: 20px;
  background: var(--van-background-2);
  border-radius: 12px;
}
.result-main {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  font-size: 20px;
  font-weight: 600;
}
.result-arrow { color: var(--van-primary-color); }
.result-adjusted { color: var(--van-primary-color); }
.result-explanation {
  text-align: center;
  color: var(--van-text-color-2);
  margin: 12px 0;
  font-size: 14px;
}
.result-meta {
  display: flex;
  justify-content: space-around;
  font-size: 12px;
  color: var(--van-text-color-3);
}
</style>
```

- [ ] **Step 2: Run typecheck**

Run: `cd frontend && npm run typecheck`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
cd frontend
git add src/components/ai/PurchasingPowerCalc.vue
git commit -m "feat(ui): add PurchasingPowerCalc component"
```

---

### Task 11: What-if 模拟器组件

**Files:**
- Create: `frontend/src/components/ai/WhatIfSimulator.vue`

- [ ] **Step 1: Create the component**

```vue
<!-- frontend/src/components/ai/WhatIfSimulator.vue -->
<template>
  <div class="whatif-simulator">
    <!-- Action list -->
    <div class="action-list">
      <div v-for="(action, idx) in actions" :key="idx" class="action-item">
        <van-cell-group inset>
          <van-field
            :model-value="actionTypeLabel(action.action_type)"
            is-link
            readonly
            label="操作类型"
            @click="showActionPicker(idx)"
          />
          <van-field
            v-if="action.action_type === 'sell' || action.action_type === 'stop_expense'"
            :model-value="assetName(action.asset_id)"
            is-link
            readonly
            label="选择资产"
            @click="showAssetPicker(idx)"
          />
          <van-field
            v-if="action.action_type === 'invest' || action.action_type === 'buy'"
            v-model.number="action.amount"
            type="number"
            label="金额"
          />
          <van-field
            v-if="action.action_type === 'invest'"
            v-model.number="action.annual_return_rate"
            type="number"
            label="年化收益率"
            placeholder="0.08"
          />
        </van-cell-group>
        <van-button v-if="actions.length > 1" size="small" plain type="danger" @click="actions.splice(idx, 1)">
          删除
        </van-button>
      </div>
      <van-button
        v-if="actions.length < 5"
        block plain type="primary" size="small"
        class="add-btn"
        @click="addAction"
      >
        {{ t('timeMachine.addAction') }}
      </van-button>
    </div>

    <!-- Parameters -->
    <van-cell-group inset class="params">
      <van-field v-model.number="projectionYears" type="number" :label="t('timeMachine.projectionYears')" />
    </van-cell-group>

    <div class="calc-btn-wrap">
      <van-button round block type="primary" :loading="loading" @click="calculate">
        {{ t('timeMachine.calculate') }}
      </van-button>
    </div>

    <!-- Chart -->
    <div v-if="chartData" ref="chartRef" class="whatif-chart" />

    <!-- Summary -->
    <div v-if="result?.summary" class="summary-card">
      <p>{{ result.summary }}</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { showToast } from 'vant'
import { postWhatIf, type WhatIfAction, type WhatIfResponse } from '@/api/timeMachine'
import * as echarts from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

echarts.use([LineChart, GridComponent, TooltipComponent, LegendComponent, CanvasRenderer])

const { t } = useI18n()

const actions = ref<WhatIfAction[]>([{ action_type: 'sell' }])
const projectionYears = ref(10)
const loading = ref(false)
const result = ref<WhatIfResponse | null>(null)
const chartData = ref(false)
const chartRef = ref<HTMLElement>()

// Asset list would be loaded from store in real implementation
const assetList = ref<{ id: number; name: string }[]>([])

function actionTypeLabel(t: string) {
  const map: Record<string, string> = { sell: '卖出资产', buy: '购买资产', invest: '新增投资', stop_expense: '停止支出' }
  return map[t] || t
}

function assetName(id?: number) {
  return assetList.value.find(a => a.id === id)?.name || '请选择'
}

function addAction() {
  if (actions.value.length < 5) {
    actions.value.push({ action_type: 'invest' })
  }
}

function showActionPicker(_idx: number) {
  // In real implementation, use van-action-sheet
}

function showAssetPicker(_idx: number) {
  // In real implementation, use van-picker with asset list
}

async function calculate() {
  loading.value = true
  try {
    const res = await postWhatIf({
      actions: actions.value,
      projection_years: projectionYears.value,
    })
    result.value = res.data
    chartData.value = true
    await nextTick()
    renderChart(res.data)
  } catch {
    showToast(t('toast.timeMachineError'))
  } finally {
    loading.value = false
  }
}

function renderChart(data: WhatIfResponse) {
  if (!chartRef.value) return
  const chart = echarts.init(chartRef.value)
  chart.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: [t('timeMachine.baseline'), t('timeMachine.scenario')] },
    grid: { left: 60, right: 20, bottom: 30 },
    xAxis: { type: 'category', data: data.projection.map(p => `${p.year}年`) },
    yAxis: { type: 'value', axisLabel: { formatter: (v: number) => `${(v / 10000).toFixed(0)}万` } },
    series: [
      {
        name: t('timeMachine.baseline'),
        type: 'line',
        data: data.projection.map(p => p.baseline_net_worth),
        smooth: true,
      },
      {
        name: t('timeMachine.scenario'),
        type: 'line',
        data: data.projection.map(p => p.scenario_net_worth),
        smooth: true,
        lineStyle: { type: 'dashed' },
      },
    ],
  })
}
</script>

<style scoped>
.action-item { margin-bottom: 8px; }
.add-btn { margin: 8px 16px; }
.params { margin-top: 12px; }
.calc-btn-wrap { padding: 16px; }
.whatif-chart { width: 100%; height: 300px; margin: 16px 0; }
.summary-card {
  margin: 0 16px 16px;
  padding: 16px;
  background: var(--van-background-2);
  border-radius: 12px;
  font-size: 14px;
  color: var(--van-text-color-2);
}
</style>
```

- [ ] **Step 2: Run typecheck**

Run: `cd frontend && npm run typecheck`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
cd frontend
git add src/components/ai/WhatIfSimulator.vue
git commit -m "feat(ui): add WhatIfSimulator component"
```

---

### Task 12: 财务推演图表组件

**Files:**
- Create: `frontend/src/components/ai/ProjectionChart.vue`

- [ ] **Step 1: Create the component**

```vue
<!-- frontend/src/components/ai/ProjectionChart.vue -->
<template>
  <div class="projection-chart">
    <van-cell-group inset class="params">
      <van-field v-model.number="projectionYears" type="number" :label="t('timeMachine.projectionYears')" />
      <van-field v-model.number="inflationRate" type="number" :label="t('timeMachine.inflationRate')" placeholder="0.03" />
    </van-cell-group>

    <div class="calc-btn-wrap">
      <van-button round block type="primary" :loading="loading" @click="calculate">
        {{ t('timeMachine.calculate') }}
      </van-button>
    </div>

    <div v-if="hasData" ref="chartRef" class="chart-container" />

    <div v-if="result?.summary" class="summary-card">
      <p>{{ result.summary }}</p>
    </div>

    <!-- Assumptions -->
    <van-cell-group v-if="result" inset class="assumptions">
      <van-cell title="资产数量" :value="result.assumptions.asset_count" />
      <van-cell title="负债数量" :value="result.assumptions.liability_count" />
      <van-cell title="通胀率" :value="`${(inflationRate * 100).toFixed(1)}%`" />
    </van-cell-group>
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import { showToast } from 'vant'
import { postProjection, type ProjectionResponse } from '@/api/timeMachine'
import * as echarts from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, MarkLineComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

echarts.use([LineChart, GridComponent, TooltipComponent, LegendComponent, MarkLineComponent, CanvasRenderer])

const { t } = useI18n()

const projectionYears = ref(5)
const inflationRate = ref(0.03)
const loading = ref(false)
const result = ref<ProjectionResponse | null>(null)
const hasData = ref(false)
const chartRef = ref<HTMLElement>()

async function calculate() {
  loading.value = true
  try {
    const res = await postProjection({
      projection_years: projectionYears.value,
      inflation_rate: inflationRate.value,
    })
    result.value = res.data
    hasData.value = true
    await nextTick()
    renderChart(res.data)
  } catch {
    showToast(t('toast.timeMachineError'))
  } finally {
    loading.value = false
  }
}

function renderChart(data: ProjectionResponse) {
  if (!chartRef.value) return
  const chart = echarts.init(chartRef.value)

  const allPoints = [...data.history, ...data.forecast]
  const years = allPoints.map(p => `${p.year}`)
  const nominal = allPoints.map(p => p.net_worth)
  const real = allPoints.map(p => p.real_net_worth)

  const historyLen = data.history.length

  chart.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: [t('timeMachine.nominal'), t('timeMachine.realValue')] },
    grid: { left: 60, right: 20, bottom: 30 },
    xAxis: { type: 'category', data: years },
    yAxis: { type: 'value', axisLabel: { formatter: (v: number) => `${(v / 10000).toFixed(0)}万` } },
    series: [
      {
        name: t('timeMachine.nominal'),
        type: 'line',
        data: nominal,
        smooth: true,
        areaStyle: { opacity: 0.1 },
        markLine: historyLen > 0 ? {
          data: [{ xAxis: historyLen - 1 }],
          label: { formatter: '今天' },
        } : undefined,
      },
      {
        name: t('timeMachine.realValue'),
        type: 'line',
        data: real,
        smooth: true,
        lineStyle: { type: 'dashed' },
      },
    ],
  })
}
</script>

<style scoped>
.params { margin-bottom: 12px; }
.calc-btn-wrap { padding: 0 16px 16px; }
.chart-container { width: 100%; height: 300px; margin: 16px 0; }
.summary-card {
  margin: 0 16px 16px;
  padding: 16px;
  background: var(--van-background-2);
  border-radius: 12px;
  font-size: 14px;
  color: var(--van-text-color-2);
}
.assumptions { margin-top: 12px; }
</style>
```

- [ ] **Step 2: Run typecheck**

Run: `cd frontend && npm run typecheck`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
cd frontend
git add src/components/ai/ProjectionChart.vue
git commit -m "feat(ui): add ProjectionChart component"
```

---

### Task 13: 时光机主页面 + AIHub 入口

**Files:**
- Create: `frontend/src/pages/AITimeMachinePage.vue`
- Modify: `frontend/src/pages/AIHubPage.vue`

- [ ] **Step 1: Create the main page with three tabs**

```vue
<!-- frontend/src/pages/AITimeMachinePage.vue -->
<template>
  <div class="time-machine-page">
    <van-nav-bar :title="t('timeMachine.title')" left-arrow @click-left="$router.back()" />
    <van-tabs v-model:active="activeTab" animated swipeable>
      <van-tab :title="t('timeMachine.whatif')">
        <WhatIfSimulator />
      </van-tab>
      <van-tab :title="t('timeMachine.projection')">
        <ProjectionChart />
      </van-tab>
      <van-tab :title="t('timeMachine.purchasingPower')">
        <PurchasingPowerCalc />
      </van-tab>
    </van-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import WhatIfSimulator from '@/components/ai/WhatIfSimulator.vue'
import ProjectionChart from '@/components/ai/ProjectionChart.vue'
import PurchasingPowerCalc from '@/components/ai/PurchasingPowerCalc.vue'

const { t } = useI18n()
const activeTab = ref(0)
</script>

<style scoped>
.time-machine-page {
  min-height: 100vh;
  background: var(--van-background);
}
</style>
```

- [ ] **Step 2: Add time machine entry card to AIHubPage.vue**

In the `features` array in `AIHubPage.vue`, add a new entry:
```typescript
{
  title: '资产时光机',
  desc: 'What-if 模拟、财务推演、购买力计算',
  route: '/ai/time-machine',
  svg: '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>',
},
```

- [ ] **Step 3: Run typecheck**

Run: `cd frontend && npm run typecheck`
Expected: No errors

- [ ] **Step 4: Commit**

```bash
cd frontend
git add src/pages/AITimeMachinePage.vue
git add -p src/pages/AIHubPage.vue
git commit -m "feat(ui): add AITimeMachinePage and hub entry card"
```

---

### Task 14: 端到端集成测试

**Files:**
- Test: `backend/tests/test_time_machine_integration.py`

- [ ] **Step 1: Write integration tests covering all three endpoints**

```python
# backend/tests/test_time_machine_integration.py
"""资产时光机端到端集成测试。"""
import pytest
from datetime import date
from app.models.asset import Asset
from app.models.category import Category
from app.models.liability import Liability


@pytest.fixture
def family_with_assets(client, auth_headers, db):
    """创建一个有资产和负债的家庭。"""
    me = client.get("/api/v1/auth/me", headers=auth_headers).json()
    family_id = me["data"]["family_id"]
    user_id = me["data"]["id"]

    physical_cat = db.query(Category).filter_by(name="车辆").first()
    financial_cat = db.query(Category).filter_by(name="基金").first()

    car = Asset(
        user_id=user_id, family_id=family_id, category_id=physical_cat.id,
        name="家用车", asset_type="physical",
        purchase_price=200000.0, current_value=150000.0,
        purchase_date=date(2022, 6, 1),
        annual_maintenance_cost=8000.0,
        expected_lifespan_days=3650,
    )
    fund = Asset(
        user_id=user_id, family_id=family_id, category_id=financial_cat.id,
        name="指数基金", asset_type="financial",
        purchase_price=100000.0, current_value=120000.0,
        purchase_date=date(2023, 1, 1),
        interest_rate=0.08,
    )
    db.add_all([car, fund])

    loan = Liability(
        user_id=user_id, family_id=family_id,
        name="车贷", category="car_loan",
        original_amount=150000.0, remaining_amount=80000.0,
        monthly_payment=3000.0, interest_rate=0.045,
        start_date=date(2022, 6, 1), end_date=date(2027, 6, 1),
        is_active=True,
    )
    db.add(loan)
    db.commit()
    db.refresh(car)
    db.refresh(fund)
    return {"car_id": car.id, "fund_id": fund.id}


def test_whatif_sell_car(client, auth_headers, family_with_assets):
    """What-if: 卖掉车，资金转投基金。"""
    car_id = family_with_assets["car_id"]
    resp = client.post(
        "/api/v1/ai/whatif",
        json={
            "actions": [
                {"action_type": "sell", "asset_id": car_id, "liquidation_rate": 0.7},
                {"action_type": "invest", "amount": 100000.0, "annual_return_rate": 0.06},
            ],
            "projection_years": 10,
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data["projection"]) == 11
    assert isinstance(data["total_difference"], float)
    assert data["summary"] is None  # AI not enabled


def test_projection_with_assets(client, auth_headers, family_with_assets):
    """财务推演：有资产和负债的家庭。"""
    resp = client.post(
        "/api/v1/ai/projection",
        json={"projection_years": 5, "inflation_rate": 0.03},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data["forecast"]) == 6
    assert data["forecast"][0]["total_assets"] > 0
    # Real net worth should be less than nominal in future years
    assert data["forecast"][5]["real_net_worth"] <= data["forecast"][5]["net_worth"]


def test_purchasing_power_api(client, auth_headers):
    """购买力计算 API。"""
    resp = client.get(
        "/api/v1/ai/purchasing-power",
        params={"amount": 50000, "from_year": 2010, "to_year": 2025},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["adjusted_amount"] > 50000
    assert data["cumulative_inflation"] > 0


def test_asset_purchasing_power(client, auth_headers, family_with_assets):
    """资产级购买力端点。"""
    car_id = family_with_assets["car_id"]
    resp = client.get(
        f"/api/v1/assets/{car_id}/purchasing-power",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["original_amount"] == 200000.0
    assert data["from_year"] == 2022


def test_whatif_invalid_asset(client, auth_headers, family_with_assets):
    """What-if: 引用不存在的资产应返回 404。"""
    resp = client.post(
        "/api/v1/ai/whatif",
        json={
            "actions": [{"action_type": "sell", "asset_id": 999999999}],
            "projection_years": 5,
        },
        headers=auth_headers,
    )
    assert resp.status_code == 404
```

- [ ] **Step 2: Run integration tests**

Run: `cd backend && uv run pytest tests/test_time_machine_integration.py -v`
Expected: All PASS

- [ ] **Step 3: Run full test suite to check for regressions**

Run: `cd backend && uv run pytest tests/ -v --tb=short`
Expected: All existing tests still pass

- [ ] **Step 4: Commit**

```bash
cd backend
git add tests/test_time_machine_integration.py
git commit -m "test: add time machine end-to-end integration tests"
```

---

### Task 15: 前端验证 + 最终提交

**Files:**
- All frontend files from Tasks 9-13

- [ ] **Step 1: Run full frontend typecheck**

Run: `cd frontend && npm run typecheck`
Expected: No errors

- [ ] **Step 2: Run frontend lint**

Run: `cd frontend && npm run lint`
Expected: No errors (or only pre-existing warnings)

- [ ] **Step 3: Run frontend build**

Run: `cd frontend && npm run build`
Expected: Build succeeds

- [ ] **Step 4: Start dev server and verify in browser**

Run manually: `cd frontend && npm run dev`

Verify:
1. Navigate to AI Hub page → time machine card is visible
2. Click card → navigates to `/ai/time-machine`
3. Three tabs are visible: What-if 模拟 / 财务推演 / 购买力计算
4. Purchasing power tab: enter amount=100000, from=2015, to=2026, click calculate → result shows
5. What-if tab: add a sell action, click calculate → chart renders
6. Projection tab: set years=5, click calculate → chart renders with history/forecast

- [ ] **Step 5: Run backend lint**

Run: `cd backend && uv run ruff check . && uv run ruff format --check .`
Expected: No errors

- [ ] **Step 6: Final commit if any fixes needed**

```bash
git add -A
git commit -m "chore: lint fixes for time machine feature"
```

---

## Summary

| Task | Description | Estimated Steps |
|------|-------------|----------------|
| 1 | CPI 常量 + 购买力 Service | 9 |
| 2 | CategoryFinancialDefault 模型 + 种子数据 | 6 |
| 3 | 购买力 API 端点 | 8 |
| 4 | What-if 计算引擎 | 8 |
| 5 | What-if API 端点 | 5 |
| 6 | 财务推演计算引擎 | 6 |
| 7 | 财务推演 API 端点 | 5 |
| 8 | Agent time_machine capability | 5 |
| 9 | Frontend API + 路由 + i18n | 6 |
| 10 | 购买力计算器组件 | 3 |
| 11 | What-if 模拟器组件 | 3 |
| 12 | 财务推演图表组件 | 3 |
| 13 | 时光机主页面 + AIHub 入口 | 4 |
| 14 | 端到端集成测试 | 4 |
| 15 | 前端验证 + 最终提交 | 6 |

**Total: 15 tasks, ~81 steps**

Dependencies:
- Tasks 1-3 可并行（购买力独立于 What-if）
- Task 2 必须在 Task 5, 7 之前（需要 CategoryFinancialDefault）
- Tasks 4-5 依赖 Task 2
- Tasks 6-7 依赖 Task 2
- Task 8 独立（Agent 层）
- Tasks 9-13 依赖 Tasks 3, 5, 7（需要 API 端点就绪）
- Task 14 依赖 Tasks 1-7
- Task 15 依赖 Tasks 9-13
