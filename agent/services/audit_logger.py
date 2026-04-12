"""Agent 调用审计日志服务。

每次 agent 调用都写入一条结构化 JSON-line 到 logs/agent-audit.log。
日志轮转：每天午夜，保留 30 天。
"""

import json
import logging
import os
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from logging.handlers import TimedRotatingFileHandler
from typing import Optional

_audit_logger: Optional[logging.Logger] = None


def _get_audit_logger() -> logging.Logger:
    global _audit_logger
    if _audit_logger is not None:
        return _audit_logger

    os.makedirs("logs", exist_ok=True)
    logger = logging.getLogger("agent.audit")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    if not logger.handlers:
        handler = TimedRotatingFileHandler(
            filename="logs/agent-audit.log",
            when="midnight",
            backupCount=30,
            encoding="utf-8",
        )
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)

    _audit_logger = logger
    return logger


@dataclass
class AuditEntry:
    family_id: str
    capability: str
    success: bool
    audit_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    user_id: Optional[str] = None
    skill_triggered: Optional[str] = None
    fallback_used: bool = False
    deerflow_attempted: bool = False
    duration_ms: Optional[int] = None
    error_type: Optional[str] = None
    output_summary: Optional[str] = None

    def __post_init__(self) -> None:
        if self.output_summary and len(self.output_summary) > 200:
            self.output_summary = self.output_summary[:200]


class AuditLogger:
    """写入结构化 agent 调用审计日志。"""

    def log_call(self, entry: AuditEntry) -> None:
        """写入一条审计日志。失败时静默吞掉，不影响主流程。"""
        try:
            logger = _get_audit_logger()
            level = logging.INFO if entry.success else logging.WARNING
            event_type = "AGENT_CALL"
            data = asdict(entry)
            # Format: <timestamp> - <level> - [AGENT_CALL] key=value | key=value
            kv = " | ".join(f"{k}={v}" for k, v in data.items() if v is not None)
            msg = f"{entry.timestamp} - {'INFO' if level == logging.INFO else 'WARNING'} - [{event_type}] {kv}"
            logger.log(level, msg)
        except Exception:
            pass  # Audit must never break the main path


audit_logger = AuditLogger()
