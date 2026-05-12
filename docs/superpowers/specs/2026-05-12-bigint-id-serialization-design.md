# Bigint ID Serialization Design

**Created:** 2026-05-12
**Status:** Approved
**Context:** Standardize Snowflake ID handling across backend to prevent JavaScript precision loss

## Problem

Backend uses Snowflake IDs (BigInteger > 2^53) stored as Python `int`. JavaScript loses precision for integers larger than 2^53, so IDs must be serialized as strings in JSON responses.

Current state has inconsistencies:
- `SnowflakeBase` exists in `app/schemas/base.py` with automatic int→str conversion
- Some schemas use it correctly (ChildResponse, AssetResponse, etc.)
- Others use plain BaseModel with manual `id: int` fields
- Some have manual validators: `@field_validator("id", mode="before") def coerce_id(cls, v): return str(v)`
- Routers contain 12 manual `str()` calls: `str(session.id)`, `str(leak.id)`, etc.

This creates technical debt and confusion about the correct pattern.

## Solution

**Standardize all response schemas on `SnowflakeBase`.**

### Core Pattern

```python
from app.schemas.base import SnowflakeBase

class MyResponse(SnowflakeBase):
    id: int  # Define as int internally (matches DB model)
    family_id: int  # Any field named 'id' or ending in '_id'
    name: str

# Automatic serialization: {"id": "123456789012345", "family_id": "987654321098765"}
```

**Key principle:**
- Schemas define IDs as `int` (matching SQLAlchemy models)
- `SnowflakeBase.model_serializer` converts to `str` in JSON output
- No manual `str()` calls in routers

### Migration Scope

**Category 1: Schemas using plain BaseModel**
Update to inherit `SnowflakeBase`, keep ID fields as `int`:
- `NotificationChannelResponse` (id, family_id)
- `NotificationConfigResponse` (id, family_id)
- `ReminderResponse` (id, family_id)
- `DeviceSessionResponse` (id currently `str` → change to `int`)
- `FamilyDeviceResponse` (id, user_id)
- Plus others in dashboard.py, projection.py, etc.

**Category 2: Schemas with manual validators**
Remove validators, inherit `SnowflakeBase`, change `id: str` to `id: int`:
- `AIConfigResponse` (has `@field_validator("id", mode="before")`)
- `AIProviderTestResultResponse` (has `@field_validator("id", mode="before")`)

**Category 3: Routers with manual str() calls (12 instances)**
Remove all manual wrapping:
- `ai_chat.py`: `str(session.id)` → `session.id`
- `device.py`: `str(session.id)` → `session.id`
- `ai_spending_leaks.py`: `str(leak.id)` → `leak.id`
- `ai_alerts.py`: `str(a.id)` → `a.id`
- `ai_disposal.py`: `str(s.id)` → `s.id`
- `ai_report.py`: `str(ticket.id)` → `ticket.id`
- `import_report.py`: `str(matched.id)` → `matched.id`

**Out of scope:**
- Request schemas (Create/Update) - work with `int` directly from frontend
- Internal DB operations - SQLAlchemy handles `int` correctly
- Query parameters - FastAPI converts from string automatically

### Implementation Strategy

**Phase 1: Backend schemas (low risk)**
- Update all response schemas to inherit `SnowflakeBase`
- Remove manual validators from `ai_config.py`
- Change `id: str` back to `id: int` in `DeviceSessionResponse`
- Run `pytest` after each schema file change

**Phase 2: Backend routers (medium risk)**
- Remove all manual `str()` wrapper calls
- Routers return ORM objects; schemas handle serialization
- Test each affected endpoint manually

**Phase 3: Frontend verification (validation)**
- Confirm TypeScript expects `string` for all IDs
- Check no TypeScript compilation errors
- API contracts unchanged (still receiving strings)

**Phase 4: Documentation update**
- Update backend CLAUDE.md with standardized pattern
- Add examples showing correct approach
- Document common pitfalls

### Why This Order

1. Schemas are isolated with clear test coverage
2. Tested schemas make router changes safer
3. Frontend validates end-to-end behavior
4. Documentation preserves pattern for future work

## Technical Details

### SnowflakeBase Implementation

Already exists in `app/schemas/base.py`:

```python
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

Matches any field named `id` or ending in `_id`, converts `int` to `str` in JSON output.

### Files Affected

**Schemas (approximate count):**
- `app/schemas/notification_channel.py` - NotificationChannelResponse
- `app/schemas/notification_config.py` - NotificationConfigResponse
- `app/schemas/reminder.py` - ReminderResponse
- `app/schemas/device.py` - DeviceSessionResponse, FamilyDeviceResponse
- `app/schemas/ai_config.py` - AIConfigResponse, AIProviderTestResultResponse
- `app/schemas/dashboard.py` - potential ID fields
- `app/schemas/projection.py` - potential ID fields
- Plus others discovered during implementation

**Routers:**
- `app/routers/ai_chat.py` - multiple str() calls
- `app/routers/device.py` - str(session.id)
- `app/routers/ai_spending_leaks.py` - str(leak.id)
- `app/routers/ai_alerts.py` - str(a.id)
- `app/routers/ai_disposal.py` - str(s.id)
- `app/routers/ai_report.py` - str(ticket.id)
- `app/routers/import_report.py` - str(matched.id)

### Testing Strategy

- Run `pytest tests/ -v` after each schema file modification
- Manual endpoint testing for router changes
- Frontend TypeScript compilation check
- End-to-end API response verification (strings in JSON)

## Success Criteria

- All response schemas containing IDs inherit from `SnowflakeBase`
- No manual `str()` calls in routers for ID fields
- All tests pass
- Frontend TypeScript compiles without errors
- API responses contain string IDs (validated in browser/network tab)

## Rollback Plan

If issues arise:
1. Revert schema changes (git revert)
2. Restore manual `str()` calls in routers
3. Frontend unchanged (already expects strings)

Low risk: API contract remains strings either way.

## Common Pitfalls to Document

1. **Don't use plain BaseModel for schemas with IDs** → Use `SnowflakeBase`
2. **Don't manually define `id: str`** → Define `id: int`, let serializer convert
3. **Don't add field_validator for ID coercion** → `SnowflakeBase` handles it
4. **Don't call str() in routers** → Return int directly, schema serializes
5. **Request schemas don't need SnowflakeBase** → Input comes as string from frontend

## Related Context

- JavaScript Number.MAX_SAFE_INTEGER = 2^53 - 1
- Snowflake IDs typically 18-19 digits (well above safe range)
- SQLAlchemy BigInteger stores as Python int (unlimited precision)
- Pydantic v2 `model_serializer` wraps all field serialization