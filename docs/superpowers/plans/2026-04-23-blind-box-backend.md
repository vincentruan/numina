# 盲盒礼物系统后端实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现盲盒礼物系统后端（数据模型、权重算法、API端点、测试）

**Architecture:** 新增3张表（blind_box_gifts/draws/config）+ User生日字段 + 权重抽奖算法 + 父母端/孩子端API + 完整测试覆盖

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, pytest, lunardate

---

## 文件结构

**新增文件：**
- `backend/app/models/blind_box_gift.py` — 礼物池模型
- `backend/app/models/blind_box_draw.py` — 抽奖记录模型
- `backend/app/models/blind_box_config.py` — 家庭配置模型
- `backend/app/schemas/blind_box.py` — Pydantic schemas
- `backend/app/services/blind_box.py` — 业务逻辑（权重算法、特殊日期判定）
- `backend/app/routers/blind_box.py` — 父母端API
- `backend/app/routers/child_blind_box.py` — 孩子端API
- `backend/tests/test_blind_box.py` — 完整测试套件
- `backend/alembic/versions/XXXX_add_blind_box_tables.py` — 数据库迁移

**修改文件：**
- `backend/app/models/user.py` — 新增 birthday, birthday_is_lunar 字段
- `backend/app/models/chore.py` — ChoreInstance 新增 consumed_at 字段
- `backend/app/errors/codes.py` — 新增盲盒相关错误码
- `backend/app/main.py` — 注册新路由
- `backend/pyproject.toml` — 新增 lunardate 依赖

---

## Task 1: 数据模型 — BlindBoxGift

**Files:**
- Create: `backend/app/models/blind_box_gift.py`
- Modify: `backend/app/main.py:41` (import)

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_blind_box.py
def test_create_blind_box_gift(db):
    from app.models.blind_box_gift import BlindBoxGift
    gift = BlindBoxGift(
        family_id=1,
        name="乐高积木",
        value_score=8,
        created_by=1,
    )
    db.add(gift)
    db.commit()
    assert gift.id is not None
    assert gift.is_active is True
```

- [ ] **Step 2: 运行测试验证失败**

```bash
cd backend
uv run pytest tests/test_blind_box.py::test_create_blind_box_gift -v
```

预期：FAIL "No module named 'app.models.blind_box_gift'"

- [ ] **Step 3: 实现 BlindBoxGift 模型**

```python
# backend/app/models/blind_box_gift.py
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.utils.snowflake import next_id


