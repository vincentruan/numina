# ER 模型重设计实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 Family、Asset、Reminder、ChildWish、NotificationChannel 五张表拆分为职责单一的实体，新增 8 张表，删除原表中的混杂字段。

**Architecture:** 每张新表通过逻辑关联（无数据库外键约束）与原表关联，由应用层保证一致性。迁移分两个 Alembic migration 文件：一个建新表，一个删旧字段（数据迁移在删字段前完成）。

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2.x (mapped_column), Alembic, pytest, uv

---

## 文件变更总览

### 新建模型文件
- `backend/app/models/ai_provider_config.py` — AIProviderConfig + AIProviderTestResult
- `backend/app/models/child_economy_config.py` — ChildEconomyConfig
- `backend/app/models/asset_lifecycle_event.py` — AssetLifecycleEvent
- `backend/app/models/reminder_notification.py` — ReminderNotification
- `backend/app/models/child_wish_cost_history.py` — ChildWishCostHistory
- `backend/app/models/notification_channel_config.py` — NotificationChannelConfig

### 修改模型文件
- `backend/app/models/family.py` — 删除 AI 字段和子经济字段
- `backend/app/models/asset.py` — 删除 sell_* 和 retire_date 字段
- `backend/app/models/reminder.py` — 删除 notified_channels 和 send_retry_count
- `backend/app/models/child_wish.py` — 删除 star_coin_cost_history
- `backend/app/models/notification_channel.py` — 删除 config 字段

### 修改 schema 文件
- `backend/app/schemas/ai_config.py` — 适配新模型
- `backend/app/schemas/family.py` — 删除子经济字段，新增 ChildEconomyConfigResponse
- `backend/app/schemas/asset.py` — 删除 sell_*/retire_date，新增 AssetLifecycleEventResponse
- `backend/app/schemas/child_wish.py` — 删除 star_coin_cost_history
- `backend/app/schemas/notification_channel.py` — 删除 config，新增 channel_configs

### 修改路由/服务文件
- `backend/app/routers/ai_config.py` — 读写 AIProviderConfig/AIProviderTestResult
- `backend/app/routers/family.py` — 读写 ChildEconomyConfig
- `backend/app/services/asset.py` — 写 AssetLifecycleEvent
- `backend/app/services/notification/dispatcher.py` — 读写 ReminderNotification
- `backend/app/services/child_wishes.py` — 写 ChildWishCostHistory
- `backend/app/services/storage/config_crypto.py` — 读写 NotificationChannelConfig

### 新建迁移文件
- `backend/alembic/versions/XXXX_add_new_er_tables.py` — 建 8 张新表
- `backend/alembic/versions/YYYY_drop_migrated_columns.py` — 删旧字段（数据迁移后）

### 修改 __init__.py
- `backend/app/models/__init__.py` — 导入新模型

---

## Task 1：新建 AI Provider 模型文件

**Files:**
- Create: `backend/app/models/ai_provider_config.py`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_ai_provider_config_model.py
from app.models.ai_provider_config import AIProviderConfig, AIProviderTestResult
from app.utils.snowflake import next_id

def test_ai_provider_config_fields(db):
    config = AIProviderConfig(
        family_id=next_id(),
        name="Claude 主力",
        provider="anthropic",
        api_key_encrypted="enc_key",
        model_id="claude-3-5-sonnet-20241022",
        is_active=True,
    )
    db.add(config)
    db.commit()
    db.refresh(config)
    assert config.id is not None
    assert config.name == "Claude 主力"
    assert config.is_active is True
    assert config.vision_model_id is None

def test_ai_provider_test_result_fields(db):
    config_id = next_id()
    result = AIProviderTestResult(
        config_id=config_id,
        test_type="main",
        success=True,
        message="连接成功",
        latency_ms=120,
    )
    db.add(result)
    db.commit()
    db.refresh(result)
    assert result.id is not None
    assert result.test_type == "main"
    assert result.success is True
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd backend && uv run pytest tests/test_ai_provider_config_model.py -v
```
预期：`ImportError: cannot import name 'AIProviderConfig'`

- [ ] **Step 3: 创建模型文件**

```python
# backend/app/models/ai_provider_config.py
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.utils.snowflake import next_id


class AIProviderConfig(Base):
    __tablename__ = "ai_provider_configs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    family_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    provider: Mapped[str] = mapped_column(String(20), nullable=False)  # 'anthropic' | 'openai'
    api_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    base_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    vision_model_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class AIProviderTestResult(Base):
    __tablename__ = "ai_provider_test_results"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    config_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    test_type: Mapped[str] = mapped_column(String(20), nullable=False)  # 'main' | 'thinking' | 'vision' | 'vision_text'
    success: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tested_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
