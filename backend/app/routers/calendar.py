"""Calendar endpoints — monthly and daily activity aggregation for children."""

import calendar
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth.deps import get_current_child_user, require_adult
from app.database import get_db
from app.models.child_milestone import ChildMilestone
from app.models.child_wish import ChildWish
from app.models.chore import ChoreInstance
from app.models.user import User
from app.schemas.calendar import (
    CalendarChoreEvent,
    CalendarDayDetail,
    CalendarDaySummary,
    CalendarMilestoneEvent,
    CalendarMonthResponse,
    CalendarWishEvent,
)

router = APIRouter(tags=["calendar"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_date(date_str: str) -> date:
    try:
        return date.fromisoformat(date_str)
    except ValueError:
        raise HTTPException(status_code=422, detail="日期格式无效，请使用 YYYY-MM-DD")


def _month_days(year: int, month: int) -> list[str]:
    """Return all YYYY-MM-DD strings for the given month."""
    _, last_day = calendar.monthrange(year, month)
    return [date(year, month, d).isoformat() for d in range(1, last_day + 1)]


def _chores_for_child_in_month(db: Session, child_user_id: int, year: int, month: int) -> list[ChoreInstance]:
    prefix = f"{year:04d}-{month:02d}"
    return (
        db.query(ChoreInstance)
        .filter(
            ChoreInstance.child_user_id == child_user_id,
            ChoreInstance.date_bucket.like(f"{prefix}%"),
            ChoreInstance.status == "approved",
        )
        .all()
    )


def _wishes_realized_in_month(db: Session, child_user_id: int, year: int, month: int) -> list[ChildWish]:
    """Wishes whose updated_at falls in the month and status == realized."""
    month_start = datetime(year, month, 1, tzinfo=timezone.utc)
    _, last_day = calendar.monthrange(year, month)
    month_end = datetime(year, month, last_day, 23, 59, 59, tzinfo=timezone.utc)
    return (
        db.query(ChildWish)
        .filter(
            ChildWish.child_user_id == child_user_id,
            ChildWish.status == "realized",
            ChildWish.updated_at >= month_start,
            ChildWish.updated_at <= month_end,
        )
        .all()
    )


def _milestones_in_month(db: Session, child_user_id: int, year: int, month: int) -> list[ChildMilestone]:
    month_start = datetime(year, month, 1, tzinfo=timezone.utc)
    _, last_day = calendar.monthrange(year, month)
    month_end = datetime(year, month, last_day, 23, 59, 59, tzinfo=timezone.utc)
    return (
        db.query(ChildMilestone)
        .filter(
            ChildMilestone.child_user_id == child_user_id,
            ChildMilestone.triggered_at >= month_start,
            ChildMilestone.triggered_at <= month_end,
        )
        .all()
    )


def _build_month_response(
    child_user_id: int,
    year: int,
    month: int,
    db: Session,
) -> CalendarMonthResponse:
    chores = _chores_for_child_in_month(db, child_user_id, year, month)
    wishes = _wishes_realized_in_month(db, child_user_id, year, month)
    milestones = _milestones_in_month(db, child_user_id, year, month)

    # Group by date
    chore_by_date: dict[str, int] = {}
    for c in chores:
        chore_by_date[c.date_bucket] = chore_by_date.get(c.date_bucket, 0) + 1

    wish_by_date: dict[str, int] = {}
    for w in wishes:
        d = w.updated_at.strftime("%Y-%m-%d")
        wish_by_date[d] = wish_by_date.get(d, 0) + 1

    milestone_by_date: dict[str, int] = {}
    for m in milestones:
        d = m.triggered_at.strftime("%Y-%m-%d")
        milestone_by_date[d] = milestone_by_date.get(d, 0) + 1

    days = [
        CalendarDaySummary(
            date=day,
            chore_count=chore_by_date.get(day, 0),
            wish_count=wish_by_date.get(day, 0),
            milestone_count=milestone_by_date.get(day, 0),
        )
        for day in _month_days(year, month)
    ]
    return CalendarMonthResponse(year=year, month=month, days=days)


def _build_day_detail(
    child_user_id: int,
    target_date: date,
    db: Session,
) -> CalendarDayDetail:
    date_str = target_date.isoformat()

    chores = (
        db.query(ChoreInstance)
        .filter(
            ChoreInstance.child_user_id == child_user_id,
            ChoreInstance.date_bucket == date_str,
            ChoreInstance.status.in_(["approved", "pending_approval"]),
        )
        .all()
    )

    day_start = datetime(target_date.year, target_date.month, target_date.day, tzinfo=timezone.utc)
    day_end = datetime(target_date.year, target_date.month, target_date.day, 23, 59, 59, tzinfo=timezone.utc)

    wishes = (
        db.query(ChildWish)
        .filter(
            ChildWish.child_user_id == child_user_id,
            ChildWish.status == "realized",
            ChildWish.updated_at >= day_start,
            ChildWish.updated_at <= day_end,
        )
        .all()
    )

    milestones = (
        db.query(ChildMilestone)
        .filter(
            ChildMilestone.child_user_id == child_user_id,
            ChildMilestone.triggered_at >= day_start,
            ChildMilestone.triggered_at <= day_end,
        )
        .all()
    )

    return CalendarDayDetail(
        date=date_str,
        chores=[
            CalendarChoreEvent(
                id=c.id,
                chore_name=c.chore_name,
                chore_emoji=c.chore_emoji,
                coin_reward=c.coin_reward,
                streak_bonus=c.streak_bonus,
                status=c.status,
            )
            for c in chores
        ],
        wishes=[
            CalendarWishEvent(
                id=w.id,
                name=w.name,
                emoji=w.emoji,
                star_coin_cost=w.star_coin_cost,
            )
            for w in wishes
        ],
        milestones=[
            CalendarMilestoneEvent(id=m.id, milestone_type=m.milestone_type)
            for m in milestones
        ],
    )


# ---------------------------------------------------------------------------
# Child endpoints
# ---------------------------------------------------------------------------

@router.get("/child/calendar", response_model=CalendarMonthResponse)
def get_child_calendar(
    year: int = Query(..., ge=2020, le=2100),
    month: int = Query(..., ge=1, le=12),
    db: Session = Depends(get_db),
    child: User = Depends(get_current_child_user),
):
    return _build_month_response(child.id, year, month, db)


@router.get("/child/calendar/day", response_model=CalendarDayDetail)
def get_child_day_detail(
    date: str = Query(..., description="YYYY-MM-DD"),
    db: Session = Depends(get_db),
    child: User = Depends(get_current_child_user),
):
    return _build_day_detail(child.id, _parse_date(date), db)


# ---------------------------------------------------------------------------
# Parent endpoints
# ---------------------------------------------------------------------------

@router.get("/family/child-calendar", response_model=CalendarMonthResponse)
def get_family_child_calendar(
    child_id: int = Query(...),
    year: int = Query(..., ge=2020, le=2100),
    month: int = Query(..., ge=1, le=12),
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    child = db.query(User).filter(User.id == child_id, User.family_id == user.family_id).first()
    if not child:
        raise HTTPException(status_code=404, detail="孩子不存在")
    return _build_month_response(child.id, year, month, db)


@router.get("/family/child-calendar/day", response_model=CalendarDayDetail)
def get_family_child_day_detail(
    child_id: int = Query(...),
    date: str = Query(..., description="YYYY-MM-DD"),
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    child = db.query(User).filter(User.id == child_id, User.family_id == user.family_id).first()
    if not child:
        raise HTTPException(status_code=404, detail="孩子不存在")
    return _build_day_detail(child.id, _parse_date(date), db)
