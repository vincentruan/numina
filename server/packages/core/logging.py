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
from datetime import UTC, datetime, timedelta
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from pathlib import Path


def setup_logging(
    log_level: str = "INFO",
    log_dir: str | None = None,
    log_format: str | None = None,
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 10,
    rotation_mode: str = "size",  # "size" or "time"
    retention_days: int = 30,
    service_name: str = "",
) -> None:
    """Setup unified logging configuration for the application.

    Args:
        log_dir: Directory for log files. When ``None``, only a console handler
            is attached — no log files are created. Pass a path (typically
            ``settings.LOG_DIR``) to enable rotating file output.
        service_name: Optional service identifier (e.g. ``"backend"``,
            ``"agent"``). When set, log files are prefixed: ``{service_name}-app.log``.
            Keeps logs separate when multiple services share one directory.
    """
    log_level_upper = log_level.upper()

    if log_format is None:
        log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    formatter = logging.Formatter(log_format)

    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level_upper, logging.INFO))

    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, log_level_upper, logging.INFO))
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    if log_dir is not None:
        _add_file_handlers(
            log_dir,
            formatter,
            log_level_upper,
            max_bytes,
            backup_count,
            rotation_mode,
            retention_days,
            service_name=service_name,
        )


def _add_file_handlers(
    log_dir: str,
    formatter: logging.Formatter,
    log_level_upper: str,
    max_bytes: int,
    backup_count: int,
    rotation_mode: str,
    retention_days: int,
    service_name: str = "",
) -> None:
    """Add rotating file handlers for app + security loggers."""
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    prefix = f"{service_name}-" if service_name else ""
    app_log_file = log_path / f"{prefix}app.log"

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
    file_handler.setLevel(getattr(logging, log_level_upper, logging.INFO))
    file_handler.setFormatter(formatter)
    logging.getLogger().addHandler(file_handler)

    _setup_security_logger(
        log_path,
        formatter,
        max_bytes,
        backup_count,
        rotation_mode,
        service_name=service_name,
    )

    cleanup_old_logs(log_path, retention_days)


def _setup_security_logger(
    log_path: Path,
    formatter: logging.Formatter,
    max_bytes: int,
    backup_count: int,
    rotation_mode: str,
    service_name: str = "",
) -> None:
    """Setup security logger with dedicated log file."""
    security_logger = logging.getLogger("security")
    security_logger.setLevel(logging.INFO)

    for handler in security_logger.handlers[:]:
        security_logger.removeHandler(handler)

    prefix = f"{service_name}-" if service_name else ""
    security_log_file = log_path / f"{prefix}security.log"

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
    """Get a logger instance with the given name."""
    return logging.getLogger(name)


def cleanup_old_logs(log_dir: Path, retention_days: int) -> int:
    """Clean up log files older than retention period."""
    if not log_dir.exists():
        return 0

    cutoff_date = datetime.now(UTC) - timedelta(days=retention_days)
    deleted_count = 0

    for log_file in log_dir.glob("**/*"):
        if log_file.is_file() and (
            log_file.suffix in (".log", ".gz") or ".log." in log_file.name
        ):
            file_mtime = datetime.fromtimestamp(log_file.stat().st_mtime, tz=UTC)

            if file_mtime < cutoff_date:
                try:
                    log_file.unlink()
                    deleted_count += 1
                except OSError:
                    pass

    return deleted_count


def archive_old_logs(log_dir: Path, compress_after_days: int = 7) -> int:
    """Archive (compress) old log files."""
    if not log_dir.exists():
        return 0

    cutoff_date = datetime.now(UTC) - timedelta(days=compress_after_days)
    compressed_count = 0

    for log_file in log_dir.glob("**/*.log.[0-9]*"):
        if (
            log_file.is_file()
            and not log_file.with_suffix(log_file.suffix + ".gz").exists()
        ):
            file_mtime = datetime.fromtimestamp(log_file.stat().st_mtime, tz=UTC)

            if file_mtime < cutoff_date:
                try:
                    with (
                        open(log_file, "rb") as f_in,
                        gzip.open(
                            log_file.with_suffix(log_file.suffix + ".gz"), "wb"
                        ) as f_out,
                    ):
                        shutil.copyfileobj(f_in, f_out)

                    log_file.unlink()
                    compressed_count += 1
                except OSError:
                    pass

    return compressed_count
