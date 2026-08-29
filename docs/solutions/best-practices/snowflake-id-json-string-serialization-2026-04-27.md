---
title: Snowflake IDs Must Be Serialized as Strings at the JSON Boundary
date: 2026-04-27
category: best-practices
module: backend
problem_type: best_practice
component: database
severity: high
applies_when:
  - Any endpoint returning Snowflake (BigInteger) IDs in JSON responses consumed by JavaScript/TypeScript
tags: [snowflake-id, json-serialization, javascript-precision, pydantic, biginteger, api-boundary]
related_components: [authentication, frontend_stimulus]
last_refreshed: 2026-08-26
---

# Snowflake IDs Must Be Serialized as Strings at the JSON Boundary

## Context

When Snowflake IDs (64-bit integers) are returned as JSON numbers, JavaScript silently corrupts them. JavaScript's `Number` type is IEEE 754 double-precision float, with a safe integer range of only up to `2^53 - 1` (9007199254740991). Snowflake IDs routinely exceed this. The corruption is silent — no error is thrown, the wrong value is stored, and downstream lookups fail with "record not found" errors that have no obvious cause.

This was discovered as a live bug during E2E testing: `source_wish_id` in `BlindBoxGiftResponse` was typed as `int | None` in the Pydantic schema. `JSON.parse` silently rounded the ID, causing lookup failures. A separate instance: `session.id` (BigInteger) passed as an httpx header without `str()` conversion caused failures across all 7 AI function routes. (session history)

## Guidance

Serialize all 64-bit integer ID fields as JSON strings at the API boundary. Keep Python internals as `int`. Keep TypeScript types as `string`.

**Define a shared Pydantic base class** (`server/apps/backend/app/schemas/base.py`):

```python
from pydantic import BaseModel, model_serializer
from typing import Any

class SnowflakeBase(BaseModel):
    """Base model that serializes all int ID fields to string for JS safety.
    Internal modeling stays int; only JSON output converts to string.
    """
    model_config = {"from_attributes": True}

    @model_serializer(mode="wrap")
    def _serialize_snowflake_ids(self, handler: Any) -> dict:
        data = handler(self)
        return {
            k: str(v) if isinstance(v, int) and (k == "id" or k.endswith("_id")) else v
            for k, v in data.items()
        }
```

**All response schemas inherit `SnowflakeBase`**:

```python
# Before
class AssetResponse(BaseModel):
    model_config = {"from_attributes": True}
    id: str
    family_id: str

# After
class AssetResponse(SnowflakeBase):
    id: int          # internal int — serialized to string in JSON output
    family_id: int
    name: str
```

**Router path parameters use `int`** (FastAPI parses from URL string automatically):

```python
@router.get("/{asset_id}")
async def get_asset(asset_id: int, ...):
    # FastAPI validates "123" → int; returns 422 on non-integer
    ...
```

**TypeScript types keep `string`** — no frontend changes needed:

```typescript
interface Asset {
  id: string        // "9007199254740993" — no precision loss
  family_id: string
  name: string
}
```

**Data flow**:
```
DB: BIGINT 9007199254740993
  → ORM: int 9007199254740993
  → Pydantic schema: int 9007199254740993   ← internal modeling
  → JSON output: {"id": "9007199254740993"} ← string at boundary
  → Frontend: string, no precision loss
```

**Also applies to non-response contexts** — any place a BigInteger ID crosses a string boundary:

```python
# httpx headers, log messages, cache keys — always str()
headers = {"X-Session-Id": str(session.id)}
cache_key = f"session:{session.id}"  # f-string auto-converts, but be explicit
```

### Anti-pattern: JSONResponse bypass (resolved)

Previously, returning `JSONResponse(content={...})` or raw dicts bypassed `SnowflakeBase.model_serializer`, requiring manual `str()` wrapping. This has been **resolved at the response layer**:

- **`EnvelopeResponse.render()`** (the `default_response_class` for all backend endpoints) now auto-converts all `id`/`*_id` int fields to `str` before JSON encoding. This covers all normal endpoints — raw dict returns, Pydantic models, nested lists — without any manual conversion.
- **`SnowflakeResponse`** (`app.responses`) provides the same conversion for endpoints that intentionally bypass the envelope (SSE metadata, captcha). Replace `JSONResponse` with `SnowflakeResponse` for these cases.

```python
from apps.backend.app.responses import SnowflakeResponse

# ✅ No manual str() needed — EnvelopeResponse handles it
return {"status": "queued", "task_id": task.id}

# ✅ For SSE/non-envelope endpoints — use SnowflakeResponse
return SnowflakeResponse(status_code=202, content={"task_id": task.id})
```

> **Note:** Manual `str()` in routers is harmless (idempotent — `str(str(x)) == str(x)`) but no longer necessary.

## Why This Matters

JS silently rounds large integers. `9007199254740993` becomes `9007199254740992` — same value, wrong record. No error is thrown. The bug only appears with IDs large enough to exceed `2^53`, which Snowflake IDs routinely do after the system has been running for a while. In production this manifests as intermittent "record not found" errors that are nearly impossible to reproduce in development (where IDs are small).

## When to Apply

- Any API endpoint returning Snowflake/BigInteger IDs in JSON
- Any place a BigInteger ID is passed as a string (HTTP headers, cache keys, log fields)
- Not needed for 32-bit integer IDs (max ~2.1 billion, safely within JS precision)

## Examples

**Before (broken for large IDs)**:
```json
{"id": 9007199254740993, "family_id": 9007199254740994}
// JS receives: {id: 9007199254740992, family_id: 9007199254740992}
// Wrong records fetched silently
```

**After (safe)**:
```json
{"id": "9007199254740993", "family_id": "9007199254740994"}
// JS receives strings — no precision loss, correct lookups
```

**Known affected fields at time of writing** (session history):
- ~~`BlindBoxGiftResponse.source_wish_id`~~ — **resolved**: the schema now inherits `SnowflakeBase` which auto-converts all `_id` fields to `str` during serialization
- `DeviceSession` device management endpoints (`GET /auth/devices`) — `device_id` must be string in response

> **Update (2026-07-31) — UTC datetime normalization:** `SnowflakeBase` now also attaches `+00:00` to tz-naive datetimes during serialization. This ensures all datetime fields in API responses include an explicit UTC offset, preventing frontend misinterpretation of naive timestamps as local time.

## Related

- `docs/solutions/best-practices/security-audit.md` — security logging patterns
- Snowflake ID design spec: `docs/superpowers/specs/2026-04-22-snowflake-id-design.md`
