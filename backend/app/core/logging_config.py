"""Unified logging configuration module.

Provides centralized logging configuration with support for:
- Configurable log format and level
- Log rotation (by size or time)
- Log archiving (compression)
- Log cleanup (deletion of expired logs)
"""

import gzip
import logging
import shutil
from datetime import datetime, timedelta
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from pathlib import Path


def setup_logging(
    log_level: str = "INFO",
    log_dir: str = "logs",
    log_format: str | None = None,
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 10,
    rotation_mode: str = "size",  # "size" or "time"
    retention_days: int = 30,
) -> None:
    """Setup unified logging configuration for the application.

    Args:
        log_level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_dir: Directory to store log files
        log_format: Custom log format string
        max_bytes: Max size per log file (for size-based rotation)
        backup_count: Number of backup files to keep
        rotation_mode: "size" for size-based, "time" for time-based rotation
        retention_days: Days to retain log files before cleanup
    """
    # Ensure log directory exists
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    # Default log format
    if log_format is None:
        log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    formatter = logging.Formatter(log_format)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Remove existing handlers to avoid duplicates
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # File handler with rotation
    app_log_file = log_path / "app.log"

    if rotation_mode == "time":
        file_handler: logging.Handler = TimedRotatingFileHandler(
            app_log_file,
            when="midnight",
            backupCount=backup_count,
            encoding="utf-8",
        )
    else:
        file_handler = RotatingFileHandler(
            app_log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
    file_handler.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    # Setup security logger with separate file
    _setup_security_logger(log_path, formatter, max_bytes, backup_count, rotation_mode)

    # Perform initial log cleanup
    cleanup_old_logs(log_path, retention_days)


def _setup_security_logger(
    log_path: Path,
    formatter: logging.Formatter,
    max_bytes: int,
    backup_count: int,
    rotation_mode: str,
) -> None:
    """Setup security logger with dedicated log file."""
    security_logger = logging.getLogger("security")
    security_logger.setLevel(logging.INFO)

    # Remove existing handlers
    for handler in security_logger.handlers[:]:
        security_logger.removeHandler(handler)

    # Security log file with rotation
    security_log_file = log_path / "security.log"

    if rotation_mode == "time":
        security_handler: logging.Handler = TimedRotatingFileHandler(
            security_log_file,
            when="midnight",
            backupCount=backup_count,
            encoding="utf-8",
        )
    else:
        security_handler = RotatingFileHandler(
            security_log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )

    security_handler.setLevel(logging.INFO)
    security_handler.setFormatter(formatter)
    security_logger.addHandler(security_handler)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the given name.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)


def cleanup_old_logs(log_dir: Path, retention_days: int) -> int:
    """Clean up log files older than retention period.

    Args:
        log_dir: Directory containing log files
        retention_days: Number of days to retain logs

    Returns:
        Number of files deleted
    """
    if not log_dir.exists():
        return 0

    cutoff_date = datetime.now() - timedelta(days=retention_days)
    deleted_count = 0

    # Get all log files (including rotated and compressed)
    for log_file in log_dir.glob("**/*"):
        if log_file.is_file() and (log_file.suffix in (".log", ".gz") or ".log." in log_file.name):
            # Get file modification time
            file_mtime = datetime.fromtimestamp(log_file.stat().st_mtime)

            if file_mtime < cutoff_date:
                try:
                    log_file.unlink()
                    deleted_count += 1
                except OSError:
                    pass  # Ignore errors during cleanup

    return deleted_count


def archive_old_logs(log_dir: Path, compress_after_days: int = 7) -> int:
    """Archive (compress) old log files.

    Args:
        log_dir: Directory containing log files
        compress_after_days: Days after which to compress log files

    Returns:
        Number of files compressed
    """
    if not log_dir.exists():
        return 0

    cutoff_date = datetime.now() - timedelta(days=compress_after_days)
    compressed_count = 0

    # Find rotated log files that haven't been compressed
    for log_file in log_dir.glob("**/*.log.[0-9]*"):
        if log_file.is_file() and not log_file.with_suffix(log_file.suffix + ".gz").exists():
            file_mtime = datetime.fromtimestamp(log_file.stat().st_mtime)

            if file_mtime < cutoff_date:
                try:
                    # Compress the file
                    with open(log_file, "rb") as f_in:
                        with gzip.open(log_file.with_suffix(log_file.suffix + ".gz"), "wb") as f_out:
                            shutil.copyfileobj(f_in, f_out)

                    # Remove original file after successful compression
                    log_file.unlink()
                    compressed_count += 1
                except OSError:
                    pass  # Ignore errors during compression

    return compressed_count