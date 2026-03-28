"""SQLite 后端实现"""

from app.db.backend import DatabaseBackend


class SQLiteBackend(DatabaseBackend):
    """SQLite 数据库后端"""

    def get_connection_args(self) -> dict:
        # SQLite 在多线程环境下需要此参数
        return {"check_same_thread": False}

    def get_pool_config(self) -> dict:
        # SQLite 不使用连接池
        return {}