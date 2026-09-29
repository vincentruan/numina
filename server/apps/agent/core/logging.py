"""Agent 服务日志配置。

委托给 packages.core 的统一日志实现，保证 backend / agent / worker 三份日志
落到同一个 LOG_DIR（app.log + security.log），格式与轮转策略一致。
"""

import os

from packages.core.logging import setup_logging as _core_setup_logging

# agent 沿用历史格式（与 backend/worker 默认格式不同，但保留向后兼容）
_AGENT_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"


def setup_logging(
    log_level: str = "INFO",
    log_dir: str | None = "logs",
) -> None:
    """初始化 agent 日志：stdout + 文件（与 backend/worker 共用 LOG_DIR）。

    当 ``log_dir`` 为 ``None`` 时仅输出到 stdout，不创建日志文件。

    ``DEV_LOG_DIR`` 环境变量可覆盖 *log_dir* 参数:
    - ``"0"`` → 禁用文件日志 (console only)
    - 其他值 → 作为日志目录路径
    - 未设置 → 使用调用方传入的 ``log_dir``
    """
    _dev_log = os.environ.get("DEV_LOG_DIR")
    if _dev_log is not None:
        log_dir = None if _dev_log == "0" else _dev_log
    _core_setup_logging(
        log_level=log_level,
        log_dir=log_dir,
        log_format=_AGENT_LOG_FORMAT,
    )
