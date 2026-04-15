from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func as sqlfunc
from sqlalchemy.orm import Session

from app.auth.deps import require_adult
from app.database import get_db
from app.errors import AppError, ErrorCode
from app.models.asset import Asset
from app.models.liability import Liability
from app.models.user import User
from app.schemas.auth import UserResponse
from app.schemas.family import FamilyResponse, MemberSummary, UpdateFamilyTitleRequest
from app.services import family as family_service
from app.services.snapshot import generate_snapshots

router = APIRouter(prefix="/family", tags=["family"])


class UpdateRoleRequest(BaseModel):
    role: str


@router.get("/info", response_model=FamilyResponse)
@router.get("/", response_model=FamilyResponse)
def get_family(
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    family = family_service.get_family_info(db, user)
    members = family_service.get_family_members(db, user)
    return FamilyResponse(
        id=family.id,
        name=family.name,
        custom_title=family.custom_title,
        invite_code=family.invite_code,
        created_by=family.created_by,
        members=[UserResponse.model_validate(m) for m in members],
    )

@router.patch("/title", response_model=FamilyResponse)
def update_family_title(
    body: UpdateFamilyTitleRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    family = family_service.update_family_title(db, user, body.custom_title)
    members = family_service.get_family_members(db, user)
    return FamilyResponse(
        id=family.id,
        name=family.name,
        custom_title=family.custom_title,
        invite_code=family.invite_code,
        created_by=family.created_by,
        members=[UserResponse.model_validate(m) for m in members],
    )


@router.get("/members", response_model=list[UserResponse])
def get_members(
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    members = family_service.get_family_members(db, user)
    return [UserResponse.model_validate(m) for m in members]


@router.get("/aggregate")
def get_aggregate(
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    family_id = user.family_id
    total_assets = (
        db.query(sqlfunc.coalesce(sqlfunc.sum(Asset.current_value), 0))
        .filter(Asset.family_id == family_id, Asset.is_archived == False)
        .scalar()
    )
    total_liabilities = (
        db.query(sqlfunc.coalesce(sqlfunc.sum(Liability.remaining_amount), 0))
        .filter(Liability.family_id == family_id, Liability.is_active == True)
        .scalar()
    )
    asset_count = (
        db.query(sqlfunc.count(Asset.id))
        .filter(Asset.family_id == family_id, Asset.is_archived == False)
        .scalar()
    )
    return {
        "total_assets": total_assets,
        "total_liabilities": total_liabilities,
        "net_worth": total_assets - total_liabilities,
        "asset_count": asset_count,
    }


@router.get("/members/{member_id}/summary", response_model=MemberSummary)
def get_member_summary(
    member_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    member = (
        db.query(User)
        .filter(User.id == member_id, User.family_id == user.family_id)
        .first()
    )
    if not member:
        raise AppError(ErrorCode.FAMILY_MEMBER_NOT_FOUND)

    total_assets = (
        db.query(sqlfunc.coalesce(sqlfunc.sum(Asset.current_value), 0))
        .filter(Asset.user_id == member_id, Asset.is_archived == False)
        .scalar()
    )
    total_liabilities = (
        db.query(sqlfunc.coalesce(sqlfunc.sum(Liability.remaining_amount), 0))
        .filter(Liability.user_id == member_id, Liability.is_active == True)
        .scalar()
    )
    asset_count = (
        db.query(sqlfunc.count(Asset.id))
        .filter(Asset.user_id == member_id, Asset.is_archived == False)
        .scalar()
    )
    return MemberSummary(
        user=UserResponse.model_validate(member),
        total_assets=total_assets,
        total_liabilities=total_liabilities,
        net_worth=total_assets - total_liabilities,
        asset_count=asset_count,
    )


@router.patch("/members/{member_id}/role", response_model=UserResponse)
def update_member_role(
    member_id: str,
    body: UpdateRoleRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    member = family_service.update_member_role(db, user, member_id, body.role)
    return UserResponse.model_validate(member)


@router.delete("/members/{member_id}")
def remove_member(
    member_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    family_service.remove_member(db, user, member_id)
    return {"detail": "已移除"}


@router.post("/invite-code")
def regenerate_invite_code(
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    if user.role != 'owner':
        raise AppError(ErrorCode.FAMILY_FORBIDDEN)
    family = family_service.regenerate_invite_code(db, user)
    return {"invite_code": family.invite_code}


@router.post("/snapshots/generate")
def trigger_snapshots(
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    snapshots = generate_snapshots(db, user.family_id)
    return {"detail": f"已生成 {len(snapshots)} 条快照"}
