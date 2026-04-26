# Phase 4：智能提醒 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 Numina 添加智能提醒系统，支持四类规则（大额消费冷静期、资产配置失衡、保险/保修到期、理财产品到期）、多渠道推送（Telegram/邮件）、总览页提醒模块。

**Architecture:** 后端在 `backend/app/services/notification/` 新增规则引擎和发送器，APScheduler 每日 09:20 定时触发，资产写入时实时触发大额消费检测。前端在总览页新增折叠提醒模块，设置页新增渠道配置页。

**Tech Stack:** Python/FastAPI/SQLAlchemy/APScheduler/httpx/smtplib · Vue 3/TypeScript/Vant 4/Pinia

---

## 文件清单

### 后端新增
| 文件 | 职责 |
|------|------|
| `backend/app/models/notification_channel.py` | 发送渠道 ORM |
| `backend/app/models/notification_subscription.py` | 渠道事件订阅 ORM |
| `backend/app/models/notification_config.py` | 家庭级大额消费阈值配置 ORM |
| `backend/app/models/reminder.py` | 提醒记录 ORM |
| `backend/app/schemas/notification_channel.py` | 渠道读写 schema |
| `backend/app/schemas/notification_config.py` | 阈值配置 schema |
| `backend/app/schemas/reminder.py` | 提醒列表/详情 schema |
| `backend/app/services/notification/__init__.py` | 包入口 |
| `backend/app/services/notification/sender.py` | Telegram + SMTP 发送，加载模板渲染 |
| `backend/app/services/notification/rules.py` | 四类提醒规则引擎 |
| `backend/app/services/notification/dispatcher.py` | 触发入口（定时 + 实时） |
| `backend/app/services/notification/templates/large_purchase.json` | 大额消费通知模板 |
| `backend/app/services/notification/templates/allocation_drift.json` | 配置失衡通知模板 |
| `backend/app/services/notification/templates/expiring_soon.json` | 保修到期通知模板 |
| `backend/app/services/notification/templates/maturity.json` | 理财到期通知模板 |
| `backend/app/routers/notification_channels.py` | CRUD `/api/v1/notification-channels` |
| `backend/app/routers/notification_config.py` | GET/PUT `/api/v1/notification-config` |
| `backend/app/routers/reminders.py` | GET/PATCH `/api/v1/reminders` |
| `backend/alembic/versions/xxxx_phase4_smart_reminders.py` | 数据库迁移 |
| `backend/tests/test_reminders.py` | 提醒 API 测试 |
| `backend/tests/test_notification_channels.py` | 渠道配置 API 测试 |
| `backend/tests/test_notification_rules.py` | 规则引擎单元测试 |

### 后端修改
| 文件 | 变更 |
|------|------|
| `backend/app/models/asset.py` | 新增 `warranty_expiry_date` 字段 |
| `backend/app/schemas/asset.py` | `AssetCreate`/`AssetUpdate`/`AssetResponse` 新增 `warranty_expiry_date` |
| `backend/app/services/asset.py` | `create_asset`/`update_asset` 传递 `warranty_expiry_date`；写入后调用 dispatcher |
| `backend/app/main.py` | 注册三个新 router；导入新 model；注册 APScheduler 任务 |
| `backend/app/scheduler.py` | 新增 `setup_reminder_schedule()` |
| `backend/tests/conftest.py` | 导入新 model 确保建表 |

### 前端新增
| 文件 | 职责 |
|------|------|
| `frontend/src/api/reminders.ts` | 提醒 API 调用 |
| `frontend/src/api/notificationChannels.ts` | 渠道配置 API 调用 |
| `frontend/src/stores/reminders.ts` | Pinia store |
| `frontend/src/pages/NotificationConfigPage.vue` | 通知渠道配置页 |
| `frontend/src/components/dashboard/SmartRemindersCard.vue` | 总览页智能提醒折叠模块 |

### 前端修改
| 文件 | 变更 |
|------|------|
| `frontend/src/pages/DashboardPage.vue` | AlertCards 下方插入 SmartRemindersCard |
| `frontend/src/pages/SettingsPage.vue` | 新增「通知设置」cell |
| `frontend/src/pages/AssetFormPage.vue` | 新增 `warranty_expiry_date` 日期选择器 |
| `frontend/src/router/index.ts` | 注册 NotificationConfigPage 路由 |
| `frontend/src/i18n/locales/zh-CN.ts` | 新增提醒相关 toast/label 文案 |
| `frontend/src/i18n/locales/en-US.ts` | 同上英文版 |

---

---

## Task 1: 数据模型 — 四张新表 + asset 新字段

**Files:**
- Create: `backend/app/models/notification_channel.py`
- Create: `backend/app/models/notification_subscription.py`
- Create: `backend/app/models/notification_config.py`
- Create: `backend/app/models/reminder.py`
- Modify: `backend/app/models/asset.py`

- [ ] **Step 1: 创建 `notification_channel.py`**

```python
# backend/app/models/notification_channel.py
from datetime import datetime
from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base
from app.utils.snowflake import next_id

class NotificationChannel(Base):
    __tablename__ = "notification_channels"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    family_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("families.id"), nullable=False, index=True)
    channel_type: Mapped[str] = mapped_column(String(20), nullable=False)  # telegram | email
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    config: Mapped[str] = mapped_column(Text, nullable=False)  # JSON encrypted
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
```

- [ ] **Step 2: 创建 `notification_subscription.py`**

```python
# backend/app/models/notification_subscription.py
from datetime import datetime
from sqlalchemy import BigInteger, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base
from app.utils.snowflake import next_id

class NotificationSubscription(Base):
    __tablename__ = "notification_subscriptions"
    __table_args__ = (UniqueConstraint("channel_id", "reminder_type", name="uq_channel_reminder_type"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    channel_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("notification_channels.id", ondelete="CASCADE"), nullable=False, index=True)
    reminder_type: Mapped[str] = mapped_column(String(30), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
```

- [ ] **Step 3: 创建 `notification_config.py`**

```python
# backend/app/models/notification_config.py
from datetime import datetime
from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base
from app.utils.snowflake import next_id

class NotificationConfig(Base):
    __tablename__ = "notification_configs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    family_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("families.id"), nullable=False, unique=True, index=True)
    large_purchase_threshold_fixed: Mapped[float | None] = mapped_column(Float, nullable=True)
    large_purchase_threshold_multiplier: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
```

- [ ] **Step 4: 创建 `reminder.py`**

```python
# backend/app/models/reminder.py
from datetime import datetime
from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base
from app.utils.snowflake import next_id

class Reminder(Base):
    __tablename__ = "reminders"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    family_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("families.id"), nullable=False, index=True)
    reminder_type: Mapped[str] = mapped_column(String(30), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(10), nullable=False, default="info")
    asset_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("assets.id", ondelete="SET NULL"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    dismissed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    notified_channels: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
```

- [ ] **Step 5: 在 `asset.py` 的 `maturity_date` 行后新增 `warranty_expiry_date`**

```python
    warranty_expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
```

- [ ] **Step 6: 验证模型可导入**

```bash
cd backend && uv run python -c "
from app.models.notification_channel import NotificationChannel
from app.models.notification_subscription import NotificationSubscription
from app.models.notification_config import NotificationConfig
from app.models.reminder import Reminder
from app.models.asset import Asset
print('all models OK')
"
```

Expected: `all models OK`

- [ ] **Step 7: Commit**

```bash
git add backend/app/models/notification_channel.py \
        backend/app/models/notification_subscription.py \
        backend/app/models/notification_config.py \
        backend/app/models/reminder.py \
        backend/app/models/asset.py
git commit -m "feat(phase4): add notification models and warranty_expiry_date field"
```

---

## Task 2: Alembic 迁移

**Files:**
- Create: `backend/alembic/versions/xxxx_phase4_smart_reminders.py` (自动生成)
- Modify: `backend/app/main.py`

- [ ] **Step 1: 在 `main.py` 现有 model import 块末尾追加四个新模型导入**

```python
from app.models.notification_channel import NotificationChannel  # noqa: F401
from app.models.notification_subscription import NotificationSubscription  # noqa: F401
from app.models.notification_config import NotificationConfig  # noqa: F401
from app.models.reminder import Reminder  # noqa: F401
```

- [ ] **Step 2: 生成迁移**

```bash
cd backend && uv run alembic revision --autogenerate -m "phase4_smart_reminders"
```

Expected: 生成 `alembic/versions/xxxx_phase4_smart_reminders.py`

- [ ] **Step 3: 检查生成的迁移文件**

确认 `upgrade()` 中包含：
- `op.create_table('notification_channels', ...)`
- `op.create_table('notification_subscriptions', ...)`
- `op.create_table('notification_configs', ...)`
- `op.create_table('reminders', ...)`
- `op.add_column('assets', sa.Column('warranty_expiry_date', sa.Date(), nullable=True))`

- [ ] **Step 4: 应用迁移**

```bash
cd backend && uv run alembic upgrade head
```

Expected: 无报错

- [ ] **Step 5: Commit**

```bash
git add backend/alembic/versions/ backend/app/main.py
git commit -m "feat(phase4): alembic migration for notification tables and warranty_expiry_date"
```

---

## Task 3: Schemas

