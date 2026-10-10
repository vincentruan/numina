"""MCP access audit log writer.

Fire-and-forget: fails silently on DB errors so audit writes never
block tool execution. Each call creates its own SessionLocal() to
avoid coupling with the caller's transaction lifecycle.
"""

from __future__ import annotations

import json
import re
from typing import Any

from packages.core.logging import get_logger

logger = get_logger(__name__)

# Patterns that indicate secrets — values are replaced with [REDACTED].
_SECRET_PATTERNS = [
    re.compile(r"mcp_[A-Za-z0-9_\-]{8,}"),  # MCP tokens
    re.compile(r"Bearer\s+\S+"),  # Bearer tokens in args
    re.compile(r"sk-[A-Za-z0-9]{10,}"),  # OpenAI-style keys
]
# Key names that should have their values redacted.
_SECRET_KEY_NAMES = {"password", "secret", "token", "api_key", "apikey", "authorization"}
_MAX_DIGEST_LEN = 1024


def _redact_value(v: str) -> str:
    """Redact a single string value if it matches secret patterns."""
    for pat in _SECRET_PATTERNS:
        if pat.search(v):
            return "[REDACTED]"
    return v


def _redact_obj(obj: Any, depth: int = 0) -> Any:
    """Recursively redact secrets from nested dicts/lists/values."""
    if depth > 10:
        return "[MAX_DEPTH]"
    if isinstance(obj, dict):
        redacted = {}
        for k, v in obj.items():
            if any(sn in k.lower() for sn in _SECRET_KEY_NAMES):
                redacted[k] = "[REDACTED]"
            else:
                redacted[k] = _redact_obj(v, depth + 1)
        return redacted
    if isinstance(obj, list):
        return [_redact_obj(item, depth + 1) for item in obj]
    if isinstance(obj, str):
        return _redact_value(obj)
    return obj


def _redact_args(args: dict | None) -> str | None:
    """Serialize and redact tool arguments for the audit digest."""
    if not args:
        return None
    try:
        redacted = _redact_obj(args)
        text = json.dumps(redacted, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        text = str(args)
    # Also scan the full text for embedded secrets
    text = _redact_value(text)
    # Truncate
    if len(text) > _MAX_DIGEST_LEN:
        text = text[:_MAX_DIGEST_LEN] + "…"
    return text


def write_mcp_access_log(
    *,
    family_id: int,
    token_id: int | None = None,
    session_id: str | None = None,
    event_type: str,
    tool_name: str | None = None,
    status: str,
    duration_ms: int | None = None,
    client_ip: str,
    user_agent: str | None = None,
    args_digest: str | dict | None = None,
    error_code: str | None = None,
) -> None:
    """Append a row to mcp_access_logs. Fails silently.

    If *args_digest* is a dict, it is serialized and redacted.
    If it is a string, it is used as-is (assumed already processed).
    """
    # Process args_digest
    if isinstance(args_digest, dict):
        digest = _redact_args(args_digest)
    else:
        digest = args_digest
        if digest and len(digest) > _MAX_DIGEST_LEN:
            digest = digest[:_MAX_DIGEST_LEN] + "…"

    try:
        from apps.backend.app.database import SessionLocal
        from apps.backend.app.models.mcp_access_log import MCPAccessLog

        db = SessionLocal()
        try:
            entry = MCPAccessLog(
                family_id=family_id,
                token_id=token_id,
                session_id=session_id,
                event_type=event_type,
                tool_name=tool_name,
                status=status,
                duration_ms=duration_ms,
                client_ip=client_ip,
                user_agent=user_agent,
                args_digest=digest,
                error_code=error_code,
            )
            db.add(entry)
            db.commit()
        finally:
            db.close()
    except Exception:
        logger.warning(
            "[mcp_audit] failed to write event_type=%s family_id=%s",
            event_type,
            family_id,
            exc_info=True,
        )
