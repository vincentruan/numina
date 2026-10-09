"""Tests for MCP anomaly detection scanner."""

from datetime import UTC, datetime, timedelta

import pytest

from apps.backend.app.models.family_mcp_token import FamilyMCPToken
from apps.backend.app.models.mcp_access_log import MCPAccessLog
from apps.backend.app.models.reminder import Reminder
from apps.backend.app.utils.snowflake import next_id


@pytest.fixture
def family_with_token(db, test_family):
    """Create an active external-enabled MCP token for the test family."""
    token = FamilyMCPToken(
        id=next_id(),
        family_id=test_family.id,
        token_hash="a" * 64,
        token_prefix="mcp_abcd",
        token_last4="wxyz",
        allow_external=True,
        allow_write=False,
        is_active=True,
    )
    db.add(token)
    db.commit()
    return test_family


def _add_tool_calls(db, family_id, count, status="success", minutes_ago=1):
    """Insert *count* tool_call audit rows within the recent window."""
    ts = datetime.now(UTC) - timedelta(minutes=minutes_ago)
    for _ in range(count):
        db.add(
            MCPAccessLog(
                id=next_id(),
                family_id=family_id,
                token_id=None,
                event_type="tool_call",
                tool_name="get_assets",
                status=status,
                client_ip="1.2.3.4",
                created_at=ts,
            )
        )
    db.commit()


class TestAnomalyScan:
    def test_frequency_spike_emits_alert(self, db, family_with_token, monkeypatch):
        """Covers P2-AE7: >threshold calls in 5 min creates an anomaly reminder."""
        import apps.backend.app.database as db_mod
        from apps.backend.app.services.mcp_anomaly import scan_mcp_anomalies

        _add_tool_calls(db, family_with_token.id, 150, minutes_ago=1)

        # Route the scanner's own SessionLocal to the test session
        monkeypatch.setattr(db_mod, "SessionLocal", lambda: _NonClosingSession(db))

        scan_mcp_anomalies()

        reminders = (
            db.query(Reminder)
            .filter(
                Reminder.family_id == family_with_token.id,
                Reminder.reminder_type == "mcp_anomaly_detected",
            )
            .all()
        )
        assert len(reminders) == 1, "expected exactly one anomaly reminder"

    def test_normal_traffic_no_alert(self, db, family_with_token, monkeypatch):
        """Below-threshold traffic produces no reminder."""
        import apps.backend.app.database as db_mod
        from apps.backend.app.services.mcp_anomaly import scan_mcp_anomalies

        _add_tool_calls(db, family_with_token.id, 5, minutes_ago=1)

        monkeypatch.setattr(db_mod, "SessionLocal", lambda: _NonClosingSession(db))
        scan_mcp_anomalies()

        reminders = (
            db.query(Reminder)
            .filter(Reminder.reminder_type == "mcp_anomaly_detected")
            .all()
        )
        assert len(reminders) == 0

    def test_high_failure_rate_emits_alert(self, db, family_with_token, monkeypatch):
        """Failure rate above threshold with enough calls triggers an alert."""
        import apps.backend.app.database as db_mod
        from apps.backend.app.services.mcp_anomaly import scan_mcp_anomalies

        _add_tool_calls(db, family_with_token.id, 8, status="error", minutes_ago=1)
        _add_tool_calls(db, family_with_token.id, 2, status="success", minutes_ago=1)

        monkeypatch.setattr(db_mod, "SessionLocal", lambda: _NonClosingSession(db))
        scan_mcp_anomalies()

        reminders = (
            db.query(Reminder)
            .filter(Reminder.reminder_type == "mcp_anomaly_detected")
            .all()
        )
        assert len(reminders) >= 1, "expected a failure-rate anomaly reminder"

    def test_dedup_within_one_hour(self, db, family_with_token, monkeypatch):
        """Covers P2-AE8: repeated scan within an hour does not duplicate."""
        import apps.backend.app.database as db_mod
        from apps.backend.app.services.mcp_anomaly import scan_mcp_anomalies

        _add_tool_calls(db, family_with_token.id, 150, minutes_ago=1)
        monkeypatch.setattr(db_mod, "SessionLocal", lambda: _NonClosingSession(db))

        scan_mcp_anomalies()
        scan_mcp_anomalies()

        reminders = (
            db.query(Reminder)
            .filter(Reminder.reminder_type == "mcp_anomaly_detected")
            .all()
        )
        assert len(reminders) == 1, "dedup should collapse repeats within the hour"


class _NonClosingSession:
    """Proxy that forwards to the shared test session without closing it."""

    def __init__(self, session):
        self._session = session

    def __getattr__(self, name):
        return getattr(self._session, name)

    def close(self):  # noqa: D102
        pass