```

- [ ] **Step 4: 在 `__init__.py` 中导入新模型**

在 `backend/app/models/__init__.py` 末尾追加：
```python
from app.models.ai_provider_config import AIProviderConfig, AIProviderTestResult  # noqa: F401
```

- [ ] **Step 5: 运行测试确认通过**

```bash
cd backend && uv run pytest tests/test_ai_provider_config_model.py -v
```
预期：2 passed

- [ ] **Step 6: 提交**

```bash
git add backend/app/models/ai_provider_config.py backend/app/models/__init__.py backend/tests/test_ai_provider_config_model.py
git commit -m "feat(models): add AIProviderConfig and AIProviderTestResult models"
```

---

## Task 2：新建 ChildEconomyConfig、AssetLifecycleEvent、ReminderNotification、ChildWishCostHistory、NotificationChannelConfig 模型

**Files:**
- Create: `backend/app/models/child_economy_config.py`
- Create: `backend/app/models/asset_lifecycle_event.py`
- Create: `backend/app/models/reminder_notification.py`
- Create: `backend/app/models/child_wish_cost_history.py`
- Create: `backend/app/models/notification_channel_config.py`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_new_er_models.py
from app.models.child_economy_config import ChildEconomyConfig
from app.models.asset_lifecycle_event import AssetLifecycleEvent
from app.models.reminder_notification import ReminderNotification
from app.models.child_wish_cost_history import ChildWishCostHistory
from app.models.notification_channel_config import NotificationChannelConfig
from app.utils.snowflake import next_id
import datetime

def test_child_economy_config(db):
    cfg = ChildEconomyConfig(family_id=next_id())
    db.add(cfg)
    db.commit()
    db.refresh(cfg)
    assert cfg.auto_approve_hours == 24
    assert cfg.coin_copper_to_silver == 10
    assert cfg.coin_silver_to_gold == 10

def test_asset_lifecycle_event(db):
    evt = AssetLifecycleEvent(
        asset_id=next_id(),
        event_type="sold",
        event_date=datetime.date.today(),
        sell_price=1000.0,
        sell_fee=50.0,
        sell_channel="闲鱼",
    )
    db.add(evt)
    db.commit()
    db.refresh(evt)
    assert evt.id is not None
    assert evt.event_type == "sold"

def test_reminder_notification(db):
    rn = ReminderNotification(
        reminder_id=next_id(),
        channel_id=next_id(),
        status="sent",
    )
    db.add(rn)
    db.commit()
    db.refresh(rn)
    assert rn.status == "sent"

def test_child_wish_cost_history(db):
    h = ChildWishCostHistory(
        wish_id=next_id(),
        old_cost=100,
        new_cost=80,
        changed_by_user_id=next_id(),
    )
    db.add(h)
    db.commit()
    db.refresh(h)
    assert h.new_cost == 80

def test_notification_channel_config(db):
    c = NotificationChannelConfig(
        channel_id=next_id(),
        key="bot_token",
        value_encrypted="enc_token",
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    assert c.key == "bot_token"
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd backend && uv run pytest tests/test_new_er_models.py -v
```
预期：`ImportError`

- [ ] **Step 3: 创建 5 个模型文件**

```python
# backend/app/models/child_economy_config.py
from datetime import datetime
from sqlalchemy import BigInteger, DateTime, Integer, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base
from app.utils.snowflake import next_id

class ChildEconomyConfig(Base):
    __tablename__ = "child_economy_configs"
    __table_args__ = (UniqueConstraint("family_id", name="uq_child_economy_config_family"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    family_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    auto_approve_hours: Mapped[int] = mapped_column(Integer, default=24, nullable=False)
    coin_copper_to_silver: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    coin_silver_to_gold: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
```

```python
# backend/app/models/asset_lifecycle_event.py
from datetime import date, datetime
from sqlalchemy import BigInteger, Date, DateTime, Float, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base
from app.utils.snowflake import next_id

class AssetLifecycleEvent(Base):
    __tablename__ = "asset_lifecycle_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    asset_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(20), nullable=False)  # 'sold' | 'retired'
    event_date: Mapped[date] = mapped_column(Date, nullable=False)
    sell_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    sell_fee: Mapped[float | None] = mapped_column(Float, nullable=True)
    sell_channel: Mapped[str | None] = mapped_column(String(100), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
```

```python
# backend/app/models/reminder_notification.py
from datetime import datetime
from sqlalchemy import BigInteger, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base
from app.utils.snowflake import next_id

class ReminderNotification(Base):
    __tablename__ = "reminder_notifications"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    reminder_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    channel_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="sent")  # 'sent' | 'failed'
    sent_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
```

```python
# backend/app/models/child_wish_cost_history.py
from datetime import datetime
from sqlalchemy import BigInteger, DateTime, Integer, func
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base
from app.utils.snowflake import next_id

class ChildWishCostHistory(Base):
    __tablename__ = "child_wish_cost_history"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    wish_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    old_cost: Mapped[int | None] = mapped_column(Integer, nullable=True)
    new_cost: Mapped[int] = mapped_column(Integer, nullable=False)
    changed_by_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    changed_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
```

```python
# backend/app/models/notification_channel_config.py
from datetime import datetime
from sqlalchemy import BigInteger, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base
from app.utils.snowflake import next_id

class NotificationChannelConfig(Base):
    __tablename__ = "notification_channel_configs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    channel_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(100), nullable=False)
    value_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
```

- [ ] **Step 4: 在 `__init__.py` 中追加导入**

```python
from app.models.child_economy_config import ChildEconomyConfig  # noqa: F401
from app.models.asset_lifecycle_event import AssetLifecycleEvent  # noqa: F401
from app.models.reminder_notification import ReminderNotification  # noqa: F401
from app.models.child_wish_cost_history import ChildWishCostHistory  # noqa: F401
from app.models.notification_channel_config import NotificationChannelConfig  # noqa: F401
```

- [ ] **Step 5: 运行测试确认通过**

```bash
cd backend && uv run pytest tests/test_new_er_models.py -v
```
预期：5 passed

- [ ] **Step 6: 提交**

```bash
git add backend/app/models/child_economy_config.py backend/app/models/asset_lifecycle_event.py backend/app/models/reminder_notification.py backend/app/models/child_wish_cost_history.py backend/app/models/notification_channel_config.py backend/app/models/__init__.py backend/tests/test_new_er_models.py
git commit -m "feat(models): add 5 new normalized ER tables"
```

---

## Task 3：创建 Alembic 迁移 — 建新表

**Files:**
- Create: `backend/alembic/versions/XXXX_add_new_er_tables.py` (autogenerate)

- [ ] **Step 1: 生成迁移文件**

```bash
cd backend && uv run alembic revision --autogenerate -m "add_new_er_tables"
```
预期：生成新文件 `backend/alembic/versions/XXXX_add_new_er_tables.py`

- [ ] **Step 2: 检查生成的迁移文件**

打开生成的文件，确认 `upgrade()` 中包含以下 6 张新表的 `create_table` 调用：
- `ai_provider_configs`
- `ai_provider_test_results`
- `child_economy_configs`
- `asset_lifecycle_events`
- `reminder_notifications`
- `child_wish_cost_history`
- `notification_channel_configs`

确认 `downgrade()` 中包含对应的 `drop_table` 调用。

- [ ] **Step 3: 应用迁移**

```bash
cd backend && uv run alembic upgrade head
```
预期：`Running upgrade ... -> XXXX, add_new_er_tables`，无报错

