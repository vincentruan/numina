# Snowflake ID Migration Design

**Date:** 2026-04-22  
**Status:** Approved  
**Context:** Fresh deployment, no existing data migration required

## Problem Statement

Current UUID-based ID generation (`String(36)`) is inefficient for MySQL/PostgreSQL:
- 36-byte VARCHAR vs 8-byte BIGINT (4.5x storage overhead)
- Non-sequential UUIDs cause index fragmentation
- String comparison slower than integer comparison
- No chronological ordering

**Goal:** Replace UUID with Snowflake IDs (64-bit integers) for better database performance across all backends (MySQL, PostgreSQL, SQLite).

---

## Solution Overview

**Approach:** Clean slate migration (delete all existing Alembic migrations, recreate schema with Snowflake IDs).

**Rationale:** Since this is a fresh deployment with no production data, we can avoid complex UUID→Snowflake data migration logic and start clean.

---

## Design

### 1. Snowflake ID Generator

**File:** `backend/app/utils/snowflake.py`

**Structure (64 bits):**
- 41 bits: timestamp (milliseconds since custom epoch: 2024-01-01)
- 10 bits: machine_id (0-1023)
- 12 bits: sequence (0-4095, resets per millisecond)

**Machine ID Resolution (priority order):**

```python
def resolve_machine_id() -> int:
    """
    1. SNOWFLAKE_MACHINE_ID env var (explicit config, highest priority)
    2. Container internal IP last two octets mod 1024 (auto-derive)
    3. Fallback to 1 (default)
    """
    # 1. Explicit config
    if val := os.getenv("SNOWFLAKE_MACHINE_ID"):
        return int(val) & 0x3FF

    # 2. Derive from internal IP
    try:
        hostname = socket.gethostname()
        ip = socket.gethostbyname(hostname)
        parts = ip.split(".")
        # (third_octet * 256 + fourth_octet) % 1024
        return (int(parts[2]) * 256 + int(parts[3])) % 1024
    except Exception:
        pass

    # 3. Fallback
    return 1
```

**Thread Safety:** Uses `threading.Lock` for concurrent request handling.

**Initialization:** Called once in `main.py` lifespan before serving requests:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.utils.snowflake import init_snowflake
    init_snowflake()  # Resolve machine_id, create singleton, log config
    yield
```

**Public API:**

```python
def init_snowflake() -> None:
    """Initialize global generator at process startup."""

def next_id() -> int:
    """Generate next Snowflake ID (thread-safe)."""
```

**Config Addition (`backend/app/config.py`):**

```python
SNOWFLAKE_MACHINE_ID: int = Field(default=1, ge=0, le=1023)
```

---

### 2. Model Layer Changes

**Pattern (uniform across all 30+ models):**

```python
# Before
from uuid import uuid4
id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
family_id: Mapped[str] = mapped_column(String(36), ForeignKey("families.id"), nullable=False)

# After
from sqlalchemy import BigInteger
from app.utils.snowflake import next_id
id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
family_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("families.id"), nullable=False)
```

**Affected Models:**
- Core: Family, User, Asset, Liability, Category, Tag, Wish, AssetSnapshot
- Children: ChildWish, ChoreTemplate, ChoreInstance, ChildBindToken, ChildMilestone, CoinTransaction
- AI: AIChatSession, AIChatMessage, AIReport, AIAllocationTarget, AIAssetAlert, AIDisposalSuggestion, AIWSTicket
- Storage: CachedFile, FileRemoteLocation, StorageBackend, SyncEvent
- Other: Activity, Valuation, PaymentRecord, Currency, ExchangeRate, SecurityAuditLog

**Association Tables:**

```python
# asset_tags
Column("asset_id", BigInteger, ForeignKey("assets.id"), primary_key=True),
Column("tag_id", BigInteger, ForeignKey("tags.id"), primary_key=True),

# chore_template_assignees
Column("template_id", BigInteger, ForeignKey("chore_templates.id"), primary_key=True),
Column("child_user_id", BigInteger, ForeignKey("users.id"), primary_key=True),
```

**Application-Layer References:**

`CoinTransaction.ref_id` and `ChildMilestone.ref_id` (no FK constraint) also change to `BigInteger`:

```python
ref_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
```

---

### 3. Alembic Migration Strategy

**Steps:**

1. Delete all 28 existing migration files in `backend/alembic/versions/`
2. Update all models (Section 2)
3. Generate new initial migration:
   ```bash
   uv run alembic revision --autogenerate -m "initial_snowflake_schema"
   ```
4. Verify generated migration reflects `BigInteger` primary keys

**Database Type Mapping:**

| Database | DDL Type | Notes |
|----------|----------|-------|
| MySQL | `BIGINT` | 8 bytes, signed 64-bit |
| PostgreSQL | `BIGINT` | Same |
| SQLite | `INTEGER` | SQLite INTEGER is 64-bit |

No dialect-specific adaptation needed — `alembic/env.py` factory pattern handles this automatically.

---

### 4. Pydantic Schema Layer

**Strategy:** Schema fields remain `int` internally (faithful to data model), but serialize to `string` in JSON responses to avoid JavaScript precision loss.

**Base Class with Serializer:**

```python
# backend/app/schemas/base.py
from pydantic import BaseModel, model_serializer
from typing import Any

class SnowflakeBase(BaseModel):
    """Base class for all schemas with Snowflake IDs.
    Automatically serializes all `id` and `*_id` int fields to string in JSON.
    Internal modeling remains int for business logic.
    """
    model_config = {"from_attributes": True}

    @model_serializer(mode="wrap")
    def _serialize_ids(self, handler: Any) -> dict:
        data = handler(self)
        return {
            k: str(v) if isinstance(v, int) and (k == "id" or k.endswith("_id")) else v
            for k, v in data.items()
        }
