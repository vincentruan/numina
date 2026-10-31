"""Tests for notification_digest_job's digest_time window matching."""

from datetime import datetime

from apps.scheduler_worker.jobs import _in_digest_window, _parse_digest_time


def test_parse_valid():
    assert _parse_digest_time("21:00") == (21, 0)
    assert _parse_digest_time("08:30") == (8, 30)
    assert _parse_digest_time("00:00") == (0, 0)


def test_parse_invalid():
    assert _parse_digest_time("25:00") is None
    assert _parse_digest_time("abc") is None
    assert _parse_digest_time("12:60") is None
    assert _parse_digest_time("12") is None


def test_in_window_exact_match():
    now = datetime(2026, 10, 30, 21, 0, 0)
    assert _in_digest_window("21:00", now) is True


def test_in_window_within_2_minutes():
    now = datetime(2026, 10, 30, 21, 1, 30)
    assert _in_digest_window("21:00", now) is True


def test_outside_window():
    now = datetime(2026, 10, 30, 21, 4, 0)
    assert _in_digest_window("21:00", now) is False


def test_midnight_wrap():
    """00:01 should match when the clock is at 23:59 (previous day)."""
    now = datetime(2026, 10, 30, 23, 59, 0)
    assert _in_digest_window("00:01", now) is True


def test_early_morning():
    now = datetime(2026, 10, 30, 8, 2, 0)
    assert _in_digest_window("08:00", now) is True
    assert _in_digest_window("08:05", now) is False


def test_malformed_always_false():
    now = datetime(2026, 10, 30, 8, 0, 0)
    assert _in_digest_window("bad", now) is False
    assert _in_digest_window("", now) is False
