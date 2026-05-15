"""Chore template and instance endpoints."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from apps.backend.app.auth.deps import (
    get_current_child_user,
    require_adult,
    require_owner,
)
from apps.backend.app.database import get_db
from apps.backend.app.errors import AppError, ErrorCode
from apps.backend.app.models.chore import ChoreInstance
from apps.backend.app.models.user import User
from apps.backend.app.schemas.blind_box import BlindBoxDrawResponse
from apps.backend.app.schemas.chore import (
    ChoreInstanceResponse,
    ChoreTemplateCreate,
    ChoreTemplateResponse,
    ChoreTemplateUpdate,
    RejectRequest,
)
from apps.backend.app.services import chores as chore_service
from apps.backend.app.services.blind_box import blind_box_trigger

router = APIRouter(tags=["chores"])


# ---------------------------------------------------------------------------
# Parent: template management
# ---------------------------------------------------------------------------

@router.post("/family/chore-templates", response_model=ChoreTemplateResponse, status_code=201)
def create_template(
    req: ChoreTemplateCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    return chore_service.create_template(db, user, req)


@router.get("/family/chore-templates", response_model=list[ChoreTemplateResponse])
def list_templates(
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    return chore_service.list_templates(db, user)


@router.patch("/family/chore-templates/{template_id}", response_model=ChoreTemplateResponse)
def update_template(
    template_id: int,
    req: ChoreTemplateUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    return chore_service.update_template(db, user, template_id, req)


@router.patch("/family/chore-templates/{template_id}/toggle", response_model=ChoreTemplateResponse)
def toggle_template(
    template_id: int,
    is_active: bool = Query(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    return chore_service.toggle_template(db, user, template_id, is_active)


@router.delete("/family/chore-templates/{template_id}", status_code=204)
def delete_template(
    template_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    chore_service.delete_template(db, user, template_id)


# ---------------------------------------------------------------------------
# Parent: view children's chores
# ---------------------------------------------------------------------------

@router.get("/family/children/chores", response_model=list[ChoreInstanceResponse])
def list_children_chores(
    date: str = Query(..., description="Local date YYYY-MM-DD"),
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    """Return all chore instances for all children in the family on a given date."""
    from datetime import datetime as dt

    try:
        d = dt.strptime(date, "%Y-%m-%d").date()
    except ValueError:
        from apps.backend.app.errors import AppError, ErrorCode
        raise AppError(ErrorCode.CALENDAR_DATE_INVALID) from None

    daily_bucket = date
    iso = d.isocalendar()
    weekly_bucket = f"{iso[0]}-W{iso[1]:02d}"

    children = db.query(User.id).filter(
        User.family_id == user.family_id,
        User.role == "child",
        User.is_active.is_(True),
    ).all()
    child_ids = [c.id for c in children]
    if not child_ids:
        return []

    instances = (
        db.query(ChoreInstance)
        .filter(
            ChoreInstance.family_id == user.family_id,
            ChoreInstance.child_user_id.in_(child_ids),
            ChoreInstance.date_bucket.in_([daily_bucket, weekly_bucket]),
        )
        .all()
    )
    return [ChoreInstanceResponse.model_validate(i) for i in instances]


# ---------------------------------------------------------------------------
# Parent: approval queue
# ---------------------------------------------------------------------------

@router.get("/family/chore-approvals", response_model=list[ChoreInstanceResponse])
def list_pending_approvals(
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
):
    """Returns pending approvals. Triggers lazy auto-approve for timed-out instances."""
    instances = chore_service.list_pending_approvals(db, user)
    result = []
    for instance in instances:
        resp = ChoreInstanceResponse.model_validate(instance)
        resp.child_display_name = getattr(instance, "_child_display_name", None)
        resp.child_avatar_color = getattr(instance, "_child_avatar_color", None)
        result.append(resp)
    return result


@router.post("/family/chore-approvals/{instance_id}/approve", response_model=ChoreInstanceResponse)
async def approve_instance(
    instance_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
):
    instance = await chore_service.approve_instance_async(db, user, instance_id)
    resp = ChoreInstanceResponse.model_validate(instance)
    resp.milestone_triggered = getattr(instance, "_milestone_triggered", None)

    # Blind box auto-trigger runs in its own transaction so a draw failure never
    # rolls back the already-committed chore approval.
    coin_recipient_id = instance.submitted_by_user_id or instance.child_user_id
    child = db.query(User).filter(User.id == coin_recipient_id, User.family_id == user.family_id).first()
    if child:
        try:
            draw = blind_box_trigger(db, child)
            db.commit()
            if draw:
                db.refresh(draw)
                resp.blind_box_draw = BlindBoxDrawResponse(
                    id=draw.id,
                    family_id=draw.family_id,
                    child_user_id=draw.child_user_id,
                    coins_spent=draw.coins_spent,
                    gift_id=draw.gift_id,
                    gift_name=draw.gift.name,
                    gift_emoji=draw.gift.emoji,
                    is_surprise=draw.is_surprise,
                    is_bonus=draw.is_bonus,
                    is_auto_triggered=draw.is_auto_triggered,
                    shown_to_child=draw.shown_to_child,
                    status=draw.status,
                    draw_at=draw.draw_at,
                    fulfilled_at=draw.fulfilled_at,
                )
        except Exception:
            db.rollback()

    return resp


@router.post("/family/chore-approvals/{instance_id}/reject", response_model=ChoreInstanceResponse)
def reject_instance(
    instance_id: int,
    req: RejectRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
):
    return chore_service.reject_instance(db, user, instance_id, req.return_to_redo)


# ---------------------------------------------------------------------------
# Child: view and complete chores
# ---------------------------------------------------------------------------

@router.get("/child/chores", response_model=list[ChoreInstanceResponse])
def get_my_chores(
    date: str = Query(..., description="Local date YYYY-MM-DD"),
    db: Session = Depends(get_db),
    child: User = Depends(get_current_child_user),
):
    return chore_service.get_or_create_instances(db, child, date)


@router.post("/child/chores/{instance_id}/complete", response_model=ChoreInstanceResponse)
def mark_complete(
    instance_id: int,
    db: Session = Depends(get_db),
    child: User = Depends(get_current_child_user),
):
    return chore_service.mark_complete(db, child, instance_id)


@router.get("/child/chores/{instance_id}/status")
def get_chore_status(
    instance_id: int,
    db: Session = Depends(get_db),
    child: User = Depends(get_current_child_user),
):
    """轻量轮询接口，返回任务实例的当前状态。"""
    instance = db.query(ChoreInstance).filter(
        ChoreInstance.id == instance_id,
        ChoreInstance.child_user_id == child.id,
    ).first()
    if not instance:
        raise AppError(ErrorCode.NOT_FOUND)
    return {"status": instance.status}