**Files:**
- Create: `backend/app/schemas/notification_channel.py`
- Create: `backend/app/schemas/notification_config.py`
- Create: `backend/app/schemas/reminder.py`
- Modify: `backend/app/schemas/asset.py`

- [ ] **Step 1: 创建 `schemas/notification_channel.py`**

```python
# backend/app/schemas/notification_channel.py
from datetime import datetime
from pydantic import BaseModel, ConfigDict

class NotificationChannelCreate(BaseModel):
    channel_type: str  # telegram | email
    name: str
    config: dict       # 明文传输，服务层 JSON 序列化后加密存储
    is_enabled: bool = True
    subscriptions: list[str] = []  # reminder_type list

class NotificationChannelUpdate(BaseModel):
    name: str | None = None
    config: dict | None = None
    is_enabled: bool | None = None
    subscriptions: list[str] | None = None

class NotificationChannelResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    family_id: int
    channel_type: str
    name: str
    is_enabled: bool
    subscriptions: list[str] = []
    created_at: datetime
    updated_at: datetime
```

- [ ] **Step 2: 创建 `schemas/notification_config.py`**

```python
# backend/app/schemas/notification_config.py
from datetime import datetime
from pydantic import BaseModel, ConfigDict

class NotificationConfigUpdate(BaseModel):
    large_purchase_threshold_fixed: float | None = None
    large_purchase_threshold_multiplier: float | None = None

class NotificationConfigResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    family_id: int
    large_purchase_threshold_fixed: float | None
    large_purchase_threshold_multiplier: float | None
    updated_at: datetime
```

- [ ] **Step 3: 创建 `schemas/reminder.py`**

```python
# backend/app/schemas/reminder.py
from datetime import datetime
from pydantic import BaseModel, ConfigDict

class ReminderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    family_id: int
    reminder_type: str
    title: str
    body: str
    severity: str
    asset_id: int | None
    status: str
    dismissed_at: datetime | None
    resolved_at: datetime | None
    created_at: datetime

class ReminderSummary(BaseModel):
    """总览页摘要：各类型 active 数量"""
    large_purchase: int = 0
    allocation_drift: int = 0
    expiring_soon: int = 0
    maturity: int = 0
    total: int = 0
```

- [ ] **Step 4: 在 `schemas/asset.py` 的 `AssetCreate`、`AssetUpdate`、`AssetResponse` 中新增 `warranty_expiry_date`**

在 `AssetCreate` 的 `maturity_date: date | None = None` 行后插入：
```python
    warranty_expiry_date: date | None = None
```

在 `AssetUpdate` 的 `maturity_date: date | None = None` 行后插入：
```python
    warranty_expiry_date: date | None = None
```

在 `AssetResponse`（或其基类）的 `maturity_date` 行后插入：
```python
    warranty_expiry_date: date | None = None
```

- [ ] **Step 5: 验证 schemas 可导入**

```bash
cd backend && uv run python -c "
from app.schemas.notification_channel import NotificationChannelCreate, NotificationChannelResponse
from app.schemas.notification_config import NotificationConfigResponse
from app.schemas.reminder import ReminderResponse, ReminderSummary
from app.schemas.asset import AssetCreate, AssetUpdate
print('all schemas OK')
"
```

Expected: `all schemas OK`

- [ ] **Step 6: Commit**

```bash
git add backend/app/schemas/notification_channel.py \
        backend/app/schemas/notification_config.py \
        backend/app/schemas/reminder.py \
        backend/app/schemas/asset.py
git commit -m "feat(phase4): add notification schemas and warranty_expiry_date in asset schema"
```

---

## Task 4: 通知模板 JSON 文件

**Files:**
- Create: `backend/app/services/notification/__init__.py`
- Create: `backend/app/services/notification/templates/large_purchase.json`
- Create: `backend/app/services/notification/templates/allocation_drift.json`
- Create: `backend/app/services/notification/templates/expiring_soon.json`
- Create: `backend/app/services/notification/templates/maturity.json`

- [ ] **Step 1: 创建包入口 `__init__.py`**

```python
# backend/app/services/notification/__init__.py
```

（空文件即可）

- [ ] **Step 2: 创建 `large_purchase.json`**

```json
{
  "telegram": {
    "text": "🛒 *大额消费提醒*\n\n你正在考虑购买 *{asset_name}*，金额 ¥{amount}。\n建议冷静 48 小时再决定。\n\n_Numina 家庭资产管理_"
  },
  "email": {
    "subject": "【Numina】大额消费冷静期提醒",
    "body": "你好，\n\n你正在考虑购买「{asset_name}」，金额 ¥{amount}，超过你设定的大额消费阈值（{threshold}）。\n\n建议冷静 48 小时后再做决定。\n\nNumina 家庭资产管理"
  }
}
```

- [ ] **Step 3: 创建 `allocation_drift.json`**

```json
{
  "telegram": {
    "text": "📊 *资产配置失衡提醒*\n\n{category} 当前占比 {current_pct}%，目标 {target_pct}%，偏差 {drift_pct}%。\n建议适当再平衡。\n\n_Numina 家庭资产管理_"
  },
  "email": {
    "subject": "【Numina】资产配置失衡提醒",
    "body": "你好，\n\n你的资产配置出现偏差：\n\n类别：{category}\n当前占比：{current_pct}%\n目标占比：{target_pct}%\n偏差：{drift_pct}%\n\n建议适当调整资产配置。\n\nNumina 家庭资产管理"
  }
}
```

- [ ] **Step 4: 创建 `expiring_soon.json`**

```json
{
  "telegram": {
    "text": "🔧 *保修即将到期*\n\n*{asset_name}* 的保修将于 {expiry_date} 到期，还有 {days_left} 天。\n\n_Numina 家庭资产管理_"
  },
  "email": {
    "subject": "【Numina】保修即将到期提醒",
    "body": "你好，\n\n以下资产的保修即将到期：\n\n资产：{asset_name}\n到期日：{expiry_date}\n剩余天数：{days_left} 天\n\n请及时处理。\n\nNumina 家庭资产管理"
  }
}
```

- [ ] **Step 5: 创建 `maturity.json`**

```json
{
  "telegram": {
    "text": "💰 *理财产品即将到期*\n\n*{asset_name}* 将于 {maturity_date} 到期，还有 {days_left} 天，金额 ¥{amount}。\n\n_Numina 家庭资产管理_"
  },
  "email": {
    "subject": "【Numina】理财产品到期提醒",
    "body": "你好，\n\n以下理财产品即将到期：\n\n产品：{asset_name}\n到期日：{maturity_date}\n剩余天数：{days_left} 天\n金额：¥{amount}\n\n请及时处理续期或赎回。\n\nNumina 家庭资产管理"
  }
}
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/notification/
git commit -m "feat(phase4): add notification message templates"
```


---

## Task 5: 通知发送器 `sender.py`

**Files:**
- Create: `backend/app/services/notification/sender.py`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_notification_rules.py (先建文件，后续 Task 7 继续扩充)
import json, pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.notification.sender import render_template, NotificationSender

def test_render_template_large_purchase():
    text = render_template("large_purchase", "telegram", {
        "asset_name": "宝马X3", "amount": "400000", "threshold": "¥5000"
    })
    assert "宝马X3" in text
    assert "400000" in text

def test_render_template_missing_key_raises():
    with pytest.raises(KeyError):
        render_template("large_purchase", "telegram", {})
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd backend && uv run pytest tests/test_notification_rules.py::test_render_template_large_purchase -v
```

Expected: `FAILED` — `ModuleNotFoundError` 或 `ImportError`

- [ ] **Step 3: 实现 `sender.py`**

```python
# backend/app/services/notification/sender.py
import json
import logging
import smtplib
from email.mime.text import MIMEText
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

_TEMPLATE_DIR = Path(__file__).parent / "templates"


def render_template(reminder_type: str, channel_type: str, variables: dict) -> str:
    """加载模板并用 variables 渲染，返回渲染后的文本。"""
    template_path = _TEMPLATE_DIR / f"{reminder_type}.json"
    with open(template_path, encoding="utf-8") as f:
        tmpl = json.load(f)
    if channel_type == "telegram":
        return tmpl["telegram"]["text"].format_map(variables)
    elif channel_type == "email_subject":
        return tmpl["email"]["subject"].format_map(variables)
    elif channel_type == "email_body":
        return tmpl["email"]["body"].format_map(variables)
    raise ValueError(f"Unknown channel_type: {channel_type}")


