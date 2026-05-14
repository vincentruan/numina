"""Database session and base model for packages.

Provides SessionLocal, Base, and get_db for use by both backend and scheduler_worker.
"""

from sqlalchemy.orm import DeclarativeBase, sessionmaker

from packages.core.settings import settings
from packages.db.engine import get_engine

engine = get_engine(settings.DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """ORM model base class."""
    pass


def get_db():
    """FastAPI dependency: yield a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
