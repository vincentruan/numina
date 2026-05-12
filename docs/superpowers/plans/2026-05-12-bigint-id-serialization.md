# Bigint ID Serialization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Standardize all response schemas to use SnowflakeBase for automatic int→str serialization, eliminating manual str() calls in routers.

**Architecture:** Pydantic v2 model_serializer in SnowflakeBase converts all int fields named 'id' or ending in '_id' to strings during JSON serialization. Schemas define IDs as int (matching DB), routers return int values directly, serialization happens at response boundary.

**Tech Stack:** Python 3.11, FastAPI, Pydantic v2, SQLAlchemy BigInteger, pytest

---

## Phase 1: Verify Infrastructure

### Task 1: Verify SnowflakeBase implementation

**Files:**
- Read: `app/schemas/base.py`
- Test: Create test to verify serialization behavior

- [ ] **Step 1: Read SnowflakeBase implementation**

Check that SnowflakeBase exists and uses model_serializer correctly:

```python
# Expected in app/schemas/base.py
class SnowflakeBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    @model_serializer(mode="wrap")
    def _serialize_snowflake_ids(self, handler: Any) -> dict[str, Any]:
        data: dict[str, Any] = handler(self)
        return {
            k: str(v) if isinstance(v, int) and (k == "id" or k.endswith("_id")) else v
            for k, v in data.items()
        }
```

- [ ] **Step 2: Write test to verify serialization**

Create `tests/test_snowflake_base.py`:

```python
"""Test SnowflakeBase serialization behavior."""
from pydantic import BaseModel
from app.schemas.base import SnowflakeBase


class MockResponse(SnowflakeBase):
    id: int
    family_id: int
    other_id: int
    name: str
    count: int  # Not an ID field


def test_snowflake_base_serializes_ids_to_strings():
    """All fields named 'id' or ending in '_id' become strings in JSON."""
    obj = MockResponse(id=123456789012345, family_id=987654321098765, other_id=111222333444555, name="test", count=42)

    data = obj.model_dump()

    assert data["id"] == "123456789012345"
    assert data["family_id"] == "987654321098765"
    assert data["other_id"] == "111222333444555"
    assert data["name"] == "test"
    assert data["count"] == 42  # Not converted


def test_plain_base_model_keeps_int():
    """Plain BaseModel does NOT convert IDs to strings."""
    class PlainResponse(BaseModel):
        id: int

    obj = PlainResponse(id=123456789012345)
    data = obj.model_dump()

    assert data["id"] == 123456789012345  # Still int
    assert isinstance(data["id"], int)
```

- [ ] **Step 3: Run tests to verify SnowflakeBase works**

Run: `pytest tests/test_snowflake_base.py -v`
Expected: Both tests pass

- [ ] **Step 4: Commit test file**

```bash
git add tests/test_snowflake_base.py
git commit -m "test: add SnowflakeBase serialization behavior tests

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Phase 2: Migrate Response Schemas

### Task 2: Migrate notification schemas

**Files:**
- Modify: `app/schemas/notification_channel.py`
- Modify: `app/schemas/notification_config.py`

- [ ] **Step 1: Update NotificationChannelResponse**

In `app/schemas/notification_channel.py`, change:

```python
# BEFORE
from pydantic import BaseModel, ConfigDict

class NotificationChannelResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    family_id: int
    # ... rest unchanged
```

To:

```python
# AFTER
from pydantic import ConfigDict

from app.schemas.base import SnowflakeBase

class NotificationChannelResponse(SnowflakeBase):
    id: int
    family_id: int
    channel_type: str
    name: str
    is_enabled: bool
    subscriptions: list[str] = []
    created_at: datetime
    updated_at: datetime
```

- [ ] **Step 2: Update NotificationConfigResponse**

In `app/schemas/notification_config.py`, change:

```python
# BEFORE
from pydantic import BaseModel, ConfigDict

class NotificationConfigResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    family_id: int
    # ... rest unchanged
```

To:

```python
# AFTER
from pydantic import ConfigDict

from app.schemas.base import SnowflakeBase

class NotificationConfigResponse(SnowflakeBase):
    id: int
    family_id: int
    large_purchase_threshold_fixed: float | None
    large_purchase_threshold_multiplier: float | None
    updated_at: datetime
```

- [ ] **Step 3: Run tests**

Run: `pytest tests/ -v -k "notification"`
Expected: All notification tests pass (schemas used in notification routers)

- [ ] **Step 4: Commit changes**

```bash
git add app/schemas/notification_channel.py app/schemas/notification_config.py
git commit -m "refactor: use SnowflakeBase for notification response schemas

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

### Task 3: Migrate reminder schema

**Files:**
- Modify: `app/schemas/reminder.py`

- [ ] **Step 1: Update ReminderResponse**

In `app/schemas/reminder.py`, change:

```python
# BEFORE
from pydantic import BaseModel, ConfigDict

class ReminderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    family_id: int
    asset_id: int | None
    # ... rest unchanged
```

To:

```python
# AFTER
from app.schemas.base import SnowflakeBase

class ReminderResponse(SnowflakeBase):
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
```

- [ ] **Step 2: Run tests**

Run: `pytest tests/ -v -k "reminder"`
Expected: All reminder tests pass

- [ ] **Step 3: Commit changes**

```bash
git add app/schemas/reminder.py
git commit -m "refactor: use SnowflakeBase for reminder response schema

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

### Task 4: Migrate device schemas

**Files:**
- Modify: `app/schemas/device.py`

- [ ] **Step 1: Update DeviceSessionResponse (id: str → int)**

In `app/schemas/device.py`, change:

```python
# BEFORE
from pydantic import BaseModel, ConfigDict

class DeviceSessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str  # Manually typed as str
    device_name: str
    # ... rest unchanged
```

To:

```python
# AFTER
from app.schemas.base import SnowflakeBase

class DeviceSessionResponse(SnowflakeBase):
    id: int  # Change back to int (SnowflakeBase converts to str)
    device_name: str
    created_at: datetime
    last_seen_at: datetime
    expires_at: datetime
    is_current: bool
```

- [ ] **Step 2: Update FamilyDeviceResponse**

Change:

```python
# BEFORE
class FamilyDeviceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    # ... rest unchanged
```

To:

```python
# AFTER
from app.schemas.base import SnowflakeBase

class FamilyDeviceResponse(SnowflakeBase):
    id: int
    user_id: int
    display_name: str
    avatar_color: str
    device_name: str
    last_seen_at: datetime
    created_at: datetime
    is_current: bool
```

- [ ] **Step 3: Verify DeviceTrustResponse**

DeviceTrustResponse has `device_id: str` (not a Snowflake ID, it's a session token). Keep as plain BaseModel:

```python
# NO CHANGE - device_id is not a Snowflake ID
class DeviceTrustResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    device_id: str  # JWT token string, not Snowflake ID
    device_name: str
    expires_at: datetime
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/ -v -k "device"`
Expected: All device tests pass

- [ ] **Step 5: Commit changes**

```bash
git add app/schemas/device.py
git commit -m "refactor: use SnowflakeBase for device session response schemas

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

### Task 5: Migrate AI config schemas

**Files:**
- Modify: `app/schemas/ai_config.py`

- [ ] **Step 1: Remove field_validator from AIConfigResponse**

In `app/schemas/ai_config.py`, change:

```python
# BEFORE
from pydantic import BaseModel, ConfigDict, field_validator

class AIConfigResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str

    @field_validator("id", mode="before")
    @classmethod
    def coerce_id(cls, v: object) -> str:
        return str(v)
    name: str
    # ... rest unchanged
```

To:

```python
# AFTER
from app.schemas.base import SnowflakeBase

class AIConfigResponse(SnowflakeBase):
    id: int  # Change from str to int
    name: str
    provider: str
    ai_api_key_masked: str | None = None
    base_url: str | None = None
    model_id: str | None = None
    vision_model_id: str | None = None
    timeout_seconds: int | None = 60
    is_active: bool
    test_results: list[AIProviderTestResultResponse] = []
```

- [ ] **Step 2: Remove field_validator from AIProviderTestResultResponse**

Change:

```python
# BEFORE
class AIProviderTestResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str

    @field_validator("id", mode="before")
    @classmethod
    def coerce_id(cls, v: object) -> str:
        return str(v)
    test_type: str
    # ... rest unchanged
```

To:

```python
# AFTER
from app.schemas.base import SnowflakeBase

class AIProviderTestResultResponse(SnowflakeBase):
    id: int  # Change from str to int
    test_type: str
    success: bool | None
    message: str | None
    latency_ms: int | None
    tested_at: datetime
```

- [ ] **Step 3: Run tests**

Run: `pytest tests/ -v -k "ai_config"`
Expected: All AI config tests pass

- [ ] **Step 4: Commit changes**

```bash
git add app/schemas/ai_config.py
git commit -m "refactor: use SnowflakeBase for AI config response schemas

Remove manual field_validator for ID coercion. SnowflakeBase
handles int→str serialization automatically.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

### Task 6: Migrate remaining schemas with ID fields

**Files:**
- Modify: `app/schemas/dashboard.py`
- Modify: `app/schemas/asset.py`
- Modify: `app/schemas/projection.py`
- Modify: `app/schemas/whatif.py`
- Modify: `app/schemas/family.py`
- Modify: `app/schemas/purchasing_power.py`

- [ ] **Step 1: Scan for remaining Response schemas with ID fields**

Run: `grep -r "class.*Response.*BaseModel" app/schemas/ --include="*.py" -A 10 | grep -E "(class|id:|_id:)"`

Expected: Identify remaining schemas like:
- AllocationItem (dashboard.py) - has category_id
- TopAssetItem (dashboard.py) - has id
- AssetLifecycleEventResponse (asset.py) - has id
- FamilySettingsResponse, MemberSummary (family.py) - potential ID fields
- PurchasingPowerResponse (purchasing_power.py)
- ProjectionResponse, WhatIfResponse (projection.py, whatif.py)

- [ ] **Step 2: Update dashboard schemas**

In `app/schemas/dashboard.py`, update AllocationItem and TopAssetItem:

```python
# BEFORE
class AllocationItem(BaseModel):
    category_id: int
    category_name: str
    percentage: float

class TopAssetItem(BaseModel):
    id: int
    name: str
    value: float
```

To:

```python
# AFTER
from app.schemas.base import SnowflakeBase

class AllocationItem(SnowflakeBase):
    category_id: int
    category_name: str
    percentage: float

class TopAssetItem(SnowflakeBase):
    id: int
    name: str
    value: float
```

- [ ] **Step 3: Update asset schemas**

In `app/schemas/asset.py`, update AssetLifecycleEventResponse:

```python
# BEFORE
class AssetLifecycleEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    event_type: str
    # ... rest
```

To:

```python
# AFTER
from app.schemas.base import SnowflakeBase

class AssetLifecycleEventResponse(SnowflakeBase):
    id: int
    event_type: str
    # ... rest of fields unchanged
```

- [ ] **Step 4: Update other schemas as needed**

Apply same pattern to remaining Response schemas in:
- `projection.py`
- `whatif.py`
- `family.py`
- `purchasing_power.py`

Pattern: Import SnowflakeBase, change `BaseModel` to `SnowflakeBase`, keep ID fields as `int`.

- [ ] **Step 5: Run full test suite**

Run: `pytest tests/ -v`
Expected: All tests pass

- [ ] **Step 6: Commit changes**

```bash
git add app/schemas/dashboard.py app/schemas/asset.py app/schemas/projection.py app/schemas/whatif.py app/schemas/family.py app/schemas/purchasing_power.py
git commit -m "refactor: use SnowflakeBase for remaining response schemas

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Phase 3: Remove Manual str() Calls from Routers