class NotificationSender:
    """封装 Telegram 和 SMTP 发送逻辑。"""

    @staticmethod
    async def send_telegram(bot_token: str, chat_id: str, text: str) -> bool:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(url, json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"})
                resp.raise_for_status()
                return True
        except Exception as e:
            logger.warning("Telegram 发送失败: %s", e)
            return False

    @staticmethod
    def send_email(smtp_host: str, smtp_port: int, smtp_user: str, smtp_password: str,
                   smtp_from: str, to: str, subject: str, body: str) -> bool:
        try:
            msg = MIMEText(body, "plain", "utf-8")
            msg["Subject"] = subject
            msg["From"] = smtp_from
            msg["To"] = to
            with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
                server.starttls()
                server.login(smtp_user, smtp_password)
                server.sendmail(smtp_from, [to], msg.as_string())
            return True
        except Exception as e:
            logger.warning("邮件发送失败: %s", e)
            return False
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd backend && uv run pytest tests/test_notification_rules.py::test_render_template_large_purchase tests/test_notification_rules.py::test_render_template_missing_key_raises -v
```

Expected: `2 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/notification/sender.py backend/tests/test_notification_rules.py
git commit -m "feat(phase4): add notification sender with template rendering"
```

---

## Task 6: 规则引擎 `rules.py`

**Files:**
- Create: `backend/app/services/notification/rules.py`

- [ ] **Step 1: 写失败测试（追加到 `test_notification_rules.py`）**

```python
# 追加到 backend/tests/test_notification_rules.py
from datetime import date, timedelta
from sqlalchemy.orm import Session
from app.services.notification.rules import (
    check_large_purchase,
    check_expiring_soon,
    check_maturity,
    check_allocation_drift,
)

def test_check_large_purchase_fixed_threshold(db: Session, auth_headers, client):
    """purchase_price 超过固定阈值时应返回 Reminder 数据"""
    result = check_large_purchase(
        db=db,
        family_id=1,
        asset_id=99,
        asset_name="豪华沙发",
        purchase_price=10000.0,
        threshold_fixed=5000.0,
        threshold_multiplier=None,
        avg_monthly_spend=None,
    )
    assert result is not None
    assert result["reminder_type"] == "large_purchase"
    assert result["severity"] == "warning"

def test_check_large_purchase_below_threshold(db: Session):
    result = check_large_purchase(
        db=db,
        family_id=1,
        asset_id=99,
        asset_name="普通水杯",
        purchase_price=50.0,
        threshold_fixed=5000.0,
        threshold_multiplier=None,
        avg_monthly_spend=None,
    )
    assert result is None

def test_check_expiring_soon_within_30_days(db: Session):
    expiry = date.today() + timedelta(days=20)
    result = check_expiring_soon(
        family_id=1, asset_id=1, asset_name="iPhone保修",
        expiry_date=expiry,
    )
    assert result is not None
    assert result["reminder_type"] == "expiring_soon"
    assert result["severity"] == "warning"

def test_check_expiring_soon_within_7_days(db: Session):
    expiry = date.today() + timedelta(days=5)
    result = check_expiring_soon(
        family_id=1, asset_id=1, asset_name="iPhone保修",
        expiry_date=expiry,
    )
    assert result is not None
    assert result["severity"] == "critical"

def test_check_expiring_soon_far_future(db: Session):
    expiry = date.today() + timedelta(days=60)
    result = check_expiring_soon(
        family_id=1, asset_id=1, asset_name="iPhone保修",
        expiry_date=expiry,
    )
    assert result is None
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd backend && uv run pytest tests/test_notification_rules.py -k "check_large_purchase or check_expiring" -v
```

Expected: `FAILED` — `ImportError`

- [ ] **Step 3: 实现 `rules.py`**

```python
# backend/app/services/notification/rules.py
from datetime import date, timedelta
from sqlalchemy.orm import Session


def check_large_purchase(
    db: Session,
    family_id: int,
    asset_id: int,
    asset_name: str,
    purchase_price: float,
    threshold_fixed: float | None,
    threshold_multiplier: float | None,
    avg_monthly_spend: float | None,
) -> dict | None:
    """大额消费冷静期规则。满足任一阈值条件则返回 reminder dict，否则返回 None。"""
    triggered = False
    if threshold_fixed is not None and purchase_price >= threshold_fixed:
        triggered = True
    if (threshold_multiplier is not None and avg_monthly_spend is not None
            and purchase_price >= avg_monthly_spend * threshold_multiplier):
        triggered = True
    if not triggered:
        return None
    return {
        "family_id": family_id,
        "reminder_type": "large_purchase",
        "title": f"大额消费提醒：{asset_name}",
        "body": f"购买「{asset_name}」金额 ¥{purchase_price:.0f}，建议冷静 48 小时再决定。",
        "severity": "warning",
        "asset_id": asset_id,
        "template_vars": {
            "asset_name": asset_name,
            "amount": f"{purchase_price:.0f}",
            "threshold": f"¥{threshold_fixed:.0f}" if threshold_fixed else "月均支出倍数",
        },
    }


def check_expiring_soon(
    family_id: int,
    asset_id: int,
    asset_name: str,
    expiry_date: date,
) -> dict | None:
    """保修/保险到期规则。提前 30 天 warning，提前 7 天 critical。"""
    today = date.today()
    days_left = (expiry_date - today).days
    if days_left > 30 or days_left < 0:
        return None
    severity = "critical" if days_left <= 7 else "warning"
    return {
        "family_id": family_id,
        "reminder_type": "expiring_soon",
        "title": f"保修即将到期：{asset_name}",
        "body": f"「{asset_name}」保修将于 {expiry_date} 到期，还有 {days_left} 天。",
        "severity": severity,
        "asset_id": asset_id,
        "template_vars": {
            "asset_name": asset_name,
            "expiry_date": str(expiry_date),
            "days_left": str(days_left),
        },
    }


def check_maturity(
    family_id: int,
    asset_id: int,
    asset_name: str,
    maturity_date: date,
    amount: float | None,
) -> dict | None:
    """理财产品到期规则。提前 30 天 warning，提前 7 天 critical。"""
    today = date.today()
    days_left = (maturity_date - today).days
    if days_left > 30 or days_left < 0:
        return None
    severity = "critical" if days_left <= 7 else "warning"
    amt_str = f"{amount:.0f}" if amount else "未知"
    return {
        "family_id": family_id,
        "reminder_type": "maturity",
        "title": f"理财产品即将到期：{asset_name}",
        "body": f"「{asset_name}」将于 {maturity_date} 到期，还有 {days_left} 天，金额 ¥{amt_str}。",
        "severity": severity,
        "asset_id": asset_id,
        "template_vars": {
            "asset_name": asset_name,
            "maturity_date": str(maturity_date),
            "days_left": str(days_left),
            "amount": amt_str,
        },
    }


def check_allocation_drift(
    family_id: int,
    category: str,
    current_pct: float,
    target_pct: float,
    drift_threshold: float,
) -> dict | None:
    """资产配置失衡规则。偏差超过 drift_threshold 百分点则触发。"""
    drift = abs(current_pct - target_pct)
    if drift <= drift_threshold:
        return None
    return {
        "family_id": family_id,
        "reminder_type": "allocation_drift",
        "title": f"资产配置失衡：{category}",
        "body": f"「{category}」当前占比 {current_pct:.1f}%，目标 {target_pct:.1f}%，偏差 {drift:.1f}%。",
        "severity": "warning",
        "asset_id": None,
        "template_vars": {
            "category": category,
            "current_pct": f"{current_pct:.1f}",
            "target_pct": f"{target_pct:.1f}",
            "drift_pct": f"{drift:.1f}",
        },
    }
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd backend && uv run pytest tests/test_notification_rules.py -v
```

Expected: 所有测试 `passed`

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/notification/rules.py backend/tests/test_notification_rules.py
git commit -m "feat(phase4): add reminder rules engine with tests"
```

---

## Task 7: 调度器 `dispatcher.py` + APScheduler 注册

**Files:**
- Create: `backend/app/services/notification/dispatcher.py`
- Modify: `backend/app/scheduler.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: 写失败测试（追加到 `test_notification_rules.py`）**

```python
# 追加到 backend/tests/test_notification_rules.py
from app.services.notification.dispatcher import ensure_reminder, get_reminder_summary

def test_ensure_reminder_creates_new(db: Session):
    """ensure_reminder 应在无 active 记录时创建新 reminder"""
    from app.models.reminder import Reminder
    reminder_data = {
        "family_id": 1,
        "reminder_type": "maturity",
        "title": "测试到期",
        "body": "测试内容",
        "severity": "warning",
        "asset_id": None,
        "template_vars": {},
    }
    ensure_reminder(db, reminder_data)
    count = db.query(Reminder).filter_by(family_id=1, reminder_type="maturity", status="active").count()
    assert count == 1

def test_ensure_reminder_idempotent(db: Session):
    """ensure_reminder 对同一条件调用两次，只创建一条记录"""
    from app.models.reminder import Reminder
    reminder_data = {
        "family_id": 1,
        "reminder_type": "maturity",
        "title": "测试到期",
        "body": "测试内容",
        "severity": "warning",
        "asset_id": None,
        "template_vars": {},
    }
    ensure_reminder(db, reminder_data)
    ensure_reminder(db, reminder_data)
    count = db.query(Reminder).filter_by(family_id=1, reminder_type="maturity", status="active").count()
    assert count == 1

def test_get_reminder_summary(db: Session):
    """get_reminder_summary 应返回各类型 active 数量"""
    from app.models.reminder import Reminder
    from app.utils.snowflake import next_id
    db.add(Reminder(id=next_id(), family_id=1, reminder_type="maturity",
                    title="t", body="b", severity="warning"))
    db.add(Reminder(id=next_id(), family_id=1, reminder_type="maturity",
                    title="t2", body="b2", severity="critical"))
    db.commit()
    summary = get_reminder_summary(db, family_id=1)
    assert summary.maturity == 2
    assert summary.total == 2
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd backend && uv run pytest tests/test_notification_rules.py -k "ensure_reminder or get_reminder_summary" -v
```

Expected: `FAILED` — `ImportError`

- [ ] **Step 3: 实现 `dispatcher.py`**

```python
# backend/app/services/notification/dispatcher.py
import asyncio
import json
import logging
from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from app.models.asset import Asset
from app.models.notification_channel import NotificationChannel
from app.models.notification_config import NotificationConfig
from app.models.notification_subscription import NotificationSubscription
from app.models.reminder import Reminder
from app.models.ai_allocation_target import AIAllocationTarget
from app.models.user import User
from app.schemas.reminder import ReminderSummary
from app.services.notification.rules import (
    check_allocation_drift,
    check_expiring_soon,
    check_large_purchase,
    check_maturity,
)
from app.services.notification.sender import NotificationSender, render_template
from app.utils.snowflake import next_id

logger = logging.getLogger(__name__)


def ensure_reminder(db: Session, data: dict) -> Reminder | None:
    """幂等创建 reminder：同 family_id + reminder_type + asset_id + status=active 已存在则跳过。"""
    existing = (
        db.query(Reminder)
        .filter_by(
            family_id=data["family_id"],
            reminder_type=data["reminder_type"],
            asset_id=data.get("asset_id"),
            status="active",
        )
        .first()
    )
    if existing:
        return None
    reminder = Reminder(
        id=next_id(),
        family_id=data["family_id"],
        reminder_type=data["reminder_type"],
        title=data["title"],
        body=data["body"],
        severity=data["severity"],
        asset_id=data.get("asset_id"),
    )
    db.add(reminder)
    db.commit()
    db.refresh(reminder)
    _dispatch_notifications(db, reminder, data.get("template_vars", {}))
    return reminder


def get_reminder_summary(db: Session, family_id: int) -> ReminderSummary:
    rows = (
        db.query(Reminder.reminder_type)
        .filter_by(family_id=family_id, status="active")
        .all()
    )
    counts: dict[str, int] = {}
    for (rtype,) in rows:
        counts[rtype] = counts.get(rtype, 0) + 1
    return ReminderSummary(
        large_purchase=counts.get("large_purchase", 0),
        allocation_drift=counts.get("allocation_drift", 0),
        expiring_soon=counts.get("expiring_soon", 0),
        maturity=counts.get("maturity", 0),
        total=sum(counts.values()),
    )


def check_on_asset_write(db: Session, asset: Asset) -> None:
    """资产写入时实时检测大额消费冷静期。"""
    if not asset.purchase_price:
        return
    config = db.query(NotificationConfig).filter_by(family_id=asset.family_id).first()
    if config is None:
        return
    if config.large_purchase_threshold_fixed is None and config.large_purchase_threshold_multiplier is None:
        return

    avg_monthly = _calc_avg_monthly_spend(db, asset.family_id)
    result = check_large_purchase(
        db=db,
        family_id=asset.family_id,
        asset_id=asset.id,
        asset_name=asset.name,
        purchase_price=asset.purchase_price,
        threshold_fixed=config.large_purchase_threshold_fixed,
        threshold_multiplier=config.large_purchase_threshold_multiplier,
        avg_monthly_spend=avg_monthly,
    )
    if result:
        ensure_reminder(db, result)


def run_scheduled_checks(db: Session) -> None:
    """APScheduler 每日 09:20 调用：检测到期类 + 配置失衡 + 清理过期冷静期。"""
    _resolve_expired_large_purchase(db)
    _check_expiring_assets(db)
    _check_maturity_assets(db)
    _check_allocation_drift_all(db)


# ── 内部辅助 ──────────────────────────────────────────────────────────────────

def _calc_avg_monthly_spend(db: Session, family_id: int) -> float | None:
    from sqlalchemy import func
    from datetime import timedelta
    cutoff = date.today() - timedelta(days=90)
    result = (
        db.query(func.sum(Asset.purchase_price))
        .filter(
            Asset.family_id == family_id,
            Asset.is_archived == False,
            Asset.purchase_date >= cutoff,
        )
        .scalar()
    )
    if result is None:
        return None
    return float(result) / 3.0


def _resolve_expired_large_purchase(db: Session) -> None:
    cutoff = datetime.now() - timedelta(hours=48)
    db.query(Reminder).filter(
        Reminder.reminder_type == "large_purchase",
        Reminder.status == "active",
        Reminder.created_at <= cutoff,
    ).update({"status": "resolved", "resolved_at": datetime.now()})
    db.commit()


def _check_expiring_assets(db: Session) -> None:
    assets = (
        db.query(Asset)
        .filter(Asset.is_archived == False, Asset.warranty_expiry_date.isnot(None))
        .all()
    )
    for asset in assets:
        result = check_expiring_soon(
            family_id=asset.family_id,
            asset_id=asset.id,
            asset_name=asset.name,
            expiry_date=asset.warranty_expiry_date,
        )
        if result:
            ensure_reminder(db, result)


def _check_maturity_assets(db: Session) -> None:
    assets = (
        db.query(Asset)
        .filter(Asset.is_archived == False, Asset.maturity_date.isnot(None))
        .all()
    )
    for asset in assets:
        result = check_maturity(
            family_id=asset.family_id,
            asset_id=asset.id,
            asset_name=asset.name,
            maturity_date=asset.maturity_date,
            amount=asset.current_value,
        )
        if result:
            ensure_reminder(db, result)


def _check_allocation_drift_all(db: Session) -> None:
    from sqlalchemy import func
    targets = db.query(AIAllocationTarget).all()
    for target in targets:
        family_id = target.family_id
        total = (
            db.query(func.sum(Asset.current_value))
            .join(User, Asset.user_id == User.id)
            .filter(User.family_id == family_id, Asset.is_archived == False)
            .scalar()
        ) or 0
        if total == 0:
            continue
        for category, target_pct in target.category_targets.items():
            current_val = (
                db.query(func.sum(Asset.current_value))
                .join(User, Asset.user_id == User.id)
                .filter(
                    User.family_id == family_id,
                    Asset.is_archived == False,
                    Asset.asset_type == category,
                )
                .scalar()
            ) or 0
            current_pct = (current_val / total) * 100
            result = check_allocation_drift(
                family_id=family_id,
                category=category,
                current_pct=current_pct,
                target_pct=float(target_pct),
                drift_threshold=target.drift_threshold,
            )
            if result:
                ensure_reminder(db, result)


def _dispatch_notifications(db: Session, reminder: Reminder, template_vars: dict) -> None:
    """向订阅了该 reminder_type 的所有启用渠道发送通知（异步，失败静默）。"""
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
    notified: list[int] = json.loads(reminder.notified_channels)
    for channel in channels:
        if channel.id in notified:
            continue
        config = json.loads(channel.config)
        success = False
        if channel.channel_type == "telegram":
            success = asyncio.get_event_loop().run_until_complete(
                NotificationSender.send_telegram(
                    bot_token=config["bot_token"],
                    chat_id=config["chat_id"],
                    text=render_template(reminder.reminder_type, "telegram", template_vars),
                )
            ) if asyncio.get_event_loop().is_running() else False
            if not success:
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
                smtp_host=config["smtp_host"],
                smtp_port=int(config["smtp_port"]),
                smtp_user=config["smtp_user"],
                smtp_password=config["smtp_password"],
                smtp_from=config["smtp_from"],
                to=config["to"],
                subject=subject,
                body=body,
            )
        if success:
            notified.append(channel.id)
    reminder.notified_channels = json.dumps(notified)
    db.commit()


