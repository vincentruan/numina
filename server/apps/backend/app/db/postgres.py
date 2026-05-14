"""PostgreSQL 后端实现"""

from apps.backend.app.db.backend import DatabaseBackend


class PostgreSQLBackend(DatabaseBackend):
    """PostgreSQL 数据库后端"""

    def get_connection_args(self) -> dict:
        # PostgreSQL 无特殊连接参数
        return {}

    def get_pool_config(self) -> dict:
        # PostgreSQL 连接池配置
        return {
            "pool_size": 10,
            "pool_pre_ping": True,
        }