### Task 7: Remove str() calls from ai_chat.py

**Files:**
- Modify: `app/routers/ai_chat.py`

- [ ] **Step 1: Identify all str() calls**

Run: `grep -n "str(session.id)" app/routers/ai_chat.py`

Expected output:
- Line 152: `"X-Thread-Id": str(session.id)`
- Line 170: `"message_id": str(session.id)`
- Line 171: `"session_id": str(session.id)`
- Line 274: `"session_id": str(s.id)`
- Line 396: `"session_id": str(s.id)`

- [ ] **Step 2: Remove str() wrapper in X-Thread-Id header**

At line 152, change:

```python
# BEFORE
headers={
    "X-Family-Id": str(current_user.family_id),
    "X-Agent-Token": settings.AGENT_INTERNAL_TOKEN,
    "X-Task-Id": task_id,
    "X-Thread-Id": str(session.id),
}
```

To:

```python
# AFTER
headers={
    "X-Family-Id": str(current_user.family_id),
    "X-Agent-Token": settings.AGENT_INTERNAL_TOKEN,
    "X-Task-Id": task_id,
    "X-Thread-Id": session.id,  # Schema will serialize as str
}
```

Note: Keep `str(current_user.family_id)` for header (not JSON response).

- [ ] **Step 3: Remove str() wrappers in response JSON**

At lines 170-171, change:

```python
# BEFORE
return {
    "message_id": str(session.id),
    "session_id": str(session.id),
    "title": title,
}
```

To:

```python
# AFTER
return {
    "message_id": session.id,
    "session_id": session.id,
    "title": title,
}
```

- [ ] **Step 4: Remove str() wrappers in session list responses**

At line 274 and 396, change:

```python
# BEFORE
"session_id": str(s.id),
```

To:

```python
# AFTER
"session_id": s.id,
```

- [ ] **Step 5: Run tests**

Run: `pytest tests/test_ai_chat.py -v`
Expected: All AI chat tests pass

- [ ] **Step 6: Commit changes**

```bash
git add app/routers/ai_chat.py
git commit -m "refactor: remove manual str() calls in ai_chat router

SnowflakeBase schemas handle ID serialization automatically.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

### Task 8: Remove str() calls from device.py

**Files:**
- Modify: `app/routers/device.py`

- [ ] **Step 1: Remove str() from device_id in DeviceTrustResponse**

At line 153, change:

```python
# BEFORE
return DeviceTrustResponse(
    device_id=str(session.id),
    device_name=device_name,
    expires_at=expires_at,
)
```

To:

```python
# AFTER
return DeviceTrustResponse(
    device_id=session.id,
    device_name=device_name,
    expires_at=expires_at,
)
```

Note: DeviceTrustResponse schema has `device_id: str`. Need to check if it should be Snowflake ID.

- [ ] **Step 2: Check DeviceTrustResponse schema**

Read `app/schemas/device.py` and `app/models/device_session.py`. DeviceSession.id is BigInteger with next_id, so device_id IS a Snowflake ID.

Update schema (done in Task 4) to use SnowflakeBase with `device_id: int`.

- [ ] **Step 3: Remove str() from id in DeviceSessionResponse**

At line 177, change:

```python
# BEFORE
return DeviceSessionResponse(
    id=str(s.id),
    device_name=s.device_name,
    created_at=s.created_at,
    last_seen_at=s.last_seen_at,
    expires_at=expires_at,
    is_current=is_current,
)
```

To:

```python
# AFTER
return DeviceSessionResponse(
    id=s.id,  # Schema will serialize as str
    device_name=s.device_name,
    created_at=s.created_at,
    last_seen_at=s.last_seen_at,
    expires_at=expires_at,
    is_current=is_current,
)
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/ -v -k "device"`
Expected: All device tests pass

- [ ] **Step 5: Commit changes**

```bash
git add app/routers/device.py
git commit -m "refactor: remove manual str() calls in device router

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