async def _send_telegram_async(channel: NotificationChannel, reminder: Reminder,
                                template_vars: dict, db: Session) -> None:
    config = json.loads(channel.config)
    text = render_template(reminder.reminder_type, "telegram", template_vars)
    success = await NotificationSender.send_telegram(
        bot_token=config["bot_token"],
        chat_id=config["chat_id"],
        text=text,
    )
    if success:
        notified = json.loads(reminder.notified_channels)
        if channel.id not in notified:
            notified.append(channel.id)
            reminder.notified_channels = json.dumps(notified)
            db.commit()
```

- [ ] **Step 4: 在 `scheduler.py` 末尾新增 `setup_reminder_schedule()`**

```python
def setup_reminder_schedule() -> None:
    """Schedule daily reminder checks at 09:20."""
    from app.services.notification.dispatcher import run_scheduled_checks

    def _reminder_job() -> None:
        db = SessionLocal()
        try:
            run_scheduled_checks(db)
            logger.info("智能提醒定时检测完成")
        except Exception as e:
            logger.exception(f"智能提醒定时检测失败: {e}")
        finally:
            db.close()

    scheduler.add_job(
        _reminder_job,
        trigger="cron",
        hour=9,
        minute=20,
        id="reminder_daily",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    logger.info("智能提醒定时任务已配置（每日 09:20）")
```

- [ ] **Step 5: 在 `main.py` 的 lifespan 中调用 `setup_reminder_schedule()`**

找到 `setup_exchange_rate_schedule()` 等调用处，追加：
```python
from app.scheduler import setup_reminder_schedule
setup_reminder_schedule()
```

- [ ] **Step 6: 运行测试确认通过**

```bash
cd backend && uv run pytest tests/test_notification_rules.py -v
```

Expected: 所有测试 `passed`

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/notification/dispatcher.py \
        backend/app/scheduler.py \
        backend/app/main.py \
        backend/tests/test_notification_rules.py
git commit -m "feat(phase4): add notification dispatcher, scheduler job, and dispatcher tests"
```

---

## Task 8: 在 `asset.py` service 中接入 dispatcher

**Files:**
- Modify: `backend/app/services/asset.py`

- [ ] **Step 1: 在 `create_asset` 末尾调用 `check_on_asset_write`**

在 `db.refresh(asset)` 之后、`return asset` 之前插入：

```python
    from app.services.notification.dispatcher import check_on_asset_write
    try:
        check_on_asset_write(db, asset)
    except Exception:
        pass  # 提醒检测失败不影响主流程
```

- [ ] **Step 2: 在 `update_asset` 末尾同样调用**

在 `db.refresh(asset)` 之后、`return asset` 之前插入：

```python
    from app.services.notification.dispatcher import check_on_asset_write
    try:
        check_on_asset_write(db, asset)
    except Exception:
        pass
```

- [ ] **Step 3: 运行现有资产测试确认无回归**

```bash
cd backend && uv run pytest tests/test_assets.py -v
```

Expected: 所有测试 `passed`

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/asset.py
git commit -m "feat(phase4): trigger large_purchase check on asset create/update"
```


---

## Task 9: API 路由 — 渠道配置、提醒配置、提醒列表

**Files:**
- Create: `backend/app/routers/notification_channels.py`
- Create: `backend/app/routers/notification_config.py`
- Create: `backend/app/routers/reminders.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: 创建 `routers/notification_channels.py`**

```python
# backend/app/routers/notification_channels.py
import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.deps import require_adult
from app.database import get_db
from app.models.notification_channel import NotificationChannel
from app.models.notification_subscription import NotificationSubscription
from app.models.user import User
from app.schemas.notification_channel import (
    NotificationChannelCreate,
    NotificationChannelResponse,
    NotificationChannelUpdate,
)
from app.utils.snowflake import next_id

router = APIRouter(prefix="/notification-channels", tags=["notification-channels"])

VALID_CHANNEL_TYPES = {"telegram", "email"}
VALID_REMINDER_TYPES = {"large_purchase", "allocation_drift", "expiring_soon", "maturity"}


def _to_response(channel: NotificationChannel, db: Session) -> NotificationChannelResponse:
    subs = db.query(NotificationSubscription).filter_by(channel_id=channel.id).all()
    return NotificationChannelResponse(
        id=channel.id,
        family_id=channel.family_id,
        channel_type=channel.channel_type,
        name=channel.name,
        is_enabled=channel.is_enabled,
        subscriptions=[s.reminder_type for s in subs],
        created_at=channel.created_at,
        updated_at=channel.updated_at,
    )


@router.get("", response_model=list[NotificationChannelResponse])
def list_channels(db: Session = Depends(get_db), user: User = Depends(require_adult)):
    channels = db.query(NotificationChannel).filter_by(family_id=user.family_id).all()
    return [_to_response(c, db) for c in channels]


@router.post("", response_model=NotificationChannelResponse, status_code=201)
def create_channel(
    req: NotificationChannelCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    if req.channel_type not in VALID_CHANNEL_TYPES:
        raise HTTPException(status_code=422, detail="不支持的渠道类型")
    channel = NotificationChannel(
        id=next_id(),
        family_id=user.family_id,
        channel_type=req.channel_type,
        name=req.name,
        config=json.dumps(req.config, ensure_ascii=False),
        is_enabled=req.is_enabled,
    )
    db.add(channel)
    db.flush()
    for rtype in req.subscriptions:
        if rtype in VALID_REMINDER_TYPES:
            db.add(NotificationSubscription(id=next_id(), channel_id=channel.id, reminder_type=rtype))
    db.commit()
    db.refresh(channel)
    return _to_response(channel, db)


@router.put("/{channel_id}", response_model=NotificationChannelResponse)
def update_channel(
    channel_id: int,
    req: NotificationChannelUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    channel = db.query(NotificationChannel).filter_by(id=channel_id, family_id=user.family_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="渠道不存在")
    if req.name is not None:
        channel.name = req.name
    if req.config is not None:
        channel.config = json.dumps(req.config, ensure_ascii=False)
    if req.is_enabled is not None:
        channel.is_enabled = req.is_enabled
    if req.subscriptions is not None:
        db.query(NotificationSubscription).filter_by(channel_id=channel.id).delete()
        for rtype in req.subscriptions:
            if rtype in VALID_REMINDER_TYPES:
                db.add(NotificationSubscription(id=next_id(), channel_id=channel.id, reminder_type=rtype))
    db.commit()
    db.refresh(channel)
    return _to_response(channel, db)


@router.delete("/{channel_id}", status_code=204)
def delete_channel(
    channel_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    channel = db.query(NotificationChannel).filter_by(id=channel_id, family_id=user.family_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="渠道不存在")
    db.query(NotificationSubscription).filter_by(channel_id=channel.id).delete()
    db.delete(channel)
    db.commit()
```

- [ ] **Step 2: 创建 `routers/notification_config.py`**

```python
# backend/app/routers/notification_config.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.deps import require_adult
from app.database import get_db
from app.models.notification_config import NotificationConfig
from app.models.user import User
from app.schemas.notification_config import NotificationConfigResponse, NotificationConfigUpdate
from app.utils.snowflake import next_id

router = APIRouter(prefix="/notification-config", tags=["notification-config"])


@router.get("", response_model=NotificationConfigResponse)
def get_config(db: Session = Depends(get_db), user: User = Depends(require_adult)):
    config = db.query(NotificationConfig).filter_by(family_id=user.family_id).first()
    if not config:
        config = NotificationConfig(id=next_id(), family_id=user.family_id)
        db.add(config)
        db.commit()
        db.refresh(config)
    return NotificationConfigResponse.model_validate(config)


@router.put("", response_model=NotificationConfigResponse)
def update_config(
    req: NotificationConfigUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    config = db.query(NotificationConfig).filter_by(family_id=user.family_id).first()
    if not config:
        config = NotificationConfig(id=next_id(), family_id=user.family_id)
        db.add(config)
    for key, val in req.model_dump(exclude_unset=True).items():
        setattr(config, key, val)
    db.commit()
    db.refresh(config)
    return NotificationConfigResponse.model_validate(config)
```

- [ ] **Step 3: 创建 `routers/reminders.py`**

```python
# backend/app/routers/reminders.py
from datetime import datetime
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth.deps import require_adult
from app.database import get_db
from app.models.reminder import Reminder
from app.models.user import User
from app.schemas.reminder import ReminderResponse, ReminderSummary
from app.services.notification.dispatcher import get_reminder_summary

router = APIRouter(prefix="/reminders", tags=["reminders"])


@router.get("/summary", response_model=ReminderSummary)
def get_summary(db: Session = Depends(get_db), user: User = Depends(require_adult)):
    return get_reminder_summary(db, family_id=user.family_id)


@router.get("", response_model=list[ReminderResponse])
def list_reminders(
    status: str = Query("active"),
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    reminders = (
        db.query(Reminder)
        .filter_by(family_id=user.family_id, status=status)
        .order_by(Reminder.created_at.desc())
        .all()
    )
    return [ReminderResponse.model_validate(r) for r in reminders]


@router.patch("/{reminder_id}/dismiss", response_model=ReminderResponse)
def dismiss_reminder(
    reminder_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    from fastapi import HTTPException
    reminder = db.query(Reminder).filter_by(id=reminder_id, family_id=user.family_id).first()
    if not reminder:
        raise HTTPException(status_code=404, detail="提醒不存在")
    reminder.status = "dismissed"
    reminder.dismissed_at = datetime.now()
    db.commit()
    db.refresh(reminder)
    return ReminderResponse.model_validate(reminder)
```

- [ ] **Step 4: 在 `main.py` 注册三个新 router**

在现有 `include_router` 列表末尾追加：

```python
from app.routers import notification_channels as notification_channels_router
from app.routers import notification_config as notification_config_router
from app.routers import reminders as reminders_router

app.include_router(notification_channels_router.router, prefix="/api/v1")
app.include_router(notification_config_router.router, prefix="/api/v1")
app.include_router(reminders_router.router, prefix="/api/v1")
```

- [ ] **Step 5: 在 `conftest.py` 导入新模型确保建表**

在现有 model import 块末尾追加：

```python
from app.models.notification_channel import NotificationChannel  # noqa: F401
from app.models.notification_subscription import NotificationSubscription  # noqa: F401
from app.models.notification_config import NotificationConfig  # noqa: F401
from app.models.reminder import Reminder  # noqa: F401
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/notification_channels.py \
        backend/app/routers/notification_config.py \
        backend/app/routers/reminders.py \
        backend/app/main.py \
        backend/tests/conftest.py
git commit -m "feat(phase4): add notification channels, config, and reminders API routers"
```

---

## Task 10: API 测试

**Files:**
- Create: `backend/tests/test_notification_channels.py`
- Create: `backend/tests/test_reminders.py`

- [ ] **Step 1: 创建 `test_notification_channels.py`**

```python
# backend/tests/test_notification_channels.py
import pytest

def test_create_telegram_channel(client, auth_headers):
    resp = client.post("/api/v1/notification-channels", headers=auth_headers, json={
        "channel_type": "telegram",
        "name": "家庭群",
        "config": {"bot_token": "fake_token", "chat_id": "123456"},
        "is_enabled": True,
        "subscriptions": ["maturity", "expiring_soon"],
    })
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["channel_type"] == "telegram"
    assert set(data["subscriptions"]) == {"maturity", "expiring_soon"}

def test_list_channels(client, auth_headers):
    client.post("/api/v1/notification-channels", headers=auth_headers, json={
        "channel_type": "email",
        "name": "邮件通知",
        "config": {"smtp_host": "smtp.example.com", "smtp_port": 587,
                   "smtp_user": "u", "smtp_password": "p",
                   "smtp_from": "from@example.com", "to": "to@example.com"},
        "is_enabled": True,
        "subscriptions": ["large_purchase"],
    })
    resp = client.get("/api/v1/notification-channels", headers=auth_headers)
    assert resp.status_code == 200
    assert len(resp.json()["data"]) >= 1

def test_update_channel(client, auth_headers):
    create_resp = client.post("/api/v1/notification-channels", headers=auth_headers, json={
        "channel_type": "telegram",
        "name": "旧名称",
        "config": {"bot_token": "t", "chat_id": "1"},
        "is_enabled": True,
        "subscriptions": [],
    })
    channel_id = create_resp.json()["data"]["id"]
    resp = client.put(f"/api/v1/notification-channels/{channel_id}", headers=auth_headers, json={
        "name": "新名称",
        "is_enabled": False,
    })
    assert resp.status_code == 200
    assert resp.json()["data"]["name"] == "新名称"
    assert resp.json()["data"]["is_enabled"] is False

def test_delete_channel(client, auth_headers):
    create_resp = client.post("/api/v1/notification-channels", headers=auth_headers, json={
        "channel_type": "telegram",
        "name": "待删除",
        "config": {"bot_token": "t", "chat_id": "1"},
        "is_enabled": True,
        "subscriptions": [],
    })
    channel_id = create_resp.json()["data"]["id"]
    resp = client.delete(f"/api/v1/notification-channels/{channel_id}", headers=auth_headers)
    assert resp.status_code == 204
    list_resp = client.get("/api/v1/notification-channels", headers=auth_headers)
    ids = [c["id"] for c in list_resp.json()["data"]]
    assert channel_id not in ids
```

- [ ] **Step 2: 创建 `test_reminders.py`**

```python
# backend/tests/test_reminders.py
import pytest

def test_get_reminder_summary_empty(client, auth_headers):
    resp = client.get("/api/v1/reminders/summary", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["total"] == 0

def test_list_reminders_empty(client, auth_headers):
    resp = client.get("/api/v1/reminders", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["data"] == []

def test_get_notification_config_default(client, auth_headers):
    resp = client.get("/api/v1/notification-config", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["large_purchase_threshold_fixed"] is None

def test_update_notification_config(client, auth_headers):
    resp = client.put("/api/v1/notification-config", headers=auth_headers, json={
        "large_purchase_threshold_fixed": 5000.0,
        "large_purchase_threshold_multiplier": 2.0,
    })
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["large_purchase_threshold_fixed"] == 5000.0

def test_dismiss_reminder(client, auth_headers, db):
    from app.models.reminder import Reminder
    from app.utils.snowflake import next_id
    # 直接插入一条 reminder
    from app.models.user import User
    user = db.query(User).first()
    r = Reminder(
        id=next_id(),
        family_id=user.family_id,
        reminder_type="maturity",
        title="测试到期",
        body="测试内容",
        severity="warning",
    )
    db.add(r)
    db.commit()

    resp = client.patch(f"/api/v1/reminders/{r.id}/dismiss", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "dismissed"
```

- [ ] **Step 3: 运行新测试**

```bash
cd backend && uv run pytest tests/test_notification_channels.py tests/test_reminders.py -v
```

Expected: 所有测试 `passed`

- [ ] **Step 4: 运行全量测试确认无回归**

```bash
cd backend && uv run pytest tests/ -v --tb=short 2>&1 | tail -20
```

Expected: 无新增失败

- [ ] **Step 5: Commit**

```bash
git add backend/tests/test_notification_channels.py backend/tests/test_reminders.py
git commit -m "feat(phase4): add API tests for notification channels and reminders"
```


---

## Task 11: 前端 API 层 + Store

**Files:**
- Create: `frontend/src/api/reminders.ts`
- Create: `frontend/src/api/notificationChannels.ts`
- Create: `frontend/src/stores/reminders.ts`

- [ ] **Step 1: 创建 `api/reminders.ts`**

```typescript
// frontend/src/api/reminders.ts
import axios from '@/utils/axios'

export interface ReminderResponse {
  id: number
  family_id: number
  reminder_type: 'large_purchase' | 'allocation_drift' | 'expiring_soon' | 'maturity'
  title: string
  body: string
  severity: 'info' | 'warning' | 'critical'
  asset_id: number | null
  status: 'active' | 'dismissed' | 'resolved'
  dismissed_at: string | null
  resolved_at: string | null
  created_at: string
}

export interface ReminderSummary {
  large_purchase: number
  allocation_drift: number
  expiring_soon: number
  maturity: number
  total: number
}

export const remindersApi = {
  getSummary(): Promise<ReminderSummary> {
    return axios.get('/api/v1/reminders/summary').then((r) => r.data.data)
  },
  list(status = 'active'): Promise<ReminderResponse[]> {
    return axios.get('/api/v1/reminders', { params: { status } }).then((r) => r.data.data)
  },
  dismiss(id: number): Promise<ReminderResponse> {
    return axios.patch(`/api/v1/reminders/${id}/dismiss`).then((r) => r.data.data)
  },
}
```

- [ ] **Step 2: 创建 `api/notificationChannels.ts`**

```typescript
// frontend/src/api/notificationChannels.ts
import axios from '@/utils/axios'

export interface NotificationChannelResponse {
  id: number
  family_id: number
  channel_type: 'telegram' | 'email'
  name: string
  is_enabled: boolean
  subscriptions: string[]
  created_at: string
  updated_at: string
}

export interface NotificationChannelCreate {
  channel_type: 'telegram' | 'email'
  name: string
  config: Record<string, string | number>
  is_enabled?: boolean
  subscriptions?: string[]
}

export interface NotificationChannelUpdate {
  name?: string
  config?: Record<string, string | number>
  is_enabled?: boolean
  subscriptions?: string[]
}

export interface NotificationConfig {
  id: number
  family_id: number
  large_purchase_threshold_fixed: number | null
  large_purchase_threshold_multiplier: number | null
  updated_at: string
}

export const notificationChannelsApi = {
  list(): Promise<NotificationChannelResponse[]> {
    return axios.get('/api/v1/notification-channels').then((r) => r.data.data)
  },
  create(data: NotificationChannelCreate): Promise<NotificationChannelResponse> {
    return axios.post('/api/v1/notification-channels', data).then((r) => r.data.data)
  },
  update(id: number, data: NotificationChannelUpdate): Promise<NotificationChannelResponse> {
    return axios.put(`/api/v1/notification-channels/${id}`, data).then((r) => r.data.data)
  },
  remove(id: number): Promise<void> {
    return axios.delete(`/api/v1/notification-channels/${id}`)
  },
  getConfig(): Promise<NotificationConfig> {
    return axios.get('/api/v1/notification-config').then((r) => r.data.data)
  },
  updateConfig(data: { large_purchase_threshold_fixed?: number | null; large_purchase_threshold_multiplier?: number | null }): Promise<NotificationConfig> {
    return axios.put('/api/v1/notification-config', data).then((r) => r.data.data)
  },
}
```

- [ ] **Step 3: 创建 `stores/reminders.ts`**

```typescript
// frontend/src/stores/reminders.ts
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { remindersApi, type ReminderResponse, type ReminderSummary } from '@/api/reminders'

export const useRemindersStore = defineStore('reminders', () => {
  const summary = ref<ReminderSummary>({ large_purchase: 0, allocation_drift: 0, expiring_soon: 0, maturity: 0, total: 0 })
  const reminders = ref<ReminderResponse[]>([])
  const loading = ref(false)

  async function fetchSummary() {
    summary.value = await remindersApi.getSummary()
  }

  async function fetchReminders() {
    loading.value = true
    try {
      reminders.value = await remindersApi.list()
    } finally {
      loading.value = false
    }
  }

  async function dismiss(id: number) {
    await remindersApi.dismiss(id)
    reminders.value = reminders.value.filter((r) => r.id !== id)
    await fetchSummary()
  }

  return { summary, reminders, loading, fetchSummary, fetchReminders, dismiss }
})
```

- [ ] **Step 4: 运行 typecheck 确认无类型错误**

```bash
cd frontend && npm run typecheck
```

Expected: 无错误

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/reminders.ts \
        frontend/src/api/notificationChannels.ts \
        frontend/src/stores/reminders.ts
git commit -m "feat(phase4): add reminders API, notification channels API, and reminders store"
```

---

## Task 12: i18n 文案

**Files:**
- Modify: `frontend/src/i18n/locales/zh-CN.ts`
- Modify: `frontend/src/i18n/locales/en-US.ts`

- [ ] **Step 1: 在 `zh-CN.ts` 的 `toast` 和新增 `reminders` 节点中添加文案**

在 `toast` 对象中追加：
```typescript
reminderDismissed: '🔕 已忽略该提醒',
channelSaved: '✅ 渠道配置已保存',
channelDeleted: '🗑️ 渠道已删除',
configSaved: '✅ 通知配置已保存',
```

在顶层追加 `reminders` 节点：
```typescript
reminders: {
  title: '智能提醒',
  empty: '暂无提醒',
  dismiss: '忽略',
  types: {
    large_purchase: '大额消费',
    allocation_drift: '配置失衡',
    expiring_soon: '保修到期',
    maturity: '理财到期',
  },
  severity: {
    info: '提示',
    warning: '警告',
    critical: '紧急',
  },
  notificationSettings: '通知设置',
  channelType: {
    telegram: 'Telegram',
    email: '邮件',
  },
  subscriptions: '订阅事件',
  thresholdFixed: '固定金额阈值（元）',
  thresholdMultiplier: '月均支出倍数',
},
```

- [ ] **Step 2: 在 `en-US.ts` 添加对应英文**

在 `toast` 对象中追加：
```typescript
reminderDismissed: '🔕 Reminder dismissed',
channelSaved: '✅ Channel saved',
channelDeleted: '🗑️ Channel deleted',
configSaved: '✅ Config saved',
```

在顶层追加 `reminders` 节点：
```typescript
reminders: {
  title: 'Smart Reminders',
  empty: 'No reminders',
  dismiss: 'Dismiss',
  types: {
    large_purchase: 'Large Purchase',
    allocation_drift: 'Allocation Drift',
    expiring_soon: 'Warranty Expiring',
    maturity: 'Maturity',
  },
  severity: {
    info: 'Info',
    warning: 'Warning',
    critical: 'Critical',
  },
  notificationSettings: 'Notification Settings',
  channelType: {
    telegram: 'Telegram',
    email: 'Email',
  },
  subscriptions: 'Subscribe to events',
  thresholdFixed: 'Fixed threshold (¥)',
  thresholdMultiplier: 'Monthly spend multiplier',
},
```

- [ ] **Step 3: 运行 typecheck**

```bash
cd frontend && npm run typecheck
```

Expected: 无错误

- [ ] **Step 4: Commit**

```bash
git add frontend/src/i18n/locales/zh-CN.ts frontend/src/i18n/locales/en-US.ts
git commit -m "feat(phase4): add i18n strings for reminders and notification settings"
```

---

## Task 13: 总览页 SmartRemindersCard 组件

**Files:**
- Create: `frontend/src/components/dashboard/SmartRemindersCard.vue`
- Modify: `frontend/src/pages/DashboardPage.vue`

- [ ] **Step 1: 创建 `SmartRemindersCard.vue`**

```vue
<!-- frontend/src/components/dashboard/SmartRemindersCard.vue -->
<template>
  <van-cell-group inset class="chart-section">
    <van-collapse v-model="expanded" @change="onToggle">
      <van-collapse-item name="reminders">
        <template #title>
          <span>🔔 {{ t('reminders.title') }}</span>
          <span v-if="store.summary.total > 0" class="reminder-summary">
            <template v-if="store.summary.expiring_soon > 0">到期 {{ store.summary.expiring_soon }}</template>
            <template v-if="store.summary.maturity > 0"> · 理财 {{ store.summary.maturity }}</template>
            <template v-if="store.summary.allocation_drift > 0"> · 失衡 {{ store.summary.allocation_drift }}</template>
            <template v-if="store.summary.large_purchase > 0"> · 冷静期 {{ store.summary.large_purchase }}</template>
          </span>
          <span v-else class="reminder-summary reminder-summary--empty">暂无提醒</span>
        </template>

        <van-loading v-if="store.loading" size="24px" class="reminder-loading" />
        <van-empty v-else-if="store.reminders.length === 0" :description="t('reminders.empty')" image-size="60" />
        <template v-else>
          <van-swipe-cell
            v-for="reminder in store.reminders"
            :key="reminder.id"
          >
            <van-cell
              :title="reminder.title"
              :label="reminder.body"
              :icon="severityIcon(reminder.severity)"
            />
            <template #right>
              <van-button
                square
                type="warning"
                :text="t('reminders.dismiss')"
                class="dismiss-btn"
                @click="onDismiss(reminder.id)"
              />
            </template>
          </van-swipe-cell>
        </template>
      </van-collapse-item>
    </van-collapse>
  </van-cell-group>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRemindersStore } from '@/stores/reminders'

