"""AI 任务状态服务 — 管理长任务的生命周期。"""

import logging
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from packages.db.models.ai_task import AITask

logger = logging.getLogger(__name__)

TASK_TIMEOUT_MINUTES = 30
QUEUED_TIMEOUT_MINUTES = 240  # 4 hours — queued tasks waiting longer are stale


def extract_run_id_from_content_location(content_location: str | None) -> str | None:
    """Extract the agent RunRecord UUID from a Content-Location header.

    The agent gateway sets ``Content-Location: /internal/gateway/runs/{app}/
    {thread_id}/{record.run_id}``. The run_id is the final path segment.
    Returns None if the header is absent or malformed.
    """
    if not content_location:
        return None
    segment = content_location.rstrip("/").rsplit("/", 1)[-1]
    return segment or None


class AITaskService:
    @staticmethod
    def get_running_task(
        family_id: int | str, skill_id: str, db: Session
    ) -> AITask | None:
        """返回 running 且未超时的任务。超时任务自动标记为 timeout 并返回 None。"""
        task = (
            db.query(AITask)
            .filter_by(
                family_id=int(family_id), skill_id=skill_id, status="running"
            )
            .first()
        )
        if task is None:
            return None
        cutoff = datetime.utcnow() - timedelta(minutes=TASK_TIMEOUT_MINUTES)
        if task.started_at < cutoff:
            try:
                task.status = "timeout"
                db.commit()
            except Exception:
                db.rollback()
            return None
        return task

    @staticmethod
    def get_any_running_task(family_id: int | str, db: Session) -> AITask | None:
        """返回该家庭任意 skill_id 的 running 任务（不含 chat）。"""
        task = (
            db.query(AITask)
            .filter(
                AITask.family_id == int(family_id),
                AITask.status == "running",
                AITask.skill_id != "chat",
            )
            .first()
        )
        if task is None:
            return None
        cutoff = datetime.utcnow() - timedelta(minutes=TASK_TIMEOUT_MINUTES)
        if task.started_at < cutoff:
            try:
                task.status = "timeout"
                db.commit()
            except Exception:
                db.rollback()
            return None
        return task

    @staticmethod
    def create_task(
        family_id: int | str,
        skill_id: str,
        session_id: int | None,
        db: Session,
        run_id: str | None = None,
        worker_id: str | None = None,
    ) -> AITask:
        """创建新任务记录。若并发请求导致唯一约束冲突，抛出 AI_TASK_IN_PROGRESS。

        Args:
            family_id: Family (tenant) ID.
            skill_id: Feature type (report, import, chat, coach, literacy, agent-*).
            session_id: Linked AIChatSession ID.
            db: SQLAlchemy session.
            run_id: Optional agent RunRecord ID for bridge reconnection.
            worker_id: Optional hostname:uuid of processing worker.
        """
        from sqlalchemy.exc import IntegrityError

        task = AITask(
            family_id=int(family_id),
            skill_id=skill_id,
            capability=skill_id,  # Legacy column mirrors skill_id
            status="running",
            session_id=session_id,
            started_at=datetime.utcnow(),
            run_id=run_id,
            worker_id=worker_id,
        )
        db.add(task)
        try:
            db.commit()
        except IntegrityError as e:
            db.rollback()
            from apps.backend.app.errors import AppError, ErrorCode

            raise AppError(ErrorCode.AI_TASK_IN_PROGRESS) from e
        db.refresh(task)
        return task

    @staticmethod
    def create_queued_task(
        family_id: int | str,
        skill_id: str,
        session_id: int | None,
        db: Session,
    ) -> AITask:
        """创建排队任务。当家庭已有其他 skill_id 运行时使用。

        queue_position 在创建时设为 None，由 get_queued_task 动态计算，
        避免并发请求导致的位置竞态条件。
        """
        from sqlalchemy.exc import IntegrityError

        task = AITask(
            family_id=int(family_id),
            skill_id=skill_id,
            capability=skill_id,  # Legacy column mirrors skill_id
            status="queued",
            session_id=session_id,
            started_at=datetime.utcnow(),
            queue_position=None,
            lease_expires_at=datetime.utcnow() + timedelta(minutes=QUEUED_TIMEOUT_MINUTES),
        )
        db.add(task)
        try:
            db.commit()
        except IntegrityError as e:
            db.rollback()
            from apps.backend.app.errors import AppError, ErrorCode

            raise AppError(ErrorCode.AI_TASK_IN_PROGRESS) from e
        db.refresh(task)
        return task

    @staticmethod
    def get_queued_task(
        family_id: int | str, skill_id: str, db: Session
    ) -> AITask | None:
        """返回该 skill_id 的排队任务，并动态计算其队列位置。"""
        from sqlalchemy import func
        fid = int(family_id)
        task = (
            db.query(AITask)
            .filter_by(family_id=fid, skill_id=skill_id, status="queued")
            .first()
        )
        if task is None:
            return None
        # Staleness check — queued tasks waiting too long are timed out
        cutoff = datetime.utcnow() - timedelta(minutes=QUEUED_TIMEOUT_MINUTES)
        if task.started_at < cutoff:
            try:
                task.status = "timeout"
                task.completed_at = datetime.utcnow()
                db.commit()
            except Exception:
                db.rollback()
            return None
        # Compute position dynamically: count tasks queued before this one
        # (by started_at)
        position = (
            db.query(func.count(AITask.id))
            .filter(
                AITask.family_id == fid,
                AITask.status == "queued",
                AITask.started_at <= task.started_at,
            )
            .scalar()
        ) or 1
        task.queue_position = position
        return task

    @staticmethod
    def _try_promote_next(family_id: int | str, db: Session) -> None:
        """Promote the next queued task if the family has no running tasks.

        Called automatically by complete_task / fail_task.  Only promotes when
        no other task is actively running for the family (respects the
        per-family single-running constraint).  The promoted task's router
        endpoint is expected to reconnect on the next frontend poll.
        """
        try:
            still_running = (
                db.query(AITask)
                .filter(
                    AITask.family_id == int(family_id),
                    AITask.status.in_(["running", "post_processing"]),
                )
                .first()
            )
            if still_running:
                return
            queued = AITaskService.get_next_queued_task(family_id, db)
            if not queued:
                return
            queued.status = "running"
            queued.started_at = datetime.utcnow()
            queued.queue_position = None
            queued.lease_expires_at = datetime.utcnow() + timedelta(seconds=120)
            db.commit()
            logger.info(
                "[ai-task] auto-promoted queued task=%s family=%s skill=%s",
                queued.id, family_id, queued.skill_id,
            )
        except Exception:
            db.rollback()
            logger.warning(
                "[ai-task] _try_promote_next failed family=%s",
                family_id, exc_info=True,
            )

    @staticmethod
    def promote_queued_task(task_id: int | str, db: Session) -> None:
        """将排队任务提升为 running。"""
        task = db.query(AITask).filter(AITask.id == int(task_id)).first()
        if task and task.status == "queued":
            task.status = "running"
            task.queue_position = None
            task.started_at = datetime.utcnow()
            db.commit()

    @staticmethod
    def get_next_queued_task(family_id: int | str, db: Session) -> AITask | None:
        """返回该家庭下排队最靠前的任务（按 started_at 升序，FIFO）。"""
        return (
            db.query(AITask)
            .filter(
                AITask.family_id == int(family_id),
                AITask.status == "queued",
            )
            .order_by(AITask.started_at)
            .first()
        )

    @staticmethod
    def mark_post_processing(task_id: int | str, db: Session) -> None:
        """流结束后切到 post_processing；仅当当前是 running 时生效。"""
        task = db.query(AITask).filter(AITask.id == int(task_id)).first()
        if task and task.status == "running":
            task.status = "post_processing"
            try:
                db.commit()
            except Exception:
                db.rollback()

    @staticmethod
    def complete_task(task_id: int | str, db: Session) -> None:
        task = db.query(AITask).filter(AITask.id == int(task_id)).first()
        if task and task.status in ("running", "post_processing", "queued"):
            task.status = "completed"
            task.completed_at = datetime.utcnow()
            db.commit()
            AITaskService._try_promote_next(task.family_id, db)

    @staticmethod
    def fail_task(task_id: int | str, error_message: str, db: Session) -> None:
        """Mark a task as failed with error message.

        Rolls back the session on failure to prevent leaving it in a bad state.
        """
        try:
            task = db.query(AITask).filter(AITask.id == int(task_id)).first()
            if task and task.status in ("running", "post_processing", "queued"):
                family_id = task.family_id
                task.status = "failed"
                task.completed_at = datetime.utcnow()
                task.error_message = error_message[:500] if error_message else None
                db.commit()
                AITaskService._try_promote_next(family_id, db)
        except Exception:
            # Rollback to prevent leaving the session in a bad state.
            # Guard the rollback itself — if the session is fatally broken
            # (connection lost, pool exhausted), rollback could raise a
            # secondary exception that masks the original error.
            try:
                db.rollback()
            except Exception:
                pass
            logger.exception(
                "[ai-task] fail_task failed — task %s may remain in running state",
                task_id,
            )

    @staticmethod
    def get_task_by_id(task_id: int | str, family_id: int | str, db: Session) -> AITask | None:
        """Lookup AITask by ID with tenant isolation.

        Args:
            task_id: AITask primary key.
            family_id: Family ID for tenant isolation.
            db: SQLAlchemy session.

        Returns:
            AITask if found and belongs to the family, None otherwise.
        """
        return (
            db.query(AITask)
            .filter(AITask.id == int(task_id), AITask.family_id == int(family_id))
            .first()
        )

    @staticmethod
    def cancel_task(family_id: int | str, skill_id: str, db: Session) -> bool:
        """终止指定 skill_id 的运行或排队任务。返回是否成功终止。"""
        task = (
            db.query(AITask)
            .filter(
                AITask.family_id == int(family_id),
                AITask.skill_id == skill_id,
                AITask.status.in_(["running", "post_processing", "queued"]),
            )
            .first()
        )
        if task:
            task.status = "cancelled"
            task.completed_at = datetime.utcnow()
            db.commit()
            return True
        return False

    # ---------------------------------------------------------------------------
    # StreamBridge task tracking methods (U4)
    # ---------------------------------------------------------------------------

    @staticmethod
    def get_task_by_run_id(run_id: str, family_id: int | str, db: Session) -> AITask | None:
        """Lookup AITask by agent RunRecord ID with tenant isolation.

        Returns the task with matching run_id and family_id, or None if not found.
        Used by backend bridge_consumer to map agent run_id → AITask primary key.

        Args:
            run_id: Agent RunRecord UUID.
            family_id: Family ID for tenant isolation.
            db: SQLAlchemy session.
        """
        return (
            db.query(AITask)
            .filter(AITask.run_id == run_id, AITask.family_id == int(family_id))
            .first()
        )

    @staticmethod
    def attach_run_id(task_id: int | str, run_id: str, family_id: int | str, db: Session) -> bool:
        """Write the agent RunRecord ID back onto an AITask (tenant-scoped).

        The agent returns its ``record.run_id`` in the ``Content-Location``
        response header of the gateway trigger endpoint. bridge_consumer needs
        this run_id to subscribe to the correct Redis stream, so the backend
        must persist it before the SSE consumer starts.

        Returns True if a row was updated, False otherwise (task not found or
        wrong family).
        """
        task = AITaskService.get_task_by_id(task_id, family_id, db)
        if not task:
            return False
        task.run_id = run_id
        db.commit()
        return True

    @classmethod
    def extract_and_attach_run_id(
        cls,
        task_id: int | str,
        content_location: str | None,
        family_id: int | str,
    ) -> str | None:
        """Extract run_id from Content-Location and persist to AITask in a self-contained session.

        Returns the run_id if successfully extracted and persisted, None otherwise.
        Callers pass the result to bridge_consumer to avoid a second DB lookup race.
        """
        import logging

        logger = logging.getLogger(__name__)

        run_id = extract_run_id_from_content_location(content_location)
        if not run_id:
            return None
        from apps.backend.app.database import SessionLocal

        _db = SessionLocal()
        try:
            ok = cls.attach_run_id(task_id, run_id, family_id, _db)
            if not ok:
                logger.warning(
                    "[attach_run_id] task not found or wrong family task=%s family=%s",
                    task_id,
                    family_id,
                )
                return None
            return run_id
        except Exception:
            logger.warning(
                "[attach_run_id] failed task=%s", task_id, exc_info=True
            )
            return None
        finally:
            _db.close()

    @staticmethod
    def get_running_tasks_by_family(
        family_id: int | str, db: Session
    ) -> list[AITask]:
        """Return all running tasks for a family (used by frontend task resume).

        Returns tasks with status='running', ordered by started_at descending
        (most recent first). Excludes timed-out tasks.
        """
        cutoff = datetime.utcnow() - timedelta(minutes=TASK_TIMEOUT_MINUTES)
        return (
            db.query(AITask)
            .filter(
                AITask.family_id == int(family_id),
                AITask.status == "running",
                AITask.started_at >= cutoff,
            )
            .order_by(AITask.started_at.desc())
            .all()
        )

    @staticmethod
    def update_lease(
        task_id: int | str,
        family_id: int | str,
        db: Session,
        expires_at: datetime | None = None,
    ) -> None:
        """Refresh worker lease heartbeat for dead-worker detection with tenant isolation.

        Args:
            task_id: AITask primary key.
            family_id: Family ID for tenant isolation.
            db: SQLAlchemy session.
            expires_at: Lease expiration timestamp. Defaults to now + 120s.
        """
        if expires_at is None:
            expires_at = datetime.utcnow() + timedelta(seconds=120)

        task = (
            db.query(AITask)
            .filter(AITask.id == int(task_id), AITask.family_id == int(family_id))
            .first()
        )
        if task:
            task.lease_expires_at = expires_at
            try:
                db.commit()
            except Exception:
                db.rollback()

    @staticmethod
    def mark_interrupted(
        task_id: int | str,
        family_id: int | str,
        error_message: str,
        db: Session,
        lease_guard: bool = False,
    ) -> bool:
        """Mark a task as interrupted with tenant isolation and optional lease guard.

        Transitions status to 'interrupted' with error message. Only applies
        to tasks in running/post_processing/queued states.

        When lease_guard=True, uses an atomic UPDATE with a WHERE clause that
        checks lease_expires_at < now. This prevents the split-brain race where
        a concurrent heartbeat renewal could win over the orphan claim.

        Args:
            task_id: AITask primary key.
            family_id: Family ID for tenant isolation.
            error_message: Error message to store.
            db: SQLAlchemy session.
            lease_guard: If True, only mark interrupted if lease has expired.
                        Returns False if lease is still valid (task is alive).

        Returns:
            True if task was marked interrupted, False if lease_guard prevented it.
        """
        if lease_guard:
            # Atomic UPDATE with lease guard to prevent split-brain race
            from sqlalchemy import update

            now = datetime.utcnow()
            stmt = (
                update(AITask)
                .where(
                    AITask.id == int(task_id),
                    AITask.family_id == int(family_id),
                    AITask.status.in_(["running", "post_processing", "queued"]),
                    AITask.lease_expires_at < now,  # Lease guard
                )
                .values(
                    status="interrupted",
                    completed_at=now,
                    error_message=error_message[:500] if error_message else None,
                )
            )
            result = db.execute(stmt)
            try:
                db.commit()
                return bool(getattr(result, "rowcount", 0) > 0)  # True if we actually updated a row
            except Exception:
                db.rollback()
                return False
        else:
            # Original read-then-write pattern (no lease guard)
            task = (
                db.query(AITask)
                .filter(AITask.id == int(task_id), AITask.family_id == int(family_id))
                .first()
            )
            if task and task.status in ("running", "post_processing", "queued"):
                task.status = "interrupted"
                task.completed_at = datetime.utcnow()
                task.error_message = error_message[:500] if error_message else None
                try:
                    db.commit()
                    return True
                except Exception:
                    db.rollback()
                    return False
            return False

    @staticmethod
    def get_stale_running_tasks(
        db: Session,
        now: datetime | None = None,
        family_id: int | str | None = None,
    ) -> list[AITask]:
        """Return tasks with expired leases (for orphan detection) with optional tenant scope.

        Args:
            db: SQLAlchemy session.
            now: Current timestamp. Defaults to datetime.utcnow().
            family_id: Optional family ID for tenant-scoped orphan recovery.
                      If None, returns stale tasks across all families.

        Returns tasks WHERE status IN ('running','post_processing') AND
        lease_expires_at < now. Used by orphan recovery to detect dead workers.
        """
        if now is None:
            now = datetime.utcnow()

        query = db.query(AITask).filter(
            AITask.status.in_(["running", "post_processing", "queued"]),
            AITask.lease_expires_at < now,
        )

        if family_id is not None:
            query = query.filter(AITask.family_id == int(family_id))

        return query.all()