### Task 9: Remove str() calls from AI capability routers

**Files:**
- Modify: `app/routers/ai_alerts.py`
- Modify: `app/routers/ai_disposal.py`
- Modify: `app/routers/ai_spending_leaks.py`

- [ ] **Step 1: Remove str() from ai_alerts.py**

At line 40, change:

```python
# BEFORE
return {
    "alerts": [
        {
            "id": str(a.id),
            "title": a.title,
            # ... rest
        }
        for a in alerts
    ]
}
```

To:

```python
# AFTER
return {
    "alerts": [
        {
            "id": a.id,
            "title": a.title,
            # ... rest
        }
        for a in alerts
    ]
}
```

- [ ] **Step 2: Remove str() from ai_disposal.py**

At line 40, change:

```python
# BEFORE
return {
    "suggestions": [
        {
            "id": str(s.id),
            "title": s.title,
            # ... rest
        }
        for s in suggestions
    ]
}
```

To:

```python
# AFTER
return {
    "suggestions": [
        {
            "id": s.id,
            "title": s.title,
            # ... rest
        }
        for s in suggestions
    ]
}
```

- [ ] **Step 3: Remove str() from ai_spending_leaks.py**

At line 42, change:

```python
# BEFORE
return {
    "leaks": [
        {
            "id": str(leak.id),
            "title": leak.title,
            # ... rest
        }
        for leak in leaks
    ]
}
```

To:

```python
# AFTER
return {
    "leaks": [
        {
            "id": leak.id,
            "title": leak.title,
            # ... rest
        }
        for leak in leaks
    ]
}
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_ai_report.py -v`
Expected: All AI capability tests pass

- [ ] **Step 5: Commit changes**

```bash
git add app/routers/ai_alerts.py app/routers/ai_disposal.py app/routers/ai_spending_leaks.py
git commit -m "refactor: remove manual str() calls in AI capability routers

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

### Task 10: Remove str() calls from remaining routers

**Files:**
- Modify: `app/routers/ai_report.py`
- Modify: `app/routers/import_report.py`

- [ ] **Step 1: Remove str() from ai_report.py ticket response**

At line 129, change:

```python
# BEFORE
return {"ticket": str(ticket.id)}
```

To:

```python
# AFTER
return {"ticket": ticket.id}
```

- [ ] **Step 2: Remove str() from import_report.py matched asset**

At line 180, change:

```python
# BEFORE
matched_asset_id=str(matched.id) if matched else None,
```

To:

```python
# AFTER
matched_asset_id=matched.id if matched else None,
```

- [ ] **Step 3: Run tests**

Run: `pytest tests/ -v -k "report"`
Expected: All report tests pass

- [ ] **Step 4: Commit changes**

```bash
git add app/routers/ai_report.py app/routers/import_report.py
git commit -m "refactor: remove manual str() calls in report routers

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Phase 4: Frontend Verification

### Task 11: Verify frontend TypeScript compilation

**Files:**
- Check: `frontend/apps/main/src/**/*.ts`
- Check: `frontend/apps/main/src/**/*.vue`

- [ ] **Step 1: Navigate to frontend directory**

Run: `cd ../frontend/apps/main`

- [ ] **Step 2: Run TypeScript compilation check**

Run: `npm run type-check`
Expected: No compilation errors (all ID fields already typed as `string` in TypeScript)

- [ ] **Step 3: Manual verification of API responses**

Start dev server (user action, not automated):

```bash
# User runs manually:
cd backend && uvicorn app.main:app --reload
cd frontend/apps/main && npm run dev
```

