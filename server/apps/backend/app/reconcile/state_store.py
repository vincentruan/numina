"""State persistence — tracks reconciliation status per resource."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.orm import Session
from sqlalchemy.sql.schema import Table

from apps.backend.app.database import Base

logger = logging.getLogger(__name__)


class ReconcileState(Base):
    """Tracks the reconciliation status of each managed resource."""

    __tablename__ = "reconcile_state"

    id = Column(Integer, primary_key=True, autoincrement=True)
    resource_name = Column(String(255), unique=True, nullable=False, index=True)
    resource_type = Column(String(64), nullable=False)
    desired_version = Column(String(128), nullable=False)
    current_version = Column(String(128), nullable=True)
    status = Column(String(32), nullable=False, default="unknown")
    critical = Column(Integer, nullable=False, default=1)
    last_checked_at = Column(DateTime(timezone=True), nullable=True)
    last_applied_at = Column(DateTime(timezone=True), nullable=True)
    last_verified_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True)
    remediation_hint = Column(Text, nullable=True)
    metadata_json = Column(Text, nullable=True)


class StateStore:
    """Reads and writes reconciliation state to the database."""

    def __init__(self, db: Session):
        self._db = db

    def _ensure_table(self) -> None:
        """Create the reconcile_state table if it doesn't exist.

        Uses raw DDL to avoid depending on alembic for this infrastructure table.
        """
        from sqlalchemy import inspect as sa_inspect

        inspector = sa_inspect(self._db.get_bind())
        if "reconcile_state" not in inspector.get_table_names():
            table = cast(Table, ReconcileState.__table__)
            table.create(self._db.get_bind())
            logger.info("Created reconcile_state table")

    def get(self, resource_name: str) -> ReconcileState | None:
        self._ensure_table()
        return (
            self._db.query(ReconcileState)
            .filter(ReconcileState.resource_name == resource_name)
            .first()
        )

    def upsert(
        self,
        resource_name: str,
        resource_type: str,
        desired_version: str,
        *,
        current_version: str | None = None,
        status: str = "unknown",
        critical: bool = True,
        error_message: str | None = None,
        remediation_hint: str | None = None,
        metadata: dict[str, Any] | None = None,
        checked_at: datetime | None = None,
        applied_at: datetime | None = None,
        verified_at: datetime | None = None,
    ) -> ReconcileState:
        self._ensure_table()
        now = datetime.now(UTC)

        row = (
            self._db.query(ReconcileState)
            .filter(ReconcileState.resource_name == resource_name)
            .first()
        )

        if row is None:
            row = ReconcileState(
                resource_name=resource_name,
                resource_type=resource_type,
                desired_version=desired_version,
                current_version=current_version,
                status=status,
                critical=1 if critical else 0,
                last_checked_at=checked_at or now,
                error_message=error_message,
                remediation_hint=remediation_hint,
                metadata_json=json.dumps(metadata) if metadata else None,
            )
            self._db.add(row)
        else:
            row.resource_type = resource_type  # type: ignore[assignment]
            row.desired_version = desired_version  # type: ignore[assignment]
            row.current_version = current_version  # type: ignore[assignment]
            row.status = status  # type: ignore[assignment]
            row.critical = 1 if critical else 0  # type: ignore[assignment]
            row.error_message = error_message  # type: ignore[assignment]
            row.remediation_hint = remediation_hint  # type: ignore[assignment]
            if checked_at:
                row.last_checked_at = checked_at  # type: ignore[assignment]
            if applied_at:
                row.last_applied_at = applied_at  # type: ignore[assignment]
            if verified_at:
                row.last_verified_at = verified_at  # type: ignore[assignment]
            if metadata:
                row.metadata_json = json.dumps(metadata)  # type: ignore[assignment]

        self._db.commit()
        return row

    def all_states(self) -> list[ReconcileState]:
        self._ensure_table()
        return (
            self._db.query(ReconcileState).order_by(ReconcileState.resource_name).all()
        )
