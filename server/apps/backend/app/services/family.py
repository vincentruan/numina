from sqlalchemy.orm import Session

from apps.backend.app.errors import AppError, ErrorCode
from apps.backend.app.models.family import Family, generate_invite_code
from apps.backend.app.models.user import User


def get_family_info(db: Session, user: User) -> Family:
    family = db.query(Family).filter(Family.id == user.family_id).first()
    return family


def get_family_members(db: Session, user: User) -> list[User]:
    return db.query(User).filter(User.family_id == user.family_id, User.is_active == True).all()


def is_root(db: Session, user: User) -> bool:
    """判断用户是否为家庭创建者（root）"""
    family = db.query(Family).filter(Family.id == user.family_id).first()
    if not family:
        raise AppError(ErrorCode.FAMILY_MEMBER_NOT_FOUND)
    return family.created_by == user.id


def can_manage(db: Session, operator: User, target: User) -> bool:
    """判断 operator 是否有权管理 target（禁用/启用、移除、重置密码）。
    角色变更需单独校验 is_root(db, operator)。"""
    if operator.role != 'owner':
        return False
    if target.family_id != operator.family_id:
        return False
    family = db.query(Family).filter(Family.id == operator.family_id).first()
    if not family:
        return False
    if target.id == family.created_by:
        return False
    return not (operator.id != family.created_by and target.role == 'owner')


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
    if not is_root(db, owner):
        raise AppError(ErrorCode.FAMILY_FORBIDDEN)
    member = db.query(User).filter(User.id == member_id, User.family_id == owner.family_id).first()
    if not member:
        raise AppError(ErrorCode.FAMILY_MEMBER_NOT_FOUND)
    if member.id == owner.id:
        raise AppError(ErrorCode.FAMILY_FORBIDDEN)
    if new_role not in ('owner', 'member'):
        raise AppError(ErrorCode.VALIDATION_ERROR)
    member.role = new_role
    db.commit()
    db.refresh(member)
    return member


def remove_member(db: Session, owner: User, member_id: str) -> None:
    if owner.id == member_id:
        raise AppError(ErrorCode.FAMILY_FORBIDDEN)
    member = db.query(User).filter(User.id == member_id, User.family_id == owner.family_id).first()
    if not member:
        raise AppError(ErrorCode.FAMILY_MEMBER_NOT_FOUND)
    if not can_manage(db, owner, member):
        raise AppError(ErrorCode.FAMILY_FORBIDDEN)
    member.is_active = False
    db.commit()


def reset_member_password(db: Session, operator: User, member_id: str, new_password: str) -> None:
    """管理员为成员重置密码。"""
    from apps.backend.app.auth.revoke_jti import revoke_all_user_tokens
    from apps.backend.app.services.auth import (
        _check_password_change_rate_limit,
        hash_password,
    )

    member = db.query(User).filter(User.id == member_id, User.family_id == operator.family_id).first()
    if not member:
        raise AppError(ErrorCode.FAMILY_MEMBER_NOT_FOUND)
    if not can_manage(db, operator, member):
        raise AppError(ErrorCode.FAMILY_FORBIDDEN)
    if len(new_password) < 8:
        raise AppError(ErrorCode.VALIDATION_ERROR)
    _check_password_change_rate_limit(str(member.id))
    member.password_hash = hash_password(new_password)
    db.commit()
    revoke_all_user_tokens(member.id)


def update_member_status(db: Session, operator: User, member_id: str, is_active: bool) -> User:
    """管理员禁用/启用成员账户。"""
    from apps.backend.app.auth.revoke_jti import revoke_all_user_tokens

    member = db.query(User).filter(User.id == member_id, User.family_id == operator.family_id).first()
    if not member:
        raise AppError(ErrorCode.FAMILY_MEMBER_NOT_FOUND)
    if not can_manage(db, operator, member):
        raise AppError(ErrorCode.FAMILY_FORBIDDEN)
    member.is_active = is_active
    db.commit()
    if not is_active:
        revoke_all_user_tokens(member.id)
    db.refresh(member)
    return member


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
