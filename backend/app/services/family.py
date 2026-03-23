from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.family import Family, generate_invite_code
from app.models.user import User


def get_family_info(db: Session, user: User) -> Family:
    family = db.query(Family).filter(Family.id == user.family_id).first()
    return family


def get_family_members(db: Session, user: User) -> list[User]:
    return db.query(User).filter(User.family_id == user.family_id, User.is_active == True).all()


def update_family_title(db: Session, owner: User, custom_title: str | None) -> Family:
    if owner.role != 'owner':
        raise HTTPException(status_code=403, detail="只有家庭创建者可以修改家庭标题")
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
        raise HTTPException(status_code=403, detail="只有家庭创建者可以修改成员角色")
    member = db.query(User).filter(User.id == member_id, User.family_id == owner.family_id).first()
    if not member:
        raise HTTPException(status_code=404, detail="成员不存在")
    if new_role not in ('owner', 'member'):
        raise HTTPException(status_code=422, detail="角色必须是 owner 或 member")
    member.role = new_role
    db.commit()
    db.refresh(member)
    return member


def remove_member(db: Session, owner: User, member_id: str) -> None:
    if owner.role != 'owner':
        raise HTTPException(status_code=403, detail="只有家庭创建者可以移除成员")
    if owner.id == member_id:
        raise HTTPException(status_code=400, detail="不能移除自己")
    member = db.query(User).filter(User.id == member_id, User.family_id == owner.family_id).first()
    if not member:
        raise HTTPException(status_code=404, detail="成员不存在")
    member.is_active = False
    db.commit()
