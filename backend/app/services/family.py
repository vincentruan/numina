from sqlalchemy.orm import Session

from app.models.family import Family, generate_invite_code
from app.models.user import User


def get_family_info(db: Session, user: User) -> Family:
    family = db.query(Family).filter(Family.id == user.family_id).first()
    return family


def get_family_members(db: Session, user: User) -> list[User]:
    return db.query(User).filter(User.family_id == user.family_id, User.is_active == True).all()


def regenerate_invite_code(db: Session, user: User) -> Family:
    family = db.query(Family).filter(Family.id == user.family_id).first()
    family.invite_code = generate_invite_code()
    db.commit()
    db.refresh(family)
    return family
