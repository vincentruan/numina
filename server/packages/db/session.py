"""Database session and base model for packages.

Provides SessionLocal, Base, and get_db for use by both backend and scheduler_worker.
"""

from datetime import UTC, datetime

from sqlalchemy import DateTime, TypeDecorator
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from packages.core.settings import settings
from packages.db.engine import get_engine


class UTCDateTime(TypeDecorator):
    """DateTime that always returns timezone-aware (UTC) datetimes.

    PostgreSQL ``TIMESTAMP WITH TIME ZONE`` already returns aware datetimes,
    but SQLite returns naive ones.  This decorator normalises both so
    application code never has to call ``ensure_utc()`` or handle the
    naive/aware mismatch.
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_result_value(self, value: datetime | None, dialect) -> datetime | None:
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value

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

