"""Agent 调用审计日志服务。

每次 agent 调用都写入一条结构化 JSON-line 到 {LOG_DIR}/agent-audit.log。
日志轮转：每天午夜，保留 30 天。
"""

import logging
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

_audit_logger: logging.Logger | None = None


def setup_audit_logger() -> None:
    """Initialize audit logger. Call from main.py lifespan startup."""
    global _audit_logger

    from apps.agent.app.config import settings

    log_dir = Path(settings.LOG_DIR)
    log_dir.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("agent.audit")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    if not logger.handlers:
        handler = TimedRotatingFileHandler(
            filename=str(log_dir / "agent-audit.log"),
            when="midnight",
            backupCount=30,
            encoding="utf-8",
        )
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)

    _audit_logger = logger


def _get_audit_logger() -> logging.Logger:
    """Return the audit logger, initializing lazily if setup wasn't called."""
    global _audit_logger
    if _audit_logger is None:
        setup_audit_logger()
    assert _audit_logger is not None
    return _audit_logger


@dataclass
class AuditEntry:
    family_id: str
    skill_id: str
    success: bool
    audit_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    user_id: str | None = None
    skill_triggered: str | None = None
    fallback_used: bool = False
    deerflow_attempted: bool = False
    duration_ms: int | None = None
    error_type: str | None = None
    output_summary: str | None = None
    run_id: str | None = None  # [Integrated with Numina Multi-Tenant]

    def __post_init__(self) -> None:
        if self.output_summary and len(self.output_summary) > 200:
            self.output_summary = self.output_summary[:200]


class AuditLogger:
    """写入结构化 agent 调用审计日志。"""

    def log_call(self, entry: AuditEntry) -> None:
        """写入一条审计日志。失败时静默吞掉，不影响主流程。"""
        try:
            level = logging.INFO if entry.success else logging.WARNING
            event_type = "AGENT_CALL"
            data = asdict(entry)
            # Format: <timestamp> - <level> - [AGENT_CALL] key=value | key=value
            kv = " | ".join(f"{k}={v}" for k, v in data.items() if v is not None)
            msg = f"{entry.timestamp} - {'INFO' if level == logging.INFO else 'WARNING'} - [{event_type}] {kv}"
            _get_audit_logger().log(level, msg)
        except Exception:
            pass  # Audit must never break the main path


audit_logger = AuditLogger()