const { t } = useI18n()
const store = useRemindersStore()
const expanded = ref<string[]>([])
const loaded = ref(false)

onMounted(() => {
  store.fetchSummary()
})

async function onToggle(names: string[]) {
  if (names.includes('reminders') && !loaded.value) {
    loaded.value = true
    await store.fetchReminders()
  }
}

async function onDismiss(id: number) {
  await store.dismiss(id)
}

function severityIcon(severity: string): string {
  if (severity === 'critical') return 'warning-o'
  if (severity === 'warning') return 'info-o'
  return 'bell'
}
</script>

<style scoped>
.reminder-summary {
  margin-left: 8px;
  font-size: 12px;
  color: var(--van-text-color-2);
}
.reminder-summary--empty {
  color: var(--van-text-color-3);
}
.reminder-loading {
  display: flex;
  justify-content: center;
  padding: 16px;
}
.dismiss-btn {
  height: 100%;
}
</style>
```

- [ ] **Step 2: 在 `DashboardPage.vue` 的 AlertCards 下方插入 SmartRemindersCard**

找到 `<!-- Alert Cards: Idle + Expiring Soon -->` 块，在其后插入：

```vue
<!-- Smart Reminders -->
<SmartRemindersCard />
```

在 `<script setup>` 中追加导入：

```typescript
import SmartRemindersCard from '@/components/dashboard/SmartRemindersCard.vue'
```

- [ ] **Step 3: 运行 typecheck**

```bash
cd frontend && npm run typecheck
```

Expected: 无错误

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/dashboard/SmartRemindersCard.vue \
        frontend/src/pages/DashboardPage.vue
git commit -m "feat(phase4): add SmartRemindersCard to dashboard"
```

