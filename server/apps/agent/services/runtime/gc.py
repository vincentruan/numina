"""Garbage collection orchestration for run lifecycle management.

Provides shutdown drain, orphan reconciliation, and deferred cleanup — all
wrapping DeerFlow's RunManager built-in methods.

# [Copied from DeerFlow Reference] — patterns from deps.py and manager.py
# [Integrated with Numina Multi-Tenant] — no tenant-specific GC yet; shared
# RunManager across all families. Phase 2 may add per-family GC when a
# persistent RunStore is introduced.
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import UTC, datetime
from typing import Any, cast

from deerflow.runtime import RunManager, RunStatus

logger = logging.getLogger(__name__)


async def drain_inflight_runs(run_manager: RunManager, *, timeout: float | None = None) -> None:
    """Graceful shutdown drain of in-flight runs.

    U7: Implements 3-phase graceful shutdown:
    1. Drain in-flight tasks for up to `timeout` seconds (default from RUN_DRAIN_TIMEOUT_SECONDS env, fallback 60s)
    2. After drain, check each run's final status
    3. Mark non-terminal runs (running/pending) as interrupted

    Uses ``asyncio.shield`` so a second SIGINT during the drain does not
    abandon the process — critical for Kubernetes rolling deployments
    where SIGTERM followed by SIGKILL is the normal shutdown sequence.

    # [Copied from DeerFlow Reference] — drain pattern from deps.py
    # [U7 Enhancement] — configurable timeout + post-drain status check
    """
    # U7: Read timeout from environment variable, default to 60s
    if timeout is None:
        timeout = float(os.getenv("RUN_DRAIN_TIMEOUT_SECONDS", "60.0"))

    logger.info(f"[drain_inflight_runs] Starting graceful shutdown drain (timeout={timeout}s)")

    if not hasattr(run_manager, "shutdown"):
        logger.debug("RunManager.shutdown not available in this DeerFlow version (no-op drain)")
        return

    # Phase 1: Drain with bounded timeout
    drain = asyncio.create_task(run_manager.shutdown(timeout=timeout))
    try:
        await asyncio.shield(drain)
    except asyncio.CancelledError:
        # Second cancellation during drain — shield should protect but
        # asyncio.shield does NOT protect against the outer task being
        # cancelled, only against the inner task being cancelled when
        # the outer is cancelled. Retry once.
        try:
            await asyncio.shield(drain)
        except Exception:
            logger.exception("In-flight run drain failed after shutdown cancellation")
        raise
    except Exception:
        logger.exception("Failed to drain in-flight runs during shutdown")

    # Phase 2-3: Check run status and mark interrupted for non-terminal runs
    # U7: DeerFlow parity — preserve true outcome of tasks that finished during drain
    logger.info("[drain_inflight_runs] Drain complete, checking run statuses")
    if hasattr(run_manager, "list_runs"):
        try:
            runs = await run_manager.list_runs()
            for run in runs:
                # Only mark interrupted if run is still in non-terminal state
                if run.status in (RunStatus.pending, RunStatus.running):
                    logger.warning(
                        f"[drain_inflight_runs] Marking run {run.run_id} as interrupted "
                        f"(status={run.status}, did not complete within {timeout}s drain)"
                    )
                    # Mark as interrupted in AITask (U7 integration)
                    # NOTE: raw SQLAlchemy against AITask model (packages/db) -
                    # the agent container does not ship apps/backend, so we
                    # cannot import backend's AITaskService here.
                    try:
                        from packages.db.models.ai_task import AITask
                        from packages.db.session import SessionLocal

                        db = SessionLocal()
                        try:
                            # Find AITask by run_id with tenant isolation
                            # Extract family_id from run metadata
                            family_id = (
                                run.metadata.get("family_id")
                                if hasattr(run, "metadata") and run.metadata
                                else None
                            )
                            if family_id:
                                task = (
                                    db.query(AITask)
                                    .filter(
                                        AITask.run_id == run.run_id,
                                        AITask.family_id == int(family_id),
                                    )
                                    .first()
                                )
                                if task and task.status in ("running", "post_processing", "queued"):
                                    task.status = "interrupted"
                                    task.completed_at = datetime.now(UTC)
                                    task.error_message = f"服务关停，任务未完成（超时 {timeout}s）"
                                    db.commit()
                                    logger.info(f"[drain_inflight_runs] Marked task {task.id} as interrupted")
                            else:
                                logger.warning(f"[drain_inflight_runs] Run {run.run_id} has no family_id in metadata, skipping")
                        finally:
                            db.close()
                    except Exception as e:
                        logger.error(f"[drain_inflight_runs] Failed to mark task interrupted: {e}")
        except Exception as e:
            logger.error(f"[drain_inflight_runs] Failed to list/check runs: {e}")


async def reconcile_orphaned_runs(
    run_manager: RunManager, *, error: str
) -> list[dict[str, Any]]:
    """Mark persisted pending/running runs as error after process restart.

    U8: DeerFlow-parity conditional claim pattern:
    - Query AITask WHERE status IN ('running','post_processing') AND lease_expires_at < now
    - For each stale task: conditional UPDATE with lease guard (prevents split-brain race)
    - Newer-run protection: skip orphan mark if newer completed task exists

    Stream lifecycle is managed by the backend-owned buffer — the agent no longer
    publishes end markers or cleans up bridges.  The backend's lifecycle consumer
    detects stream completion via the shared bridge and updates AITask status.

    When ``RunManager`` has no persistent store (``store=None``), this is a
    no-op.  Wired here so the integration point is live when a ``RunStore``
    is added in Phase 2.

    # [Copied from DeerFlow Reference] — from manager.py
    # [U8 Enhancement] — AITask integration + conditional claim + stream end marker

    Note: ``reconcile_orphaned_inflight_runs`` is not available in all DeerFlow
    versions. Fall back gracefully when the method is missing.
    """
    if hasattr(run_manager, "reconcile_orphaned_inflight_runs"):
        return cast("list[dict[str, Any]]", await run_manager.reconcile_orphaned_inflight_runs(error=error))

    # U8: AITask-based orphan recovery
    # NOTE: Uses raw SQLAlchemy against the AITask model (packages/db) instead of
    # importing backend's AITaskService - the agent container does not ship
    # apps/backend (see agent Dockerfile), so cross-app imports would fail.
    logger.info("[reconcile_orphaned_runs] Starting AITask-based orphan recovery")
    recovered = []

    try:
        from datetime import datetime

        from sqlalchemy import update

        from packages.db.models.ai_task import AITask
        from packages.db.session import SessionLocal

        db = SessionLocal()
        try:
            # Get all stale running tasks (lease expired)
            now = datetime.now(UTC)
            stale_tasks = (
                db.query(AITask)
                .filter(
                    AITask.status.in_(["running", "post_processing"]),
                    AITask.lease_expires_at < now,
                )
                .all()
            )

            for task in stale_tasks:
                # Newer-run protection: check if a newer completed task exists
                newer_completed = (
                    db.query(AITask)
                    .filter(
                        AITask.family_id == task.family_id,
                        AITask.skill_id == task.skill_id,
                        AITask.status == "completed",
                        AITask.started_at > task.started_at,
                    )
                    .first()
                )

                if newer_completed:
                    logger.info(
                        f"[reconcile_orphaned_runs] Skipping orphan mark for task {task.id} "
                        f"(newer completed task {newer_completed.id} exists)"
                    )
                    continue

                # Conditional claim: atomic UPDATE with lease guard.
                # This prevents the split-brain race where a concurrent heartbeat
                # renewal could win over the orphan claim.
                claim_stmt = (
                    update(AITask)
                    .where(
                        AITask.id == task.id,
                        AITask.status.in_(["running", "post_processing"]),
                        AITask.lease_expires_at < now,
                    )
                    .values(
                        status="interrupted",
                        completed_at=now,
                        error_message="服务重启，任务中断，请重试",
                    )
                )
                result = db.execute(claim_stmt)
                try:
                    db.commit()
                except Exception:
                    db.rollback()
                    continue

                if not getattr(result, "rowcount", 0):
                    logger.info(
                        f"[reconcile_orphaned_runs] Task {task.id} lease was renewed "
                        f"concurrently, skipping orphan mark"
                    )
                    continue

                logger.warning(
                    f"[reconcile_orphaned_runs] Marked task {task.id} as interrupted "
                    f"(lease expired at {task.lease_expires_at}, now={now})"
                )

                recovered.append({
                    "task_id": str(task.id),
                    "run_id": task.run_id,
                    "family_id": str(task.family_id),
                    "skill_id": task.skill_id,
                    "stop_reason": "orphan_recovered",
                })

                # U8: The backend-owned buffer manages stream lifecycle.
                # The agent no longer publishes end markers — the backend's
                # lifecycle consumer detects stream completion via the shared
                # bridge and updates AITask status accordingly.
                logger.info(
                    "[reconcile_orphaned_runs] orphan recovered run=%s task=%s "
                    "(backend lifecycle consumer handles completion)",
                    task.run_id,
                    str(task.id),
                )

        finally:
            db.close()

    except Exception as e:
        logger.error(f"[reconcile_orphaned_runs] Failed to reconcile orphaned runs: {e}")

    return recovered


async def schedule_run_cleanup(
    run_manager: RunManager, run_id: str, *, delay: float = 300
) -> None:
    """Deferred removal of a ``RunRecord`` from the in-memory registry.

    After the run has ended and all consumers have drained buffered events,
    remove the record so it does not accumulate indefinitely.  Default 300s
    (5 minutes) gives late subscribers time to join and replay.

    # [Copied from DeerFlow Reference] — from manager.py
    """
    await run_manager.cleanup(run_id, delay=delay)
