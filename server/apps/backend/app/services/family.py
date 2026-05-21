from sqlalchemy.orm import Session

from apps.backend.app.errors import AppError, ErrorCode
from apps.backend.app.models.family import Family, generate_invite_code
from apps.backend.app.models.user import User


def get_family_info(db: Session, user: User) -> Family:
    family = db.query(Family).filter(Family.id == user.family_id).first()
    return family


def get_family_members(db: Session, user: User) -> list[User]:
    return db.query(User).filter(User.family_id == user.family_id, User.is_active == True).all()


def update_family_title(db: Session, owner: User, custom_title: str | None) -> Family:
    if owner.role != 'owner':
        raise AppError(ErrorCode.FAMILY_FORBIDDEN)
    family = db.query(Family).filter(Family.id == owner.family_id).first()
    family.custom_title = custom_title
    db.commit()
    db.refresh(family)
    return family


def regenerate_invite_code(db: Session, user: User) -> Family:
    family = db.query(Family).filter(Family.id == user.family_id).first()
    family.invite_code = generate_invite_code()
    db.commit()
    db.refresh(family)
    return family


def update_member_role(db: Session, owner: User, member_id: str, new_role: str) -> User:
    if owner.role != 'owner':
        raise AppError(ErrorCode.FAMILY_FORBIDDEN)
    member = db.query(User).filter(User.id == member_id, User.family_id == owner.family_id).first()
    if not member:
        raise AppError(ErrorCode.FAMILY_MEMBER_NOT_FOUND)
    if new_role not in ('owner', 'member'):
        raise AppError(ErrorCode.VALIDATION_ERROR)
    member.role = new_role
    db.commit()
    db.refresh(member)
    return member


def remove_member(db: Session, owner: User, member_id: str) -> None:
    if owner.role != 'owner':
        raise AppError(ErrorCode.FAMILY_FORBIDDEN)
    if owner.id == member_id:
        raise AppError(ErrorCode.FAMILY_FORBIDDEN)
    member = db.query(User).filter(User.id == member_id, User.family_id == owner.family_id).first()
    if not member:
        raise AppError(ErrorCode.FAMILY_MEMBER_NOT_FOUND)
    member.is_active = False
    db.commit()


def list_members(db: Session, family_id: str) -> list[dict]:
    """List members for a family."""
    rows = db.query(User).filter(User.family_id == family_id, User.is_active == True).all()
    return [
        {
            "id": str(u.id),
            "username": u.username,
            "role": u.role,
        }
        for u in rows
    ]
