"""SQLite-backed session index for AI Agent sessions.

Stores session metadata (title, status, last summary, etc.) in the same
SQLite file as the DeerFlow checkpointer (.deer-flow/data/deerflow.db).
The JSONL file holds the full event stream; this table is the index layer.

AiSessionRow inherits from DeerFlow's Base so it is auto-created when
init_engine() calls Base.metadata.create_all().
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from deerflow.persistence.base import Base
from sqlalchemy import Boolean, DateTime, Index, String, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import Mapped, mapped_column

logger = logging.getLogger(__name__)


class AiSessionRow(Base):
    __tablename__ = "ai_sessions"

    session_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    family_id: Mapped[str] = mapped_column(String(64), nullable=False)
    user_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    capability: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str | None] = mapped_column(String(256), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    jsonl_path: Mapped[str] = mapped_column(String(512), nullable=False)
    last_message_summary: Mapped[str | None] = mapped_column(String(200), nullable=True)
    last_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    has_attachments: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    __table_args__ = (
        Index("ix_ai_sessions_family_updated", "family_id", "updated_at"),
    )


class AiSessionRepository:
    """CRUD operations for ai_sessions, always scoped to family_id."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sf = session_factory

    async def upsert(
        self,
        *,
        session_id: str,
        family_id: str,
        user_id: str | None,
        capability: str,
        jsonl_path: str,
        last_model: str | None = None,
    ) -> None:
        """Insert or update a session record (idempotent)."""
        async with self._sf() as session:
            existing = await session.get(AiSessionRow, session_id)
            if existing is None:
                row = AiSessionRow(
                    session_id=session_id,
                    family_id=family_id,
                    user_id=user_id,
                    capability=capability,
                    jsonl_path=jsonl_path,
                    last_model=last_model,
                )
                session.add(row)
            else:
                # Only update mutable fields; preserve title and summary set elsewhere
                existing.updated_at = datetime.now(UTC)
                if last_model:
                    existing.last_model = last_model
            await session.commit()

    async def update_summary(
        self,
        *,
        session_id: str,
        family_id: str,
        summary: str | None,
        model: str | None = None,
        status: str = "completed",
    ) -> None:
        """Update last_message_summary and status after a turn completes."""
        async with self._sf() as session:
            row = await session.get(AiSessionRow, session_id)
            if row is None or row.family_id != family_id:
                return
            if summary:
                row.last_message_summary = summary[:200]
            row.status = status
            if model:
                row.last_model = model
            row.updated_at = datetime.now(UTC)
            await session.commit()

    async def list_sessions(
        self,
        family_id: str,
        *,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[dict], int]:
        """Return (sessions, total) ordered by updated_at DESC, scoped to family."""
        async with self._sf() as session:
            count_q = select(func.count()).where(AiSessionRow.family_id == family_id)
            total: int = (await session.execute(count_q)).scalar_one()

            rows_q = (
                select(AiSessionRow)
                .where(AiSessionRow.family_id == family_id)
                .order_by(AiSessionRow.updated_at.desc())
                .limit(limit)
                .offset(offset)
            )
            rows = (await session.execute(rows_q)).scalars().all()
            return [_row_to_dict(r) for r in rows], total

    async def get_session(self, session_id: str, family_id: str) -> dict | None:
        """Return session dict or None if not found / wrong family."""
        async with self._sf() as session:
            row = await session.get(AiSessionRow, session_id)
            if row is None or row.family_id != family_id:
                return None
            return _row_to_dict(row)


def _row_to_dict(row: AiSessionRow) -> dict:
    return {
        "session_id": row.session_id,
        "family_id": row.family_id,
        "user_id": row.user_id,
        "capability": row.capability,
        "title": row.title,
        "status": row.status,
        "last_message_summary": row.last_message_summary,
        "last_model": row.last_model,
        "has_attachments": row.has_attachments,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }
