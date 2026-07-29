"""Parent-facing literacy report endpoints.

Mounted at ``/api/v1/literacy-reports``. All endpoints require the caller to be
an adult user (``require_adult``).
"""
from __future__ import annotations

import json
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from apps.backend.app.auth.deps import require_adult
from apps.backend.app.database import get_db
from apps.backend.app.errors import AppError, ErrorCode
from apps.backend.app.models.literacy_report import LiteracyWeeklyReport
from apps.backend.app.models.user import User
from apps.backend.app.schemas.literacy_report import (
    ReportChildItem,
    ReportChildListResponse,
    ReportHistoryItem,
    ReportHistoryResponse,
    WeeklyReportResponse,
)

router = APIRouter(prefix="/literacy-reports", tags=["literacy-parent"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_report_json(raw: str) -> dict:
    """Safely parse the ``report_json`` Text column into a dict."""
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}
    if not isinstance(data, dict):
        return {}
    return data


def _validate_child_in_family(db: Session, child_id: int, family_id: int) -> User:
    """Return the child User if they belong to the caller's family, else raise."""
    child = (
        db.execute(
            select(User).where(
                User.id == child_id,
                User.family_id == family_id,
                User.role == "child",
                User.is_active.is_(True),
            )
        )
        .scalar_one_or_none()
    )
    if child is None:
        raise AppError(ErrorCode.AUTH_CHILD_NOT_FOUND)
    return child


# ---------------------------------------------------------------------------
# GET /literacy-reports
# ---------------------------------------------------------------------------


@router.get("", response_model=WeeklyReportResponse)
def get_report(
    child_id: str = Query(..., description="Child user ID"),
    week_start: str | None = Query(None, description="ISO date for week start (Sunday)"),
    current_user: User = Depends(require_adult),
    db: Session = Depends(get_db),
):
    """Return a weekly report for a child.

    If ``week_start`` is omitted, return the latest report for the child.
    """
    try:
        cid = int(child_id)
    except (ValueError, TypeError):
        raise AppError(ErrorCode.VALIDATION_ERROR, details=f"无效的 child_id: {child_id}") from None
    _validate_child_in_family(db, cid, current_user.family_id)

    if week_start:
        ws = date.fromisoformat(week_start)
        report = (
            db.execute(
                select(LiteracyWeeklyReport).where(
                    LiteracyWeeklyReport.child_id == cid,
                    LiteracyWeeklyReport.week_start == ws,
                )
            )
            .scalar_one_or_none()
        )
    else:
        report = (
            db.execute(
                select(LiteracyWeeklyReport)
                .where(LiteracyWeeklyReport.child_id == cid)
                .order_by(desc(LiteracyWeeklyReport.week_start))
            )
            .scalars()
            .first()
        )

    if report is None:
        raise AppError(ErrorCode.LITERACY_REPORT_NOT_FOUND)

    return WeeklyReportResponse(
        id=report.id,
        child_id=report.child_id,
        week_start=report.week_start,
        report_json=_parse_report_json(report.report_json),
        narrative=report.narrative,
        generated_at=report.generated_at,
    )


# ---------------------------------------------------------------------------
# GET /literacy-reports/children
# ---------------------------------------------------------------------------


@router.get("/children", response_model=ReportChildListResponse)
def get_children(
    current_user: User = Depends(require_adult),
    db: Session = Depends(get_db),
):
    """Return all children in the family with their latest report week."""
    children = (
        db.execute(
            select(User).where(
                User.family_id == current_user.family_id,
                User.role == "child",
                User.is_active.is_(True),
            )
        )
        .scalars()
        .all()
    )

    items: list[ReportChildItem] = []
    for child in children:
        latest_week = (
            db.execute(
                select(LiteracyWeeklyReport.week_start)
                .where(LiteracyWeeklyReport.child_id == child.id)
                .order_by(desc(LiteracyWeeklyReport.week_start))
            )
            .scalars()
            .first()
        )
        items.append(
            ReportChildItem(
                child_id=child.id,
                display_name=child.display_name,
                latest_week_start=latest_week,
            )
        )

    return ReportChildListResponse(children=items)


# ---------------------------------------------------------------------------
# GET /literacy-reports/history
# ---------------------------------------------------------------------------


@router.get("/history", response_model=ReportHistoryResponse)
def get_history(
    child_id: str = Query(..., description="Child user ID"),
    weeks: int = Query(12, ge=1, le=52, description="Number of weeks to return"),
    current_user: User = Depends(require_adult),
    db: Session = Depends(get_db),
):
    """Return available report weeks for a child (most recent first)."""
    try:
        cid = int(child_id)
    except (ValueError, TypeError):
        raise AppError(ErrorCode.VALIDATION_ERROR, details=f"无效的 child_id: {child_id}") from None
    _validate_child_in_family(db, cid, current_user.family_id)

    # Collect existing report weeks for this child
    existing_weeks = set(
        db.execute(
            select(LiteracyWeeklyReport.week_start).where(
                LiteracyWeeklyReport.child_id == cid
            )
        )
        .scalars()
        .all()
    )

    # Build the last N weeks starting from the current week
    from apps.backend.app.services.literacy_report import _sunday_of

    current_sunday = _sunday_of(date.today())
    week_list: list[ReportHistoryItem] = []
    for i in range(weeks):
        from datetime import timedelta

        ws = current_sunday - timedelta(weeks=i)
        week_list.append(
            ReportHistoryItem(
                week_start=ws,
                has_report=ws in existing_weeks,
            )
        )

    return ReportHistoryResponse(weeks=week_list)