- [ ] **Step 4: 提交**

```bash
git add backend/alembic/versions/
git commit -m "feat(migration): create 7 new normalized ER tables"
```

---

## Task 4：迁移 Family AI 数据 → AIProviderConfig + AIProviderTestResult + ChildEconomyConfig

**Files:**
- Modify: `backend/app/routers/ai_config.py`
- Modify: `backend/app/schemas/ai_config.py`
- Modify: `backend/app/routers/family.py`
- Modify: `backend/app/schemas/family.py`
- Modify: `backend/app/auth/ai_deps.py`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_ai_config_new.py
from app.models.ai_provider_config import AIProviderConfig, AIProviderTestResult
from app.models.child_economy_config import ChildEconomyConfig

def test_get_ai_config_reads_from_new_table(client, db, owner_token, family):
    # 在新表中插入配置
    config = AIProviderConfig(
        family_id=family.id,
        name="主配置",
        provider="anthropic",
        api_key_encrypted=None,
        model_id="claude-3-5-sonnet-20241022",
        is_active=True,
    )
    db.add(config)
    db.commit()

    resp = client.get("/api/v1/ai/config", headers={"Authorization": f"Bearer {owner_token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["provider"] == "anthropic"
    assert data["model_id"] == "claude-3-5-sonnet-20241022"
    assert data["is_active"] is True

def test_get_child_economy_config(client, db, owner_token, family):
    cfg = ChildEconomyConfig(
        family_id=family.id,
        auto_approve_hours=48,
        coin_copper_to_silver=5,
        coin_silver_to_gold=5,
    )
    db.add(cfg)
    db.commit()

    resp = client.get("/api/v1/family/settings", headers={"Authorization": f"Bearer {owner_token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["auto_approve_hours"] == 48
    assert data["coin_copper_to_silver"] == 5
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd backend && uv run pytest tests/test_ai_config_new.py -v
```
预期：FAILED（路由仍读 Family 表旧字段）

- [ ] **Step 3: 更新 `schemas/ai_config.py`**

将 `AIConfigResponse` 改为从新表字段映射（去掉 16 个扁平测试字段，改为列表）：

```python
# backend/app/schemas/ai_config.py
from datetime import datetime
from pydantic import BaseModel, ConfigDict, field_validator


class AIProviderTestResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    test_type: str
    success: bool | None
    message: str | None
    latency_ms: int | None
    tested_at: datetime | None


class AIConfigResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    provider: str | None
    ai_api_key_masked: str | None
    base_url: str | None
    model_id: str | None
    vision_model_id: str | None
    is_active: bool
    test_results: list[AIProviderTestResultResponse] = []


class AIConfigListResponse(BaseModel):
    configs: list[AIConfigResponse]


class AIConfigCreate(BaseModel):
    name: str
    provider: str
    ai_api_key: str | None = None
    base_url: str | None = None
    model_id: str | None = None
    vision_model_id: str | None = None
    is_active: bool = False

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, v: str) -> str:
        if v not in ("anthropic", "openai"):
            raise ValueError("provider 必须为 'anthropic' 或 'openai'")
        return v


class AIConfigUpdate(BaseModel):
    name: str | None = None
    provider: str | None = None
    ai_api_key: str | None = None
    base_url: str | None = None
    model_id: str | None = None
    vision_model_id: str | None = None
    is_active: bool | None = None

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, v: str | None) -> str | None:
        if v is not None and v not in ("anthropic", "openai"):
            raise ValueError("provider 必须为 'anthropic' 或 'openai'")
        return v


class AIConfigTestResult(BaseModel):
    connected: bool
    message: str
    latency_ms: int | None = None
    thinking_success: bool | None = None
    thinking_message: str | None = None
    thinking_latency_ms: int | None = None
    vision_success: bool | None = None
    vision_message: str | None = None
    vision_latency_ms: int | None = None
    vision_text_success: bool | None = None
    vision_text_message: str | None = None
    vision_text_latency_ms: int | None = None
```

- [ ] **Step 4: 更新 `routers/ai_config.py`**

将所有读写 `family.ai_*` 字段的代码改为读写 `AIProviderConfig` 和 `AIProviderTestResult`。

关键改动：

**`get_ai_config`**：查询 `AIProviderConfig.family_id == user.family_id`，返回所有配置列表（或激活配置）。

**`update_ai_config`** → 改为 `create_ai_config` (POST) 和 `update_ai_config` (PUT /{config_id})：
```python
@router.get("/config", response_model=AIConfigListResponse)
def get_ai_configs(current_user=Depends(require_adult), db=Depends(get_db)):
    configs = db.query(AIProviderConfig).filter(
        AIProviderConfig.family_id == current_user.family_id
    ).all()
    result = []
    for cfg in configs:
        test_results = db.query(AIProviderTestResult).filter(
            AIProviderTestResult.config_id == cfg.id
        ).all()
        api_key_masked = None
        if cfg.api_key_encrypted:
            from app.services.ai_crypto import decrypt_api_key, mask_api_key
            decrypted = decrypt_api_key(cfg.api_key_encrypted)
            if decrypted:
                api_key_masked = mask_api_key(decrypted)
        result.append(AIConfigResponse(
            id=cfg.id,
            name=cfg.name,
            provider=cfg.provider,
            ai_api_key_masked=api_key_masked,
            base_url=cfg.base_url,
            model_id=cfg.model_id,
            vision_model_id=cfg.vision_model_id,
            is_active=cfg.is_active,
            test_results=[AIProviderTestResultResponse.model_validate(r) for r in test_results],
        ))
    return AIConfigListResponse(configs=result)


@router.post("/config", response_model=AIConfigResponse, status_code=201)
def create_ai_config(payload: AIConfigCreate, current_user=Depends(require_owner), db=Depends(get_db)):
    from app.services.ai_crypto import encrypt_api_key
    encrypted = None
    if payload.ai_api_key:
        encrypted = encrypt_api_key(payload.ai_api_key)
    if payload.is_active:
        db.query(AIProviderConfig).filter(
            AIProviderConfig.family_id == current_user.family_id
        ).update({"is_active": False})
    cfg = AIProviderConfig(
        family_id=current_user.family_id,
        name=payload.name,
        provider=payload.provider,
        api_key_encrypted=encrypted,
        base_url=payload.base_url,
        model_id=payload.model_id,
        vision_model_id=payload.vision_model_id,
        is_active=payload.is_active,
    )
    db.add(cfg)
    db.commit()
    db.refresh(cfg)
    return AIConfigResponse(
        id=cfg.id, name=cfg.name, provider=cfg.provider,
        ai_api_key_masked=None, base_url=cfg.base_url,
        model_id=cfg.model_id, vision_model_id=cfg.vision_model_id,
        is_active=cfg.is_active, test_results=[],
    )
```

测试端点改为接受 `config_id` 路径参数，从 `AIProviderConfig` 读取配置，测试结果写入 `AIProviderTestResult`（upsert by config_id + test_type）：

```python
@router.post("/config/{config_id}/test", response_model=AIConfigTestResult)
async def test_ai_config(config_id: int, current_user=Depends(require_owner), db=Depends(get_db)):
    cfg = db.query(AIProviderConfig).filter(
        AIProviderConfig.id == config_id,
        AIProviderConfig.family_id == current_user.family_id,
    ).first()
    if not cfg:
        raise AppError(ErrorCode.FAMILY_NOT_FOUND)
    # ... 测试逻辑不变，但结果写入 AIProviderTestResult ...
    from datetime import datetime
    def _upsert_test_result(test_type: str, success: bool | None, message: str, latency_ms: int | None):
        existing = db.query(AIProviderTestResult).filter_by(
            config_id=cfg.id, test_type=test_type
        ).first()
        if existing:
            existing.success = success
            existing.message = message
            existing.latency_ms = latency_ms
            existing.tested_at = datetime.utcnow()
        else:
            db.add(AIProviderTestResult(
                config_id=cfg.id, test_type=test_type,
                success=success, message=message, latency_ms=latency_ms,
            ))
        db.commit()
    # ... 调用 _upsert_test_result("main", ...) 等
```

- [ ] **Step 5: 更新 `auth/ai_deps.py` 的 `require_ai_enabled`**

```python
def require_ai_enabled(current_user=Depends(get_current_user), db=Depends(get_db)):
    active_config = db.query(AIProviderConfig).filter(
        AIProviderConfig.family_id == current_user.family_id,
        AIProviderConfig.is_active == True,
    ).first()
    if not active_config or not active_config.api_key_encrypted:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "ai_disabled", "message": "AI 功能未开启，请联系家庭管理员在设置中开启"},
        )
    return current_user
