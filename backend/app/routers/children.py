from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.children import (
    ChildBindTokenResponse,
    ChildResponse,
    CreateChildRequest,
    UpdateChildRequest,
)
from app.services import children as children_service

router = APIRouter(prefix="/family", tags=["children"])


def _require_owner(user: User) -> User:
    if user.role != "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="只有家庭创建者可以执行此操作"
        )
    return user


@router.post("/children", response_model=ChildResponse, status_code=201)
def create_child(
    req: CreateChildRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_owner(user)
    child = children_service.create_child(db, user.family_id, req)
    return ChildResponse.model_validate(child)


@router.get("/children", response_model=list[ChildResponse])
def list_children(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    children = children_service.list_children(db, user.family_id)
    return [ChildResponse.model_validate(c) for c in children]


@router.patch("/children/{child_id}", response_model=ChildResponse)
def update_child(
    child_id: str,
    req: UpdateChildRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_owner(user)
    child = children_service.update_child(db, child_id, user.family_id, req)
    return ChildResponse.model_validate(child)


@router.delete("/children/{child_id}", status_code=204)
def deactivate_child(
    child_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_owner(user)
    children_service.deactivate_child(db, child_id, user.family_id)
    return Response(status_code=204)


@router.post("/children/{child_id}/unlock")
def unlock_child_pin(
    child_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_owner(user)
    children_service.unlock_child_pin(db, child_id, user.family_id)
    return {"message": "已解锁"}


@router.post("/children/{child_id}/force-logout")
def force_logout_child(
    child_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_owner(user)
    children_service.force_logout_child(db, child_id, user.family_id)
    return {"message": "已强制退出"}


@router.post(
    "/child-bind-token", response_model=ChildBindTokenResponse, status_code=201
)
def create_bind_token(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_owner(user)
    bind_token = children_service.create_bind_token(db, user.family_id)
    return ChildBindTokenResponse(
        token=bind_token.token,
        expires_at=bind_token.expires_at.isoformat(),
        bind_url=f"/child/bind?token={bind_token.token}",
    )
