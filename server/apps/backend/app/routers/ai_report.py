"""家庭资产体检报告端点。

- GET  /api/v1/ai/report          — 获取最新报告
- GET  /api/v1/ai/report/markdown — 获取markdown报告文件内容
- POST /api/v1/ai/report/generate/events — 触发生成（NDJSON 流式推送进度）
"""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from apps.backend.app.auth.ai_deps import require_ai_enabled, require_owner
from apps.backend.app.auth.deps import require_adult
from apps.backend.app.database import get_db
from apps.backend.app.errors import AppError, ErrorCode
from apps.backend.app.models.ai_chat_session import AIChatSession
from apps.backend.app.models.ai_report import AIReport
from apps.backend.app.models.user import User
from apps.backend.app.routers._ai_events_helper import (
    check_circuit_blocked,
    proxy_report_events,
)
from apps.backend.app.services.ai_task_service import AITaskService
from apps.backend.app.services.chat_session import ChatSessionService
from packages.core.path_manager import PathManager

router = APIRouter(prefix="/ai/report", tags=["ai-report"])
logger = logging.getLogger(__name__)


class MarkdownResponse(BaseModel):
    """Markdown report file content response."""
    content: str
    filename: str
    generated_at: datetime
    file_size: int


def _latest_report(family_id: str, db: Session) -> AIReport | None:
    return (
        db.query(AIReport)
        .filter(AIReport.family_id == family_id, AIReport.status == "completed")
        .order_by(AIReport.generated_at.desc())
        .first()
    )


@router.get("")
def get_report(
    current_user: User = Depends(require_adult),
    db: Session = Depends(get_db),
):
    """获取家庭最新体检报告。"""
    report = _latest_report(current_user.family_id, db)
    if not report:
        return {"report": None}
    return {"report": report.report_json, "generated_at": report.generated_at.isoformat()}


@router.post("/generate/events")
async def trigger_generate_events(
    current_user: User = Depends(require_adult),
    _ai: None = Depends(require_ai_enabled),
    _owner: None = Depends(require_owner),
    db: Session = Depends(get_db),
):
    """触发体检报告生成（NDJSON 事件流）。"""
    blocked_resp = check_circuit_blocked(current_user.family_id, "report", db)
    if blocked_resp is not None:
        return blocked_resp

    # Check if there's already a running task - resume it instead of 409
    existing = AITaskService.get_running_task(current_user.family_id, "report", db)
    if existing:
        # 已有运行中任务 — 直接接续，不重复创建
        task = existing
        session_id = str(task.session_id) if task.session_id else str(task.id)
        session = (
            db.query(AIChatSession)
            .filter_by(id=session_id, family_id=current_user.family_id)
            .first()
        )
        if not session:
            raise AppError(ErrorCode.NOT_FOUND)
    else:
        # No running task - create new session and task
        session = await ChatSessionService.create_session(
            family_id=current_user.family_id,
            user_id=current_user.id,
            db=db,
        )
        any_running = AITaskService.get_any_running_task(current_user.family_id, db)
        if any_running:
            task = AITaskService.create_queued_task(
                family_id=current_user.family_id,
                capability="report",
                session_id=session.id,
                db=db,
            )
            return JSONResponse(
                status_code=202,
                content={"status": "queued", "task_id": task.id, "queue_position": task.queue_position},
            )
        task = AITaskService.create_task(
            family_id=current_user.family_id,
            capability="report",
            session_id=session.id,
            db=db,
        )
        session_id = str(session.id)

    task_id = str(task.id)
    family_id = current_user.family_id

    return StreamingResponse(
        proxy_report_events(
            task_id=task_id,
            session_id=session_id,
            family_id=family_id,
            current_user=current_user,
            db=db,
        ),
        media_type="application/x-ndjson",
        headers={"X-Accel-Buffering": "no"},
    )


@router.get("/markdown")
def get_report_markdown(
    current_user: User = Depends(require_adult),
    db: Session = Depends(get_db),
) -> MarkdownResponse:
    """获取markdown报告文件内容。

    返回最新报告的markdown源文件内容，供前端预览使用。
    """
    report = _latest_report(current_user.family_id, db)
    if not report:
        raise HTTPException(
            status_code=404,
            detail={"code": "report_not_found", "message": "报告不存在"}
        )
    if not report.markdown_file_path:
        raise HTTPException(
            status_code=404,
            detail={"code": "markdown_not_found", "message": "报告文件不存在或已被删除"}
        )

    # Read markdown file via PathManager
    pm = PathManager()
    filename = report.markdown_file_path.split("/")[-1]
    try:
        file_path = pm.tenant_report_file(int(current_user.family_id), filename)
    except Exception as e:
        logger.warning(f"Invalid markdown file path for family {current_user.family_id}: {e}")
        raise HTTPException(
            status_code=404,
            detail={"code": "markdown_not_found", "message": "报告文件路径无效"}
        ) from None

    if not file_path.exists():
        raise HTTPException(
            status_code=404,
            detail={"code": "markdown_not_found", "message": "报告文件不存在或已被删除"}
        )

    content = file_path.read_text(encoding="utf-8")
    return MarkdownResponse(
        content=content,
        filename=filename,
        generated_at=report.generated_at,
        file_size=len(content),
    )
