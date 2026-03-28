"""MySQL 后端实现"""

from app.db.backend import DatabaseBackend


class MySQLBackend(DatabaseBackend):
    """MySQL 数据库后端"""

    def get_connection_args(self) -> dict:
        # MySQL 无特殊连接参数
        return {}

    def get_pool_config(self) -> dict:
        # MySQL 连接池配置
        return {
            "pool_size": 10,
            "pool_recycle": 3600,  # 1小时回收连接，避免 MySQL 8小时超时
            "pool_pre_ping": True,  # 连接前检查有效性
        }