"""Literacy weekly report orchestration service (U6).

Orchestrates the end-to-end generation of a weekly literacy report for a child:
builds context from signal aggregation, dispatches the agent for LLM narrative
generation via SSE, and persists the result to ``LiteracyWeeklyReport``.

Idempotent: at most one report per (child_id, week_start). Calling
``generate_literacy_report`` twice for the same week returns the existing row.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from apps.backend.app.services.agent_client import AgentClient
from apps.backend.app.services.literacy_report import (
    _aggregate_signals,
    _get_age_group,
    _sunday_of,
)
from packages.db.models.literacy_report import LiteracyWeeklyReport
from packages.db.models.user import User

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_thread_id(family_id: int, child_id: int) -> str:
    """Generate a unique thread ID for the literacy report agent run."""
    return f"literacy-report-{family_id}-{child_id}-{uuid.uuid4().hex[:8]}"


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def _validate_child_in_family(
    db: Session, *, child_id: int, family_id: int
) -> None:
    """Verify child_id belongs to family_id. Raises ValueError if not.

    Defense-in-depth: callers should already validate, but the service layer
    must not trust upstream validation blindly.
    """
    exists = db.execute(
        select(User.id).where(
            User.id == child_id,
            User.family_id == family_id,
            User.role == "child",
        )
    ).scalar_one_or_none()
    if exists is None:
        raise ValueError(
            f"child {child_id} not found in family {family_id}"
        )


# ---------------------------------------------------------------------------
# Context builder
# ---------------------------------------------------------------------------


def build_report_context(
    db: Session, *, child_id: int, week_start: date
) -> dict:
    """Build structured context dict for the LLM prompt.

    Aggregates signals for the current week and the previous week so the LLM
    can compare trends. Includes child display_name and age_group.
    """
    # Look up child for display_name and birthday
    child = db.execute(
        select(User).where(User.id == child_id)
    ).scalar_one()

    age_group = _get_age_group(child.birthday, reference=week_start)
    current_signals = _aggregate_signals(db, child_id, week_start)

    prev_week_start = week_start - timedelta(days=7)
    prev_signals = _aggregate_signals(db, child_id, prev_week_start)

    return {
        "child_display_name": child.display_name,
        "age_group": age_group,
        "week_start": week_start.isoformat(),
        "prev_week_start": prev_week_start.isoformat(),
        "current_week": current_signals,
        "prev_week": prev_signals,
    }


# ---------------------------------------------------------------------------
# Status query
# ---------------------------------------------------------------------------


def get_report_status(
    db: Session, *, family_id: int, child_id: int
) -> dict:
    """Return status dict for BabyPage entry display.

    Checks ``LiteracyWeeklyReport`` for the current week. Returns:
    - ``{status: 'none'}`` if no report exists
    - ``{status: 'ready', thread_id, week_start, narrative, generated_at}`` if present

    ``narrative`` is truncated to the first 80 chars for the card preview.
    """
    # Defense-in-depth: verify child belongs to caller's family
    _validate_child_in_family(db, child_id=child_id, family_id=family_id)

    today = date.today()
    week_start = _sunday_of(today)

    row = db.execute(
        select(LiteracyWeeklyReport).where(
            LiteracyWeeklyReport.child_id == child_id,
            LiteracyWeeklyReport.week_start == week_start,
        )
    ).scalar_one_or_none()

    if row is None:
        return {"status": "none"}

    narrative_preview = row.narrative[:80] + "…" if len(row.narrative) > 80 else row.narrative

    return {
        "status": "ready",
        "thread_id": row.thread_id,
        "week_start": week_start.isoformat(),
        "narrative": narrative_preview,
        "generated_at": row.generated_at.isoformat() if row.generated_at else None,
    }


# ---------------------------------------------------------------------------
# Agent dispatch
# ---------------------------------------------------------------------------


async def _stream_report_sse(
    *, family_id: int, user_id: int, context: dict, thread_id: str
) -> bytes:
    """Call the agent gateway and collect SSE bytes.

    Endpoint: ``/internal/gateway/runs/literacy-weekly-report/{thread_id}``

    Returns the raw collected SSE bytes for downstream parsing.
    """
    agent_client = AgentClient(family_id=family_id, user_id=user_id, timeout=120.0)
    agent_url = f"/internal/gateway/runs/literacy-weekly-report/{thread_id}"

    async with agent_client.stream(
        "POST",
        agent_url,
        json={
            "family_id": str(family_id),
            "user_id": str(user_id),
            "input": {
                "messages": [
                    {"role": "user", "content": json.dumps(context, ensure_ascii=False)}
                ]
            },
        },
    ) as resp:
        if resp.status_code != 200:
            body = await resp.aread()
            logger.warning(
                "[literacy-report] agent non-200: status=%s body=%s",
                resp.status_code,
                body[:200],
            )
            raise RuntimeError(
                f"literacy-report agent returned {resp.status_code}"
            )

        collected = b""
        async for line in resp.aiter_lines():
            collected += (line + "\n").encode()

    return collected


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


def _persist_report_result(
    db: Session,
    *,
    child_id: int,
    week_start: date,
    thread_id: str,
    collected_sse: bytes,
) -> LiteracyWeeklyReport | None:
    """Parse the ``literacy_weekly_report.result`` custom event from SSE bytes.

    Extracts the narrative and upserts a ``LiteracyWeeklyReport`` row.
    Returns the persisted row, or ``None`` if the result frame was missing.
    """
    text = collected_sse.decode("utf-8", errors="replace")
    narrative = None
    report_payload = None

    for block in text.split("\n\n"):
        if "literacy_weekly_report.result" not in block:
            continue
        for line in block.split("\n"):
            if line.startswith("data: "):
                try:
                    data = json.loads(line[len("data: "):])
                    if data.get("type") == "literacy_weekly_report.result":
                        report_payload = data.get("payload", {})
                        narrative = report_payload.get("report") or report_payload.get("narrative")
                except json.JSONDecodeError:
                    continue

    if narrative is None:
        logger.info("[literacy-report] no result frame in stream — not persisting")
        return None

    # Build structured report JSON from the context signals
    report_json = json.dumps(
        {"week_start": week_start.isoformat(), "source": "agent_sse"},
        ensure_ascii=False,
    )

    # Upsert: check for existing row first
    existing = db.execute(
        select(LiteracyWeeklyReport).where(
            LiteracyWeeklyReport.child_id == child_id,
            LiteracyWeeklyReport.week_start == week_start,
        )
    ).scalar_one_or_none()

    if existing is not None:
        existing.narrative = narrative
        existing.thread_id = thread_id
        existing.report_json = report_json
        db.commit()
        db.refresh(existing)
        return existing

    row = LiteracyWeeklyReport(
        child_id=child_id,
        week_start=week_start,
        report_json=report_json,
        narrative=narrative,
        thread_id=thread_id,
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        # TOCTOU: another caller inserted the same (child_id, week_start)
        # between our SELECT and INSERT. Re-query the existing row.
        db.rollback()
        logger.info(
            "[literacy-report] unique constraint hit for child=%s week=%s — "
            "returning existing row",
            child_id,
            week_start,
        )
        row = db.execute(
            select(LiteracyWeeklyReport).where(
                LiteracyWeeklyReport.child_id == child_id,
                LiteracyWeeklyReport.week_start == week_start,
            )
        ).scalar_one_or_none()
        return row
    db.refresh(row)
    return row


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


async def generate_literacy_report(
    db: Session,
    *,
    family_id: int,
    child_id: int,
    week_start: date,
    user_id: int,
) -> LiteracyWeeklyReport | None:
    """Generate (or return existing) weekly literacy report.

    Idempotent: if a report already exists for this child + week, it is
    returned unchanged without calling the agent.

    Flow:
    1. Check for existing report (idempotency guard)
    2. Build context via ``build_report_context``
    3. Stream via agent gateway
    4. Persist result
    """
    # Defense-in-depth: verify child belongs to caller's family
    _validate_child_in_family(db, child_id=child_id, family_id=family_id)

    # Idempotency check
    existing = db.execute(
        select(LiteracyWeeklyReport).where(
            LiteracyWeeklyReport.child_id == child_id,
            LiteracyWeeklyReport.week_start == week_start,
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    # Build context
    context = build_report_context(db, child_id=child_id, week_start=week_start)

    # Generate thread ID and dispatch
    thread_id = _make_thread_id(family_id, child_id)

    try:
        collected_sse = await _stream_report_sse(
            family_id=family_id,
            user_id=user_id,
            context=context,
            thread_id=thread_id,
        )
    except Exception:
        logger.warning(
            "[literacy-report] agent dispatch failed for child=%s week=%s",
            child_id,
            week_start,
            exc_info=True,
        )
        return None

    # Persist the result
    return _persist_report_result(
        db,
        child_id=child_id,
        week_start=week_start,
        thread_id=thread_id,
        collected_sse=collected_sse,
    )
