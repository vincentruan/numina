"""Periodic orphan task detector (Phase 5.1).

Scans for AITask records stuck in 'running'/'post_processing'/'queued' with
expired leases (lease_expires_at < now). These are tasks whose worker died or
lost connectivity without completing the task (P2-6: now includes 'queued').

Uses existing infrastructure:
- AITaskService.get_stale_running_tasks() — query for expired-lease tasks
  (now covers running, post_processing, AND queued states)
- AITaskService.mark_interrupted(lease_guard=True) — atomic transition

Registered as a FastAPI lifespan background task in app/main.py.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

logger = logging.getLogger(__name__)

# Scan interval in seconds
SCAN_INTERVAL_SECONDS = 120


def _scan_and_recover_sync() -> int:
    """Run one scan cycle synchronously. Returns the number of tasks recovered.

    All DB I/O happens here — callers must run this in a thread to avoid
    blocking the asyncio event loop (P1-1 fix).

    Two-phase recovery:
      Phase 1 — Cancel zombie tasks (running but no run_id).  These are created
                when a previous orphan recovery promoted a queued task that the
                agent never picked up.  They block all future promotion.
      Phase 2 — Mark stale tasks (expired lease) as interrupted.
    """
    from apps.backend.app.services.ai_task_service import AITaskService
    from packages.db.session import SessionLocal

    db = SessionLocal()
    try:
        recovered = 0

        # Phase 1: Cancel zombie running tasks without run_id.
        # Unlike stale tasks (lease expired), zombies have a fresh lease
        # (set when they were promoted) but the agent never started them.
        # They will never self-resolve, so cancel immediately.
        zombies = AITaskService.get_zombie_running_tasks(db)
        for z in zombies:
            try:
                z.status = "interrupted"
                z.completed_at = datetime.now(UTC)
                z.error_message = "任务启动后 agent 未分配 run_id，孤儿检测自动取消"
                db.commit()
                recovered += 1
                logger.info(
                    "[orphan_detector] cancelled zombie task=%s family=%s skill=%s",
                    z.id, z.family_id, z.skill_id,
                )
            except Exception:
                db.rollback()
                logger.warning(
                    "[orphan_detector] failed to cancel zombie task=%s",
                    z.id, exc_info=True,
                )

        # Phase 2: Mark stale tasks (expired lease) as interrupted.
        stale_tasks = AITaskService.get_stale_running_tasks(db)
        if not stale_tasks:
            return recovered

        for task in stale_tasks:
            try:
                # mark_interrupted(lease_guard=True) commits atomically per-task
                # (P1-2 fix: removed the redundant outer db.commit block —
                # each task's transition is durable on its own commit)
                result = AITaskService.mark_interrupted(
                    task_id=task.id,
                    family_id=task.family_id,
                    error_message="任务执行超时，worker 无响应（孤儿检测）",
                    db=db,
                    lease_guard=True,
                )
                if result:
                    recovered += 1
                    logger.info(
                        "[orphan_detector] recovered task=%s family=%s skill=%s",
                        task.id,
                        task.family_id,
                        task.skill_id,
                    )
            except Exception:
                db.rollback()
                logger.warning(
                    "[orphan_detector] failed to recover task=%s",
                    task.id,
                    exc_info=True,
                )

        return recovered
    finally:
        db.close()


async def _scan_and_recover() -> int:
    """Async wrapper — delegates to sync DB work via asyncio.to_thread (P1-1 fix).

    Keeps the blocking SQLAlchemy queries off the event loop so pool exhaustion
    or slow DB cannot stall other asyncio tasks (e.g. SSE heartbeats).
    """
    return await asyncio.to_thread(_scan_and_recover_sync)


async def orphan_detector_loop() -> None:
    """Background loop that scans for orphan tasks every SCAN_INTERVAL_SECONDS.

    Registered as an asyncio.Task in the FastAPI lifespan.
    Cancels gracefully when the task is cancelled (shutdown).
    """
    logger.info(
        "[orphan_detector] started — scanning every %ds",
        SCAN_INTERVAL_SECONDS,
    )
    while True:
        try:
            recovered = await _scan_and_recover()
            if recovered > 0:
                logger.info(
                    "[orphan_detector] scan complete — recovered %d orphan(s)",
                    recovered,
                )
        except asyncio.CancelledError:
            logger.info("[orphan_detector] shutting down")
            raise
        except Exception:
            logger.error("[orphan_detector] scan cycle failed", exc_info=True)

        await asyncio.sleep(SCAN_INTERVAL_SECONDS)
