"""AI 任务状态服务 — 管理长任务的生命周期。"""

import uuid
from datetime import datetime, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.errors import AppError, ErrorCode
from app.models.ai_task import AITask

TASK_TIMEOUT_MINUTES = 30


class AITaskService:

    @staticmethod
    def get_running_task(family_id: int | str, capability: str, db: Session) -> AITask | None:
        """返回 running 且未超时的任务。超时任务自动标记为 timeout 并返回 None。"""
        task = (
            db.query(AITask)
            .filter_by(family_id=int(family_id), capability=capability, status="running")
            .first()
        )
        if task is None:
            return None
        cutoff = datetime.utcnow() - timedelta(minutes=TASK_TIMEOUT_MINUTES)
        if task.started_at < cutoff:
            task.status = "timeout"
            db.commit()
            return None
        return task

    @staticmethod
    def create_task(
        family_id: int | str,
        capability: str,
        session_id: str | None,
        db: Session,
    ) -> AITask:
        """创建新任务记录。若并发请求导致唯一约束冲突，抛出 AI_TASK_IN_PROGRESS。"""
        task = AITask(
            id=str(uuid.uuid4()),
            family_id=int(family_id),
            capability=capability,
            status="running",
            session_id=session_id,
            started_at=datetime.utcnow(),
        )
        db.add(task)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise AppError(ErrorCode.AI_TASK_IN_PROGRESS)
        db.refresh(task)
        return task

    @staticmethod
    def complete_task(task_id: str, db: Session) -> None:
        task = db.query(AITask).filter_by(id=task_id).first()
        if task:
            task.status = "completed"
            task.completed_at = datetime.utcnow()
            db.commit()

    @staticmethod
    def fail_task(task_id: str, error_message: str, db: Session) -> None:
        task = db.query(AITask).filter_by(id=task_id).first()
        if task:
            task.status = "failed"
            task.completed_at = datetime.utcnow()
            task.error_message = error_message[:500] if error_message else None
            db.commit()

    @staticmethod
    def get_task_by_id(task_id: str, db: Session) -> AITask | None:
        return db.query(AITask).filter_by(id=task_id).first()
