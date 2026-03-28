"""数据库配置模块 - 使用多数据库后端工厂"""

from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings
from app.db import get_engine

# 使用工厂创建 engine（自动识别数据库类型）
engine = get_engine(settings.DATABASE_URL)

# Session 工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """ORM 模型基类"""
    pass


def get_db():
    """FastAPI 依赖注入：获取数据库 Session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()