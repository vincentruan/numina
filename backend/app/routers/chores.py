"""Chore template and instance endpoints."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user, require_adult, require_owner
from app.auth.deps import get_current_child_user
from app.database import get_db
from app.models.user import User
from app.schemas.chore import (
    ApproveRequest,
    ChoreInstanceResponse,
    ChoreTemplateCreate,
    ChoreTemplateResponse,
    ChoreTemplateUpdate,
    RejectRequest,
)
from app.services import chores as chore_service

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
    template_id: str,
    req: ChoreTemplateUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    return chore_service.update_template(db, user, template_id, req)


@router.patch("/family/chore-templates/{template_id}/toggle", response_model=ChoreTemplateResponse)
def toggle_template(
    template_id: str,
    is_active: bool = Query(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    return chore_service.toggle_template(db, user, template_id, is_active)


@router.delete("/family/chore-templates/{template_id}", status_code=204)
def delete_template(
    template_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    chore_service.delete_template(db, user, template_id)


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
    instance_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
):
    instance = await chore_service.approve_instance_async(db, user, instance_id)
    resp = ChoreInstanceResponse.model_validate(instance)
    resp.milestone_triggered = getattr(instance, "_milestone_triggered", None)
    return resp


@router.post("/family/chore-approvals/{instance_id}/reject", response_model=ChoreInstanceResponse)
def reject_instance(
    instance_id: str,
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
    instance_id: str,
    db: Session = Depends(get_db),
    child: User = Depends(get_current_child_user),
):
    return chore_service.mark_complete(db, child, instance_id)