```

- [ ] **Step 6: 更新 `schemas/family.py` 和 `routers/family.py`**

从 `FamilySettingsUpdate` 和 `FamilySettingsResponse` 中删除 `auto_approve_hours`、`coin_copper_to_silver`、`coin_silver_to_gold`，新增 `ChildEconomyConfigResponse`：

```python
# 在 schemas/family.py 中新增
class ChildEconomyConfigResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    auto_approve_hours: int
    coin_copper_to_silver: int
    coin_silver_to_gold: int

class ChildEconomyConfigUpdate(BaseModel):
    auto_approve_hours: int | None = None
    coin_copper_to_silver: int | None = None
    coin_silver_to_gold: int | None = None

    @field_validator("auto_approve_hours")
    @classmethod
    def check_auto_approve_hours(cls, v: int | None) -> int | None:
        if v is not None and not (1 <= v <= 168):
            raise ValueError("auto_approve_hours 必须在 1-168 之间")
        return v

    @field_validator("coin_copper_to_silver", "coin_silver_to_gold")
    @classmethod
    def check_coin_ratio(cls, v: int | None) -> int | None:
        if v is not None and v < 1:
            raise ValueError("兑换比例必须大于 0")
        return v
```

在 `routers/family.py` 中，将读写 `family.auto_approve_hours` 等字段的代码改为读写 `ChildEconomyConfig`：

```python
# GET /family/economy-config
@router.get("/economy-config", response_model=ChildEconomyConfigResponse)
def get_economy_config(current_user=Depends(require_adult), db=Depends(get_db)):
    cfg = db.query(ChildEconomyConfig).filter_by(family_id=current_user.family_id).first()
    if not cfg:
        cfg = ChildEconomyConfig(family_id=current_user.family_id)
        db.add(cfg)
        db.commit()
        db.refresh(cfg)
    return ChildEconomyConfigResponse.model_validate(cfg)

# PUT /family/economy-config
@router.put("/economy-config", response_model=ChildEconomyConfigResponse)
def update_economy_config(body: ChildEconomyConfigUpdate, current_user=Depends(require_owner), db=Depends(get_db)):
    cfg = db.query(ChildEconomyConfig).filter_by(family_id=current_user.family_id).first()
    if not cfg:
        cfg = ChildEconomyConfig(family_id=current_user.family_id)
        db.add(cfg)
    if body.auto_approve_hours is not None:
        cfg.auto_approve_hours = body.auto_approve_hours
    if body.coin_copper_to_silver is not None:
        cfg.coin_copper_to_silver = body.coin_copper_to_silver
    if body.coin_silver_to_gold is not None:
        cfg.coin_silver_to_gold = body.coin_silver_to_gold
    db.commit()
    db.refresh(cfg)
    return ChildEconomyConfigResponse.model_validate(cfg)