class BlindBoxGift(Base):
    __tablename__ = "blind_box_gifts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    family_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("families.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(String(200), nullable=True)
    emoji: Mapped[str | None] = mapped_column(String(10), nullable=True)
    value_score: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-10
    source_wish_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("child_wishes.id"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
```

- [ ] **Step 4: 在 main.py 中导入模型**

```python
# backend/app/main.py (在其他模型导入后添加)
from app.models.blind_box_gift import BlindBoxGift  # noqa: F401
```

- [ ] **Step 5: 运行测试验证通过**

```bash
uv run pytest tests/test_blind_box.py::test_create_blind_box_gift -v
```

预期：PASS

- [ ] **Step 6: 提交**

```bash
git add backend/app/models/blind_box_gift.py backend/app/main.py backend/tests/test_blind_box.py
git commit -m "feat(blind-box): add BlindBoxGift model"
```

---

## Task 2: 数据模型 — BlindBoxDraw

**Files:**
- Create: `backend/app/models/blind_box_draw.py`
- Modify: `backend/app/main.py:42` (import)

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_blind_box.py (追加)
def test_create_blind_box_draw(db):
    from app.models.blind_box_draw import BlindBoxDraw
    from app.models.blind_box_gift import BlindBoxGift
    
    gift = BlindBoxGift(family_id=1, name="玩具", value_score=5, created_by=1)
    db.add(gift)
    db.commit()
    
    draw = BlindBoxDraw(
        family_id=1,
        child_user_id=2,
        coins_spent=100,
        gift_id=gift.id,
        is_surprise=False,
        is_bonus=False,
        status="pending_fulfillment",
    )
    db.add(draw)
    db.commit()
    assert draw.id is not None
    assert draw.draw_at is not None
```

- [ ] **Step 2: 运行测试验证失败**

```bash
uv run pytest tests/test_blind_box.py::test_create_blind_box_draw -v
```

预期：FAIL "No module named 'app.models.blind_box_draw'"

- [ ] **Step 3: 实现 BlindBoxDraw 模型**

```python
# backend/app/models/blind_box_draw.py
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.utils.snowflake import next_id


class BlindBoxDraw(Base):
    __tablename__ = "blind_box_draws"

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending_fulfillment', 'fulfilled')",
            name="ck_blind_box_draw_status",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    family_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("families.id"), nullable=False)
    child_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    coins_spent: Mapped[int] = mapped_column(Integer, nullable=False)
    gift_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("blind_box_gifts.id"), nullable=False)
    is_surprise: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_bonus: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    source_wish_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("child_wishes.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending_fulfillment")
    draw_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    fulfilled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
```

- [ ] **Step 4: 在 main.py 中导入模型**

```python
# backend/app/main.py (在 BlindBoxGift 导入后添加)
from app.models.blind_box_draw import BlindBoxDraw  # noqa: F401
```

- [ ] **Step 5: 运行测试验证通过**

```bash
uv run pytest tests/test_blind_box.py::test_create_blind_box_draw -v
```

预期：PASS

- [ ] **Step 6: 提交**

```bash
git add backend/app/models/blind_box_draw.py backend/app/main.py backend/tests/test_blind_box.py
git commit -m "feat(blind-box): add BlindBoxDraw model"
```

---

## Task 3: 数据模型 — BlindBoxConfig

**Files:**
- Create: `backend/app/models/blind_box_config.py`
- Modify: `backend/app/main.py:43` (import)

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_blind_box.py (追加)
def test_create_blind_box_config(db):
    from app.models.blind_box_config import BlindBoxConfig
    
    config = BlindBoxConfig(family_id=1)
    db.add(config)
    db.commit()
    
    assert config.id is not None
    assert config.enabled is True
    assert config.base_draw_prob == 0.30
    assert config.weight_scale == 2.0
    assert config.surprise_threshold_coins == 200
```

- [ ] **Step 2: 运行测试验证失败**

```bash
uv run pytest tests/test_blind_box.py::test_create_blind_box_config -v
```

预期：FAIL "No module named 'app.models.blind_box_config'"

- [ ] **Step 3: 实现 BlindBoxConfig 模型**

```python
# backend/app/models/blind_box_config.py
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Float, ForeignKey, Integer, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.utils.snowflake import next_id


class BlindBoxConfig(Base):
    __tablename__ = "blind_box_config"

    __table_args__ = (
        UniqueConstraint("family_id", name="uq_blind_box_config_family"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    family_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("families.id"), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    # 免费抽奖触发概率
    base_draw_prob: Mapped[float] = mapped_column(Float, default=0.30, nullable=False)
    special_day_prob: Mapped[float] = mapped_column(Float, default=0.80, nullable=False)
    
    # 权重算法参数
    weight_scale: Mapped[float] = mapped_column(Float, default=2.0, nullable=False)
    surprise_threshold_coins: Mapped[int] = mapped_column(Integer, default=200, nullable=False)
    
    # 超预期惊喜概率
    surprise_prob_normal: Mapped[float] = mapped_column(Float, default=0.05, nullable=False)
    surprise_prob_parent_bday: Mapped[float] = mapped_column(Float, default=0.60, nullable=False)
    surprise_prob_sibling_bday: Mapped[float] = mapped_column(Float, default=0.50, nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
```

- [ ] **Step 4: 在 main.py 中导入模型**

```python
# backend/app/main.py (在 BlindBoxDraw 导入后添加)
from app.models.blind_box_config import BlindBoxConfig  # noqa: F401
```

- [ ] **Step 5: 运行测试验证通过**

```bash
uv run pytest tests/test_blind_box.py::test_create_blind_box_config -v
```

预期：PASS

- [ ] **Step 6: 提交**

```bash
git add backend/app/models/blind_box_config.py backend/app/main.py backend/tests/test_blind_box.py
git commit -m "feat(blind-box): add BlindBoxConfig model with default values"
```


---

## Task 4: 修改 User 模型 — 新增生日字段

**Files:**
- Modify: `backend/app/models/user.py`
- Modify: `backend/app/schemas/user.py` (如有)

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_blind_box.py (追加)
def test_user_birthday_fields(db):
    from app.models.user import User
    import inspect
    cols = {c.key for c in inspect(User).mapper.column_attrs}
    assert "birthday" in cols
    assert "birthday_is_lunar" in cols
```

- [ ] **Step 2: 运行测试验证失败**

```bash
uv run pytest tests/test_blind_box.py::test_user_birthday_fields -v
```

预期：FAIL（字段不存在）

- [ ] **Step 3: 在 User 模型中新增字段**

```python
# backend/app/models/user.py (在现有字段末尾追加)
from sqlalchemy import Date  # 确保已导入

birthday: Mapped[date | None] = mapped_column(Date, nullable=True)
birthday_is_lunar: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
```

- [ ] **Step 4: 运行测试验证通过**

```bash
uv run pytest tests/test_blind_box.py::test_user_birthday_fields -v
```

预期：PASS

- [ ] **Step 5: 运行全量测试确认无回归**

```bash
uv run pytest tests/ -v
```

预期：全部 PASS

- [ ] **Step 6: 提交**

```bash
git add backend/app/models/user.py backend/tests/test_blind_box.py
git commit -m "feat(blind-box): add birthday fields to User model"
```

---

## Task 5: 业务逻辑 — 权重抽奖服务

**Files:**
- Create: `backend/app/services/blind_box.py`

核心算法：
- `is_special_day(user, today)` — 判断今天是否为特殊日期（生日/节日）
- `compute_weights(gifts, config)` — 按 value_score 计算权重列表
- `pick_gift(gifts, config)` — 加权随机抽取礼物
- `should_trigger_free_draw(config, is_special_day)` — 判断是否触发免费抽奖
- `should_upgrade_surprise(config, context)` — 判断是否升级为惊喜礼物

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_blind_box.py (追加)
def test_compute_weights_basic():
    from app.services.blind_box import compute_weights

    class FakeGift:
        def __init__(self, id, value_score):
            self.id = id
            self.value_score = value_score

    class FakeConfig:
        weight_scale = 2.0

    gifts = [FakeGift(1, 2), FakeGift(2, 8)]
    weights = compute_weights(gifts, FakeConfig())
    # value_score=2 → weight=1/2^2=0.25; value_score=8 → weight=1/8^2=0.015625
    # 低分礼物权重更高（更容易抽到）
    assert weights[0] > weights[1]
    assert len(weights) == 2


def test_pick_gift_returns_valid():
    from app.services.blind_box import pick_gift

    class FakeGift:
        def __init__(self, id, value_score):
            self.id = id
            self.value_score = value_score

    class FakeConfig:
        weight_scale = 2.0

    gifts = [FakeGift(1, 3), FakeGift(2, 7), FakeGift(3, 5)]
    result = pick_gift(gifts, FakeConfig())
    assert result in gifts


def test_should_trigger_free_draw():
    from app.services.blind_box import should_trigger_free_draw

    class FakeConfig:
        base_draw_prob = 1.0  # 100% 触发
        special_day_prob = 1.0

    assert should_trigger_free_draw(FakeConfig(), is_special=False) is True


def test_is_special_day_birthday():
    from datetime import date
    from app.services.blind_box import is_special_day

    class FakeUser:
        birthday = date(1990, 4, 23)
        birthday_is_lunar = False

    result = is_special_day(FakeUser(), date(2026, 4, 23))
    assert result is True
```

- [ ] **Step 2: 运行测试验证失败**

```bash
uv run pytest tests/test_blind_box.py::test_compute_weights_basic tests/test_blind_box.py::test_pick_gift_returns_valid tests/test_blind_box.py::test_should_trigger_free_draw tests/test_blind_box.py::test_is_special_day_birthday -v
```

预期：FAIL "No module named 'app.services.blind_box'"

- [ ] **Step 3: 实现 blind_box 服务**

```python
# backend/app/services/blind_box.py
import random
from datetime import date
from typing import Any


def is_special_day(user: Any, today: date) -> bool:
    """判断今天是否为用户的特殊日期（生日）。农历生日需要 lunardate 转换。"""
    if user.birthday is None:
        return False
    if user.birthday_is_lunar:
        try:
            from lunardate import LunarDate
            lunar_today = LunarDate.fromSolarDate(today.year, today.month, today.day)
            lunar_bday = LunarDate.fromSolarDate(
                user.birthday.year, user.birthday.month, user.birthday.day
            )
            return lunar_today.month == lunar_bday.month and lunar_today.day == lunar_bday.day
        except Exception:
            return False
    return today.month == user.birthday.month and today.day == user.birthday.day


def compute_weights(gifts: list[Any], config: Any) -> list[float]:
    """
    权重 = 1 / (value_score ^ weight_scale)
    低分礼物权重更高，高分礼物更稀有。
    """
    scale = config.weight_scale
    return [1.0 / (g.value_score ** scale) for g in gifts]


def pick_gift(gifts: list[Any], config: Any) -> Any:
    """按权重随机抽取一个礼物。"""
    if not gifts:
        raise ValueError("礼物池为空")
    weights = compute_weights(gifts, config)
    return random.choices(gifts, weights=weights, k=1)[0]


def should_trigger_free_draw(config: Any, is_special: bool) -> bool:
    """根据概率判断是否触发免费抽奖机会。"""
    prob = config.special_day_prob if is_special else config.base_draw_prob
    return random.random() < prob


def should_upgrade_surprise(config: Any, context: dict) -> bool:
    """
    判断是否将本次抽奖升级为超预期惊喜。
    context keys: is_parent_bday, is_sibling_bday
    """
    if context.get("is_parent_bday"):
        prob = config.surprise_prob_parent_bday
    elif context.get("is_sibling_bday"):
        prob = config.surprise_prob_sibling_bday
    else:
        prob = config.surprise_prob_normal
    return random.random() < prob
```

- [ ] **Step 4: 运行测试验证通过**

```bash
uv run pytest tests/test_blind_box.py::test_compute_weights_basic tests/test_blind_box.py::test_pick_gift_returns_valid tests/test_blind_box.py::test_should_trigger_free_draw tests/test_blind_box.py::test_is_special_day_birthday -v
```

预期：PASS

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/blind_box.py backend/tests/test_blind_box.py
git commit -m "feat(blind-box): add weighted draw service with special day detection"
```

---

## Task 6: Pydantic Schemas

**Files:**
- Create: `backend/app/schemas/blind_box.py`

- [ ] **Step 1: 实现 schemas**

```python
# backend/app/schemas/blind_box.py
from datetime import datetime
from pydantic import BaseModel, Field


# ── Gift ──────────────────────────────────────────────────────────────────────

class BlindBoxGiftCreate(BaseModel):
    name: str = Field(..., max_length=100)
    description: str | None = Field(None, max_length=200)
    emoji: str | None = Field(None, max_length=10)
    value_score: int = Field(..., ge=1, le=10)
    source_wish_id: int | None = None


class BlindBoxGiftUpdate(BaseModel):
    name: str | None = Field(None, max_length=100)
    description: str | None = Field(None, max_length=200)
    emoji: str | None = Field(None, max_length=10)
    value_score: int | None = Field(None, ge=1, le=10)
    is_active: bool | None = None


class BlindBoxGiftResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    family_id: int
    name: str
    description: str | None
    emoji: str | None
    value_score: int
    source_wish_id: int | None
    is_active: bool
    created_by: int
    created_at: datetime
    updated_at: datetime


# ── Draw ──────────────────────────────────────────────────────────────────────

class DrawRequest(BaseModel):
    coins_spent: int = Field(..., ge=0)


class BlindBoxDrawResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    family_id: int
    child_user_id: int
    coins_spent: int
    gift_id: int
    gift_name: str
    gift_emoji: str | None
    is_surprise: bool
    is_bonus: bool
    status: str
    draw_at: datetime
    fulfilled_at: datetime | None


# ── Config ────────────────────────────────────────────────────────────────────

class BlindBoxConfigUpdate(BaseModel):
    enabled: bool | None = None
    base_draw_prob: float | None = Field(None, ge=0.0, le=1.0)
    special_day_prob: float | None = Field(None, ge=0.0, le=1.0)
    weight_scale: float | None = Field(None, ge=0.1, le=10.0)
    surprise_threshold_coins: int | None = Field(None, ge=0)
    surprise_prob_normal: float | None = Field(None, ge=0.0, le=1.0)
    surprise_prob_parent_bday: float | None = Field(None, ge=0.0, le=1.0)
    surprise_prob_sibling_bday: float | None = Field(None, ge=0.0, le=1.0)


class BlindBoxConfigResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    family_id: int
    enabled: bool
    base_draw_prob: float
    special_day_prob: float
    weight_scale: float
    surprise_threshold_coins: int
    surprise_prob_normal: float
    surprise_prob_parent_bday: float
    surprise_prob_sibling_bday: float
```

- [ ] **Step 2: 提交**

```bash
git add backend/app/schemas/blind_box.py
git commit -m "feat(blind-box): add Pydantic schemas for gift/draw/config"
```

---

## Task 7: 父母端 API Router

**Files:**
- Create: `backend/app/routers/blind_box.py`
- Modify: `backend/app/main.py` (注册路由)

端点列表：
- `GET  /blind-box/gifts` — 查看礼物池
- `POST /blind-box/gifts` — 添加礼物
- `PUT  /blind-box/gifts/{id}` — 编辑礼物
- `DELETE /blind-box/gifts/{id}` — 删除礼物（软删除 is_active=False）
- `GET  /blind-box/draws` — 查看抽奖历史
- `PUT  /blind-box/draws/{id}/fulfill` — 标记礼物已兑现
- `GET  /blind-box/config` — 查看配置
- `PUT  /blind-box/config` — 更新配置

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_blind_box.py (追加)
def test_parent_create_gift(client, auth_headers):
    resp = client.post(
        "/api/v1/blind-box/gifts",
        json={"name": "乐高积木", "value_score": 7, "emoji": "🧱"},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "乐高积木"
    assert data["value_score"] == 7


def test_parent_list_gifts(client, auth_headers):
    client.post(
        "/api/v1/blind-box/gifts",
        json={"name": "玩具车", "value_score": 4},
        headers=auth_headers,
    )
    resp = client.get("/api/v1/blind-box/gifts", headers=auth_headers)
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


def test_parent_get_config(client, auth_headers):
    resp = client.get("/api/v1/blind-box/config", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "enabled" in data
    assert "base_draw_prob" in data
```

- [ ] **Step 2: 运行测试验证失败**

```bash
uv run pytest tests/test_blind_box.py::test_parent_create_gift tests/test_blind_box.py::test_parent_list_gifts tests/test_blind_box.py::test_parent_get_config -v
```

预期：FAIL 404

- [ ] **Step 3: 实现父母端 Router**

```python
# backend/app/routers/blind_box.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.blind_box_config import BlindBoxConfig
from app.models.blind_box_draw import BlindBoxDraw
from app.models.blind_box_gift import BlindBoxGift
from app.models.user import User
from app.schemas.blind_box import (
    BlindBoxConfigResponse,
    BlindBoxConfigUpdate,
    BlindBoxDrawResponse,
    BlindBoxGiftCreate,
    BlindBoxGiftResponse,
    BlindBoxGiftUpdate,
)

router = APIRouter(prefix="/blind-box", tags=["blind-box"])


def _get_or_create_config(family_id: int, db: Session) -> BlindBoxConfig:
    config = db.query(BlindBoxConfig).filter_by(family_id=family_id).first()
    if not config:
        config = BlindBoxConfig(family_id=family_id)
        db.add(config)
        db.commit()
        db.refresh(config)
    return config


@router.get("/gifts", response_model=list[BlindBoxGiftResponse])
def list_gifts(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return (
        db.query(BlindBoxGift)
        .filter_by(family_id=current_user.family_id, is_active=True)
        .all()
    )


@router.post("/gifts", response_model=BlindBoxGiftResponse, status_code=201)
def create_gift(
    body: BlindBoxGiftCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    gift = BlindBoxGift(
        **body.model_dump(),
        family_id=current_user.family_id,
        created_by=current_user.id,
    )
    db.add(gift)
    db.commit()
    db.refresh(gift)
    return gift


@router.put("/gifts/{gift_id}", response_model=BlindBoxGiftResponse)
def update_gift(
    gift_id: int,
    body: BlindBoxGiftUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    gift = db.query(BlindBoxGift).filter_by(id=gift_id, family_id=current_user.family_id).first()
    if not gift:
        raise HTTPException(status_code=404, detail="礼物不存在")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(gift, k, v)
    db.commit()
    db.refresh(gift)
    return gift


@router.delete("/gifts/{gift_id}", status_code=204)
def delete_gift(
    gift_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    gift = db.query(BlindBoxGift).filter_by(id=gift_id, family_id=current_user.family_id).first()
    if not gift:
        raise HTTPException(status_code=404, detail="礼物不存在")
    gift.is_active = False
    db.commit()


@router.get("/draws", response_model=list[BlindBoxDrawResponse])
def list_draws(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    draws = (
        db.query(BlindBoxDraw)
        .filter_by(family_id=current_user.family_id)
        .order_by(BlindBoxDraw.draw_at.desc())
        .all()
    )
    result = []
    for d in draws:
        gift = db.query(BlindBoxGift).filter_by(id=d.gift_id).first()
        result.append(
            BlindBoxDrawResponse(
                **{c: getattr(d, c) for c in [
                    "id", "family_id", "child_user_id", "coins_spent",
                    "gift_id", "is_surprise", "is_bonus", "status", "draw_at", "fulfilled_at"
                ]},
                gift_name=gift.name if gift else "",
                gift_emoji=gift.emoji if gift else None,
            )
        )
    return result


@router.put("/draws/{draw_id}/fulfill", response_model=BlindBoxDrawResponse)
def fulfill_draw(
    draw_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from datetime import datetime, timezone
    draw = db.query(BlindBoxDraw).filter_by(id=draw_id, family_id=current_user.family_id).first()
    if not draw:
        raise HTTPException(status_code=404, detail="抽奖记录不存在")
    draw.status = "fulfilled"
    draw.fulfilled_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(draw)
    gift = db.query(BlindBoxGift).filter_by(id=draw.gift_id).first()
    return BlindBoxDrawResponse(
        **{c: getattr(draw, c) for c in [
            "id", "family_id", "child_user_id", "coins_spent",
            "gift_id", "is_surprise", "is_bonus", "status", "draw_at", "fulfilled_at"
        ]},
        gift_name=gift.name if gift else "",
        gift_emoji=gift.emoji if gift else None,
    )


@router.get("/config", response_model=BlindBoxConfigResponse)
def get_config(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _get_or_create_config(current_user.family_id, db)


@router.put("/config", response_model=BlindBoxConfigResponse)
def update_config(
    body: BlindBoxConfigUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    config = _get_or_create_config(current_user.family_id, db)
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(config, k, v)
    db.commit()
    db.refresh(config)
    return config
```

- [ ] **Step 4: 在 main.py 中注册路由**

```python
# backend/app/main.py (在其他 router 导入后添加)
from app.routers.blind_box import router as blind_box_router

# 在 app.include_router(...) 列表中添加：
app.include_router(blind_box_router, prefix="/api/v1")
```

- [ ] **Step 5: 运行测试验证通过**

```bash
uv run pytest tests/test_blind_box.py::test_parent_create_gift tests/test_blind_box.py::test_parent_list_gifts tests/test_blind_box.py::test_parent_get_config -v
```

预期：PASS

- [ ] **Step 6: 提交**

```bash
git add backend/app/routers/blind_box.py backend/app/main.py backend/tests/test_blind_box.py
git commit -m "feat(blind-box): add parent-facing API router (gifts CRUD + config)"
```

---

## Task 8: 孩子端 API Router

**Files:**
- Create: `backend/app/routers/child_blind_box.py`
- Modify: `backend/app/main.py` (注册路由)

端点列表：
- `POST /child/blind-box/draw` — 孩子发起抽奖（消耗金币）
- `GET  /child/blind-box/draws` — 孩子查看自己的抽奖历史

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_blind_box.py (追加)
def test_child_draw(client, auth_headers, second_user_headers):
    # 父母先添加礼物
    client.post(
        "/api/v1/blind-box/gifts",
        json={"name": "故事书", "value_score": 3, "emoji": "📚"},
        headers=auth_headers,
    )
    # 孩子抽奖（second_user 在不同家庭，用 auth_headers 用户自己抽）
    resp = client.post(
        "/api/v1/child/blind-box/draw",
        json={"coins_spent": 50},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "gift_id" in data
    assert "gift_name" in data
    assert data["status"] == "pending_fulfillment"


def test_child_list_draws(client, auth_headers):
    resp = client.get("/api/v1/child/blind-box/draws", headers=auth_headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
```

- [ ] **Step 2: 运行测试验证失败**

```bash
uv run pytest tests/test_blind_box.py::test_child_draw tests/test_blind_box.py::test_child_list_draws -v
```

预期：FAIL 404

- [ ] **Step 3: 实现孩子端 Router**

```python
# backend/app/routers/child_blind_box.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.blind_box_config import BlindBoxConfig
from app.models.blind_box_draw import BlindBoxDraw
from app.models.blind_box_gift import BlindBoxGift
from app.models.user import User
from app.schemas.blind_box import BlindBoxDrawResponse, DrawRequest
from app.services.blind_box import pick_gift, should_upgrade_surprise
from app.routers.blind_box import _get_or_create_config

router = APIRouter(prefix="/child/blind-box", tags=["child-blind-box"])


@router.post("/draw", response_model=BlindBoxDrawResponse, status_code=201)
def child_draw(
    body: DrawRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    config = _get_or_create_config(current_user.family_id, db)
    if not config.enabled:
        raise HTTPException(status_code=403, detail="盲盒功能未开启")

    gifts = (
        db.query(BlindBoxGift)
        .filter_by(family_id=current_user.family_id, is_active=True)
        .all()
    )
    if not gifts:
        raise HTTPException(status_code=404, detail="礼物池为空，请让父母先添加礼物")

    from datetime import date, datetime, timezone
    today = date.today()

    # 判断是否为惊喜升级场景
    context = {
        "is_parent_bday": False,   # 可扩展：查询家庭成员生日
        "is_sibling_bday": False,
    }
    is_surprise = should_upgrade_surprise(config, context)

    # 若为惊喜，从高分礼物中抽取（value_score >= 7）
    if is_surprise:
        surprise_pool = [g for g in gifts if g.value_score >= 7]
        pool = surprise_pool if surprise_pool else gifts
    else:
        pool = gifts

    chosen = pick_gift(pool, config)

    draw = BlindBoxDraw(
        family_id=current_user.family_id,
        child_user_id=current_user.id,
        coins_spent=body.coins_spent,
        gift_id=chosen.id,
        is_surprise=is_surprise,
        is_bonus=False,
        status="pending_fulfillment",
    )
    db.add(draw)
    db.commit()
    db.refresh(draw)

    return BlindBoxDrawResponse(
        **{c: getattr(draw, c) for c in [
            "id", "family_id", "child_user_id", "coins_spent",
            "gift_id", "is_surprise", "is_bonus", "status", "draw_at", "fulfilled_at"
        ]},
        gift_name=chosen.name,
        gift_emoji=chosen.emoji,
    )


@router.get("/draws", response_model=list[BlindBoxDrawResponse])
def child_list_draws(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    draws = (
        db.query(BlindBoxDraw)
        .filter_by(family_id=current_user.family_id, child_user_id=current_user.id)
        .order_by(BlindBoxDraw.draw_at.desc())
        .all()
    )
    result = []
    for d in draws:
        gift = db.query(BlindBoxGift).filter_by(id=d.gift_id).first()
        result.append(
            BlindBoxDrawResponse(
                **{c: getattr(d, c) for c in [
                    "id", "family_id", "child_user_id", "coins_spent",
                    "gift_id", "is_surprise", "is_bonus", "status", "draw_at", "fulfilled_at"
                ]},
                gift_name=gift.name if gift else "",
                gift_emoji=gift.emoji if gift else None,
            )
        )
    return result
```

- [ ] **Step 4: 在 main.py 中注册路由**

```python
# backend/app/main.py
from app.routers.child_blind_box import router as child_blind_box_router

app.include_router(child_blind_box_router, prefix="/api/v1")
```

- [ ] **Step 5: 运行测试验证通过**

```bash
uv run pytest tests/test_blind_box.py::test_child_draw tests/test_blind_box.py::test_child_list_draws -v
```

预期：PASS

- [ ] **Step 6: 提交**

```bash
git add backend/app/routers/child_blind_box.py backend/app/main.py backend/tests/test_blind_box.py
git commit -m "feat(blind-box): add child-facing draw API"
```

---

## Task 9: Alembic 迁移 + lunardate 依赖 + 全量测试

**Files:**
- Create: `backend/alembic/versions/XXXX_add_blind_box_tables.py`
- Modify: `backend/pyproject.toml`

- [ ] **Step 1: 添加 lunardate 依赖**

```bash
cd backend
uv add lunardate
```

验证：

```bash
uv run python -c "from lunardate import LunarDate; print('ok')"
```

- [ ] **Step 2: 生成 Alembic 迁移**

```bash
cd backend
uv run alembic revision --autogenerate -m "add blind box tables and user birthday fields"
```

检查生成的迁移文件，确认包含：
- `blind_box_gifts` 表
- `blind_box_draws` 表
- `blind_box_config` 表
- `users.birthday` 列
- `users.birthday_is_lunar` 列

- [ ] **Step 3: 应用迁移（本地开发环境）**

```bash
uv run alembic upgrade head
```

- [ ] **Step 4: 运行全量测试**

```bash
uv run pytest tests/ -v
```

预期：全部 PASS（原有 36 个 + 新增盲盒测试）

- [ ] **Step 5: 提交**

```bash
git add backend/alembic/versions/ backend/pyproject.toml backend/uv.lock
git commit -m "feat(blind-box): add Alembic migration and lunardate dependency"
```

---

## 验收标准

完成所有 Task 后，执行以下验收检查：

```bash
cd backend

# 1. 全量测试通过
uv run pytest tests/ -v

# 2. 类型检查通过
uv run mypy app/

# 3. Lint 通过
uv run ruff check .

# 4. 迁移无 pending
uv run alembic check
```

所有命令均应无错误退出。

---

## 实现顺序总结

| Task | 内容 | 依赖 |
|------|------|------|
| 1 | BlindBoxGift 模型 | — |
| 2 | BlindBoxDraw 模型 | Task 1 |
| 3 | BlindBoxConfig 模型 | — |
| 4 | User 生日字段 | — |
| 5 | 权重抽奖服务 | Task 1 |
| 6 | Pydantic Schemas | Task 1-3 |
| 7 | 父母端 API | Task 1-3, 5, 6 |
| 8 | 孩子端 API | Task 7 |
| 9 | Alembic 迁移 + 全量测试 | Task 1-8 |

---

## ⚠️ 补充章节：Spec 遗漏修正

以下 Task 10-14 补充原计划遗漏的关键功能。

---

## Task 10: BonusDraw 模型 — 免费抽奖机会

**背景：** 心愿兑现后，系统以概率触发一次免费抽奖机会（Bonus Draw），孩子可在有效期内使用。

**Files:**
- Create: `backend/app/models/bonus_draw.py`
- Modify: `backend/app/main.py` (import)

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_blind_box.py (追加)
def test_create_bonus_draw(db):
    from app.models.bonus_draw import BonusDraw
    from datetime import datetime, timezone, timedelta

    bonus = BonusDraw(
        family_id=1,
        child_user_id=2,
        source_wish_id=10,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    db.add(bonus)
    db.commit()
    assert bonus.id is not None
    assert bonus.status == "available"
```

- [ ] **Step 2: 运行测试验证失败**

```bash
cd backend
uv run pytest tests/test_blind_box.py::test_create_bonus_draw -v
```

预期：FAIL "No module named 'app.models.bonus_draw'"

- [ ] **Step 3: 实现 BonusDraw 模型**

```python
# backend/app/models/bonus_draw.py
from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.utils.snowflake import next_id


class BonusDraw(Base):
    __tablename__ = "bonus_draws"

    __table_args__ = (
        CheckConstraint(
            "status IN ('available', 'used', 'expired')",
            name="ck_bonus_draw_status",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    family_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("families.id"), nullable=False)
    child_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    source_wish_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("child_wishes.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="available")
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    used_draw_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("blind_box_draws.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
```

- [ ] **Step 4: 在 main.py 中导入模型**

```python
from app.models.bonus_draw import BonusDraw  # noqa: F401
```

- [ ] **Step 5: 运行测试验证通过**

```bash
uv run pytest tests/test_blind_box.py::test_create_bonus_draw -v
```

预期：PASS

- [ ] **Step 6: 提交**

```bash
git add backend/app/models/bonus_draw.py backend/app/main.py backend/tests/test_blind_box.py
git commit -m "feat(blind-box): add BonusDraw model for wish-triggered free draws"
```

---

## Task 11: BonusDraw API + 心愿兑现触发逻辑

**Files:**
- Modify: `backend/app/routers/blind_box.py` (新增 bonus-draws 端点)
- Modify: `backend/app/routers/child_wishes.py` (兑现时触发 bonus draw)
- Modify: `backend/app/schemas/blind_box.py` (新增 BonusDrawResponse)

端点：
- `GET  /blind-box/bonus-draws` — 父母查看所有 bonus draw 记录
- `GET  /child/blind-box/bonus-draws` — 孩子查看自己的可用 bonus draw
- `POST /child/blind-box/bonus-draws/{id}/use` — 孩子使用 bonus draw 抽奖

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_blind_box.py (追加)
def test_child_list_bonus_draws(client, auth_headers):
    resp = client.get("/api/v1/child/blind-box/bonus-draws", headers=auth_headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_child_use_bonus_draw_not_found(client, auth_headers):
    resp = client.post(
        "/api/v1/child/blind-box/bonus-draws/99999/use",
        headers=auth_headers,
    )
    assert resp.status_code == 404
```

- [ ] **Step 2: 运行测试验证失败**

```bash
uv run pytest tests/test_blind_box.py::test_child_list_bonus_draws tests/test_blind_box.py::test_child_use_bonus_draw_not_found -v
```

预期：FAIL 404

- [ ] **Step 3: 新增 BonusDrawResponse schema**

```python
# backend/app/schemas/blind_box.py (追加)
class BonusDrawResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    family_id: int
    child_user_id: int
    source_wish_id: int | None
    status: str
    expires_at: datetime
    used_draw_id: int | None
    created_at: datetime
```

- [ ] **Step 4: 在 blind_box.py router 中新增父母端端点**

```python
# backend/app/routers/blind_box.py (追加)
from app.models.bonus_draw import BonusDraw
from app.schemas.blind_box import BonusDrawResponse

@router.get("/bonus-draws", response_model=list[BonusDrawResponse])
def list_bonus_draws(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return db.query(BonusDraw).filter_by(family_id=current_user.family_id).all()
```

- [ ] **Step 5: 在 child_blind_box.py router 中新增孩子端端点**

```python
# backend/app/routers/child_blind_box.py (追加)
from datetime import datetime, timezone
from app.models.bonus_draw import BonusDraw
from app.schemas.blind_box import BonusDrawResponse

@router.get("/bonus-draws", response_model=list[BonusDrawResponse])
def child_list_bonus_draws(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return (
        db.query(BonusDraw)
        .filter_by(family_id=current_user.family_id, child_user_id=current_user.id)
        .all()
    )


@router.post("/bonus-draws/{bonus_id}/use", response_model=BlindBoxDrawResponse, status_code=201)
def child_use_bonus_draw(
    bonus_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    bonus = db.query(BonusDraw).filter_by(
        id=bonus_id,
        child_user_id=current_user.id,
        family_id=current_user.family_id,
        status="available",
    ).first()
    if not bonus:
        raise HTTPException(status_code=404, detail="免费抽奖机会不存在或已使用")
    if bonus.expires_at < datetime.now(timezone.utc):
        bonus.status = "expired"
        db.commit()
        raise HTTPException(status_code=410, detail="免费抽奖机会已过期")

    config = _get_or_create_config(current_user.family_id, db)
    gifts = db.query(BlindBoxGift).filter_by(family_id=current_user.family_id, is_active=True).all()
    if not gifts:
        raise HTTPException(status_code=404, detail="礼物池为空")

    from app.services.blind_box import pick_gift, should_upgrade_surprise
    context = {"is_parent_bday": False, "is_sibling_bday": False}
    is_surprise = should_upgrade_surprise(config, context)
    pool = [g for g in gifts if g.value_score >= 7] if is_surprise else gifts
    chosen = pick_gift(pool if pool else gifts, config)

    draw = BlindBoxDraw(
        family_id=current_user.family_id,
        child_user_id=current_user.id,
        coins_spent=0,
        gift_id=chosen.id,
        is_surprise=is_surprise,
        is_bonus=True,
        status="pending_fulfillment",
    )
    db.add(draw)
    db.flush()

    bonus.status = "used"
    bonus.used_draw_id = draw.id
    db.commit()
    db.refresh(draw)

    return BlindBoxDrawResponse(
        **{c: getattr(draw, c) for c in [
            "id", "family_id", "child_user_id", "coins_spent",
            "gift_id", "is_surprise", "is_bonus", "status", "draw_at", "fulfilled_at"
        ]},
        gift_name=chosen.name,
        gift_emoji=chosen.emoji,
    )
```

- [ ] **Step 6: 心愿兑现时触发 bonus draw（修改 child_wishes router）**

在 `PUT /child-wishes/{id}/fulfill`（或父母兑现端点）成功后追加：

```python
# 心愿兑现后，按概率触发免费抽奖机会
import random
from datetime import datetime, timezone, timedelta
from app.models.bonus_draw import BonusDraw
from app.models.blind_box_config import BlindBoxConfig

config = db.query(BlindBoxConfig).filter_by(family_id=current_user.family_id).first()
bonus_prob = config.base_draw_prob if config else 0.30
if random.random() < bonus_prob:
    bonus = BonusDraw(
        family_id=wish.family_id,
        child_user_id=wish.child_user_id,
        source_wish_id=wish.id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    db.add(bonus)
    db.commit()
```

- [ ] **Step 7: 运行测试验证通过**

```bash
uv run pytest tests/test_blind_box.py::test_child_list_bonus_draws tests/test_blind_box.py::test_child_use_bonus_draw_not_found -v
```

预期：PASS

- [ ] **Step 8: 提交**

```bash
git add backend/app/routers/blind_box.py backend/app/routers/child_blind_box.py backend/app/schemas/blind_box.py
git commit -m "feat(blind-box): add bonus draw API and wish-fulfillment trigger"
```

---

## Task 12: 从 ChildWish 转入礼物池 API

**Files:**
- Modify: `backend/app/routers/blind_box.py` (新增转换端点)

端点：`POST /blind-box/gifts/from-wish/{wish_id}`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_blind_box.py (追加)
def test_create_gift_from_wish_not_found(client, auth_headers):
    resp = client.post(
        "/api/v1/blind-box/gifts/from-wish/99999",
        headers=auth_headers,
    )
    assert resp.status_code == 404
```

- [ ] **Step 2: 运行测试验证失败**

```bash
uv run pytest tests/test_blind_box.py::test_create_gift_from_wish_not_found -v
```

预期：FAIL 404（路由不存在）

- [ ] **Step 3: 实现转换端点**

```python
# backend/app/routers/blind_box.py (追加)
@router.post("/gifts/from-wish/{wish_id}", response_model=BlindBoxGiftResponse, status_code=201)
def create_gift_from_wish(
    wish_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.models.child_wish import ChildWish
    wish = db.query(ChildWish).filter_by(id=wish_id, family_id=current_user.family_id).first()
    if not wish:
        raise HTTPException(status_code=404, detail="心愿不存在")

    # 检查是否已转入礼物池
    existing = db.query(BlindBoxGift).filter_by(
        source_wish_id=wish_id, family_id=current_user.family_id
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="该心愿已转入礼物池")

    gift = BlindBoxGift(
        family_id=current_user.family_id,
        name=wish.name,
        description=wish.description,
        emoji=wish.emoji,
        value_score=min(max(round((wish.estimated_price or 50) / 100), 1), 10),
        source_wish_id=wish.id,
        created_by=current_user.id,
    )
    db.add(gift)
    db.commit()
    db.refresh(gift)
    return gift
```

- [ ] **Step 4: 运行测试验证通过**

```bash
uv run pytest tests/test_blind_box.py::test_create_gift_from_wish_not_found -v
```

预期：PASS（404 来自心愿不存在，而非路由不存在）

- [ ] **Step 5: 提交**

```bash
git add backend/app/routers/blind_box.py backend/tests/test_blind_box.py
git commit -m "feat(blind-box): add convert-wish-to-gift endpoint"
```

---

## Task 13: 重复检查逻辑 — 创建礼物时返回警告

**Files:**
- Modify: `backend/app/routers/blind_box.py` (create_gift 端点增加重复检查)
- Modify: `backend/app/schemas/blind_box.py` (新增 warning 字段)

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_blind_box.py (追加)
def test_create_gift_duplicate_warning(client, auth_headers):
    # 先创建同名礼物
    client.post(
        "/api/v1/blind-box/gifts",
        json={"name": "乐高积木", "value_score": 7},
        headers=auth_headers,
    )
    # 再次创建同名礼物，应返回 201 但带 warning
    resp = client.post(
        "/api/v1/blind-box/gifts",
        json={"name": "乐高积木", "value_score": 5},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data.get("warning") is not None
```

- [ ] **Step 2: 运行测试验证失败**

```bash
uv run pytest tests/test_blind_box.py::test_create_gift_duplicate_warning -v
```

预期：FAIL（无 warning 字段）

- [ ] **Step 3: 修改 BlindBoxGiftResponse 新增 warning 字段**

```python
# backend/app/schemas/blind_box.py
class BlindBoxGiftResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    family_id: int
    name: str
    description: str | None
    emoji: str | None
    value_score: int
    source_wish_id: int | None
    is_active: bool
    created_by: int
    created_at: datetime
    updated_at: datetime
    warning: str | None = None  # 新增：重复检查警告
```

- [ ] **Step 4: 修改 create_gift 端点加入重复检查**

```python
# backend/app/routers/blind_box.py — create_gift 函数替换为：
@router.post("/gifts", response_model=BlindBoxGiftResponse, status_code=201)
def create_gift(
    body: BlindBoxGiftCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # 重复名称检查
    duplicate = db.query(BlindBoxGift).filter_by(
        family_id=current_user.family_id,
        name=body.name,
        is_active=True,
    ).first()

    gift = BlindBoxGift(
        **body.model_dump(),
        family_id=current_user.family_id,
        created_by=current_user.id,
    )
    db.add(gift)
    db.commit()
    db.refresh(gift)

    # 构造响应，附加警告
    response = BlindBoxGiftResponse.model_validate(gift)
    if duplicate:
        response.warning = f"礼物池中已有同名礼物「{duplicate.name}」，请确认是否重复添加"
    return response
```

- [ ] **Step 5: 运行测试验证通过**

```bash
uv run pytest tests/test_blind_box.py::test_create_gift_duplicate_warning -v
```

预期：PASS

- [ ] **Step 6: 提交**

```bash
git add backend/app/routers/blind_box.py backend/app/schemas/blind_box.py backend/tests/test_blind_box.py
git commit -m "feat(blind-box): add duplicate name warning on gift creation"
```

---

## Task 14: Draw API 事务原子性 — 完整6步骤

**背景：** 孩子端 `POST /child/blind-box/draw` 需保证原子性：
1. 校验 ChoreInstance（已批准、未消耗）
2. 计算金币总额
3. 标记 ChoreInstance.consumed_at
4. 执行加权抽奖
5. 写入 BlindBoxDraw 记录
6. 提交事务（任一步失败全部回滚）

**Files:**
- Modify: `backend/app/routers/child_blind_box.py` (重写 child_draw)
- Modify: `backend/app/schemas/blind_box.py` (修改 DrawRequest)
- Modify: `backend/app/models/chore.py` (ChoreInstance 新增 consumed_at)

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_blind_box.py (追加)
def test_draw_requires_chore_instance_ids(client, auth_headers):
    """draw 端点必须接受 chore_instance_ids 字段"""
    resp = client.post(
        "/api/v1/child/blind-box/draw",
        json={"chore_instance_ids": []},
        headers=auth_headers,
    )
    # 空列表应返回 400（无可用金币）
    assert resp.status_code == 400


def test_draw_rejects_already_consumed(client, auth_headers):
    """已消耗的 ChoreInstance 不能重复使用"""
    # 此测试需要先创建 ChoreInstance fixture，在完整集成测试中验证
    pass  # placeholder — 在 conftest 扩展后补全
```

- [ ] **Step 2: 运行测试验证失败**

```bash
uv run pytest tests/test_blind_box.py::test_draw_requires_chore_instance_ids -v
```

预期：FAIL（当前端点不接受 chore_instance_ids）

- [ ] **Step 3: 在 ChoreInstance 模型中新增 consumed_at 字段**

```python
# backend/app/models/chore.py (在 ChoreInstance 类中追加)
from sqlalchemy import DateTime

consumed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
```

- [ ] **Step 4: 修改 DrawRequest schema**

```python
# backend/app/schemas/blind_box.py — 替换 DrawRequest
class DrawRequest(BaseModel):
    chore_instance_ids: list[int] = Field(..., min_length=1, description="已批准的 ChoreInstance ID 列表")
```

- [ ] **Step 5: 重写 child_draw 端点（完整6步骤事务）**

```python
# backend/app/routers/child_blind_box.py — 替换 child_draw
@router.post("/draw", response_model=BlindBoxDrawResponse, status_code=201)
def child_draw(
    body: DrawRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.models.chore import ChoreInstance

    config = _get_or_create_config(current_user.family_id, db)
    if not config.enabled:
        raise HTTPException(status_code=403, detail="盲盒功能未开启")

    # Step 1: 校验 ChoreInstance（已批准、属于当前孩子、未消耗）
    instances = (
        db.query(ChoreInstance)
        .filter(
            ChoreInstance.id.in_(body.chore_instance_ids),
            ChoreInstance.child_user_id == current_user.id,
            ChoreInstance.status == "approved",
            ChoreInstance.consumed_at.is_(None),
        )
        .all()
    )
    if len(instances) != len(body.chore_instance_ids):
        raise HTTPException(status_code=400, detail="部分任务记录无效、未批准或已使用")

    # Step 2: 计算金币总额
    coins_total = sum(inst.coins_reward for inst in instances)
    if coins_total <= 0:
        raise HTTPException(status_code=400, detail="金币不足，无法抽奖")

    # Step 3: 标记 consumed_at（事务内，尚未提交）
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    for inst in instances:
        inst.consumed_at = now

    # Step 4: 执行加权抽奖
    gifts = db.query(BlindBoxGift).filter_by(family_id=current_user.family_id, is_active=True).all()
    if not gifts:
        raise HTTPException(status_code=404, detail="礼物池为空，请让父母先添加礼物")

    from app.services.blind_box import pick_gift, should_upgrade_surprise
    context = {"is_parent_bday": False, "is_sibling_bday": False}
    is_surprise = should_upgrade_surprise(config, context)
    pool = [g for g in gifts if g.value_score >= 7] if is_surprise else gifts
    chosen = pick_gift(pool if pool else gifts, config)

    # Step 5: 写入 BlindBoxDraw 记录
    draw = BlindBoxDraw(
        family_id=current_user.family_id,
        child_user_id=current_user.id,
        coins_spent=coins_total,
        gift_id=chosen.id,
        is_surprise=is_surprise,
        is_bonus=False,
        status="pending_fulfillment",
    )
    db.add(draw)

    # Step 6: 原子提交
    db.commit()
    db.refresh(draw)

    return BlindBoxDrawResponse(
        **{c: getattr(draw, c) for c in [
            "id", "family_id", "child_user_id", "coins_spent",
            "gift_id", "is_surprise", "is_bonus", "status", "draw_at", "fulfilled_at"
        ]},
        gift_name=chosen.name,
        gift_emoji=chosen.emoji,
    )
```

- [ ] **Step 6: 运行测试验证通过**

```bash
uv run pytest tests/test_blind_box.py::test_draw_requires_chore_instance_ids -v
```

预期：PASS

- [ ] **Step 7: 运行全量测试**

```bash
uv run pytest tests/ -v
```

预期：全部 PASS

- [ ] **Step 8: 提交**

```bash
git add backend/app/routers/child_blind_box.py backend/app/schemas/blind_box.py backend/app/models/chore.py backend/tests/test_blind_box.py
git commit -m "feat(blind-box): atomic 6-step draw transaction with ChoreInstance validation"
```

---

## 补充实现顺序

| Task | 内容 | 依赖 |
|------|------|------|
| 10 | BonusDraw 模型 | Task 1 |
| 11 | BonusDraw API + 心愿触发 | Task 10, Task 7 |
| 12 | 从心愿转入礼物池 | Task 7 |
| 13 | 重复检查警告 | Task 7 |
| 14 | Draw 事务原子性（6步骤） | Task 8 |
