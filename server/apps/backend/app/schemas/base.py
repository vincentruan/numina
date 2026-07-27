"""Base Pydantic schema for models with Snowflake IDs.

Serializes all `id` and `*_id` integer fields to strings in JSON output.
Internal schema fields remain `int` to faithfully model the data layer.
This prevents JavaScript Number precision loss for IDs > 2^53.
"""

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, model_serializer


def ensure_utc(dt: datetime) -> datetime:
    """Attach UTC tzinfo to a naive datetime so .isoformat() includes +00:00.

    Backend stores naive UTC datetimes (``DateTime`` without timezone).
    Without this, ``.isoformat()`` produces ``"2026-07-27T08:00:00"``
    which JavaScript parses as local time — an 8h error for UTC+8 users.
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


class SnowflakeBase(BaseModel):
    """Inherit this instead of BaseModel for any schema that contains Snowflake IDs.

    Behaviour:
    - `model_config` sets `from_attributes=True` (ORM mode).
    - JSON serialization converts every field named `id` or ending in `_id`
      from int to str. All other fields are unchanged.
    - Naive datetime fields (no tzinfo) are treated as UTC and serialized
      with ``+00:00`` suffix so JavaScript ``new Date()`` parses them correctly.
    """

    model_config = ConfigDict(from_attributes=True)

    @model_serializer(mode="wrap")
    def _serialize_snowflake_ids(self, handler: Any) -> dict[str, Any]:
        data: dict[str, Any] = handler(self)
        result: dict[str, Any] = {}
        for k, v in data.items():
            if isinstance(v, int) and (k == "id" or k.endswith("_id")):
                result[k] = str(v)
            elif isinstance(v, datetime) and v.tzinfo is None:
                result[k] = v.replace(tzinfo=UTC)
            else:
                result[k] = v
        return result