---

## Task 14: 通知配置页 + 路由 + 设置页入口

**Files:**
- Create: `frontend/src/pages/NotificationConfigPage.vue`
- Modify: `frontend/src/router/index.ts`
- Modify: `frontend/src/pages/SettingsPage.vue`
- Modify: `frontend/src/pages/AssetFormPage.vue`

- [ ] **Step 1: 创建 `NotificationConfigPage.vue`**

```vue
<!-- frontend/src/pages/NotificationConfigPage.vue -->
<template>
  <van-nav-bar :title="t('reminders.notificationSettings')" left-arrow @click-left="$router.back()" />

  <div class="page-content">
    <!-- 大额消费阈值配置 -->
    <van-cell-group inset :title="'大额消费阈值'" class="section">
      <van-field
        v-model="fixedThreshold"
        :label="t('reminders.thresholdFixed')"
        type="number"
        placeholder="如 5000"
        clearable
      />
      <van-field
        v-model="multiplierThreshold"
        :label="t('reminders.thresholdMultiplier')"
        type="number"
        placeholder="如 2（月均支出的2倍）"
        clearable
      />
      <van-cell>
        <van-button type="primary" size="small" block @click="saveConfig">保存阈值配置</van-button>
      </van-cell>
    </van-cell-group>

    <!-- 渠道列表 -->
    <van-cell-group inset title="通知渠道" class="section">
      <van-swipe-cell
        v-for="channel in channels"
        :key="channel.id"
      >
        <van-cell
          :title="channel.name"
          :label="`${t('reminders.channelType.' + channel.channel_type)} · ${channel.subscriptions.map(s => t('reminders.types.' + s)).join('、')}`"
          :value="channel.is_enabled ? '已启用' : '已停用'"
          is-link
          @click="editChannel(channel)"
        />
        <template #right>
          <van-button
            square
            type="danger"
            text="删除"
            class="delete-btn"
            @click="removeChannel(channel.id)"
          />
        </template>
      </van-swipe-cell>
      <van-cell title="添加渠道" is-link icon="plus" @click="showAddSheet = true" />
    </van-cell-group>
  </div>

  <!-- 添加/编辑渠道弹窗 -->
  <van-popup v-model:show="showAddSheet" position="bottom" round :style="{ height: '70%' }">
    <div class="popup-content">
      <van-nav-bar :title="editingChannel ? '编辑渠道' : '添加渠道'" @click-right="showAddSheet = false">
        <template #right><van-icon name="cross" /></template>
      </van-nav-bar>
      <van-cell-group inset>
        <van-field v-model="form.name" label="渠道名称" placeholder="如：家庭群" />
        <van-field v-if="!editingChannel" v-model="form.channel_type" label="渠道类型" readonly is-link @click="showTypePicker = true" />
        <!-- Telegram 配置 -->
        <template v-if="form.channel_type === 'telegram'">
          <van-field v-model="form.bot_token" label="Bot Token" placeholder="从 @BotFather 获取" type="password" />
          <van-field v-model="form.chat_id" label="Chat ID" placeholder="数字 ID" />
        </template>
        <!-- 邮件配置 -->
        <template v-if="form.channel_type === 'email'">
          <van-field v-model="form.smtp_host" label="SMTP 服务器" placeholder="smtp.example.com" />
          <van-field v-model="form.smtp_port" label="端口" type="number" placeholder="587" />
          <van-field v-model="form.smtp_user" label="用户名" />
          <van-field v-model="form.smtp_password" label="密码" type="password" />
          <van-field v-model="form.smtp_from" label="发件人" placeholder="from@example.com" />
          <van-field v-model="form.email_to" label="收件人" placeholder="to@example.com" />
        </template>
        <!-- 订阅事件 -->
        <van-cell title="订阅事件">
          <template #value>
            <van-checkbox-group v-model="form.subscriptions" direction="horizontal">
              <van-checkbox v-for="type in reminderTypes" :key="type" :name="type" shape="square">
                {{ t('reminders.types.' + type) }}
              </van-checkbox>
            </van-checkbox-group>
          </template>
        </van-cell>
        <van-cell>
          <van-button type="primary" block @click="saveChannel">保存</van-button>
        </van-cell>
      </van-cell-group>
    </div>
  </van-popup>

  <!-- 渠道类型选择器 -->
  <van-popup v-model:show="showTypePicker" position="bottom" round>
    <van-picker
      :columns="[{ values: ['telegram', 'email'], text: (v: string) => t('reminders.channelType.' + v) }]"
      @confirm="onTypeConfirm"
      @cancel="showTypePicker = false"
    />
  </van-popup>
</template>

<script setup lang="ts">
import { ref, onMounted, reactive } from 'vue'
import { useI18n } from 'vue-i18n'
import { showToast } from 'vant'
import {
  notificationChannelsApi,
  type NotificationChannelResponse,
} from '@/api/notificationChannels'

const { t } = useI18n()

const channels = ref<NotificationChannelResponse[]>([])
const fixedThreshold = ref('')
const multiplierThreshold = ref('')
const showAddSheet = ref(false)
const showTypePicker = ref(false)
const editingChannel = ref<NotificationChannelResponse | null>(null)

const reminderTypes = ['large_purchase', 'allocation_drift', 'expiring_soon', 'maturity']

const form = reactive({
  name: '',
  channel_type: 'telegram' as 'telegram' | 'email',
  bot_token: '',
  chat_id: '',
  smtp_host: '',
  smtp_port: '587',
  smtp_user: '',
  smtp_password: '',
  smtp_from: '',
  email_to: '',
  subscriptions: [] as string[],
})

onMounted(async () => {
  channels.value = await notificationChannelsApi.list()
  const config = await notificationChannelsApi.getConfig()
  fixedThreshold.value = config.large_purchase_threshold_fixed?.toString() ?? ''
  multiplierThreshold.value = config.large_purchase_threshold_multiplier?.toString() ?? ''
})

async function saveConfig() {
  await notificationChannelsApi.updateConfig({
    large_purchase_threshold_fixed: fixedThreshold.value ? parseFloat(fixedThreshold.value) : null,
    large_purchase_threshold_multiplier: multiplierThreshold.value ? parseFloat(multiplierThreshold.value) : null,
  })
  showToast(t('toast.configSaved'))
}

function editChannel(channel: NotificationChannelResponse) {
  editingChannel.value = channel
  form.name = channel.name
  form.channel_type = channel.channel_type
  form.subscriptions = [...channel.subscriptions]
  showAddSheet.value = true
}

async function saveChannel() {
  const config: Record<string, string | number> =
    form.channel_type === 'telegram'
      ? { bot_token: form.bot_token, chat_id: form.chat_id }
      : {
          smtp_host: form.smtp_host,
          smtp_port: parseInt(form.smtp_port),
          smtp_user: form.smtp_user,
          smtp_password: form.smtp_password,
          smtp_from: form.smtp_from,
          to: form.email_to,
        }

  if (editingChannel.value) {
    const updated = await notificationChannelsApi.update(editingChannel.value.id, {
      name: form.name,
      config,
      subscriptions: form.subscriptions,
    })
    const idx = channels.value.findIndex((c) => c.id === editingChannel.value!.id)
    if (idx >= 0) channels.value[idx] = updated
  } else {
    const created = await notificationChannelsApi.create({
      channel_type: form.channel_type,
      name: form.name,
      config,
      subscriptions: form.subscriptions,
    })
    channels.value.push(created)
  }
  showToast(t('toast.channelSaved'))
  showAddSheet.value = false
  editingChannel.value = null
}

async function removeChannel(id: number) {
  await notificationChannelsApi.remove(id)
  channels.value = channels.value.filter((c) => c.id !== id)
  showToast(t('toast.channelDeleted'))
}

function onTypeConfirm({ selectedValues }: { selectedValues: string[] }) {
  form.channel_type = selectedValues[0] as 'telegram' | 'email'
  showTypePicker.value = false
}
</script>

<style scoped>
.page-content { padding-bottom: 32px; }
.section { margin-top: 12px; }
.delete-btn { height: 100%; }
.popup-content { height: 100%; overflow-y: auto; }
</style>
```

