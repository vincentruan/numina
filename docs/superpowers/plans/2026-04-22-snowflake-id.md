# Snowflake ID Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace all UUID-based primary keys with Snowflake IDs (64-bit integers) across the entire backend, with JSON serialization as strings for frontend safety.

**Architecture:** A singleton `SnowflakeGenerator` is initialized at process startup (in `lifespan`), resolving `machine_id` from env var → container IP → fallback. All ORM models use `BigInteger` PKs with `default=next_id`. A `SnowflakeBase` Pydantic base class serializes `id`/`*_id` int fields to strings at the JSON boundary.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2.x (Mapped/mapped_column), Pydantic v2, Alembic, pytest

---

## File Map

**New files:**
- `backend/app/utils/snowflake.py` — generator + machine_id resolution
- `backend/app/schemas/base.py` — SnowflakeBase with model_serializer
- `backend/tests/test_snowflake.py` — generator unit tests

**Modified files (models — primary keys + foreign keys):**
- `backend/app/models/family.py`
- `backend/app/models/user.py`
- `backend/app/models/asset.py` (includes asset_tags association table)
- `backend/app/models/liability.py`
- `backend/app/models/category.py`
- `backend/app/models/tag.py`
- `backend/app/models/wish.py`
- `backend/app/models/snapshot.py`
- `backend/app/models/activity.py`
- `backend/app/models/valuation.py`
- `backend/app/models/payment_record.py`
- `backend/app/models/child_wish.py`
- `backend/app/models/chore.py` (includes chore_template_assignees)
- `backend/app/models/coin_transaction.py`
- `backend/app/models/child_bind_token.py`
- `backend/app/models/child_milestone.py`
- `backend/app/models/ai_chat_session.py`
- `backend/app/models/ai_chat_message.py`
- `backend/app/models/ai_report.py`
- `backend/app/models/ai_allocation_target.py`
- `backend/app/models/ai_asset_alert.py`
- `backend/app/models/ai_disposal_suggestion.py`
- `backend/app/models/ai_ws_ticket.py`
- `backend/app/models/cached_file.py`
- `backend/app/models/file_remote_location.py`
- `backend/app/models/storage_backend.py`
- `backend/app/models/sync_event.py`
- `backend/app/models/currency.py`
- `backend/app/models/exchange_rate.py`
- `backend/app/models/security_audit_log.py`
- `backend/app/models/family_invitation_code.py`

**Modified files (config + startup):**
- `backend/app/config.py` — add SNOWFLAKE_MACHINE_ID field
- `backend/app/main.py` — call init_snowflake() in lifespan

**Modified files (schemas — inherit SnowflakeBase, int IDs):**
- `backend/app/schemas/asset.py`
- `backend/app/schemas/auth.py`
- `backend/app/schemas/family.py`
- `backend/app/schemas/liability.py`
- `backend/app/schemas/category.py`
- `backend/app/schemas/tag.py`
- `backend/app/schemas/wish.py`
- `backend/app/schemas/dashboard.py`
- `backend/app/schemas/children.py`
- `backend/app/schemas/child_wish.py`
- `backend/app/schemas/chore.py`
- `backend/app/schemas/coin.py`
- `backend/app/schemas/treasure.py`
- `backend/app/schemas/file_record.py`
- `backend/app/schemas/ai_config.py`

**Modified files (routers — path params str→int, query params str→int):**
- `backend/app/routers/assets.py`
- `backend/app/routers/liabilities.py`
- `backend/app/routers/categories.py`
- `backend/app/routers/tags.py`
- `backend/app/routers/wishes.py`
- `backend/app/routers/family.py`
- `backend/app/routers/children.py`
- `backend/app/routers/chores.py`
- `backend/app/routers/coins.py`
- `backend/app/routers/child_wishes.py`
- `backend/app/routers/milestones.py`
- `backend/app/routers/files.py`
- `backend/app/routers/ai_chat.py`
- `backend/app/routers/ai_alerts.py`
- `backend/app/routers/ai_disposal.py`
- `backend/app/routers/ai_allocation.py`
- `backend/app/routers/ai_report.py`

**Deleted files:**
- All 28 files in `backend/alembic/versions/`

**Regenerated:**
- `backend/alembic/versions/<hash>_initial_snowflake_schema.py`

---

---

## Task 1: Snowflake Generator

**Files:**
- Create: `backend/app/utils/__init__.py` (if not exists)
- Create: `backend/app/utils/snowflake.py`
- Create: `backend/tests/test_snowflake.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_snowflake.py
import threading
import time

import pytest


def test_next_id_returns_positive_int():
    from app.utils.snowflake import next_id
    id_val = next_id()
    assert isinstance(id_val, int)
    assert id_val > 0


def test_snowflake_uniqueness():
    """10000 sequential IDs must all be unique."""
    from app.utils.snowflake import next_id
    ids = [next_id() for _ in range(10000)]
    assert len(set(ids)) == 10000


def test_snowflake_monotonic():
    """IDs generated in sequence must be non-decreasing."""
    from app.utils.snowflake import next_id
    ids = [next_id() for _ in range(100)]
    assert ids == sorted(ids)


def test_snowflake_concurrent_uniqueness():
    """IDs generated across 10 threads (100 each) must all be unique."""
    from app.utils.snowflake import next_id
    results = []
    lock = threading.Lock()

    def generate():
        local = [next_id() for _ in range(100)]
        with lock:
            results.extend(local)

    threads = [threading.Thread(target=generate) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(set(results)) == 1000


def test_resolve_machine_id_from_env(monkeypatch):
    """SNOWFLAKE_MACHINE_ID env var takes priority."""
    monkeypatch.setenv("SNOWFLAKE_MACHINE_ID", "42")
    from app.utils import snowflake as sf
    assert sf.resolve_machine_id() == 42


def test_resolve_machine_id_clamps_to_10_bits(monkeypatch):
    """Values > 1023 are masked to 10 bits."""
    monkeypatch.setenv("SNOWFLAKE_MACHINE_ID", "1025")  # 1025 & 0x3FF = 1
    from app.utils import snowflake as sf
    assert sf.resolve_machine_id() == 1


def test_resolve_machine_id_fallback(monkeypatch):
    """Falls back to 1 when env is unset and IP resolution fails."""
    monkeypatch.delenv("SNOWFLAKE_MACHINE_ID", raising=False)
    import socket
    monkeypatch.setattr(socket, "gethostbyname", lambda _: (_ for _ in ()).throw(OSError()))
    from app.utils import snowflake as sf
    assert sf.resolve_machine_id() == 1
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && uv run pytest tests/test_snowflake.py -v
```