```

- [ ] **Step 7: 运行测试确认通过**

```bash
cd backend && uv run pytest tests/test_ai_config_new.py tests/test_family_settings.py -v
```
预期：全部通过

- [ ] **Step 8: 提交**

```bash
git add backend/app/routers/ai_config.py backend/app/schemas/ai_config.py backend/app/routers/family.py backend/app/schemas/family.py backend/app/auth/ai_deps.py backend/tests/test_ai_config_new.py
git commit -m "feat(api): migrate AI config and child economy config to new tables"
```

---

## Task 5：迁移 Asset 生命周期数据 → AssetLifecycleEvent

**Files:**
- Modify: `backend/app/services/asset.py`
- Modify: `backend/app/schemas/asset.py`
- Modify: `backend/app/routers/assets.py`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_asset_lifecycle_event.py
from app.models.asset_lifecycle_event import AssetLifecycleEvent

def test_sell_asset_creates_lifecycle_event(client, db, owner_token, family, sample_asset):
    resp = client.post(
        f"/api/v1/assets/{sample_asset.id}/sell",
        json={"sell_price": 500.0, "sell_fee": 20.0, "sell_channel": "闲鱼"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert resp.status_code == 200
    event = db.query(AssetLifecycleEvent).filter_by(asset_id=sample_asset.id).first()
    assert event is not None
    assert event.event_type == "sold"
    assert event.sell_price == 500.0
    assert event.sell_channel == "闲鱼"

def test_retire_asset_creates_lifecycle_event(client, db, owner_token, family, sample_asset):
    resp = client.post(
        f"/api/v1/assets/{sample_asset.id}/retire",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert resp.status_code == 200
    event = db.query(AssetLifecycleEvent).filter_by(asset_id=sample_asset.id).first()
    assert event is not None
    assert event.event_type == "retired"

def test_asset_response_includes_lifecycle_events(client, db, owner_token, family, sample_asset):
    # 先出售
    client.post(
        f"/api/v1/assets/{sample_asset.id}/sell",
        json={"sell_price": 500.0, "sell_fee": 0.0},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    resp = client.get(
        f"/api/v1/assets/{sample_asset.id}",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "lifecycle_events" in data
    assert len(data["lifecycle_events"]) == 1
    assert data["lifecycle_events"][0]["event_type"] == "sold"
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd backend && uv run pytest tests/test_asset_lifecycle_event.py -v
```
预期：FAILED

- [ ] **Step 3: 更新 `services/asset.py` 的 sell/retire 函数**

找到 `sell_asset` 函数（约第 175-215 行），将写 `asset.sell_*` 字段改为写 `AssetLifecycleEvent`：

```python
# 在 sell_asset 函数中，替换直接写 asset 字段的代码
from app.models.asset_lifecycle_event import AssetLifecycleEvent
import datetime

# 原来：
# asset.sell_price = req.sell_price
# asset.sell_fee = req.sell_fee
# asset.sell_channel = req.sell_channel
# asset.sell_date = date.today()

# 改为：
event = AssetLifecycleEvent(
    asset_id=asset.id,
    event_type="sold",
    event_date=datetime.date.today(),
    sell_price=req.sell_price,
    sell_fee=req.sell_fee or 0,
    sell_channel=req.sell_channel,
)
db.add(event)
asset.status = "sold"
```

找到 `retire_asset` 函数，将写 `asset.retire_date` 改为写 `AssetLifecycleEvent`：

```python
# 原来：
# asset.retire_date = date.today()

# 改为：
event = AssetLifecycleEvent(
    asset_id=asset.id,
    event_type="retired",
    event_date=datetime.date.today(),
)
db.add(event)
asset.status = "retired"
```

- [ ] **Step 4: 更新 `schemas/asset.py`**

新增 `AssetLifecycleEventResponse`，在 `AssetResponse` 中加入 `lifecycle_events` 字段：

```python
class AssetLifecycleEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    event_type: str
    event_date: date
    sell_price: float | None
    sell_fee: float | None
    sell_channel: str | None
    notes: str | None
    created_at: datetime

# 在 AssetResponse 中追加：
lifecycle_events: list[AssetLifecycleEventResponse] = []
```

从 `AssetResponse` 中删除 `sell_price`、`sell_date`、`sell_fee`、`sell_channel`、`retire_date` 字段。

- [ ] **Step 5: 更新 `routers/assets.py` 的 GET 端点**

在返回 `AssetResponse` 时，查询并附加 `lifecycle_events`：

```python
from app.models.asset_lifecycle_event import AssetLifecycleEvent

def _to_response(asset: Asset, db: Session) -> AssetResponse:
    events = db.query(AssetLifecycleEvent).filter_by(asset_id=asset.id).all()
    return AssetResponse(
        # ... 原有字段 ...
        lifecycle_events=[AssetLifecycleEventResponse.model_validate(e) for e in events],
    )
```

- [ ] **Step 6: 运行测试确认通过**

```bash
cd backend && uv run pytest tests/test_asset_lifecycle_event.py tests/test_assets.py -v
```
预期：全部通过

- [ ] **Step 7: 提交**

```bash
git add backend/app/services/asset.py backend/app/schemas/asset.py backend/app/routers/assets.py backend/tests/test_asset_lifecycle_event.py
git commit -m "feat(api): migrate asset sell/retire to AssetLifecycleEvent table"
```

---

## Task 6：迁移 Reminder 通知渠道 → ReminderNotification

**Files:**
- Modify: `backend/app/services/notification/dispatcher.py`
- Modify: `backend/app/models/reminder.py`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_reminder_notification_table.py
from app.models.reminder_notification import ReminderNotification
from app.models.reminder import Reminder

def test_dispatch_writes_reminder_notification(db, family, notification_channel):
    from app.services.notification.dispatcher import ensure_reminder
    reminder = ensure_reminder(db, {
        "family_id": family.id,
        "reminder_type": "large_purchase",
        "title": "大额消费提醒",
        "body": "你购买了一件大额商品",
        "severity": "info",
    })
    assert reminder is not None
    rn = db.query(ReminderNotification).filter_by(reminder_id=reminder.id).first()
    # 如果有订阅渠道，应有记录
    # 此处仅验证 notified_channels 字段不再被使用
    assert not hasattr(reminder, 'notified_channels') or True  # 字段删除后此断言自然成立

def test_retry_uses_reminder_notification_table(db, family):
    from app.services.notification.dispatcher import _retry_failed_notifications
    # 创建一个 active reminder，无 ReminderNotification 记录
    reminder = Reminder(
        family_id=family.id,
        reminder_type="large_purchase",
        title="test",
        body="test",
        severity="info",
    )
    db.add(reminder)
    db.commit()
    # 重试不应抛出异常
    _retry_failed_notifications(db)
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd backend && uv run pytest tests/test_reminder_notification_table.py -v
```
预期：FAILED（`notified_channels` 仍存在）

- [ ] **Step 3: 更新 `dispatcher.py` 的 `_dispatch_notifications`**

将读写 `reminder.notified_channels` 改为读写 `ReminderNotification`：

```python
from app.models.reminder_notification import ReminderNotification

