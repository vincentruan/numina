"""数据库后端工厂"""

from sqlalchemy import Engine
from sqlalchemy.engine.url import make_url

from app.db.backend import DatabaseBackend
from app.db.postgres import PostgreSQLBackend
from app.db.sqlite import SQLiteBackend

BACKEND_MAP: dict[str, type[DatabaseBackend]] = {
    "sqlite": SQLiteBackend,
    "postgresql": PostgreSQLBackend,
    "postgresql+psycopg2": PostgreSQLBackend,
    "postgresql+psycopg": PostgreSQLBackend,
}


def create_backend(url: str) -> DatabaseBackend:
    """根据 DATABASE_URL 创建对应的 Backend

    Args:
        url: SQLAlchemy 连接 URL，如:
            - sqlite:///./data/numina.db
            - postgresql+psycopg2://user:pass@host:5432/db

    Returns:
        DatabaseBackend 实例

    Raises:
        ValueError: 不支持的数据库类型
    """
    parsed = make_url(url)
    dialect = parsed.drivername

    # 尝试完整匹配
    if dialect in BACKEND_MAP:
        return BACKEND_MAP[dialect]()

    # 提取基础方言名（去除驱动部分）
    base_dialect = dialect.split("+")[0] if "+" in dialect else dialect

    if base_dialect not in BACKEND_MAP:
        supported = ", ".join(BACKEND_MAP.keys())
        raise ValueError(f"不支持的数据库类型: {dialect}。支持的类型: {supported}")

    return BACKEND_MAP[base_dialect]()


def get_engine(url: str) -> Engine:
    """便捷函数：直接返回 Engine"""
    backend = create_backend(url)
    return backend.create_engine(url)


def get_session_factory(url: str):
    """便捷函数：返回 Session 工厂"""
    backend = create_backend(url)
    engine = backend.create_engine(url)
    return backend.create_session_factory(engine)