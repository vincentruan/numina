"""Literacy weekly report trigger endpoint.

POST /api/v1/ai/literacy-report/generate?child_id=...&force=false
"""
import logging
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from apps.backend.app.auth.ai_deps import require_ai_enabled
from apps.backend.app.auth.deps import require_adult
from apps.backend.app.database import get_db
from apps.backend.app.errors import AppError, ErrorCode
from apps.backend.app.models.user import User
from apps.backend.app.services.literacy_report import _sunday_of
from apps.backend.app.services.literacy_report_service import (
    generate_literacy_report,
    get_report_status,
)

router = APIRouter(prefix="/ai/literacy-report", tags=["ai-literacy-report"])
logger = logging.getLogger(__name__)


@router.post("/generate")
async def trigger_generate(
    child_id: str = Query(..., description="Child user ID"),
    force: bool = Query(False),
    current_user: User = Depends(require_adult),
    _ai: User = Depends(require_ai_enabled),
    db: Session = Depends(get_db),
):
    """Generate (or return cached) weekly literacy report for a child."""
    try:
        cid = int(child_id)
    except (ValueError, TypeError):
        raise AppError(
            ErrorCode.VALIDATION_ERROR,
            details=f"无效的 child_id: {child_id}",
        ) from None

    child = (
        db.query(User)
        .filter(
            User.id == cid,
            User.family_id == current_user.family_id,
            User.role == "child",
        )
        .first()
    )
    if child is None:
        raise AppError(ErrorCode.AUTH_CHILD_NOT_FOUND)

    week_start = _sunday_of(date.today())

    if not force:
        status = get_report_status(db, family_id=current_user.family_id, child_id=cid)
        if status["status"] == "ready":
            return status

    report = await generate_literacy_report(
        db,
        family_id=current_user.family_id,
        child_id=cid,
        week_start=week_start,
        user_id=current_user.id,
    )

    if report is None:
        return {
            "status": "error",
            "thread_id": None,
            "week_start": week_start.isoformat(),
            "narrative": None,
            "generated_at": None,
        }

    return {
        "status": "ready",
        "thread_id": report.thread_id,
        "week_start": report.week_start.isoformat(),
        "narrative": report.narrative[:100] if report.narrative else None,
        "generated_at": report.generated_at.isoformat() if report.generated_at else None,
    }