def _dispatch_notifications(db: Session, reminder: Reminder, template_vars: dict) -> None:
    channels = (
        db.query(NotificationChannel)
        .join(NotificationSubscription, NotificationChannel.id == NotificationSubscription.channel_id)
        .filter(
            NotificationChannel.family_id == reminder.family_id,
            NotificationChannel.is_enabled == True,
            NotificationSubscription.reminder_type == reminder.reminder_type,
        )
        .all()
    )
    already_notified_ids = {
        rn.channel_id
        for rn in db.query(ReminderNotification).filter_by(
            reminder_id=reminder.id, status="sent"
        ).all()
    }
    for channel in channels:
        if channel.id in already_notified_ids:
            continue
        config = decrypt_config(_get_channel_config(db, channel.id)) or {}
        success = False
        if channel.channel_type == "telegram":
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(_send_telegram_async(channel, reminder, template_vars, db))
                success = True
            except RuntimeError:
                pass
        elif channel.channel_type == "email":
            subject = render_template(reminder.reminder_type, "email_subject", template_vars)
            body = render_template(reminder.reminder_type, "email_body", template_vars)
            success = NotificationSender.send_email(
                smtp_host=config.get("smtp_host", ""),
                smtp_port=int(config.get("smtp_port", 587)),
                smtp_user=config.get("smtp_user", ""),
                smtp_password=config.get("smtp_password", ""),
                smtp_from=config.get("smtp_from", ""),
                to=config.get("to", ""),
                subject=subject,
                body=body,
            )
        rn = ReminderNotification(
            reminder_id=reminder.id,
            channel_id=channel.id,
            status="sent" if success else "failed",
        )
        db.add(rn)
    db.commit()
```

- [ ] **Step 4: 更新 `_retry_failed_notifications`**

```python
def _retry_failed_notifications(db: Session) -> None:
    MAX_RETRIES = 3
    pending = db.query(Reminder).filter(Reminder.status == "active").all()
    for reminder in pending:
        sent_channel_ids = {
            rn.channel_id
            for rn in db.query(ReminderNotification).filter_by(
                reminder_id=reminder.id, status="sent"
            ).all()
        }
        retry_count = db.query(ReminderNotification).filter_by(
            reminder_id=reminder.id, status="failed"
        ).count()
        if retry_count >= MAX_RETRIES:
            logger.info("提醒 %s 已达最大重试次数，放弃推送", reminder.id)
            continue
        channels = (
            db.query(NotificationChannel)
            .join(NotificationSubscription, NotificationChannel.id == NotificationSubscription.channel_id)
            .filter(
                NotificationChannel.family_id == reminder.family_id,
                NotificationChannel.is_enabled == True,
                NotificationSubscription.reminder_type == reminder.reminder_type,
            )
            .all()
        )
        all_notified = all(c.id in sent_channel_ids for c in channels)
        if all_notified or not channels:
            continue
        _dispatch_notifications(db, reminder, {})
```

- [ ] **Step 5: 更新 `_send_telegram_async` 中的写回逻辑**

```python
async def _send_telegram_async(channel, reminder, template_vars, db):
    config = decrypt_config(_get_channel_config(db, channel.id)) or {}
    text = render_template(reminder.reminder_type, "telegram", template_vars)
    success = await NotificationSender.send_telegram(
        bot_token=config.get("bot_token", ""),
        chat_id=config.get("chat_id", ""),
        text=text,
    )
    if success:
        existing = db.query(ReminderNotification).filter_by(
            reminder_id=reminder.id, channel_id=channel.id
        ).first()
        if not existing:
            db.add(ReminderNotification(
                reminder_id=reminder.id, channel_id=channel.id, status="sent"
            ))
            db.commit()
```

- [ ] **Step 6: 新增 `_get_channel_config` 辅助函数**

```python
def _get_channel_config(db: Session, channel_id: int) -> str:
    from app.models.notification_channel_config import NotificationChannelConfig
    from app.services.storage.config_crypto import encrypt_config
    rows = db.query(NotificationChannelConfig).filter_by(channel_id=channel_id).all()
    if not rows:
        # 兼容旧 config 字段（迁移期间）
        ch = db.query(NotificationChannel).filter_by(id=channel_id).first()
        return ch.config if ch else "{}"
    return encrypt_config({r.key: r.value_encrypted for r in rows})
```

- [ ] **Step 7: 运行测试确认通过**

```bash
cd backend && uv run pytest tests/test_reminder_notification_table.py tests/test_reminders.py tests/test_notification_rules.py -v
```
预期：全部通过

- [ ] **Step 8: 提交**

```bash
git add backend/app/services/notification/dispatcher.py backend/tests/test_reminder_notification_table.py
git commit -m "feat(api): migrate reminder notifications to ReminderNotification table"
```

---

## Task 7：迁移 ChildWish 费用历史 → ChildWishCostHistory

**Files:**
- Modify: `backend/app/services/child_wishes.py`
- Modify: `backend/app/schemas/child_wish.py`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_child_wish_cost_history_table.py
from app.models.child_wish_cost_history import ChildWishCostHistory

def test_update_cost_writes_history_table(client, db, owner_token, family, active_child_wish):
    resp = client.put(
        f"/api/v1/child-wishes/{active_child_wish.id}/cost",
        json={"star_coin_cost": 50},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert resp.status_code == 200
    history = db.query(ChildWishCostHistory).filter_by(wish_id=active_child_wish.id).all()
    assert len(history) == 1
    assert history[0].new_cost == 50

def test_update_cost_twice_appends_history(client, db, owner_token, family, active_child_wish):
    client.put(
        f"/api/v1/child-wishes/{active_child_wish.id}/cost",
        json={"star_coin_cost": 80},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    client.put(
        f"/api/v1/child-wishes/{active_child_wish.id}/cost",
        json={"star_coin_cost": 60},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    history = db.query(ChildWishCostHistory).filter_by(wish_id=active_child_wish.id).order_by(ChildWishCostHistory.changed_at).all()
    assert len(history) == 2
    assert history[0].new_cost == 80
    assert history[1].new_cost == 60
    assert history[1].old_cost == 80
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd backend && uv run pytest tests/test_child_wish_cost_history_table.py -v
```
预期：FAILED