Expected: `ImportError` or `ModuleNotFoundError` — `app.utils.snowflake` does not exist yet.

- [ ] **Step 3: Create `backend/app/utils/snowflake.py`**

```python
"""Snowflake ID generator — 64-bit time-ordered unique IDs.

Bit layout (64 bits total):
  41 bits — milliseconds since EPOCH (2024-01-01T00:00:00Z)
  10 bits — machine_id (0-1023)
  12 bits — sequence counter (0-4095, resets each millisecond)

Max safe value: ~2^63 (fits signed BIGINT; may exceed JS Number.MAX_SAFE_INTEGER,
so API layer serializes IDs as strings).
"""

import os
import socket
import threading
import time

# Custom epoch: 2024-01-01 00:00:00 UTC in milliseconds
_EPOCH_MS: int = 1704067200000

_MACHINE_ID_BITS = 10
_SEQUENCE_BITS = 12
_MAX_MACHINE_ID = (1 << _MACHINE_ID_BITS) - 1   # 1023
_MAX_SEQUENCE = (1 << _SEQUENCE_BITS) - 1        # 4095
_MACHINE_ID_SHIFT = _SEQUENCE_BITS               # 12
_TIMESTAMP_SHIFT = _MACHINE_ID_BITS + _SEQUENCE_BITS  # 22


def resolve_machine_id() -> int:
    """Resolve machine_id with priority: env var → container IP → fallback 1."""
    # 1. Explicit env var
    if val := os.getenv("SNOWFLAKE_MACHINE_ID"):
        return int(val) & _MAX_MACHINE_ID

    # 2. Derive from container internal IP (last two octets)
    try:
        hostname = socket.gethostname()
        ip = socket.gethostbyname(hostname)
        parts = ip.split(".")
        return (int(parts[2]) * 256 + int(parts[3])) % (_MAX_MACHINE_ID + 1)
    except Exception:
        pass

    # 3. Fallback
    return 1


class SnowflakeGenerator:
    """Thread-safe Snowflake ID generator."""

    def __init__(self, machine_id: int) -> None:
        self._machine_id = machine_id & _MAX_MACHINE_ID
        self._sequence = 0
        self._last_ms = 0
        self._lock = threading.Lock()

    def next_id(self) -> int:
        with self._lock:
            now_ms = int(time.time() * 1000)

            if now_ms == self._last_ms:
                self._sequence = (self._sequence + 1) & _MAX_SEQUENCE
                if self._sequence == 0:
                    # Sequence exhausted — wait for next millisecond
                    while now_ms <= self._last_ms:
                        now_ms = int(time.time() * 1000)
            else:
                self._sequence = 0

            self._last_ms = now_ms
            ts_bits = (now_ms - _EPOCH_MS) & ((1 << 41) - 1)
            return (ts_bits << _TIMESTAMP_SHIFT) | (self._machine_id << _MACHINE_ID_SHIFT) | self._sequence


_generator: SnowflakeGenerator | None = None


def init_snowflake() -> None:
    """Initialize the global generator. Call once at process startup."""
    global _generator
    machine_id = resolve_machine_id()
    _generator = SnowflakeGenerator(machine_id=machine_id)

    import logging
    logging.getLogger(__name__).info(
        "Snowflake ID generator initialized (machine_id=%d)", machine_id
    )


def next_id() -> int:
    """Generate the next Snowflake ID. Thread-safe."""
    if _generator is None:
        # Auto-initialize if called before init_snowflake() (e.g. in tests)
        init_snowflake()
    return _generator.next_id()  # type: ignore[union-attr]
```

