"""DatabaseSeedResource — ensures DB records match desired state via upsert."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from sqlalchemy.orm import Session

from apps.backend.app.reconcile.base import Resource
from apps.backend.app.reconcile.types import (
    FailureAction,
    ResourceResult,
    ResourceType,
)

logger = logging.getLogger(__name__)


class DatabaseSeedResource(Resource):
    """Ensures database records exist and match desired state.

    Key design principles:
    - Uses stable keys (not auto-increment IDs) for identity
    - Supports field-level comparison to detect drift
    - Never overwrites random/generated fields after first creation
    - Supports version tracking for seed data evolution
    """

    def __init__(
        self,
        name: str,
        *,
        desired_version: str = "1",
        critical: bool = True,
        failure_action: FailureAction = FailureAction.FAIL_STARTUP,
        check_fn: Callable[[Session], ResourceResult | None] | None = None,
        apply_fn: Callable[[Session], ResourceResult | None] | None = None,
        verify_fn: Callable[[Session], ResourceResult | None] | None = None,
    ):
        super().__init__(
            name=name,
            resource_type=ResourceType.DATABASE_SEED,
            desired_version=desired_version,
            critical=critical,
            failure_action=failure_action,
            offline_hint="Ensure the database is accessible and migrations have been applied.",
        )
        self._check_fn = check_fn
        self._apply_fn = apply_fn
        self._verify_fn = verify_fn

    def check(self, db: Session | None = None) -> ResourceResult:
        if db is None:
            return self._failed(error="No database session provided")
        if self._check_fn:
            result = self._check_fn(db)
            if result is not None:
                return result
        return self._verified()

    def apply(self, db: Session | None = None) -> ResourceResult:
        if db is None:
            return self._failed(error="No database session provided")
        if self._apply_fn:
            result = self._apply_fn(db)
            if result is not None:
                return result
        return self._verified()

    def verify(self, db: Session | None = None) -> ResourceResult:
        if db is None:
            return self._failed(error="No database session provided")
        if self._verify_fn:
            result = self._verify_fn(db)
            if result is not None:
                return result
        return self.check(db)


class UpsertSeedResource(DatabaseSeedResource):
    """Convenience subclass for simple table-based seed data.

    Handles the common pattern: a list of records with stable keys,
    where some fields are "managed" (updated on drift) and some are
    "generated" (only set on first creation, never overwritten).
    """

    def __init__(
        self,
        name: str,
        *,
        model_class: type,
        records: list[dict[str, Any]],
        key_fields: list[str],
        managed_fields: list[str] | None = None,
        generated_fields: dict[str, Callable[[], Any]] | None = None,
        desired_version: str = "1",
        critical: bool = True,
        failure_action: FailureAction = FailureAction.FAIL_STARTUP,
    ):
        self._model_class = model_class
        self._records = records
        self._key_fields = key_fields
        self._managed_fields = managed_fields or []
        self._generated_fields = generated_fields or {}

        super().__init__(
            name=name,
            desired_version=desired_version,
            critical=critical,
            failure_action=failure_action,
            check_fn=self._do_check,
            apply_fn=self._do_apply,
            verify_fn=self._do_verify,
        )

    def _find_existing(self, db: Session, record: dict[str, Any]):
        """Find an existing record by key fields."""
        query = db.query(self._model_class)
        for key in self._key_fields:
            query = query.filter(getattr(self._model_class, key) == record[key])
        return query.first()

    def _do_check(self, db: Session) -> ResourceResult:
        missing = 0
        drifted = 0

        for record in self._records:
            existing = self._find_existing(db, record)
            if existing is None:
                missing += 1
                continue

            for field in self._managed_fields:
                if field in record:
                    current_val = getattr(existing, field, None)
                    desired_val = record[field]
                    if current_val != desired_val:
                        drifted += 1
                        break

        if missing > 0 or drifted > 0:
            return self._drifted(
                current_version=f"missing={missing},drifted={drifted}",
                metadata={"missing": missing, "drifted": drifted},
            )
        return self._verified(current_version=self.desired_version)

    def _do_apply(self, db: Session) -> ResourceResult:
        created = 0
        updated = 0

        for record in self._records:
            existing = self._find_existing(db, record)

            if existing is None:
                # Create new record with generated fields
                new_data = dict(record)
                for field, generator in self._generated_fields.items():
                    if field not in new_data:
                        new_data[field] = generator()
                obj = self._model_class(**new_data)
                db.add(obj)
                created += 1
            else:
                # Update only managed fields that have drifted
                changed = False
                for field in self._managed_fields:
                    if field in record:
                        current_val = getattr(existing, field, None)
                        desired_val = record[field]
                        if current_val != desired_val:
                            setattr(existing, field, desired_val)
                            changed = True
                if changed:
                    updated += 1

        db.commit()
        return self._verified(
            current_version=self.desired_version,
            metadata={"created": created, "updated": updated},
        )

    def _do_verify(self, db: Session) -> ResourceResult:
        return self._do_check(db)
