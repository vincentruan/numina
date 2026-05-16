"""AI 任务状态服务 — 管理长任务的生命周期。"""

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from packages.db.models.ai_task import AITask

TASK_TIMEOUT_MINUTES = 30


class AITaskService:
    @staticmethod
    def get_running_task(
        family_id: int | str, capability: str, db: Session
    ) -> AITask | None:
        """返回 running 且未超时的任务。超时任务自动标记为 timeout 并返回 None。"""
        task = (
            db.query(AITask)
            .filter_by(
                family_id=int(family_id), capability=capability, status="running"
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
        """返回该家庭任意 capability 的 running 任务（不含 chat）。"""
        task = (
            db.query(AITask)
            .filter(
                AITask.family_id == int(family_id),
                AITask.status == "running",
                AITask.capability != "chat",
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
        capability: str,
        session_id: int | None,
        db: Session,
    ) -> AITask:
        """创建新任务记录。若并发请求导致唯一约束冲突，抛出 AI_TASK_IN_PROGRESS。"""
        from sqlalchemy.exc import IntegrityError

        task = AITask(
            family_id=int(family_id),
            capability=capability,
            status="running",
            session_id=session_id,
            started_at=datetime.utcnow(),
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
        capability: str,
        session_id: int | None,
        db: Session,
    ) -> AITask:
        """创建排队任务。当家庭已有其他 capability 运行时使用。

        queue_position 在创建时设为 None，由 get_queued_task 动态计算，
        避免并发请求导致的位置竞态条件。
        """
        from sqlalchemy.exc import IntegrityError

        task = AITask(
            family_id=int(family_id),
            capability=capability,
            status="queued",
            session_id=session_id,
            started_at=datetime.utcnow(),
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
        family_id: int | str, capability: str, db: Session
    ) -> AITask | None:
        """返回该 capability 的排队任务，并动态计算其队列位置。"""
        from sqlalchemy import func
        fid = int(family_id)
        task = (
            db.query(AITask)
            .filter_by(family_id=fid, capability=capability, status="queued")
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
            task.started_at = datetime.utcnow()
            db.commit()

    @staticmethod
    def get_next_queued_task(family_id: int | str, db: Session) -> AITask | None:
        """返回该家庭下排队最靠前的任务（按 queue_position 升序）。"""
        return (
            db.query(AITask)
            .filter(
                AITask.family_id == int(family_id),
                AITask.status == "queued",
            )
            .order_by(AITask.queue_position)
            .first()
        )

    @staticmethod
    def complete_task(task_id: int | str, db: Session) -> None:
        task = db.query(AITask).filter(AITask.id == int(task_id)).first()
        if task and task.status in ("running", "queued"):
            task.status = "completed"
            task.completed_at = datetime.utcnow()
            db.commit()

    @staticmethod
    def fail_task(task_id: int | str, error_message: str, db: Session) -> None:
        task = db.query(AITask).filter(AITask.id == int(task_id)).first()
        if task and task.status in ("running", "queued"):
            task.status = "failed"
            task.completed_at = datetime.utcnow()
            task.error_message = error_message[:500] if error_message else None
            db.commit()

    @staticmethod
    def get_task_by_id(task_id: int | str, db: Session) -> AITask | None:
        return db.query(AITask).filter(AITask.id == int(task_id)).first()

    @staticmethod
    def cancel_task(family_id: int | str, capability: str, db: Session) -> bool:
        """终止指定 capability 的运行或排队任务。返回是否成功终止。"""
        task = (
            db.query(AITask)
            .filter(
                AITask.family_id == int(family_id),
                AITask.capability == capability,
                AITask.status.in_(["running", "queued"]),
            )
            .first()
        )
        if task:
            task.status = "cancelled"
            task.completed_at = datetime.utcnow()
            db.commit()
            return True
        return False