- [ ] **Step 2: 在 `router/index.ts` 注册路由**

在现有路由数组中追加：

```typescript
{
  path: '/settings/notifications',
  component: () => import('@/pages/NotificationConfigPage.vue'),
},
```

- [ ] **Step 3: 在 `SettingsPage.vue` 新增「通知设置」cell**

找到设置页中合适的 cell-group（通常是「账户」或「系统」分组），追加：

```vue
<van-cell
  :title="t('reminders.notificationSettings')"
  is-link
  icon="bell"
  @click="$router.push('/settings/notifications')"
/>
```

- [ ] **Step 4: 在 `AssetFormPage.vue` 新增 `warranty_expiry_date` 字段**

找到 `maturity_date` 相关的日期选择器，在其后追加保修到期日选择器（仅在 `asset_type === 'physical'` 时显示）：

```vue
<!-- 保修到期日（实物资产） -->
<van-field
  v-if="form.asset_type === 'physical'"
  v-model="form.warranty_expiry_date"
  label="保修到期日"
  placeholder="选择日期"
  readonly
  is-link
  @click="showWarrantyPicker = true"
/>
<van-popup v-model:show="showWarrantyPicker" position="bottom" round>
  <van-date-picker
    v-model="warrantyDateParts"
    title="保修到期日"
    @confirm="onWarrantyDateConfirm"
    @cancel="showWarrantyPicker = false"
  />
</van-popup>
```

