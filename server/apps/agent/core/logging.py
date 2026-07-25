"""Agent 服务日志配置。

委托给 packages.core 的统一日志实现，保证 backend / agent / worker 三份日志
落到同一个 LOG_DIR（app.log + security.log），格式与轮转策略一致。
"""

from packages.core.logging import setup_logging as _core_setup_logging

# agent 沿用历史格式（与 backend/worker 默认格式不同，但保留向后兼容）
_AGENT_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"


def setup_logging(
    log_level: str = "INFO",
    log_dir: str = "logs",
) -> None:
    """初始化 agent 日志：stdout + 文件（与 backend/worker 共用 LOG_DIR）。"""
    _core_setup_logging(
        log_level=log_level,
        log_dir=log_dir,
        log_format=_AGENT_LOG_FORMAT,
    )
