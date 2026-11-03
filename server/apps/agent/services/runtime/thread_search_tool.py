"""Family-scoped session search tool (T25 U5).

Provides the LLM with a way to discover past family conversations by
title and last-message-summary. This complements the upstream
``history_search`` tool, which searches only the current thread's
messages.

The tool is registered as a ``StructuredTool`` so it composes naturally
with DeerFlow's tool assembly. The factory binds ``family_id`` at
dispatch time; the tool itself is pure search and performs no
authorization — the bound ``family_id`` is the authority.
"""

from __future__ import annotations

import json
from typing import Any

from langchain_core.tools import StructuredTool

from packages.core.logging import get_logger

logger = get_logger(__name__)


def _matches_query(session: dict[str, Any], query_lower: str) -> bool:
    """Case-insensitive substring match on title and last_message_summary."""
    q = query_lower.strip()
    if not q:
        return True
    title = (session.get("title") or "").lower()
    snippet = (session.get("last_message_summary") or "").lower()
    return q in title or q in snippet


def _snippet(session: dict[str, Any], max_chars: int = 200) -> str | None:
    """Return a snippet from last_message_summary, truncated to max_chars."""
    raw = session.get("last_message_summary")
    if not raw:
        return None
    return raw[:max_chars]


async def _search(
    family_id: str,
    query: str,
    limit: int = 10,
) -> str:
    """Search family sessions and return a JSON page."""
    try:
        # Import lazily so the tool module loads without a running backend
        # client at import time.
        from apps.agent.core.backend_client import list_sessions

        clamped = max(1, min(limit, 20))
        # Fetch a wider page than the requested limit to give the filter
        # room to drop non-matching sessions.
        fetch_limit = clamped * 3
        sessions, _total = await list_sessions(
            family_id,
            limit=fetch_limit,
            sort_by="updated_at",
            sort_order="desc",
        )
    except Exception as exc:  # noqa: BLE001 — tool boundary
        logger.warning("thread_search backend failure: %s", exc)
        return json.dumps({"error": f"backend_unavailable: {exc}"})

    query_lower = (query or "").strip().lower()
    matched = [s for s in sessions if _matches_query(s, query_lower)][:clamped]

    results = [
        {
            "thread_id": s.get("thread_id"),
            "title": s.get("title"),
            "snippet": _snippet(s),
            "source": s.get("source"),
            "updated_at": s.get("updated_at"),
        }
        for s in matched
    ]
    return json.dumps(results, ensure_ascii=False)


def build_thread_search_tool(family_id: str) -> StructuredTool:
    """Build a thread_search tool bound to a family.

    The returned tool's coroutine closes over ``family_id`` so the LLM
    need not (and cannot) pass it.
    """

    async def _coroutine(query: str, limit: int = 10) -> str:
        return await _search(family_id, query, limit)

    return StructuredTool.from_function(
        coroutine=_coroutine,
        name="thread_search",
        description=(
            "Search past family conversations by title or recent content. "
            "Returns thread_id, title, snippet, and timestamp for each match. "
            "Use this to discover relevant past sessions, then use "
            "read_conversation(thread_id) to read one in full. "
            "Scope: this family only; excludes the current thread."
        ),
    )
