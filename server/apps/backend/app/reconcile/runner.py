"""DesiredStateRunner — orchestrates the reconciliation lifecycle."""

from __future__ import annotations

import contextlib
import enum
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from apps.backend.app.reconcile.state_store import StateStore
from apps.backend.app.reconcile.types import (
    ReconcileReport,
    ResourceResult,
    ResourceStatus,
)

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine
    from sqlalchemy.orm import Session

    from apps.backend.app.reconcile.base import Resource
    from apps.backend.app.reconcile.lock import LockProvider

logger = logging.getLogger(__name__)


class RunMode(enum.StrEnum):
    NORMAL = "normal"
    CHECK_ONLY = "check-only"
    DRY_RUN = "dry-run"
    VERIFY = "verify"
    REPAIR = "repair"
    OFFLINE = "offline"
    STRICT = "strict"


class DesiredStateRunner:
    """Drives the full reconciliation cycle for a set of resources."""

    def __init__(
        self,
        resources: list[Resource],
        engine: Engine,
        db: Session,
        *,
        mode: RunMode = RunMode.NORMAL,
        lock_provider: LockProvider | None = None,
    ):
        self._resources = resources
        self._engine = engine
        self._db = db
        self._mode = mode
        self._lock_provider = lock_provider
        self._store = StateStore(db)

    def run(self) -> ReconcileReport:
        """Execute reconciliation for all registered resources."""
        report = ReconcileReport(
            mode=self._mode.value,
            started_at=datetime.now(UTC),
        )

        lock_name = "reconcile_main"
        locked = False

        if self._mode not in (RunMode.CHECK_ONLY, RunMode.VERIFY, RunMode.DRY_RUN) and self._lock_provider:
            locked = self._lock_provider.acquire(lock_name)
            if not locked:
                logger.warning(
                    "Another instance is running reconciliation. "
                    "Falling back to check-only mode."
                )
                self._mode = RunMode.CHECK_ONLY

        try:
            for resource in self._resources:
                result = self._reconcile_one(resource)
                report.results.append(result)
                self._persist_result(result)
                # Ensure session is clean after each resource, even on failure,
                # so one resource's DB error doesn't cascade to subsequent resources.
                with contextlib.suppress(Exception):
                    self._db.rollback()
        finally:
            if locked and self._lock_provider:
                self._lock_provider.release(lock_name)

        report.finished_at = datetime.now(UTC)
        self._finalize_report(report)
        return report

    def _reconcile_one(self, resource: Resource) -> ResourceResult:
        """Run the check → apply → verify cycle for a single resource."""
        logger.info(f"[reconcile] checking: {resource.name}")

        # --- CHECK ---
        try:
            result = resource.check(self._db)
        except Exception as e:
            logger.error(f"[reconcile] check failed for {resource.name}: {e}")
            # Rollback to ensure session is clean for subsequent resources
            with contextlib.suppress(Exception):
                self._db.rollback()
            return resource._failed(
                error=f"Check error: {e}",
                remediation_hint=resource.offline_hint,
            )

        result.checked_at = datetime.now(UTC)

        if result.status == ResourceStatus.VERIFIED:
            logger.debug(f"[reconcile] {resource.name}: already at desired state")
            return result

        if result.status == ResourceStatus.FAILED:
            return result

        # --- DRY-RUN / CHECK-ONLY / VERIFY: stop here ---
        if self._mode in (RunMode.DRY_RUN, RunMode.CHECK_ONLY, RunMode.VERIFY):
            if result.status == ResourceStatus.DRIFTED:
                logger.info(
                    f"[reconcile] {resource.name}: drifted "
                    f"(current={result.current_version}, desired={resource.desired_version})"
                )
            return result

        # --- APPLY ---
        if result.status == ResourceStatus.DRIFTED:
            logger.info(f"[reconcile] applying: {resource.name}")
            try:
                result = resource.apply(self._db)
                result.applied_at = datetime.now(UTC)
                result.changed = True
            except Exception as e:
                logger.error(f"[reconcile] apply failed for {resource.name}: {e}")
                with contextlib.suppress(Exception):
                    self._db.rollback()
                return resource._failed(
                    error=f"Apply error: {e}",
                    remediation_hint=resource.offline_hint,
                )

            if result.status == ResourceStatus.FAILED:
                return result

        # --- VERIFY ---
        try:
            verify_result = resource.verify(self._db)
            verify_result.verified_at = datetime.now(UTC)
            verify_result.changed = result.changed
            return verify_result
        except Exception as e:
            logger.error(f"[reconcile] verify failed for {resource.name}: {e}")
            return resource._failed(error=f"Verify error: {e}")

    def _persist_result(self, result: ResourceResult) -> None:
        """Write result to the state store."""
        try:
            self._store.upsert(
                resource_name=result.resource_name,
                resource_type=result.resource_type.value,
                desired_version=result.desired_version,
                current_version=result.current_version,
                status=result.status.value,
                critical=result.critical,
                error_message=result.error,
                remediation_hint=result.remediation_hint,
                checked_at=result.checked_at,
                applied_at=result.applied_at,
                verified_at=result.verified_at,
            )
        except Exception as e:
            logger.warning(f"Failed to persist state for {result.resource_name}: {e}")

    def _finalize_report(self, report: ReconcileReport) -> None:
        """Compute summary fields from individual results."""
        for result in report.results:
            if result.status == ResourceStatus.FAILED:
                if result.critical:
                    report.critical_failures += 1
                    report.success = False
                else:
                    report.warnings += 1
                    if self._mode == RunMode.STRICT:
                        report.success = False

            if result.feature_disabled:
                report.features_disabled.append(result.feature_disabled)

        if report.critical_failures > 0:
            logger.error(
                f"Reconciliation completed with {report.critical_failures} critical failure(s)"
            )
        elif report.warnings > 0:
            logger.warning(
                f"Reconciliation completed with {report.warnings} warning(s)"
            )
        else:
            logger.info("Reconciliation completed successfully — all resources verified")
