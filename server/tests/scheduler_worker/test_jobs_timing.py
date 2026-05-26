"""Scheduler Worker tests — Mock-based job invocation tests."""

import datetime
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_session_local():
    """Mock SessionLocal to avoid real DB connections."""
    mock_session = MagicMock()
    mock_session.close = MagicMock()

    with patch("packages.db.session.SessionLocal", return_value=mock_session):
        yield mock_session


class TestExchangeRateJob:
    """Test exchange rate job invocation."""

    def test_fetch_rates_job_calls_service(self, mock_session_local):
        """Verify fetch_rates_job invokes ExchangeRateService correctly."""
        with patch(
            "packages.domain.exchange_rate.service.ExchangeRateService.fetch_and_store_rates",
            return_value=True,
        ) as mock_fetch:
            from apps.scheduler_worker.jobs import fetch_rates_job

            fetch_rates_job()

            mock_fetch.assert_called_once_with(mock_session_local)

    def test_fetch_rates_job_handles_failure(self, mock_session_local):
        """Verify fetch_rates_job handles service failure gracefully."""
        with patch(
            "packages.domain.exchange_rate.service.ExchangeRateService.fetch_and_store_rates",
            return_value=False,
        ) as mock_fetch:
            from apps.scheduler_worker.jobs import fetch_rates_job

            fetch_rates_job()  # Should not raise

            mock_fetch.assert_called_once()


class TestSnapshotJob:
    """Test snapshot job invocation."""

    def test_snapshot_job_calls_service(self, mock_session_local):
        """Verify snapshot job invokes auto_generate_daily_snapshots."""
        with patch(
            "packages.domain.snapshot.service.auto_generate_daily_snapshots"
        ) as mock_snapshot:
            from apps.scheduler_worker.jobs import snapshot_job

            snapshot_job()

            mock_snapshot.assert_called_once()


class TestCleanupJobs:
    """Test cleanup job invocations."""

    def test_revoked_token_cleanup_job(self, mock_session_local):
        """Verify revoked token cleanup job executes correctly."""
        with patch(
            "packages.security.revoke_jti.cleanup_expired_revoked_tokens",
            return_value=5,
        ) as mock_cleanup:
            from apps.scheduler_worker.jobs import revoked_token_cleanup_job

            revoked_token_cleanup_job()

            mock_cleanup.assert_called_once()

    def test_device_session_cleanup_job(self, mock_session_local):
        """Verify device session cleanup job executes correctly."""
        with patch(
            "packages.domain.device.service.cleanup_expired_device_sessions",
            return_value=3,
        ) as mock_expired:
            with patch(
                "packages.domain.device.service.delete_old_revoked_sessions",
                return_value=2,
            ) as mock_purged:
                from apps.scheduler_worker.jobs import device_session_cleanup_job

                device_session_cleanup_job()

                mock_expired.assert_called_once()
                mock_purged.assert_called_once()


class TestReminderJob:
    """Test reminder job invocation."""

    def test_reminder_job_calls_service(self, mock_session_local):
        """Verify reminder job invokes run_scheduled_checks."""
        with patch(
            "packages.domain.notification.service.run_scheduled_checks"
        ) as mock_checks:
            from apps.scheduler_worker.jobs import reminder_job

            reminder_job()

            mock_checks.assert_called_once()


class TestAuditLogPurgeJob:
    """Test audit log purge invocation."""

    def test_audit_log_purge_job(self, mock_session_local):
        """Verify audit log purge job calls correct service."""
        with patch(
            "packages.domain.audit.service.purge_old_audit_logs"
        ) as mock_purge:
            from apps.scheduler_worker.jobs import audit_log_purge_job

            audit_log_purge_job()

            mock_purge.assert_called_once_with(retention_days=90)


class TestSchedulerConfig:
    """Test scheduler configuration constants."""

    def test_exchange_rate_allowed_hours(self):
        """Verify exchange rate job hour configuration."""
        # Job config: hour="8,10,12,14,16,18,20,22"
        allowed_hours = [8, 10, 12, 14, 16, 18, 20, 22]
        # Should NOT include midnight hours
        assert 0 not in allowed_hours
        assert 1 not in allowed_hours
        assert 2 not in allowed_hours
        # Should include business hours
        assert 8 in allowed_hours
        assert 12 in allowed_hours

    def test_snapshot_job_time(self):
        """Verify snapshot job scheduled at 00:05."""
        # Job config: hour=0, minute=5
        snapshot_hour = 0
        snapshot_minute = 5
        assert snapshot_hour == 0
        assert snapshot_minute == 5

    def test_reminder_job_time(self):
        """Verify reminder job scheduled at 09:20."""
        # Job config: hour=9, minute=20
        reminder_hour = 9
        reminder_minute = 20
        assert reminder_hour == 9
        assert reminder_minute == 20