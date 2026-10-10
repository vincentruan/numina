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


def _add_call(db, family_id, client_ip, minutes_ago=1, event_type="connect"):
    """Insert a single audit row from *client_ip* at a given offset."""
    db.add(
        MCPAccessLog(
            id=next_id(),
            family_id=family_id,
            token_id=None,
            event_type=event_type,
            tool_name=None,
            status="success",
            client_ip=client_ip,
            created_at=datetime.now(UTC) - timedelta(minutes=minutes_ago),
        )
    )
    db.commit()


class TestNewSourceIP:
    """P2-R11(b): alert on a source IP not seen in the 30-day lookback window."""

    def test_new_ip_emits_alert(self, db, family_with_token, monkeypatch):
        """An IP with no prior history in the lookback window alerts."""
        import apps.backend.app.database as db_mod
        from apps.backend.app.services.mcp_anomaly import scan_mcp_anomalies

        # Known IP, seen 10 days ago (outside the recent window, inside lookback)
        _add_call(db, family_with_token.id, "1.1.1.1", minutes_ago=10 * 24 * 60)
        # Never-before-seen IP, right now
        _add_call(db, family_with_token.id, "2.2.2.2", minutes_ago=1)

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
        titles = [r.title for r in reminders]
        assert any("new_source_ip" in t for t in titles), (
            f"expected a new_source_ip alert, got {titles}"
        )
        assert any("2.2.2.2" in t for t in titles), "alert should name the new IP"

    def test_known_ip_no_alert(self, db, family_with_token, monkeypatch):
        """An IP already seen within the lookback window does not alert."""
        import apps.backend.app.database as db_mod
        from apps.backend.app.services.mcp_anomaly import scan_mcp_anomalies

        _add_call(db, family_with_token.id, "3.3.3.3", minutes_ago=10 * 24 * 60)
        _add_call(db, family_with_token.id, "3.3.3.3", minutes_ago=1)

        monkeypatch.setattr(db_mod, "SessionLocal", lambda: _NonClosingSession(db))
        scan_mcp_anomalies()

        reminders = (
            db.query(Reminder)
            .filter(Reminder.reminder_type == "mcp_anomaly_detected")
            .all()
        )
        assert not any("new_source_ip" in r.title for r in reminders)

    def test_ip_outside_lookback_window_is_new(self, db, family_with_token, monkeypatch):
        """An IP last seen 45 days ago (outside the 30-day window) counts as new."""
        import apps.backend.app.database as db_mod
        from apps.backend.app.services.mcp_anomaly import scan_mcp_anomalies

        _add_call(db, family_with_token.id, "4.4.4.4", minutes_ago=45 * 24 * 60)
        _add_call(db, family_with_token.id, "4.4.4.4", minutes_ago=1)

        monkeypatch.setattr(db_mod, "SessionLocal", lambda: _NonClosingSession(db))
        scan_mcp_anomalies()

        reminders = (
            db.query(Reminder)
            .filter(Reminder.reminder_type == "mcp_anomaly_detected")
            .all()
        )
        assert any("new_source_ip" in r.title for r in reminders)

    def test_unknown_ip_sentinel_ignored(self, db, family_with_token, monkeypatch):
        """The 'unknown' client_ip sentinel never raises an alert."""
        import apps.backend.app.database as db_mod
        from apps.backend.app.services.mcp_anomaly import scan_mcp_anomalies

        _add_call(db, family_with_token.id, "unknown", minutes_ago=1)

        monkeypatch.setattr(db_mod, "SessionLocal", lambda: _NonClosingSession(db))
        scan_mcp_anomalies()

        reminders = (
            db.query(Reminder)
            .filter(Reminder.reminder_type == "mcp_anomaly_detected")
            .all()
        )
        assert not any("new_source_ip" in r.title for r in reminders)

    def test_new_ip_dedup_within_hour(self, db, family_with_token, monkeypatch):
        """Repeated scans do not duplicate a new_source_ip alert."""
        import apps.backend.app.database as db_mod
        from apps.backend.app.services.mcp_anomaly import scan_mcp_anomalies

        # Baseline history is required for new-IP detection to engage
        _add_call(db, family_with_token.id, "6.6.6.6", minutes_ago=10 * 24 * 60)
        _add_call(db, family_with_token.id, "5.5.5.5", minutes_ago=1)
        monkeypatch.setattr(db_mod, "SessionLocal", lambda: _NonClosingSession(db))

        scan_mcp_anomalies()
        scan_mcp_anomalies()

        reminders = (
            db.query(Reminder)
            .filter(Reminder.reminder_type == "mcp_anomaly_detected")
            .all()
        )
        assert len(reminders) == 1, "dedup should collapse repeats within the hour"

    def test_first_ever_connection_no_alert(self, db, family_with_token, monkeypatch):
        """A family's very first connection has no baseline, so nothing is 'new'."""
        import apps.backend.app.database as db_mod
        from apps.backend.app.services.mcp_anomaly import scan_mcp_anomalies

        _add_call(db, family_with_token.id, "7.7.7.7", minutes_ago=1)
        monkeypatch.setattr(db_mod, "SessionLocal", lambda: _NonClosingSession(db))
        scan_mcp_anomalies()

        reminders = (
            db.query(Reminder)
            .filter(Reminder.reminder_type == "mcp_anomaly_detected")
            .all()
        )
        assert not any("new_source_ip" in r.title for r in reminders)

    def test_two_distinct_new_ips_each_alert(self, db, family_with_token, monkeypatch):
        """Distinct conditions alert separately, even while one is still unread."""
        import apps.backend.app.database as db_mod
        from apps.backend.app.services.mcp_anomaly import scan_mcp_anomalies

        _add_call(db, family_with_token.id, "8.8.8.8", minutes_ago=10 * 24 * 60)
        _add_call(db, family_with_token.id, "9.9.9.9", minutes_ago=1)
        _add_call(db, family_with_token.id, "10.10.10.10", minutes_ago=1)

        monkeypatch.setattr(db_mod, "SessionLocal", lambda: _NonClosingSession(db))
        scan_mcp_anomalies()

        reminders = (
            db.query(Reminder)
            .filter(Reminder.reminder_type == "mcp_anomaly_detected")
            .all()
        )
        assert len(reminders) == 2, (
            f"each distinct new IP needs its own alert, got {[r.title for r in reminders]}"
        )
        assert any("9.9.9.9" in r.title for r in reminders)
        assert any("10.10.10.10" in r.title for r in reminders)

    def test_same_ip_does_not_duplicate_across_scans(
        self, db, family_with_token, monkeypatch
    ):
        """The same condition stays quiet across scans (stable title identity)."""
        import apps.backend.app.database as db_mod
        from apps.backend.app.services.mcp_anomaly import scan_mcp_anomalies

        _add_call(db, family_with_token.id, "11.11.11.11", minutes_ago=10 * 24 * 60)
        _add_call(db, family_with_token.id, "12.12.12.12", minutes_ago=1)
        monkeypatch.setattr(db_mod, "SessionLocal", lambda: _NonClosingSession(db))

        scan_mcp_anomalies()
        scan_mcp_anomalies()

        reminders = (
            db.query(Reminder)
            .filter(Reminder.reminder_type == "mcp_anomaly_detected")
            .all()
        )
        assert len(reminders) == 1

    def test_drift_in_measurement_does_not_defeat_dedup(
        self, db, family_with_token, monkeypatch
    ):
        """A changing call count must not create a fresh alert each scan."""
        import apps.backend.app.database as db_mod
        from apps.backend.app.services.mcp_anomaly import scan_mcp_anomalies

        _add_tool_calls(db, family_with_token.id, 150, minutes_ago=1)
        monkeypatch.setattr(db_mod, "SessionLocal", lambda: _NonClosingSession(db))
        scan_mcp_anomalies()

        # More traffic in the same window → the measured count changes
        _add_tool_calls(db, family_with_token.id, 30, minutes_ago=1)
        scan_mcp_anomalies()

        reminders = (
            db.query(Reminder)
            .filter(Reminder.reminder_type == "mcp_anomaly_detected")
            .all()
        )
        assert len(reminders) == 1, (
            "measured count belongs in the body, not the dedup key"
        )
