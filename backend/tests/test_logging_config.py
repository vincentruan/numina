"""Tests for logging configuration module."""

import gzip
import logging
import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from app.core.logging_config import (
    archive_old_logs,
    cleanup_old_logs,
    get_logger,
    setup_logging,
)


class TestSetupLogging:
    """Tests for setup_logging function."""

    def test_setup_logging_creates_log_directory(self, tmp_path: Path):
        """Test that setup_logging creates the log directory if it doesn't exist."""
        log_dir = tmp_path / "logs"
        assert not log_dir.exists()

        setup_logging(log_dir=str(log_dir))

        assert log_dir.exists()
        assert log_dir.is_dir()

    def test_setup_logging_creates_app_log_file(self, tmp_path: Path):
        """Test that setup_logging creates app.log file."""
        log_dir = tmp_path / "logs"

        setup_logging(log_dir=str(log_dir))

        app_log = log_dir / "app.log"
        assert app_log.exists()

    def test_setup_logging_creates_security_log_file(self, tmp_path: Path):
        """Test that setup_logging creates security.log file."""
        log_dir = tmp_path / "logs"

        setup_logging(log_dir=str(log_dir))

        security_log = log_dir / "security.log"
        assert security_log.exists()

    def test_setup_logging_configures_root_logger(self, tmp_path: Path):
        """Test that setup_logging configures the root logger correctly."""
        log_dir = tmp_path / "logs"

        setup_logging(log_level="DEBUG", log_dir=str(log_dir))

        root_logger = logging.getLogger()
        assert root_logger.level == logging.DEBUG
        assert len(root_logger.handlers) >= 2  # console + file

    def test_setup_logging_uses_custom_format(self, tmp_path: Path):
        """Test that setup_logging applies custom log format."""
        log_dir = tmp_path / "logs"
        custom_format = "%(levelname)s - %(message)s"

        setup_logging(log_format=custom_format, log_dir=str(log_dir))

        root_logger = logging.getLogger()
        for handler in root_logger.handlers:
            if hasattr(handler, "formatter"):
                assert handler.formatter._fmt == custom_format

    def test_setup_logging_size_rotation(self, tmp_path: Path):
        """Test that size-based rotation is configured correctly."""
        log_dir = tmp_path / "logs"

        setup_logging(
            rotation_mode="size",
            max_bytes=1024,
            backup_count=5,
            log_dir=str(log_dir),
        )

        root_logger = logging.getLogger()
        file_handlers = [h for h in root_logger.handlers if isinstance(h, logging.handlers.RotatingFileHandler)]
        assert len(file_handlers) >= 1
        assert file_handlers[0].maxBytes == 1024
        assert file_handlers[0].backupCount == 5

    def test_setup_logging_time_rotation(self, tmp_path: Path):
        """Test that time-based rotation is configured correctly."""
        log_dir = tmp_path / "logs"

        setup_logging(
            rotation_mode="time",
            backup_count=7,
            log_dir=str(log_dir),
        )

        root_logger = logging.getLogger()
        time_handlers = [h for h in root_logger.handlers if isinstance(h, logging.handlers.TimedRotatingFileHandler)]
        assert len(time_handlers) >= 1

    def test_setup_logging_removes_duplicate_handlers(self, tmp_path: Path):
        """Test that calling setup_logging twice doesn't duplicate handlers."""
        log_dir = tmp_path / "logs"

        setup_logging(log_dir=str(log_dir))
        initial_count = len(logging.getLogger().handlers)

        setup_logging(log_dir=str(log_dir))
        final_count = len(logging.getLogger().handlers)

        assert initial_count == final_count


class TestGetLogger:
    """Tests for get_logger function."""

    def test_get_logger_returns_logger_instance(self):
        """Test that get_logger returns a Logger instance."""
        logger = get_logger("test_module")
        assert isinstance(logger, logging.Logger)
        assert logger.name == "test_module"

    def test_get_logger_same_name_returns_same_instance(self):
        """Test that get_logger with same name returns same logger."""
        logger1 = get_logger("test_module")
        logger2 = get_logger("test_module")
        assert logger1 is logger2


