"""Tests for security logging service."""

import logging
import pytest
from pathlib import Path

from app.services.security_log import (
    SecurityEventType,
    setup_security_logging,
    _log_security_event,
)


class TestSecurityEventType:
    """Tests for SecurityEventType constants."""

    def test_event_types_exist(self):
        """Test that all expected event types are defined."""
        assert hasattr(SecurityEventType, "LOGIN_SUCCESS")
        assert hasattr(SecurityEventType, "LOGIN_FAILED_WRONG_PASSWORD")
        assert hasattr(SecurityEventType, "LOGIN_FAILED_USER_NOT_FOUND")
        assert hasattr(SecurityEventType, "LOGIN_RATE_LIMITED")
        assert hasattr(SecurityEventType, "UPLOAD_MAGIC_BYTES_MISMATCH")
        assert hasattr(SecurityEventType, "GLOBAL_RATE_LIMITED")


class TestSetupSecurityLogging:
    """Tests for setup_security_logging function."""

    def test_creates_logs_directory(self, tmp_path, monkeypatch):
        """Test that logs directory is created."""
        # Change to temp directory
        monkeypatch.chdir(tmp_path)
        setup_security_logging()
        assert Path("logs").exists()

    def test_configures_logger(self):
        """Test that logger is configured."""
        logger = logging.getLogger("security")
        # Just verify it doesn't raise an error
        setup_security_logging()


class TestLogSecurityEvent:
    """Tests for _log_security_event function."""

    def test_log_success_event(self, caplog):
        """Test logging a success event."""
        with caplog.at_level(logging.INFO, logger="security"):
            _log_security_event(SecurityEventType.LOGIN_SUCCESS, username="testuser", user_id="123")
        assert any("login_success" in record.message for record in caplog.records)
        assert any(record.levelno == logging.INFO for record in caplog.records)

    def test_log_failed_event(self, caplog):
        """Test logging a failed event."""
        with caplog.at_level(logging.INFO, logger="security"):
            _log_security_event(SecurityEventType.LOGIN_FAILED_WRONG_PASSWORD, username="testuser")
        # Check that the event was logged (at WARNING level which is >= INFO)
        assert any("login_failed_wrong_password" in record.message for record in caplog.records)

    def test_log_event_with_multiple_details(self, caplog):
        """Test logging with multiple details."""
        with caplog.at_level(logging.INFO, logger="security"):
            _log_security_event(
                SecurityEventType.LOGIN_SUCCESS,
                username="testuser",
                user_id="123",
                ip_address="192.168.1.1"
            )
        assert any("username=testuser" in record.message for record in caplog.records)
        assert any("user_id=123" in record.message for record in caplog.records)
        assert any("ip_address=192.168.1.1" in record.message for record in caplog.records)