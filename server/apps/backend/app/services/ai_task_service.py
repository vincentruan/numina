"""AI 任务状态服务 — 管理长任务的生命周期。"""

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from packages.db.models.ai_task import AITask

TASK_TIMEOUT_MINUTES = 30


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
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=TASK_TIMEOUT_MINUTES)
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
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=TASK_TIMEOUT_MINUTES)
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
            status="running",
            session_id=session_id,
            started_at=datetime.now(timezone.utc),
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
            status="queued",
            session_id=session_id,
            started_at=datetime.now(timezone.utc),
            queue_position=None,
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
    def promote_queued_task(task_id: int | str, db: Session) -> None:
        """将排队任务提升为 running。"""
        task = db.query(AITask).filter(AITask.id == int(task_id)).first()
        if task and task.status == "queued":
            task.status = "running"
            task.queue_position = None
            task.started_at = datetime.now(timezone.utc)
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
            task.completed_at = datetime.now(timezone.utc)
            db.commit()

    @staticmethod
    def fail_task(task_id: int | str, error_message: str, db: Session) -> None:
        task = db.query(AITask).filter(AITask.id == int(task_id)).first()
        if task and task.status in ("running", "post_processing", "queued"):
            task.status = "failed"
            task.completed_at = datetime.now(timezone.utc)
            task.error_message = error_message[:500] if error_message else None
            db.commit()

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
            task.completed_at = datetime.now(timezone.utc)
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
    def get_running_tasks_by_family(
        family_id: int | str, db: Session
    ) -> list[AITask]:
        """Return all running tasks for a family (used by frontend task resume).

        Returns tasks with status='running', ordered by started_at descending
        (most recent first). Excludes timed-out tasks.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=TASK_TIMEOUT_MINUTES)
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
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=120)

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
    ) -> None:
        """Mark a task as interrupted with tenant isolation.

        Transitions status to 'interrupted' with error message. Only applies
        to tasks in running/post_processing/queued states.

        Args:
            task_id: AITask primary key.
            family_id: Family ID for tenant isolation.
            error_message: Error message to store.
            db: SQLAlchemy session.
        """
        task = (
            db.query(AITask)
            .filter(AITask.id == int(task_id), AITask.family_id == int(family_id))
            .first()
        )
        if task and task.status in ("running", "post_processing", "queued"):
            task.status = "interrupted"
            task.completed_at = datetime.now(timezone.utc)
            task.error_message = error_message[:500] if error_message else None
            try:
                db.commit()
            except Exception:
                db.rollback()

    @staticmethod
    def get_stale_running_tasks(
        db: Session,
        now: datetime | None = None,
        family_id: int | str | None = None,
    ) -> list[AITask]:
        """Return tasks with expired leases (for orphan detection) with optional tenant scope.

        Args:
            db: SQLAlchemy session.
            now: Current timestamp. Defaults to datetime.now(timezone.utc).
            family_id: Optional family ID for tenant-scoped orphan recovery.
                      If None, returns stale tasks across all families.

        Returns tasks WHERE status IN ('running','post_processing') AND
        lease_expires_at < now. Used by orphan recovery to detect dead workers.
        """
        if now is None:
            now = datetime.now(timezone.utc)

        query = db.query(AITask).filter(
            AITask.status.in_(["running", "post_processing"]),
            AITask.lease_expires_at < now,
        )

        if family_id is not None:
            query = query.filter(AITask.family_id == int(family_id))

        return query.all()
