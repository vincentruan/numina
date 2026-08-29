"""Tests for the literacy weekly report orchestration service (U6)."""
from __future__ import annotations

import json
from datetime import date, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from apps.backend.app.models.user import User
from apps.backend.app.services.literacy_report import _sunday_of
from apps.backend.app.services.literacy_report_service import (
    _make_thread_id,
    _persist_report_result,
    build_report_context,
    generate_literacy_report,
    get_report_status,
)
from apps.backend.app.utils.snowflake import next_id
from packages.db.models.literacy_report import LiteracyWeeklyReport

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def report_family(db):
    from apps.backend.app.models.family import Family

    family = Family(id=next_id(), name="Report Svc Family", created_by=next_id())
    db.add(family)
    db.commit()
    db.refresh(family)
    return family


@pytest.fixture
def report_child(db, report_family):
    user = User(
        id=next_id(),
        username="rpt_child",
        display_name="Report Child",
        password_hash="test_hash",
        family_id=report_family.id,
        role="child",
        birthday=date(2018, 6, 15),  # ~8 years old → "mid"
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def current_week_start():
    return _sunday_of(date.today())


# ---------------------------------------------------------------------------
# _make_thread_id
# ---------------------------------------------------------------------------


class TestMakeThreadId:
    def test_format_contains_family_and_child(self):
        tid = _make_thread_id(123, 456)
        assert tid.startswith("literacy-report-123-456-")
        # suffix is 8 hex chars
        suffix = tid.split("-")[-1]
        assert len(suffix) == 8

    def test_uniqueness(self):
        t1 = _make_thread_id(1, 2)
        t2 = _make_thread_id(1, 2)
        assert t1 != t2


# ---------------------------------------------------------------------------
# build_report_context
# ---------------------------------------------------------------------------


class TestBuildReportContext:
    def test_includes_child_data(self, db, report_child, current_week_start):
        ctx = build_report_context(
            db, child_id=report_child.id, week_start=current_week_start
        )

        assert ctx["child_display_name"] == "Report Child"
        assert ctx["age_group"] == "mid"
        assert ctx["week_start"] == current_week_start.isoformat()
        prev_ws = current_week_start - timedelta(days=7)
        assert ctx["prev_week_start"] == prev_ws.isoformat()
        # current_week and prev_week are dicts with signal keys
        assert "chores_total" in ctx["current_week"]
        assert "coin_earned" in ctx["current_week"]
        assert "chores_total" in ctx["prev_week"]

    def test_age_group_low_for_young_child(self, db, report_family):
        young = User(
            id=next_id(),
            username="young_child",
            display_name="Young",
            password_hash="h",
            family_id=report_family.id,
            role="child",
            birthday=date.today().replace(year=date.today().year - 6),
        )
        db.add(young)
        db.commit()
        db.refresh(young)

        ctx = build_report_context(
            db, child_id=young.id, week_start=_sunday_of(date.today())
        )
        assert ctx["age_group"] == "low"


# ---------------------------------------------------------------------------
# get_report_status
# ---------------------------------------------------------------------------


class TestGetReportStatus:
    def test_no_report_returns_none(self, db, report_child):
        status = get_report_status(
            db, family_id=report_child.family_id, child_id=report_child.id
        )
        assert status["status"] == "none"

    def test_with_report_returns_ready(self, db, report_child, current_week_start):
        row = LiteracyWeeklyReport(
            child_id=report_child.id,
            week_start=current_week_start,
            report_json="{}",
            narrative="本周表现很好，继续努力！",
            thread_id="literacy-report-1-2-abcd1234",
        )
        db.add(row)
        db.commit()

        status = get_report_status(
            db, family_id=report_child.family_id, child_id=report_child.id
        )
        assert status["status"] == "ready"
        assert status["thread_id"] == "literacy-report-1-2-abcd1234"
        assert status["week_start"] == current_week_start.isoformat()
        assert "本周表现很好" in status["narrative"]
        assert status["generated_at"] is not None

    def test_narrative_truncated_at_80(self, db, report_child, current_week_start):
        long_narrative = "测" * 120
        row = LiteracyWeeklyReport(
            child_id=report_child.id,
            week_start=current_week_start,
            report_json="{}",
            narrative=long_narrative,
        )
        db.add(row)
        db.commit()

        status = get_report_status(
            db, family_id=report_child.family_id, child_id=report_child.id
        )
        # 80 chars + ellipsis
        assert len(status["narrative"]) == 81
        assert status["narrative"].endswith("…")


# ---------------------------------------------------------------------------
# _persist_report_result
# ---------------------------------------------------------------------------


def _build_sse_bytes(narrative: str) -> bytes:
    """Build a fake SSE byte stream containing a literacy_weekly_report.result event."""
    payload = {"type": "literacy_weekly_report.result", "payload": {"report": narrative}}
    block = f"event: custom\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
    return block.encode("utf-8")


class TestPersistReportResult:
    def test_persists_narrative(self, db, report_child, current_week_start):
        sse = _build_sse_bytes("这是一段测试叙述。")
        row = _persist_report_result(
            db,
            child_id=report_child.id,
            week_start=current_week_start,
            thread_id="test-thread-id",
            collected_sse=sse,
        )
        assert row is not None
        assert row.narrative == "这是一段测试叙述。"
        assert row.thread_id == "test-thread-id"

    def test_returns_none_when_no_result_frame(self, db, report_child, current_week_start):
        sse = b"event: end\ndata: {}\n\n"
        row = _persist_report_result(
            db,
            child_id=report_child.id,
            week_start=current_week_start,
            thread_id="test-thread-id",
            collected_sse=sse,
        )
        assert row is None

    def test_upsert_existing(self, db, report_child, current_week_start):
        existing = LiteracyWeeklyReport(
            child_id=report_child.id,
            week_start=current_week_start,
            report_json="{}",
            narrative="old narrative",
        )
        db.add(existing)
        db.commit()

        sse = _build_sse_bytes("updated narrative")
        row = _persist_report_result(
            db,
            child_id=report_child.id,
            week_start=current_week_start,
            thread_id="new-thread",
            collected_sse=sse,
        )
        assert row is not None
        assert row.narrative == "updated narrative"
        assert row.thread_id == "new-thread"


# ---------------------------------------------------------------------------
# generate_literacy_report (integration)
# ---------------------------------------------------------------------------


class TestGenerateLiteracyReport:
    async def test_idempotent_returns_existing(self, db, report_child, current_week_start):
        existing = LiteracyWeeklyReport(
            child_id=report_child.id,
            week_start=current_week_start,
            report_json="{}",
            narrative="already exists",
            thread_id="existing-thread",
        )
        db.add(existing)
        db.commit()

        result = await generate_literacy_report(
            db,
            family_id=report_child.family_id,
            child_id=report_child.id,
            week_start=current_week_start,
            user_id=report_child.id,
        )
        assert result is not None
        assert result.narrative == "already exists"
        assert result.thread_id == "existing-thread"

    async def test_calls_agent_and_persists(self, db, report_child, current_week_start):
        sse_bytes = _build_sse_bytes("AI generated narrative for the week.")

        with patch(
            "apps.backend.app.services.literacy_report_service._stream_report_sse",
            new_callable=AsyncMock,
            return_value=sse_bytes,
        ):
            result = await generate_literacy_report(
                db,
                family_id=report_child.family_id,
                child_id=report_child.id,
                week_start=current_week_start,
                user_id=report_child.id,
            )

        assert result is not None
        assert result.narrative == "AI generated narrative for the week."
        assert result.thread_id is not None
        assert result.thread_id.startswith("literacy-report-")

    async def test_returns_none_on_agent_failure(self, db, report_child, current_week_start):
        with patch(
            "apps.backend.app.services.literacy_report_service._stream_report_sse",
            new_callable=AsyncMock,
            side_effect=RuntimeError("agent down"),
        ):
            result = await generate_literacy_report(
                db,
                family_id=report_child.family_id,
                child_id=report_child.id,
                week_start=current_week_start,
                user_id=report_child.id,
            )

        assert result is None

    async def test_force_true_regenerates(self, db, report_child, current_week_start):
        """force=True deletes the existing row and generates a new report."""
        existing = LiteracyWeeklyReport(
            child_id=report_child.id,
            week_start=current_week_start,
            report_json="{}",
            narrative="old narrative",
            thread_id="old-thread",
        )
        db.add(existing)
        db.commit()

        sse_bytes = _build_sse_bytes("fresh narrative")

        with patch(
            "apps.backend.app.services.literacy_report_service._stream_report_sse",
            new_callable=AsyncMock,
            return_value=sse_bytes,
        ):
            result = await generate_literacy_report(
                db,
                family_id=report_child.family_id,
                child_id=report_child.id,
                week_start=current_week_start,
                user_id=report_child.id,
                force=True,
            )

        assert result is not None
        assert result.narrative == "fresh narrative"
        assert result.thread_id != "old-thread"

    def test_persist_stores_thinking_in_report_json(
        self, db, report_child, current_week_start
    ):
        """_persist_report_result stores thinking text in report_json."""
        payload = {
            "type": "literacy_weekly_report.result",
            "payload": {"report": "report text", "thinking": "deep reasoning"},
        }
        block = f"event: custom\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
        sse = block.encode("utf-8")

        row = _persist_report_result(
            db,
            child_id=report_child.id,
            week_start=current_week_start,
            thread_id="test-thread-thinking",
            collected_sse=sse,
        )
        assert row is not None
        stored = json.loads(row.report_json)
        assert stored["thinking"] == "deep reasoning"
        assert stored["narrative"] == "report text"
