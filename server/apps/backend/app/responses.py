from __future__ import annotations

from typing import Any

from fastapi.responses import JSONResponse


def _convert_snowflake_ids(obj: Any) -> Any:
    """Recursively convert int fields named ``id`` or ending in ``_id`` to str.

    This is the safety net that catches every code path where a BigInteger ID
    reaches the JSON boundary without going through ``SnowflakeBase`` — raw dict
    returns, ``JSONResponse(content={...})``, nested lists, etc.  The conversion
    is idempotent: already-string values pass through unchanged.
    """
    if isinstance(obj, dict):
        return {
            k: str(v)
            if isinstance(v, int) and (k == "id" or k.endswith("_id"))
            else _convert_snowflake_ids(v)
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [_convert_snowflake_ids(item) for item in obj]
    return obj


class EnvelopeResponse(JSONResponse):
    """Default response class — wraps content in ``{code, message, data}``
    and auto-converts snowflake IDs at the boundary."""

    def __init__(self, content=None, status_code: int = 200, **kwargs):
        super().__init__(
            content={"code": "OK", "message": "", "data": content},
            status_code=status_code,
            **kwargs,
        )

    def render(self, body: Any) -> bytes:
        if body is not None:
            body = _convert_snowflake_ids(body)
        return super().render(body)


class SnowflakeResponse(JSONResponse):
    """Raw JSON response (no envelope) with snowflake ID auto-conversion.

    Use for SSE metadata, captcha, and other endpoints that intentionally
    bypass ``EnvelopeResponse`` but still return BigInteger IDs.
    """

    def render(self, body: Any) -> bytes:
        if body is not None:
            body = _convert_snowflake_ids(body)
        return super().render(body)
