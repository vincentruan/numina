"""Database session and base model for packages.

Provides SessionLocal, Base, and get_db for use by both backend and scheduler_worker.
The engine factory (app.db) stays in backend for Phase 1; scheduler_worker will
configure its own engine directly using DATABASE_URL from packages.core.settings.
"""

from sqlalchemy.orm import DeclarativeBase, sessionmaker

from packages.core.settings import settings

# Import engine factory from backend for Phase 1 (scheduler_worker configures its own)
from app.db import get_engine

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