In browser DevTools Network tab:
1. Make API request (e.g., GET /api/v1/ai/chat/sessions)
2. Check response JSON - all IDs should be strings
3. Verify no JavaScript Number precision warnings

- [ ] **Step 4: Document verification results**

Add note to commit confirming frontend unchanged:

```bash
git commit --allow-empty -m "verify: frontend TypeScript unchanged after SnowflakeBase migration

All IDs already typed as string in frontend. Backend now serializes
consistently via SnowflakeBase instead of manual str() calls.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Phase 5: Documentation Update

### Task 12: Update backend CLAUDE.md

**Files:**
- Modify: `CLAUDE.md` (backend)

- [ ] **Step 1: Add SnowflakeBase pattern section**

After "Key Invariants" section, add:

```markdown
## Snowflake ID Serialization

All response schemas containing IDs inherit from `SnowflakeBase` (app/schemas/base.py).

### Pattern

```python
from app.schemas.base import SnowflakeBase

class MyResponse(SnowflakeBase):
    id: int  # Define as int (matches DB)
    family_id: int
    other_id: int
    name: str
```

JSON output automatically converts IDs to strings:
```json
{"id": "123456789012345", "family_id": "987654321098765"}
```

### Key Points

- Schemas define IDs as `int` (internal representation matches SQLAlchemy)
- SnowflakeBase.model_serializer converts to `str` during JSON serialization
- No manual `str()` calls in routers - return int values directly
- Request schemas (Create/Update) don't need SnowflakeBase - input comes as string

### Common Pitfalls

1. **Don't use plain BaseModel for schemas with IDs** → Use SnowflakeBase
2. **Don't manually define `id: str`** → Define `id: int`, let serializer convert
3. **Don't add field_validator for ID coercion** → SnowflakeBase handles it
4. **Don't call str() in routers** → Return int, schema serializes
5. **Request schemas don't need SnowflakeBase** → Input validation handles string→int

### Why

JavaScript loses precision for integers > 2^53. Snowflake IDs are 18-19 digits.
Serializing as strings preserves exact values across the API boundary.
```

- [ ] **Step 2: Update Bigint Serialization section**

Replace existing "Bigint Serialization" section with reference to new pattern:

```markdown
### Bigint Serialization

JS loses precision on integers > 2⁵³. All `bigint` fields (IDs, large amounts, etc.) **must be serialized as strings in API responses** and typed as `string` in TypeScript.

**Implementation:** All response schemas use `SnowflakeBase` which automatically converts `int` fields named `id` or ending in `_id` to `str` during JSON serialization. See "Snowflake ID Serialization" section for pattern details.
```

- [ ] **Step 3: Run tests to verify docs didn't break anything**

Run: `pytest tests/ -v`
Expected: All tests still pass

- [ ] **Step 4: Commit documentation**

```bash
git add CLAUDE.md
git commit -m "docs: add SnowflakeBase pattern to backend CLAUDE.md

Document standardized approach for Snowflake ID serialization.
Update bigint serialization section to reference new pattern.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Success Criteria

After completing all tasks:

- [ ] All response schemas with ID fields inherit from SnowflakeBase
- [ ] No manual str() calls in routers for ID fields (except headers)
- [ ] All tests pass: `pytest tests/ -v`
- [ ] Frontend TypeScript compiles: `npm run type-check`
- [ ] API responses verified: IDs are strings in JSON (browser DevTools)
- [ ] Documentation updated: backend CLAUDE.md has pattern section

---

## Rollback Plan

If critical issues arise:

1. **Revert schema changes:**
   ```bash
   git revert <schema-commit-sha>
   ```

2. **Revert router changes:**
   ```bash
   git revert <router-commit-sha>
   ```

3. **Revert documentation:**
   ```bash
   git revert <docs-commit-sha>
   ```

Low risk because:
- API contract remains strings either way
- Frontend already expects strings
- Changes are in separate commits per phase