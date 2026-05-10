"""独立数据库连接模块 - 支持 SQLite/MySQL/PostgreSQL"""

import os
from typing import Generator
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, Session, declarative_base

# 从环境变量读取数据库 URL，支持多种数据库
DEFAULT_DATABASE_URL = "sqlite:///./numina_test.db"
DATABASE_URL = os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL") or DEFAULT_DATABASE_URL

# SQLAlchemy ORM Base
Base = declarative_base()


def get_engine(database_url: str = None) -> Engine:
    """
    创建数据库引擎
    
    支持:
    - SQLite: sqlite:///path/to/db.db
    - MySQL: mysql+pymysql://user:pass@host/db
    - PostgreSQL: postgresql://user:pass@host/db
    """
    url = database_url or DATABASE_URL
    
    connect_args = {}
    
    # SQLite 特殊处理
    if url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
        engine = create_engine(url, connect_args=connect_args, echo=False)
    else:
        # MySQL/PostgreSQL 连接池配置
        engine = create_engine(
            url,
            pool_size=5,
            max_overflow=10,
            pool_timeout=30,
            pool_recycle=3600,
            echo=False
        )
    
    return engine


# 延迟初始化，允许在运行时指定 URL
_engine = None


def init_engine(database_url: str = None):
    """初始化引擎（允许运行时指定 URL）"""
    global _engine
    _engine = get_engine(database_url)
    return _engine


def get_engine_instance() -> Engine:
    """获取引擎实例（懒加载）"""
    global _engine
    if _engine is None:
        _engine = get_engine()
    return _engine


# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False)


def init_session_factory(engine: Engine = None):
    """初始化 session factory"""
    if engine is None:
        engine = get_engine_instance()
    SessionLocal.configure(bind=engine)
    return SessionLocal


def get_db() -> Generator[Session, None, None]:
    """获取数据库 session（上下文管理器）"""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_db_session() -> Session:
    """直接获取数据库 session（需手动管理）"""
    return SessionLocal()


def execute_sql(db: Session, sql: str, params: dict = None):
    """执行原始 SQL"""
    return db.execute(text(sql), params or {})


def get_database_type(url: str = None) -> str:
    """获取数据库类型"""
    url = url or DATABASE_URL
    if url.startswith("sqlite"):
        return "sqlite"
    elif url.startswith("mysql"):
        return "mysql"
    elif url.startswith("postgresql"):
        return "postgresql"
    return "unknown"