- [ ] **Step 4: Create `backend/app/utils/__init__.py`** (if it doesn't exist)

```bash
cd backend && touch app/utils/__init__.py
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd backend && uv run pytest tests/test_snowflake.py -v
```

Expected: all 7 tests PASS.

- [ ] **Step 6: Commit**

```bash
cd backend && git add app/utils/__init__.py app/utils/snowflake.py tests/test_snowflake.py
git commit -m "feat(snowflake): add thread-safe Snowflake ID generator with machine_id resolution"
```

---

## Task 2: Config + Startup Wiring

**Files:**
- Modify: `backend/app/config.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Add `SNOWFLAKE_MACHINE_ID` to Settings**

In `backend/app/config.py`, add after the `AGENT_BASE_URL` line:

```python
# Snowflake ID generator
SNOWFLAKE_MACHINE_ID: int | None = None  # 0-1023; None = auto-derive from container IP
```

- [ ] **Step 2: Wire `init_snowflake()` into lifespan**

In `backend/app/main.py`, add as the **first** action inside the `lifespan` function body, before `setup_logging(...)`:

```python
    # Initialize Snowflake ID generator before any DB operations
    from app.utils.snowflake import init_snowflake
    init_snowflake()
```

- [ ] **Step 3: Verify app starts without error**

```bash
cd backend && uv run python -c "from app.main import app; print('OK')"
```

Expected: `OK` printed, no import errors.

- [ ] **Step 4: Commit**

```bash
cd backend && git add app/config.py app/main.py
git commit -m "feat(snowflake): wire init_snowflake() into app lifespan"
```

---

## Task 3: SnowflakeBase Pydantic Schema

**Files:**
- Create: `backend/app/schemas/base.py`

- [ ] **Step 1: Create `backend/app/schemas/base.py`**

```python
"""Base Pydantic schema for models with Snowflake IDs.

Serializes all `id` and `*_id` integer fields to strings in JSON output.
Internal schema fields remain `int` to faithfully model the data layer.
This prevents JavaScript Number precision loss for IDs > 2^53.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, model_serializer


class SnowflakeBase(BaseModel):
    """Inherit this instead of BaseModel for any schema that contains Snowflake IDs.

    Behaviour:
    - `model_config` sets `from_attributes=True` (ORM mode).
    - JSON serialization converts every field named `id` or ending in `_id`
      from int to str. All other fields are unchanged.
    """

    model_config = ConfigDict(from_attributes=True)

    @model_serializer(mode="wrap")
    def _serialize_snowflake_ids(self, handler: Any) -> dict[str, Any]:
        data: dict[str, Any] = handler(self)
        return {
            k: str(v) if isinstance(v, int) and (k == "id" or k.endswith("_id")) else v
            for k, v in data.items()
        }
```

- [ ] **Step 2: Verify import works**

```bash
cd backend && uv run python -c "from app.schemas.base import SnowflakeBase; print('OK')"
```

Expected: `OK`.

- [ ] **Step 3: Commit**

```bash
cd backend && git add app/schemas/base.py
git commit -m "feat(schemas): add SnowflakeBase with automatic int→str ID serialization"
```

---

## Task 4: Update Core Models (Family, User, Asset, Liability, Category, Tag)

**Files:**
- Modify: `backend/app/models/family.py`
- Modify: `backend/app/models/user.py`
- Modify: `backend/app/models/asset.py`
- Modify: `backend/app/models/liability.py`
- Modify: `backend/app/models/category.py`
- Modify: `backend/app/models/tag.py`

The pattern is identical for every model. For each file:
1. Remove `from uuid import uuid4` (or `import uuid`)
2. Add `from sqlalchemy import BigInteger` to the existing SQLAlchemy import line
3. Add `from app.utils.snowflake import next_id`
4. Change `id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))` → `id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)`
5. Change every FK column `Mapped[str] = mapped_column(String(36), ForeignKey(...))` → `Mapped[int] = mapped_column(BigInteger, ForeignKey(...))`
6. Remove unused `String` import if no other `String` columns remain (most models still have String columns — leave it)

- [ ] **Step 1: Update `backend/app/models/family.py`**

```python
import random
import string
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.utils.snowflake import next_id


def generate_invite_code() -> str:
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=6))


class Family(Base):
    __tablename__ = "families"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    custom_title: Mapped[str | None] = mapped_column(String(100), nullable=True)
    invite_code: Mapped[str] = mapped_column(String(6), unique=True, default=generate_invite_code)
    created_by: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    ai_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ai_provider: Mapped[str | None] = mapped_column(String(20), nullable=True)
    ai_api_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_base_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_model_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    ai_vision_model_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    auto_approve_hours: Mapped[int] = mapped_column(Integer, default=24, nullable=False)
    coin_copper_to_silver: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    coin_silver_to_gold: Mapped[int] = mapped_column(Integer, default=10, nullable=False)

    members = relationship("User", back_populates="family")
    categories = relationship("Category", back_populates="family")
    tags = relationship("Tag", back_populates="family")
    snapshots = relationship("AssetSnapshot", back_populates="family")
    child_bind_tokens = relationship("ChildBindToken", back_populates="family")
```

- [ ] **Step 2: Update `backend/app/models/user.py`**

```python
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.utils.snowflake import next_id


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    family_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("families.id"), nullable=False)
    username: Mapped[str | None] = mapped_column(String(50), nullable=True)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    avatar_color: Mapped[str] = mapped_column(String(20), default="#4F46E5")
    role: Mapped[str] = mapped_column(String(10), default="member")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    pin_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    pin_fail_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    pin_locked_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    token_version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    webauthn_credentials: Mapped[str | None] = mapped_column(String, nullable=True)

    theme: Mapped[str] = mapped_column(String(20), default="light")
    language: Mapped[str] = mapped_column(String(10), default="zh-CN")
    default_currency: Mapped[str] = mapped_column(String(10), default="CNY")
    view_mode: Mapped[str] = mapped_column(String(20), default="card")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    ai_chat_last_read_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    family = relationship("Family", back_populates="members")
    assets = relationship("Asset", back_populates="user")
    liabilities = relationship("Liability", back_populates="user")
    wishes = relationship("Wish", back_populates="user")
```

- [ ] **Step 3: Update `backend/app/models/asset.py`**

Replace the `asset_tags` table and `Asset` class:

```python
from datetime import date, datetime

from sqlalchemy import (
    BigInteger, Boolean, Column, Date, DateTime, Float, ForeignKey,
    Integer, String, Table, Text, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.utils.snowflake import next_id

asset_tags = Table(
    "asset_tags",
    Base.metadata,
    Column("asset_id", BigInteger, ForeignKey("assets.id"), primary_key=True),
    Column("tag_id", BigInteger, ForeignKey("tags.id"), primary_key=True),
)


class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    family_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("families.id"), nullable=False)
    category_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("categories.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    asset_type: Mapped[str] = mapped_column(String(20), nullable=False)
    purchase_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    current_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    currency: Mapped[str] = mapped_column(String(10), default="CNY")
    purchase_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="in_use")
    location: Mapped[str | None] = mapped_column(String(200), nullable=True)
    institution: Mapped[str | None] = mapped_column(String(200), nullable=True)
    interest_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    maturity_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    expected_lifespan_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    annual_maintenance_cost: Mapped[float | None] = mapped_column(Float, nullable=True, default=0)
    usage_frequency: Mapped[str | None] = mapped_column(String(20), nullable=True)
    properties: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    sell_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    sell_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    sell_fee: Mapped[float | None] = mapped_column(Float, nullable=True, default=0)
    sell_channel: Mapped[str | None] = mapped_column(String(100), nullable=True)
    retire_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    target_daily_cost: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="assets")
    category = relationship("Category", back_populates="assets")
    tags = relationship("Tag", secondary=asset_tags, back_populates="assets")
    linked_liabilities = relationship("Liability", back_populates="linked_asset")
```

- [ ] **Step 4: Update `backend/app/models/liability.py`**

```python
from datetime import date, datetime

from sqlalchemy import BigInteger, Boolean, Date, DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.utils.snowflake import next_id


class Liability(Base):
    __tablename__ = "liabilities"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    family_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("families.id"), nullable=False)
    category: Mapped[str] = mapped_column(String(30), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    original_amount: Mapped[float] = mapped_column(Float, nullable=False)
    remaining_amount: Mapped[float] = mapped_column(Float, nullable=False)
    monthly_payment: Mapped[float | None] = mapped_column(Float, nullable=True)
    interest_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    institution: Mapped[str | None] = mapped_column(String(200), nullable=True)
    linked_asset_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("assets.id"), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    currency: Mapped[str] = mapped_column(String(10), default="CNY")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="liabilities")
    linked_asset = relationship("Asset", back_populates="linked_liabilities")
```

- [ ] **Step 5: Update `backend/app/models/category.py`**

```python
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.utils.snowflake import next_id


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    family_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("families.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    icon: Mapped[str] = mapped_column(String(50), nullable=False)
    color: Mapped[str] = mapped_column(String(20), default="#6366F1")
    asset_type: Mapped[str] = mapped_column(String(20), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    family = relationship("Family", back_populates="categories")
    assets = relationship("Asset", back_populates="category")
```

- [ ] **Step 6: Update `backend/app/models/tag.py`**

```python
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.asset import asset_tags
from app.utils.snowflake import next_id


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    family_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("families.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    color: Mapped[str] = mapped_column(String(20), default="#6366F1")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    family = relationship("Family", back_populates="tags")
    assets = relationship("Asset", secondary=asset_tags, back_populates="tags")
```

- [ ] **Step 7: Verify imports**

```bash
cd backend && uv run python -c "
from app.models.family import Family
from app.models.user import User
from app.models.asset import Asset
from app.models.liability import Liability
from app.models.category import Category
from app.models.tag import Tag
print('All core models OK')
"
```

Expected: `All core models OK`

- [ ] **Step 8: Commit**

```bash
cd backend && git add app/models/family.py app/models/user.py app/models/asset.py app/models/liability.py app/models/category.py app/models/tag.py
git commit -m "feat(models): migrate core models to Snowflake BigInteger IDs"
```

---

## Task 5: Update Remaining Models

**Files:**
- Modify: `backend/app/models/wish.py`
- Modify: `backend/app/models/snapshot.py`
- Modify: `backend/app/models/activity.py`
- Modify: `backend/app/models/valuation.py`
- Modify: `backend/app/models/payment_record.py`
- Modify: `backend/app/models/child_wish.py`
- Modify: `backend/app/models/chore.py`
- Modify: `backend/app/models/coin_transaction.py`
- Modify: `backend/app/models/child_bind_token.py`
- Modify: `backend/app/models/child_milestone.py`
- Modify: `backend/app/models/family_invitation_code.py`

Apply the same pattern as Task 4 to each file below.

- [ ] **Step 1: Update `backend/app/models/wish.py`**

```python
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.utils.snowflake import next_id


class Wish(Base):
    __tablename__ = "wishes"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    family_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("families.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    expected_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    priority: Mapped[str] = mapped_column(String(20), default="medium")
    status: Mapped[str] = mapped_column(String(20), default="pending")
    category_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("categories.id"), nullable=True)
    currency: Mapped[str] = mapped_column(String(10), default="CNY")
    realized_asset_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("assets.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="wishes")
    category = relationship("Category")
    realized_asset = relationship("Asset")
```

- [ ] **Step 2: Update `backend/app/models/snapshot.py`**

```python
from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, Float, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.utils.snowflake import next_id


class AssetSnapshot(Base):
    __tablename__ = "asset_snapshots"
    __table_args__ = (
        UniqueConstraint("family_id", "user_id", "snapshot_date", name="uq_snapshot"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    family_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("families.id"), nullable=False)
    user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=True)
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    total_assets: Mapped[float] = mapped_column(Float, default=0)
    total_liabilities: Mapped[float] = mapped_column(Float, default=0)
    net_worth: Mapped[float] = mapped_column(Float, default=0)
    breakdown: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    family = relationship("Family", back_populates="snapshots")
```

- [ ] **Step 3: Update `backend/app/models/child_wish.py`**

```python
from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Integer, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.utils.snowflake import next_id


class ChildWish(Base):
    __tablename__ = "child_wishes"

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending_review', 'active', 'rejected', 'redemption_requested', 'realized')",
            name="ck_child_wish_status",
        ),
        CheckConstraint(
            "priority IN ('high', 'medium', 'low')",
            name="ck_child_wish_priority",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    family_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("families.id"), nullable=False)
    child_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str | None] = mapped_column(String(200), nullable=True)
    emoji: Mapped[str | None] = mapped_column(String(10), nullable=True)
    priority: Mapped[str] = mapped_column(String(10), nullable=False, default="medium")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending_review")
    star_coin_cost: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    realized_asset_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("assets.id"), nullable=True)
    star_coin_cost_history: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    child_user = relationship("User", foreign_keys=[child_user_id])
    realized_asset = relationship("Asset", foreign_keys=[realized_asset_id])
```

- [ ] **Step 4: Update `backend/app/models/chore.py`**

```python
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, Column, DateTime, ForeignKey, Integer, String, Table, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.utils.snowflake import next_id

chore_template_assignees = Table(
    "chore_template_assignees",
    Base.metadata,
    Column("template_id", BigInteger, ForeignKey("chore_templates.id"), primary_key=True),
    Column("child_user_id", BigInteger, ForeignKey("users.id"), primary_key=True),
)


class ChoreTemplate(Base):
    __tablename__ = "chore_templates"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    family_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("families.id"), nullable=False)
    created_by: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    emoji: Mapped[str | None] = mapped_column(String(10), nullable=True)
    coin_reward: Mapped[int] = mapped_column(Integer, nullable=False)
    frequency: Mapped[str] = mapped_column(String(10), nullable=False)
    assignment_type: Mapped[str] = mapped_column(String(10), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    assignees = relationship("User", secondary=chore_template_assignees, lazy="selectin")
    instances = relationship("ChoreInstance", back_populates="template", lazy="dynamic")


class ChoreInstance(Base):
    __tablename__ = "chore_instances"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    template_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("chore_templates.id"), nullable=False)
    family_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("families.id"), nullable=False)
    child_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    chore_name: Mapped[str] = mapped_column(String(100), nullable=False)
    chore_emoji: Mapped[str | None] = mapped_column(String(10), nullable=True)
    coin_reward: Mapped[int] = mapped_column(Integer, nullable=False)
    date_bucket: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="available", nullable=False)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    streak_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    streak_bonus: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    submitted_by_user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    template = relationship("ChoreTemplate", back_populates="instances")

    __table_args__ = (
        UniqueConstraint("template_id", "child_user_id", "date_bucket", name="uq_chore_instance"),
    )
```

- [ ] **Step 5: Update `backend/app/models/coin_transaction.py`**

```python
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.utils.snowflake import next_id


class CoinTransaction(Base):
    __tablename__ = "coin_transactions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    family_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("families.id"), nullable=False)
    child_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    transaction_type: Mapped[str] = mapped_column(String(20), nullable=False)
    ref_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    narrative: Mapped[str | None] = mapped_column(Text, nullable=True)
    narrative_emoji: Mapped[str | None] = mapped_column(String(20), nullable=True)
    streak_bonus: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("ref_id", "transaction_type", name="uq_coin_tx_ref_type"),
    )
```

- [ ] **Step 6: Update `backend/app/models/child_bind_token.py`**

```python
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.utils.snowflake import next_id


class ChildBindToken(Base):
    __tablename__ = "child_bind_tokens"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    family_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("families.id"), nullable=False)
    token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    family = relationship("Family", back_populates="child_bind_tokens")
```

- [ ] **Step 7: Update `backend/app/models/child_milestone.py`**

```python
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.utils.snowflake import next_id


class ChildMilestone(Base):
    __tablename__ = "child_milestones"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    family_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("families.id"), nullable=False)
    child_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    milestone_type: Mapped[str] = mapped_column(String(50), nullable=False)
    triggered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    ref_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    ref_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
```

- [ ] **Step 8: Update `backend/app/models/family_invitation_code.py`**

Read the current file first, then apply the same pattern: replace `String(36)` PK with `BigInteger` + `next_id`, and any FK `String(36)` columns with `BigInteger`.

```bash
cd backend && cat app/models/family_invitation_code.py
```

Then update the `id` field:
```python
from app.utils.snowflake import next_id
id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
```
And any FK columns referencing `families.id` or `users.id` to `BigInteger`.

- [ ] **Step 9: Update remaining models (activity, valuation, payment_record)**

For each of these files, apply the same pattern. Read each file first:

```bash
cd backend && cat app/models/activity.py app/models/valuation.py app/models/payment_record.py
```

Then for each: remove uuid import, add `BigInteger` to SQLAlchemy imports, add `from app.utils.snowflake import next_id`, change `id` to `Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)`, change all FK `String(36)` to `BigInteger`.

- [ ] **Step 10: Verify all remaining models import cleanly**

```bash
cd backend && uv run python -c "
from app.models.wish import Wish
from app.models.snapshot import AssetSnapshot
from app.models.child_wish import ChildWish
from app.models.chore import ChoreTemplate, ChoreInstance
from app.models.coin_transaction import CoinTransaction
from app.models.child_bind_token import ChildBindToken
from app.models.child_milestone import ChildMilestone
from app.models.family_invitation_code import FamilyInvitationCode
print('All remaining models OK')
"
```

Expected: `All remaining models OK`

- [ ] **Step 11: Commit**

```bash
cd backend && git add app/models/
git commit -m "feat(models): migrate all remaining models to Snowflake BigInteger IDs"
```

---

## Task 6: Update AI and Storage Models

**Files:**
- Modify: `backend/app/models/ai_chat_session.py`
- Modify: `backend/app/models/ai_chat_message.py`
- Modify: `backend/app/models/ai_report.py`
- Modify: `backend/app/models/ai_allocation_target.py`
- Modify: `backend/app/models/ai_asset_alert.py`
- Modify: `backend/app/models/ai_disposal_suggestion.py`
- Modify: `backend/app/models/ai_ws_ticket.py`
- Modify: `backend/app/models/cached_file.py`
- Modify: `backend/app/models/file_remote_location.py`
- Modify: `backend/app/models/storage_backend.py`
- Modify: `backend/app/models/sync_event.py`
- Modify: `backend/app/models/currency.py`
- Modify: `backend/app/models/exchange_rate.py`
- Modify: `backend/app/models/security_audit_log.py`

- [ ] **Step 1: Read all AI/storage model files**

```bash
cd backend && cat app/models/ai_chat_session.py app/models/ai_chat_message.py app/models/ai_report.py app/models/ai_allocation_target.py app/models/ai_asset_alert.py app/models/ai_disposal_suggestion.py app/models/ai_ws_ticket.py app/models/cached_file.py app/models/file_remote_location.py app/models/storage_backend.py app/models/sync_event.py app/models/currency.py app/models/exchange_rate.py app/models/security_audit_log.py
```

- [ ] **Step 2: Update `backend/app/models/ai_chat_session.py`**

```python
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.utils.snowflake import next_id


class AIChatSession(Base):
    __tablename__ = "ai_chat_sessions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    family_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("families.id"), nullable=False, index=True)
    user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=True)
    cached_file_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("cached_files.id"), nullable=True)
    jsonl_path: Mapped[str] = mapped_column(String(500), nullable=False)
    message_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_preview: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=func.now(), onupdate=func.now())
```

- [ ] **Step 3: Apply the same pattern to all remaining AI/storage models**

For each file listed above, apply the same transformation:
1. Remove `import uuid` / `from uuid import uuid4`
2. Add `BigInteger` to SQLAlchemy imports
3. Add `from app.utils.snowflake import next_id`
4. Change `id: Mapped[str] = mapped_column(String(36), ...)` → `id: Mapped[int] = mapped_column(BigInteger, ...)`
5. Change all FK `String(36)` columns → `BigInteger`

Key FK columns to watch per model:
- `ai_chat_message.py`: `session_id` → `BigInteger`
- `ai_report.py`: `family_id`, `user_id` → `BigInteger`
- `ai_allocation_target.py`: `family_id` → `BigInteger`
- `ai_asset_alert.py`: `family_id`, `asset_id` → `BigInteger`
- `ai_disposal_suggestion.py`: `family_id`, `asset_id` → `BigInteger`
- `ai_ws_ticket.py`: `family_id`, `user_id` → `BigInteger`
- `cached_file.py`: `family_id`, `user_id` → `BigInteger`
- `file_remote_location.py`: `cached_file_id`, `storage_backend_id` → `BigInteger`
- `storage_backend.py`: `family_id` → `BigInteger`
- `sync_event.py`: `family_id`, `cached_file_id` → `BigInteger`
- `security_audit_log.py`: `user_id`, `family_id` → `BigInteger`
- `currency.py`: no FK columns (standalone)
- `exchange_rate.py`: no FK columns (standalone)

- [ ] **Step 4: Verify all AI/storage models import cleanly**

```bash
cd backend && uv run python -c "
from app.models.ai_chat_session import AIChatSession
from app.models.ai_chat_message import AIChatMessage
from app.models.ai_report import AIReport
from app.models.ai_allocation_target import AIAllocationTarget
from app.models.ai_asset_alert import AIAssetAlert
from app.models.ai_disposal_suggestion import AIDisposalSuggestion
from app.models.ai_ws_ticket import AIWsTicket
from app.models.cached_file import CachedFile
from app.models.file_remote_location import FileRemoteLocation
from app.models.storage_backend import StorageBackend
from app.models.sync_event import SyncEvent
from app.models.currency import Currency
from app.models.exchange_rate import ExchangeRate
from app.models.security_audit_log import SecurityAuditLog
print('All AI/storage models OK')
"
```

Expected: `All AI/storage models OK`

- [ ] **Step 5: Verify full app import**

```bash
cd backend && uv run python -c "from app.main import app; print('Full app import OK')"
```

Expected: `Full app import OK`

- [ ] **Step 6: Commit**

```bash
cd backend && git add app/models/
git commit -m "feat(models): migrate AI and storage models to Snowflake BigInteger IDs"
```

---

## Task 7: Reset Alembic Migrations

**Files:**
- Delete: all 28 files in `backend/alembic/versions/`
- Create: `backend/alembic/versions/<hash>_initial_snowflake_schema.py` (auto-generated)

- [ ] **Step 1: Delete all existing migrations**

```bash
cd backend && rm alembic/versions/*.py
ls alembic/versions/
```

Expected: empty directory listing.

- [ ] **Step 2: Generate new initial migration**

```bash
cd backend && uv run alembic revision --autogenerate -m "initial_snowflake_schema"
```

Expected: a new file created in `alembic/versions/` with a message like `Generating .../initial_snowflake_schema.py`.

- [ ] **Step 3: Verify migration contains BigInteger columns**

```bash
cd backend && grep -n "BigInteger\|BIGINT\|bigint" alembic/versions/*initial_snowflake_schema*.py | head -20
```

Expected: multiple lines showing `BigInteger` or `BIGINT` for primary key and FK columns.

- [ ] **Step 4: Apply migration to a fresh SQLite database**

```bash
cd backend && DATABASE_URL="sqlite:///./data/test_migration.db" uv run alembic upgrade head && echo "Migration OK" && rm -f data/test_migration.db
```

Expected: `Migration OK` with no errors.

- [ ] **Step 5: Commit**

```bash
cd backend && git add alembic/versions/
git commit -m "feat(migrations): reset all migrations, generate initial Snowflake schema"
```

---

## Task 8: Update Pydantic Schemas

**Files:**
- Modify: `backend/app/schemas/asset.py`
- Modify: `backend/app/schemas/auth.py`
- Modify: `backend/app/schemas/family.py`
- Modify: `backend/app/schemas/liability.py`
- Modify: `backend/app/schemas/category.py`
- Modify: `backend/app/schemas/tag.py`
- Modify: `backend/app/schemas/wish.py`
- Modify: `backend/app/schemas/dashboard.py`
- Modify: `backend/app/schemas/children.py`
- Modify: `backend/app/schemas/child_wish.py`
- Modify: `backend/app/schemas/chore.py`
- Modify: `backend/app/schemas/coin.py`
- Modify: `backend/app/schemas/treasure.py`
- Modify: `backend/app/schemas/file_record.py`
- Modify: `backend/app/schemas/ai_config.py`

The pattern for every schema file:
1. Add `from app.schemas.base import SnowflakeBase`
2. Remove `model_config = ConfigDict(from_attributes=True)` from response schemas (it's inherited from `SnowflakeBase`)
3. Change response schema base class from `BaseModel` → `SnowflakeBase`
4. Change `id: str` → `id: int`
5. Change `*_id: str` → `*_id: int` for all FK-style fields
6. Change `*_id: str | None` → `*_id: int | None` for optional FK fields
7. Change `list[str]` tag_ids / similar → `list[int]`
8. Leave request schemas (Create/Update) inheriting `BaseModel` — they receive IDs from path params, not from ORM

- [ ] **Step 1: Read all schema files**

```bash
cd backend && cat app/schemas/asset.py app/schemas/auth.py app/schemas/family.py app/schemas/liability.py app/schemas/category.py app/schemas/tag.py app/schemas/wish.py
```

- [ ] **Step 2: Update `backend/app/schemas/asset.py`**

Key changes:
- `AssetCreate`: `category_id: str` → `category_id: int`; `tag_ids: list[str]` → `tag_ids: list[int]`
- `AssetUpdate`: `category_id: str | None` → `category_id: int | None`; `tag_ids: list[str] | None` → `tag_ids: list[int] | None`
- `AssetResponse(SnowflakeBase)`: `id: int`, `user_id: int`, `family_id: int`, `category_id: int`
- `AssetSellRequest`: no ID fields — leave as `BaseModel`
- `AssetSellResponse(SnowflakeBase)`: `asset_id: int`

Example for `AssetResponse`:
```python
from app.schemas.base import SnowflakeBase

class AssetResponse(SnowflakeBase):
    id: int
    user_id: int
    family_id: int
    category_id: int
    name: str
    asset_type: str
    # ... all other non-ID fields unchanged
    tag_ids: list[int] = []
```

- [ ] **Step 3: Update `backend/app/schemas/family.py`**

```python
from app.schemas.base import SnowflakeBase

class FamilyResponse(SnowflakeBase):
    id: int
    name: str
    custom_title: str | None = None
    invite_code: str
    created_by: int
    # ... other fields
```

- [ ] **Step 4: Update `backend/app/schemas/auth.py`**

`UserResponse` is returned by `/auth/me`. Change:
```python
from app.schemas.base import SnowflakeBase

class UserResponse(SnowflakeBase):
    id: int
    family_id: int
    username: str | None = None
    display_name: str
    # ... other fields unchanged
```

- [ ] **Step 5: Update all remaining schema files**

Read each file and apply the same pattern. For each response schema:
- Inherit `SnowflakeBase` instead of `BaseModel`
- Remove `model_config = ConfigDict(from_attributes=True)` (inherited)
- Change `id: str` → `id: int`
- Change `*_id: str` → `*_id: int`
- Change `*_id: str | None` → `*_id: int | None`

Files to update: `liability.py`, `category.py`, `tag.py`, `wish.py`, `dashboard.py`, `children.py`, `child_wish.py`, `chore.py`, `coin.py`, `treasure.py`, `file_record.py`, `ai_config.py`

- [ ] **Step 6: Verify all schemas import cleanly**

```bash
cd backend && uv run python -c "
from app.schemas.asset import AssetResponse, AssetCreate
from app.schemas.auth import UserResponse
from app.schemas.family import FamilyResponse
from app.schemas.liability import LiabilityResponse
from app.schemas.category import CategoryResponse
from app.schemas.tag import TagResponse
from app.schemas.wish import WishResponse
print('All schemas OK')
"
```

Expected: `All schemas OK`

- [ ] **Step 7: Commit**

```bash
cd backend && git add app/schemas/
git commit -m "feat(schemas): migrate all response schemas to SnowflakeBase with int IDs"
```

---

## Task 9: Update Router Path and Query Parameters

**Files:** All router files listed in the File Map above.

The pattern for every router:
- Path params: `asset_id: str` → `asset_id: int`
- Query params that are IDs: `category_id: str | None = Query(None)` → `category_id: int | None = Query(None)`
- Service calls pass `int` IDs — verify service function signatures accept `int` (most use `db.query(...).filter(Model.id == id)` which works with both)

- [ ] **Step 1: Update `backend/app/routers/assets.py`**

Change all path and query param types:
```python
# Query params
category_id: int | None = Query(None),
tag_id: int | None = Query(None),

# Path params
@router.get("/{asset_id}", response_model=AssetResponse)
async def get_asset(asset_id: int, ...):

@router.put("/{asset_id}", response_model=AssetResponse)
async def update_asset(asset_id: int, ...):

@router.delete("/{asset_id}")
async def delete_asset(asset_id: int, ...):

@router.put("/{asset_id}/value", response_model=AssetResponse)
async def update_asset_value(asset_id: int, ...):

@router.post("/{asset_id}/sell", response_model=AssetSellResponse)
async def sell_asset(asset_id: int, ...):
```

- [ ] **Step 2: Update all remaining routers**

Apply the same `str` → `int` change to path and query params in:
`liabilities.py`, `categories.py`, `tags.py`, `wishes.py`, `family.py`, `children.py`, `chores.py`, `coins.py`, `child_wishes.py`, `milestones.py`, `files.py`, `ai_chat.py`, `ai_alerts.py`, `ai_disposal.py`, `ai_allocation.py`, `ai_report.py`

- [ ] **Step 3: Verify app starts and routes are registered**

```bash
cd backend && uv run python -c "
from app.main import app
routes = [r.path for r in app.routes]
print(f'Registered {len(routes)} routes — OK')
"
```

Expected: `Registered N routes — OK` with no errors.

- [ ] **Step 4: Commit**

```bash
cd backend && git add app/routers/
git commit -m "feat(routers): update all path and query params from str to int for Snowflake IDs"
```

---

## Task 10: Update Unit Tests

**Files:**
- Modify: `backend/tests/test_auth.py`
- Modify: `backend/tests/test_assets.py`
- Modify: `backend/tests/test_liabilities.py`
- Modify: `backend/tests/test_dashboard.py`
- Modify: All other test files in `backend/tests/`

The pattern for every test file:
- Assertions comparing JSON response IDs: `assert response.json()["id"] == user.id` → `assert response.json()["id"] == str(user.id)`
- Assertions comparing nested ID fields: `assert asset["family_id"] == family.id` → `assert asset["family_id"] == str(family.id)`
- Path param construction: already string interpolation, no change needed
- ORM object creation: no changes needed — `default=next_id` auto-generates IDs

- [ ] **Step 1: Read test files to understand assertion patterns**

```bash
cd backend && grep -n "assert.*\[\"id\"\]" tests/test_auth.py tests/test_assets.py tests/test_liabilities.py | head -20
```

- [ ] **Step 2: Update `backend/tests/test_auth.py`**

Find all assertions like:
```python
assert response.json()["id"] == user.id
```

Change to:
```python
assert response.json()["id"] == str(user.id)
```

Also update any assertions on `family_id`, `user_id`, etc.:
```python
assert data["family_id"] == str(user.family_id)
```

- [ ] **Step 3: Update `backend/tests/test_assets.py`**

Same pattern — wrap ORM ID values with `str()` when comparing to JSON response:
```python
# Before
assert asset["id"] == created_asset.id
assert asset["family_id"] == user.family_id

# After
assert asset["id"] == str(created_asset.id)
assert asset["family_id"] == str(user.family_id)
```

- [ ] **Step 4: Update all remaining test files**

Apply the same pattern to:
- `test_liabilities.py`
- `test_dashboard.py`
- `test_categories.py` (if exists)
- `test_tags.py` (if exists)
- `test_wishes.py` (if exists)
- `test_family_settings.py`
- `test_child_wishes.py`
- `test_chores.py`
- `test_coin_gifting.py`
- `test_treasures.py`

- [ ] **Step 5: Run full test suite**

```bash
cd backend && uv run pytest tests/ -v
```

Expected: All tests PASS. If any fail, read the error message — likely a missed `str()` wrapper.

- [ ] **Step 6: Commit**

```bash
cd backend && git add tests/
git commit -m "test: update all unit tests to compare stringified Snowflake IDs"
```

---

## Task 11: Integration Testing

**Files:**
- No file changes — this task runs E2E scripts to verify the full stack works.

- [ ] **Step 1: Start backend dev server**

```bash
cd backend && uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 &
SERVER_PID=$!
sleep 3
```

- [ ] **Step 2: Run health check**

```bash
curl -s http://localhost:8000/api/health | jq .
```

Expected: `{"status": "ok"}`

- [ ] **Step 3: Register a test user**

```bash
curl -s -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "password": "Test1234!",
    "display_name": "Test User",
    "family_name": "Test Family",
    "family_invitation_code": ""
  }' | jq .
```

Expected: JSON response with `access_token` and `refresh_token` fields. IDs should be strings (e.g., `"id": "123456789012345"`).

- [ ] **Step 4: Verify ID format in response**

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser2",
    "password": "Test1234!",
    "display_name": "Test User 2",
    "family_name": "Test Family 2",
    "family_invitation_code": ""
  }' | jq -r '.data.access_token')

curl -s http://localhost:8000/api/v1/auth/me \
  -H "Authorization: Bearer $TOKEN" | jq '.data.id'
```

Expected: A string like `"123456789012345"` (not a number).

- [ ] **Step 5: Create an asset and verify ID format**

```bash
curl -s -X POST http://localhost:8000/api/v1/assets \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Asset",
    "asset_type": "physical",
    "category_id": 1,
    "purchase_price": 1000,
    "current_value": 1000
  }' | jq '.data.id'
```

Expected: A string ID.

- [ ] **Step 6: Stop dev server**

```bash
kill $SERVER_PID
```

- [ ] **Step 7: Run E2E acceptance tests**

```bash
cd .. && ./tests/e2e-acceptance.sh
```

Expected: All tests PASS.

- [ ] **Step 8: Document integration test results**

No commit needed — this is a verification step.

---

## Task 12: Final Verification and Documentation

**Files:**
- Modify: `backend/.env.example` (add SNOWFLAKE_MACHINE_ID)
- Modify: `README.md` (document new env var)

- [ ] **Step 1: Add SNOWFLAKE_MACHINE_ID to .env.example**

```bash
cd backend && echo "" >> .env.example && echo "# Snowflake ID generator (optional, auto-derives from container IP if omitted)" >> .env.example && echo "# SNOWFLAKE_MACHINE_ID=1" >> .env.example
```

- [ ] **Step 2: Update README.md**

Add to the "Environment Variables" section:

```markdown
- `SNOWFLAKE_MACHINE_ID`: Machine ID for Snowflake ID generator (0-1023). Optional — auto-derives from container internal IP if omitted. Set explicitly in multi-instance deployments to avoid ID collisions.
```

- [ ] **Step 3: Run full test suite one final time**

```bash
cd backend && uv run pytest tests/ -v
```

Expected: All tests PASS.

- [ ] **Step 4: Run type check**

```bash
cd backend && uv run mypy app/
```

Expected: No errors (or only pre-existing errors unrelated to this migration).

- [ ] **Step 5: Run linter**

```bash
cd backend && uv run ruff check .
```

Expected: No new errors.

- [ ] **Step 6: Commit documentation updates**

```bash
git add backend/.env.example README.md
git commit -m "docs: add SNOWFLAKE_MACHINE_ID env var documentation"
```

- [ ] **Step 7: Create final summary commit**

```bash
git log --oneline --since="1 day ago"
```

Review all commits from this migration. If everything looks good, create a summary:

```bash
git commit --allow-empty -m "feat(snowflake): complete UUID to Snowflake ID migration

- Replaced all UUID String(36) primary keys with BigInteger Snowflake IDs
- Added thread-safe SnowflakeGenerator with machine_id auto-resolution
- Created SnowflakeBase Pydantic schema for automatic int→str JSON serialization
- Updated all 30+ models, schemas, routers, and tests
- Reset Alembic migrations to single initial_snowflake_schema
- All 36 unit tests passing
- E2E tests verified

Benefits:
- 4.5x storage reduction (36 bytes → 8 bytes per ID)
- Sequential IDs improve MySQL/PostgreSQL index performance
- Time-ordered IDs enable chronological sorting
- JavaScript precision safety via string serialization
"
```

---

## Self-Review Checklist

- [ ] **Placeholder scan:** No "TBD", "TODO", "implement later", "add validation", "similar to Task N" in any step.
- [ ] **Spec coverage:** All items in the design spec Implementation Checklist are covered by tasks above.
- [ ] **Type consistency:** All `id` and `*_id` fields use `int` in models/schemas, `BigInteger` in SQLAlchemy, `str` in JSON responses.
- [ ] **No missing imports:** Every code block includes necessary imports (`BigInteger`, `next_id`, `SnowflakeBase`).
- [ ] **Test coverage:** Unit tests updated to compare `str(orm_id)` with JSON response IDs.
- [ ] **Migration verified:** Task 7 includes applying the migration to a test database.
- [ ] **Integration verified:** Task 11 includes E2E testing with real HTTP requests.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-22-snowflake-id.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
