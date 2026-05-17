"""Agent 服务配置。

环境变量层级（优先级从高到低）：
1. 系统环境变量（os.environ）— 最高优先级
2. DeerFlow 动态注入（family_adapter_cache 设置 DEER_FLOW_CONFIG_PATH、
   AI_MODEL、AI_API_KEY）
3. .env 文件中的值
4. 类中的默认值
"""

from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings

_OLD_DEFAULTS = {
    "SESSIONS_DATA_DIR": "data/sessions",
    "AGENT_DATA_DIR": "data/workspace",
}


class AgentSettings(BaseSettings):
    ENVIRONMENT: str = "development"

    # 统一数据根目录
    DATA_ROOT: str = "~/.numina/data"

    # Backend 内部通信
    BACKEND_BASE_URL: str = "http://backend:8000"
    AGENT_INTERNAL_TOKEN: str = ""  # 与 backend 共享的 service-to-service token

    # 加密（与 backend 共享同一个 Fernet key，用于解密 API Key）
    AI_ENCRYPTION_KEY: str = ""

    # 日志
    LOG_LEVEL: str = "INFO"
    LOG_DIR: str = ""

    # 会话 JSONL 文件存储目录（按 family_id 隔离）
    SESSIONS_DATA_DIR: str = "data/sessions"

    # Agent 数据根目录（memory、session JSONL 等按家庭隔离的文件均存放于此）
    AGENT_DATA_DIR: str = "data/workspace"

    # DeerFlow checkpointer DB 路径
    DEERFLOW_DB_PATH: str = ""

    # DeerFlow 并发与超时
    DEERFLOW_CONCURRENCY: int = 8
    DEERFLOW_DEFAULT_TIMEOUT: int = 120

    # DeerFlow Gateway API 地址（内部代理端点使用）
    DEERFLOW_GATEWAY_URL: str = "http://localhost:8001"

    model_config = {"env_file": ".env", "extra": "ignore"}

    @model_validator(mode="after")
    def _resolve_data_root(self) -> "AgentSettings":
        root = str(Path(self.DATA_ROOT).expanduser().resolve())
        self.DATA_ROOT = root

        if _OLD_DEFAULTS["SESSIONS_DATA_DIR"] == self.SESSIONS_DATA_DIR or not self.SESSIONS_DATA_DIR:
            self.SESSIONS_DATA_DIR = str(Path(root) / "workspace")

        if _OLD_DEFAULTS["AGENT_DATA_DIR"] == self.AGENT_DATA_DIR or not self.AGENT_DATA_DIR:
            self.AGENT_DATA_DIR = str(Path(root) / "workspace")

        if not self.LOG_DIR:
            self.LOG_DIR = str(Path(root) / "logs")

        if not self.DEERFLOW_DB_PATH:
            self.DEERFLOW_DB_PATH = str(Path(root) / "db" / "deerflow-checkpoints.db")

        return self

    def validate_required(self) -> None:
        """启动时校验必填配置，缺失则快速失败。"""
        if not self.AGENT_INTERNAL_TOKEN:
            raise ValueError(
                "AGENT_INTERNAL_TOKEN 未配置。请在环境变量或 .env 文件中设置此值。"
            )


settings = AgentSettings()
