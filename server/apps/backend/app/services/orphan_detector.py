"""Periodic orphan task detector (Phase 5.1).

Scans for AITask records stuck in 'running'/'post_processing' with expired
leases (lease_expires_at < now). These are tasks whose worker died or
lost connectivity without completing the task.

Uses existing infrastructure:
- AITaskService.get_stale_running_tasks() — query for expired-lease tasks
- AITaskService.mark_interrupted(lease_guard=True) — atomic transition

Registered as a FastAPI lifespan background task in app/main.py.
"""

from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger(__name__)

# Scan interval in seconds
SCAN_INTERVAL_SECONDS = 120


async def _scan_and_recover() -> int:
    """Run one scan cycle. Returns the number of tasks recovered."""
    from packages.db.session import SessionLocal
    from apps.backend.app.services.ai_task_service import AITaskService

    db = SessionLocal()
    try:
        stale_tasks = AITaskService.get_stale_running_tasks(db)
        if not stale_tasks:
            return 0

        recovered = 0
        for task in stale_tasks:
            try:
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
                logger.warning(
                    "[orphan_detector] failed to recover task=%s",
                    task.id,
                    exc_info=True,
                )

        if recovered > 0:
            try:
                db.commit()
            except Exception:
                db.rollback()
                logger.error("[orphan_detector] commit failed", exc_info=True)

        return recovered
    finally:
        db.close()


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