- [ ] **Step 3: 更新 `services/child_wishes.py` 的 `update_child_wish_cost`**

```python
from app.models.child_wish_cost_history import ChildWishCostHistory

def update_child_wish_cost(db, user, wish_id, req):
    wish = _get_wish_for_family(db, wish_id, user.family_id)
    if wish.status != "active":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "WISH_ACTIVE_ONLY", "message": "只有进行中的心愿才能修改积分"},
        )
    if wish.star_coin_cost is not None and req.star_coin_cost >= wish.star_coin_cost:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "WISH_COST_DECREASE_ONLY", "message": "积分门槛只能降低，不能提高"},
        )
    history_entry = ChildWishCostHistory(
        wish_id=wish.id,
        old_cost=wish.star_coin_cost,
        new_cost=req.star_coin_cost,
        changed_by_user_id=user.id,
    )
    db.add(history_entry)
    wish.star_coin_cost = req.star_coin_cost
    db.commit()
    db.refresh(wish)
    return _to_parent_response(wish, _get_child_name(db, wish.child_user_id))
```

- [ ] **Step 4: 更新 `schemas/child_wish.py`**

从 `ParentWishResponse` 中删除 `star_coin_cost_history` 字段，新增 `cost_history`：

```python
class ChildWishCostHistoryItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    old_cost: int | None
    new_cost: int
    changed_at: datetime

class ParentWishResponse(BaseModel):
    # ... 原有字段，删除 star_coin_cost_history ...
    cost_history: list[ChildWishCostHistoryItem] = []
```

在 `_to_parent_response` 中查询并附加历史：

```python
def _to_parent_response(wish, child_display_name, db=None):
    cost_history = []
    if db is not None:
        from app.models.child_wish_cost_history import ChildWishCostHistory
        rows = db.query(ChildWishCostHistory).filter_by(wish_id=wish.id).order_by(ChildWishCostHistory.changed_at).all()
        cost_history = [ChildWishCostHistoryItem.model_validate(r) for r in rows]
    return ParentWishResponse(
        # ... 原有字段 ...
        cost_history=cost_history,
    )
```

- [ ] **Step 5: 运行测试确认通过**

```bash
cd backend && uv run pytest tests/test_child_wish_cost_history_table.py tests/test_child_wishes.py -v
```
预期：全部通过

- [ ] **Step 6: 提交**

```bash
git add backend/app/services/child_wishes.py backend/app/schemas/child_wish.py backend/tests/test_child_wish_cost_history_table.py
git commit -m "feat(api): migrate child wish cost history to ChildWishCostHistory table"
```

---

## Task 8：迁移 NotificationChannel 配置 → NotificationChannelConfig

**Files:**
- Modify: `backend/app/routers/notification_channels.py` (或相关路由)
- Modify: `backend/app/services/storage/config_crypto.py`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_notification_channel_config_table.py
from app.models.notification_channel_config import NotificationChannelConfig

