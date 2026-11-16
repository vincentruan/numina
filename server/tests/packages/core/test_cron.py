"""Tests for the cron helper shared by the scheduled-task API and poll job.

The contract that matters to users: a cron expression they type is interpreted
in Asia/Shanghai local time, and the value persisted to the database is UTC.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from packages.core.cron import compute_next_run_at, is_valid_cron


class TestIsValidCron:
    @pytest.mark.parametrize(
        "expression",
        ["0 9 * * *", "*/15 * * * *", "0 9 * * 0", "30 2 1 * *"],
    )
    def test_accepts_five_field_expressions(self, expression):
        assert is_valid_cron(expression) is True

    @pytest.mark.parametrize(
        "expression",
        ["", "0 9 * *", "0 9 * * * *", "not a cron", "0 25 * * *", "0 9 * * 9"],
    )
    def test_rejects_malformed_expressions(self, expression):
        assert is_valid_cron(expression) is False


class TestComputeNextRunAt:
    def test_daily_nine_local_maps_to_utc(self):
        # 2026-11-03 20:00 Beijing == 12:00 UTC — next 09:00 Beijing is next day.
        after = datetime(2026, 11, 3, 12, 0, tzinfo=UTC)

        nxt = compute_next_run_at("0 9 * * *", after=after)

        assert nxt == datetime(2026, 11, 4, 1, 0, tzinfo=UTC)
        assert nxt.tzinfo == UTC

    def test_local_interpretation_not_server_interpretation(self):
        # 2026-11-03 00:30 UTC is 08:30 Beijing — 09:00 Beijing is same local day.
        after = datetime(2026, 11, 3, 0, 30, tzinfo=UTC)

        nxt = compute_next_run_at("0 9 * * *", after=after)

        assert nxt == datetime(2026, 11, 3, 1, 0, tzinfo=UTC)

    def test_weekly_sunday_schedule(self):
        # 2026-11-03 is a Tuesday; next Sunday 09:00 Beijing is 2026-11-08.
        after = datetime(2026, 11, 3, 12, 0, tzinfo=UTC)

        nxt = compute_next_run_at("0 9 * * 0", after=after)

        assert nxt == datetime(2026, 11, 8, 1, 0, tzinfo=UTC)

    def test_naive_after_is_treated_as_utc(self):
        aware = compute_next_run_at(
            "0 9 * * *", after=datetime(2026, 11, 3, 12, 0, tzinfo=UTC)
        )
        naive = compute_next_run_at("0 9 * * *", after=datetime(2026, 11, 3, 12, 0))

        assert naive == aware

    def test_result_is_strictly_after_the_base(self):
        # A base that lands exactly on a fire time must advance past it, otherwise
        # the poll job would re-run the same slot forever.
        exact = datetime(2026, 11, 4, 1, 0, tzinfo=UTC)

        nxt = compute_next_run_at("0 9 * * *", after=exact)

        assert nxt > exact
        assert nxt == datetime(2026, 11, 5, 1, 0, tzinfo=UTC)

    def test_invalid_expression_raises(self):
        with pytest.raises(ValueError):
            compute_next_run_at("bogus", after=datetime(2026, 11, 3, 12, 0, tzinfo=UTC))