class TestCleanupOldLogs:
    """Tests for cleanup_old_logs function."""

    def test_cleanup_removes_old_log_files(self, tmp_path: Path):
        """Test that cleanup removes log files older than retention period."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir()

        # Create an old log file
        old_log = log_dir / "old.log"
        old_log.write_text("old content")

        # Set modification time to 40 days ago
        old_time = datetime.now() - timedelta(days=40)
        os.utime(old_log, (old_time.timestamp(), old_time.timestamp()))

        # Create a new log file
        new_log = log_dir / "new.log"
        new_log.write_text("new content")

        deleted = cleanup_old_logs(log_dir, retention_days=30)

        assert deleted == 1
        assert not old_log.exists()
        assert new_log.exists()

    def test_cleanup_removes_compressed_log_files(self, tmp_path: Path):
        """Test that cleanup removes compressed .gz files older than retention."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir()

        # Create an old compressed log file
        old_gz = log_dir / "old.log.gz"
        with gzip.open(old_gz, "wt") as f:
            f.write("old compressed content")

        # Set modification time to 40 days ago
        old_time = datetime.now() - timedelta(days=40)
        os.utime(old_gz, (old_time.timestamp(), old_time.timestamp()))

        deleted = cleanup_old_logs(log_dir, retention_days=30)

        assert deleted == 1
        assert not old_gz.exists()

    def test_cleanup_removes_rotated_log_files(self, tmp_path: Path):
        """Test that cleanup removes rotated log files (.log.1, .log.2, etc.)."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir()

        # Create an old rotated log file
        old_rotated = log_dir / "app.log.1"
        old_rotated.write_text("rotated content")

        # Set modification time to 40 days ago
        old_time = datetime.now() - timedelta(days=40)
        os.utime(old_rotated, (old_time.timestamp(), old_time.timestamp()))

        deleted = cleanup_old_logs(log_dir, retention_days=30)

        assert deleted == 1
        assert not old_rotated.exists()

    def test_cleanup_keeps_recent_logs(self, tmp_path: Path):
        """Test that cleanup keeps log files within retention period."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir()

        # Create a recent log file (10 days old)
        recent_log = log_dir / "recent.log"
        recent_log.write_text("recent content")

        recent_time = datetime.now() - timedelta(days=10)
        os.utime(recent_log, (recent_time.timestamp(), recent_time.timestamp()))

        deleted = cleanup_old_logs(log_dir, retention_days=30)

        assert deleted == 0
        assert recent_log.exists()

    def test_cleanup_nonexistent_directory_returns_zero(self):
        """Test that cleanup returns 0 for nonexistent directory."""
        nonexistent = Path("/nonexistent/logs")
        deleted = cleanup_old_logs(nonexistent, retention_days=30)
        assert deleted == 0


class TestArchiveOldLogs:
    """Tests for archive_old_logs function."""

    def test_archive_compresses_old_rotated_logs(self, tmp_path: Path):
        """Test that archive compresses rotated log files older than threshold."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir()

        # Create an old rotated log file
        old_rotated = log_dir / "app.log.1"
        old_rotated.write_text("rotated content to compress")

        # Set modification time to 10 days ago
        old_time = datetime.now() - timedelta(days=10)
        os.utime(old_rotated, (old_time.timestamp(), old_time.timestamp()))

        compressed = archive_old_logs(log_dir, compress_after_days=7)

        assert compressed == 1
        assert not old_rotated.exists()
        assert (log_dir / "app.log.1.gz").exists()

        # Verify content is preserved
        with gzip.open(log_dir / "app.log.1.gz", "rt") as f:
            assert f.read() == "rotated content to compress"

    def test_archive_keeps_recent_rotated_logs(self, tmp_path: Path):
        """Test that archive doesn't compress files newer than threshold."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir()

        # Create a recent rotated log file (3 days old)
        recent_rotated = log_dir / "app.log.1"
        recent_rotated.write_text("recent rotated content")

        recent_time = datetime.now() - timedelta(days=3)
        os.utime(recent_rotated, (recent_time.timestamp(), recent_time.timestamp()))

        compressed = archive_old_logs(log_dir, compress_after_days=7)

        assert compressed == 0
        assert recent_rotated.exists()
        assert not (log_dir / "app.log.1.gz").exists()

    def test_archive_skips_already_compressed_files(self, tmp_path: Path):
        """Test that archive skips files that already have .gz versions."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir()

        # Create an old rotated log file and its compressed version
        old_rotated = log_dir / "app.log.1"
        old_rotated.write_text("old content")
        old_gz = log_dir / "app.log.1.gz"
        with gzip.open(old_gz, "wt") as f:
            f.write("already compressed")

        # Set modification time to 10 days ago
        old_time = datetime.now() - timedelta(days=10)
        os.utime(old_rotated, (old_time.timestamp(), old_time.timestamp()))

        compressed = archive_old_logs(log_dir, compress_after_days=7)

        assert compressed == 0  # Skipped because .gz already exists

    def test_archive_nonexistent_directory_returns_zero(self):
        """Test that archive returns 0 for nonexistent directory."""
        nonexistent = Path("/nonexistent/logs")
        compressed = archive_old_logs(nonexistent, compress_after_days=7)
        assert compressed == 0


class TestLogFormatConsistency:
    """Tests for log format consistency."""

    def test_default_format_contains_required_fields(self, tmp_path: Path):
        """Test that default log format includes timestamp, name, level, message."""
        log_dir = tmp_path / "logs"

        setup_logging(log_dir=str(log_dir))

        logger = get_logger("test.app")
        logger.info("Test message")

        # Read the log file
        app_log = log_dir / "app.log"
        content = app_log.read_text()

        # Verify format contains expected components
        assert "INFO" in content
        assert "test.app" in content
        assert "Test message" in content
        # Timestamp format: YYYY-MM-DD HH:MM:SS
        assert len(content.split(" - ")) >= 4

    def test_security_logger_format_matches_app_logger(self, tmp_path: Path):
        """Test that security logger uses same format as app logger."""
        log_dir = tmp_path / "logs"

        setup_logging(log_dir=str(log_dir))

        security_logger = get_logger("security")
        security_logger.info("Security event test")

        # Read the security log file
        security_log = log_dir / "security.log"
        content = security_log.read_text()

        # Verify format matches app log format
        assert "INFO" in content
        assert "security" in content
        assert "Security event test" in content
        assert len(content.split(" - ")) >= 3