在 `<script setup>` 中追加：

```typescript
const showWarrantyPicker = ref(false)
const warrantyDateParts = ref<string[]>([])

function onWarrantyDateConfirm({ selectedValues }: { selectedValues: string[] }) {
  form.warranty_expiry_date = selectedValues.join('-')
  showWarrantyPicker.value = false
}
```

在 `form` 对象中追加：

```typescript
warranty_expiry_date: '' as string,
```

- [ ] **Step 5: 运行 typecheck**

```bash
cd frontend && npm run typecheck
```

Expected: 无错误

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/NotificationConfigPage.vue \
        frontend/src/router/index.ts \
        frontend/src/pages/SettingsPage.vue \
        frontend/src/pages/AssetFormPage.vue
git commit -m "feat(phase4): add NotificationConfigPage, router, settings entry, and warranty_expiry_date field"
```


---

## Task 15: 发送重试逻辑

**Files:**
- Modify: `backend/app/models/reminder.py`
- Modify: `backend/app/services/notification/dispatcher.py`
- Modify: `backend/alembic/versions/xxxx_phase4_smart_reminders.py` (或新建迁移)

**背景：** Spec 要求发送失败后，下次 APScheduler 运行时重试未推送的 `active` reminder，最多重试 3 次后放弃推送（reminder 记录保留）。

- [ ] **Step 1: 在 `reminder.py` 新增 `send_retry_count` 字段**

在 `notified_channels` 行后追加：

```python
    send_retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
```

并在 import 中补充 `Integer`：

```python
from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text, func
```

- [ ] **Step 2: 生成并应用迁移**

```bash
cd backend && uv run alembic revision --autogenerate -m "add_send_retry_count_to_reminders"
cd backend && uv run alembic upgrade head
```

Expected: 无报错，`reminders` 表新增 `send_retry_count` 列

- [ ] **Step 3: 在 `dispatcher.py` 的 `run_scheduled_checks` 末尾追加重试逻辑**

在 `run_scheduled_checks` 函数末尾追加调用：

```python
    _retry_failed_notifications(db)
```

新增 `_retry_failed_notifications` 函数：

```python
def _retry_failed_notifications(db: Session) -> None:
    """重试尚未推送成功且重试次数 < 3 的 active reminders。"""
    MAX_RETRIES = 3
    pending = (
        db.query(Reminder)
        .filter(
            Reminder.status == "active",
            Reminder.send_retry_count < MAX_RETRIES,
        )
        .all()
    )
    for reminder in pending:
        notified = json.loads(reminder.notified_channels)
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
        all_notified = all(c.id in notified for c in channels)
        if all_notified or not channels:
            continue
        # 尝试重新发送未推送的渠道
        _dispatch_notifications(db, reminder, {})
        reminder.send_retry_count += 1
        if reminder.send_retry_count >= MAX_RETRIES:
            logger.info("提醒 %s 已达最大重试次数，放弃推送", reminder.id)
        db.commit()
```

- [ ] **Step 4: 运行全量测试确认无回归**

```bash
cd backend && uv run pytest tests/ -v --tb=short 2>&1 | tail -20
```

Expected: 无新增失败

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/reminder.py \
        backend/app/services/notification/dispatcher.py \
        backend/alembic/versions/
git commit -m "feat(phase4): add send retry logic for failed notification channels"
```