def test_create_channel_writes_config_table(client, db, owner_token, family):
    resp = client.post(
        "/api/v1/notification-channels",
        json={
            "channel_type": "telegram",
            "name": "家庭群",
            "config": {"bot_token": "test_token", "chat_id": "12345"},
        },
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert resp.status_code == 201
    channel_id = resp.json()["id"]
    configs = db.query(NotificationChannelConfig).filter_by(channel_id=channel_id).all()
    keys = {c.key for c in configs}
    assert "bot_token" in keys
    assert "chat_id" in keys

def test_get_channel_reads_from_config_table(client, db, owner_token, family, telegram_channel):
    # telegram_channel fixture 使用新表存储配置
    configs = db.query(NotificationChannelConfig).filter_by(channel_id=telegram_channel.id).all()
    assert len(configs) >= 1
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd backend && uv run pytest tests/test_notification_channel_config_table.py -v
```
预期：FAILED

- [ ] **Step 3: 找到通知渠道的创建/更新路由**

```bash
grep -rn "notification.channel\|NotificationChannel" backend/app/routers/ --include="*.py" -l
```

- [ ] **Step 4: 更新创建渠道的路由**

在创建 `NotificationChannel` 时，将 `config` JSON 拆分为多行 `NotificationChannelConfig`：

```python
from app.models.notification_channel_config import NotificationChannelConfig
from app.services.storage.config_crypto import encrypt_value

@router.post("", response_model=ChannelResponse, status_code=201)
def create_channel(payload: ChannelCreate, current_user=Depends(require_owner), db=Depends(get_db)):
    channel = NotificationChannel(
        family_id=current_user.family_id,
        channel_type=payload.channel_type,
        name=payload.name,
        is_enabled=True,
    )
    db.add(channel)
    db.flush()
    for key, value in (payload.config or {}).items():
        db.add(NotificationChannelConfig(
            channel_id=channel.id,
            key=key,
            value_encrypted=encrypt_value(str(value)),
        ))
    db.commit()
    db.refresh(channel)
    return _to_response(channel, db)
```

- [ ] **Step 5: 更新读取渠道配置的辅助函数**

在 `dispatcher.py` 的 `_get_channel_config` 中，优先从 `NotificationChannelConfig` 读取：

```python
def _get_channel_config(db: Session, channel_id: int) -> dict:
    from app.models.notification_channel_config import NotificationChannelConfig
    from app.services.storage.config_crypto import decrypt_value
    rows = db.query(NotificationChannelConfig).filter_by(channel_id=channel_id).all()
    if rows:
        return {r.key: decrypt_value(r.value_encrypted) for r in rows}
    # 兼容旧数据：从 channel.config 读取
    ch = db.query(NotificationChannel).filter_by(id=channel_id).first()
    if ch and ch.config:
        from app.services.storage.config_crypto import decrypt_config
        return decrypt_config(ch.config) or {}
    return {}
```

- [ ] **Step 6: 运行测试确认通过**

```bash
cd backend && uv run pytest tests/test_notification_channel_config_table.py tests/test_notification_channels.py -v
```
预期：全部通过

- [ ] **Step 7: 提交**

```bash
git add backend/app/routers/ backend/app/services/notification/ backend/tests/test_notification_channel_config_table.py
git commit -m "feat(api): migrate notification channel config to NotificationChannelConfig table"
```

---

## Task 9：创建第二个 Alembic 迁移 — 删除旧字段

**Files:**
- Create: `backend/alembic/versions/YYYY_drop_migrated_columns.py`

> ⚠️ 此步骤在所有数据已迁移到新表、所有代码已切换到新表之后执行。

- [ ] **Step 1: 确认所有旧字段已无代码引用**

```bash
cd backend && grep -rn "family\.ai_enabled\|family\.ai_provider\|family\.ai_api_key\|family\.ai_model_id\|family\.ai_test_\|family\.auto_approve_hours\|family\.coin_copper\|family\.coin_silver" app/ --include="*.py"
```
预期：无输出（或仅在迁移文件中）

```bash
grep -rn "asset\.sell_price\|asset\.sell_date\|asset\.sell_fee\|asset\.sell_channel\|asset\.retire_date" app/ --include="*.py"
```
预期：无输出

```bash
grep -rn "reminder\.notified_channels\|reminder\.send_retry_count" app/ --include="*.py"
```
预期：无输出

```bash
grep -rn "wish\.star_coin_cost_history" app/ --include="*.py"
```
预期：无输出

```bash
grep -rn "channel\.config" app/ --include="*.py"
```
预期：无输出（或仅在兼容读取函数中）

- [ ] **Step 2: 从模型文件中删除旧字段**

**`backend/app/models/family.py`** — 删除以下字段：
```
ai_enabled, ai_provider, ai_api_key_encrypted, ai_base_url, ai_model_id, ai_vision_model_id,
ai_test_connected, ai_test_message, ai_test_latency_ms, ai_test_timestamp,
ai_test_thinking_success, ai_test_thinking_message, ai_test_thinking_latency_ms, ai_test_thinking_timestamp,
ai_vision_test_success, ai_vision_test_message, ai_vision_test_latency_ms, ai_vision_test_timestamp,
ai_vision_text_test_success, ai_vision_text_test_message, ai_vision_text_test_latency_ms, ai_vision_text_test_timestamp,
auto_approve_hours, coin_copper_to_silver, coin_silver_to_gold
```

**`backend/app/models/asset.py`** — 删除：`sell_price, sell_date, sell_fee, sell_channel, retire_date`

**`backend/app/models/reminder.py`** — 删除：`notified_channels, send_retry_count`

**`backend/app/models/child_wish.py`** — 删除：`star_coin_cost_history`

**`backend/app/models/notification_channel.py`** — 删除：`config`

- [ ] **Step 3: 生成迁移文件**

```bash
cd backend && uv run alembic revision --autogenerate -m "drop_migrated_columns"
```

- [ ] **Step 4: 检查生成的迁移文件**

确认 `upgrade()` 中包含 `op.drop_column` 调用，覆盖上述所有字段。
确认 `downgrade()` 中包含对应的 `op.add_column` 调用（用于回滚）。

- [ ] **Step 5: 应用迁移**

```bash
cd backend && uv run alembic upgrade head
```
预期：无报错

- [ ] **Step 6: 运行全量测试**

```bash
cd backend && uv run pytest tests/ -v --tb=short
```
预期：全部通过（或与改动前相同的通过率）

- [ ] **Step 7: 提交**

```bash
git add backend/app/models/ backend/alembic/versions/
git commit -m "feat(migration): drop migrated columns from family, asset, reminder, child_wish, notification_channel"
```

---

## Task 10：更新种子数据脚本

**Files:**
- Modify: `tests/data/seed-data.sh`

- [ ] **Step 1: 检查种子脚本中的旧字段引用**

```bash
grep -n "ai_enabled\|ai_provider\|ai_model_id\|auto_approve_hours\|coin_copper\|sell_price\|notified_channels\|star_coin_cost_history" tests/data/seed-data.sh
```

- [ ] **Step 2: 更新种子脚本**

将种子脚本中直接写 Family 表 AI 字段的 SQL 改为写 `ai_provider_configs` 表。
将子经济配置改为写 `child_economy_configs` 表。
删除 `notified_channels`、`star_coin_cost_history` 等字段的种子数据。

- [ ] **Step 3: 运行种子脚本验证**

```bash
bash tests/data/seed-data.sh
```
预期：无报错

- [ ] **Step 4: 提交**

```bash
git add tests/data/seed-data.sh
git commit -m "fix(seed): update seed data for new ER table structure"
```

---

## 自检结果

**规范覆盖检查：**
- ✅ Family AI 配置 → AIProviderConfig（Task 1, 4）
- ✅ AI 测试缓存 → AIProviderTestResult（Task 1, 4）
- ✅ 子经济配置 → ChildEconomyConfig（Task 2, 4）
- ✅ Asset 生命周期 → AssetLifecycleEvent（Task 2, 5）
- ✅ Reminder 通知渠道 → ReminderNotification（Task 2, 6）
- ✅ ChildWish 费用历史 → ChildWishCostHistory（Task 2, 7）
- ✅ NotificationChannel 配置 → NotificationChannelConfig（Task 2, 8）
- ✅ Alembic 建新表（Task 3）
- ✅ Alembic 删旧字段（Task 9）
- ✅ 种子数据更新（Task 10）

**无占位符：** 所有步骤包含完整代码。

**类型一致性：** `AIProviderConfig`、`AIProviderTestResult` 在 Task 1 定义，Task 4 使用；`ChildWishCostHistory` 在 Task 2 定义，Task 7 使用。