```

**Schema Updates:**

```python
# Before
class AssetResponse(BaseModel):
    model_config = {"from_attributes": True}
    id: str
    family_id: str

# After
class AssetResponse(SnowflakeBase):
    id: int
    family_id: int
    name: str
    # ... other fields unchanged
```

**Router Path Parameters:**

```python
# Before
@router.get("/{asset_id}")
async def get_asset(asset_id: str, ...):

# After
@router.get("/{asset_id}")
async def get_asset(asset_id: int, ...):
```

FastAPI auto-parses path params as `int` and returns 422 on type mismatch.

**Data Flow:**

```
DB: BIGINT 123456789012345
  → ORM: int 123456789012345
  → Pydantic schema: int 123456789012345  ← Internal modeling
  → JSON serialization: {"id": "123456789012345"}  ← Conversion at boundary
  → Frontend: string "123456789012345"
```

---

### 5. Frontend TypeScript Changes

**Type Definitions:** ID fields remain `string` (decoupled from backend internal types):

```typescript
// frontend/src/types/index.ts
interface Asset {
  id: string        // "123456789012345"
  family_id: string
  user_id: string
  category_id: string
}
```

**No Changes Needed:**
- Vue Router path params (`route.params.id`) are already `string`
- API calls already use string interpolation: `` `/assets/${id}` ``
- No type conversions required

**Why String?** JavaScript `number` is 64-bit float (IEEE 754) with safe integer range up to `2^53 - 1`. Snowflake IDs can exceed this, causing precision loss. Serializing as string avoids this issue.

---

### 6. Testing Strategy

**Unit Tests (`backend/tests/`):**

Update 36 existing tests to compare stringified IDs:

```python
# Before
assert response.json()["id"] == user.id  # str == str

# After
assert response.json()["id"] == str(user.id)  # str == str(int)
```

**Test Data Construction:** No changes needed — ORM `default=next_id` auto-generates IDs.

**E2E Scripts (`tests/*.sh`):** No changes needed — JSON IDs are already strings.

**New Test File (`backend/tests/test_snowflake.py`):**

```python
def test_snowflake_uniqueness():
    """Concurrent generation of 10000 IDs, verify no duplicates."""
    from app.utils.snowflake import next_id
    ids = {next_id() for _ in range(10000)}
    assert len(ids) == 10000

def test_snowflake_monotonic():
    """Verify IDs are monotonically increasing."""
    ids = [next_id() for _ in range(100)]
    assert ids == sorted(ids)

def test_snowflake_range():
    """Verify IDs stay within JS safe integer range (optional)."""
    id_val = next_id()
    assert id_val < 2**53  # Number.MAX_SAFE_INTEGER
```

---

### 7. Deployment

**Docker Deployment (Fresh Install):**

```bash
# 1. Stop existing services
docker-compose down

# 2. Delete old database (fresh deployment, no data to preserve)
rm -rf backend/data/numina.db

# 3. Build new image
docker-compose build

# 4. Start services (auto-runs Alembic migrations)
docker-compose up -d
```

**Environment Variables (Optional):**

```env
# .env
SNOWFLAKE_MACHINE_ID=1  # Optional, auto-derives from container IP if omitted
```

**Rollback (if needed):**

Since this is fresh deployment:
1. Checkout old code branch
2. Delete database file
3. Rebuild and redeploy

No complex reverse data migration required.

---

## Benefits

| Aspect | UUID (Before) | Snowflake (After) |
|--------|---------------|-------------------|
| Storage | 36 bytes (VARCHAR) | 8 bytes (BIGINT) |
| Index Performance | Random, fragmented | Sequential, clustered |
| Comparison Speed | String comparison | Integer comparison |
| Chronological Order | ❌ No | ✅ Yes (timestamp embedded) |
| Multi-Backend Support | ✅ Yes | ✅ Yes |
| JS Precision Safety | ✅ Yes (string) | ✅ Yes (serialize to string) |

---

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Machine ID collision in multi-instance deployment | Use `SNOWFLAKE_MACHINE_ID` env var to assign unique IDs per instance |
| Clock skew causing duplicate IDs | Generator waits for next millisecond if sequence exhausted |
| JS precision loss for large IDs | Serialize IDs as strings in JSON responses |
| Breaking existing API clients | Fresh deployment, no existing clients to break |

---

## Implementation Checklist

- [ ] Create `backend/app/utils/snowflake.py` with generator
- [ ] Add `SNOWFLAKE_MACHINE_ID` to `config.py`
- [ ] Update `main.py` lifespan to call `init_snowflake()`
- [ ] Update all 30+ model files (primary keys + foreign keys)
- [ ] Update association tables (`asset_tags`, `chore_template_assignees`)
- [ ] Delete all 28 existing Alembic migrations
- [ ] Generate new initial migration
- [ ] Create `backend/app/schemas/base.py` with `SnowflakeBase`
- [ ] Update all schema files to inherit `SnowflakeBase` and use `int` types
- [ ] Update router path parameters to `int`
- [ ] Update 36 unit tests to compare stringified IDs
- [ ] Create `backend/tests/test_snowflake.py`
- [ ] Run full test suite: `uv run pytest tests/ -v`
- [ ] Frontend: verify types remain `string` (no changes needed)
- [ ] Deploy to Docker and verify database schema
- [ ] Run E2E tests: `./tests/e2e-acceptance.sh`

---

## Next Steps

After design approval:
1. Invoke `superpowers:writing-plans` skill to create detailed implementation plan
2. Execute implementation in phases (generator → models → schemas → tests)
3. Verify with full test suite before deployment
