from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.auth.deps import require_adult
from app.database import get_db
from app.errors import AppError, ErrorCode
from app.models.tag import Tag
from app.models.user import User
from app.schemas.tag import TagCreate, TagResponse, TagUpdate

router = APIRouter(prefix="/tags", tags=["tags"])


@router.get("/", response_model=list[TagResponse])
def list_tags(
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    return db.query(Tag).filter(Tag.family_id == user.family_id).all()


@router.post("/", response_model=TagResponse, status_code=201)
def create_tag(
    req: TagCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    tag = Tag(family_id=user.family_id, name=req.name, color=req.color)
    db.add(tag)
    db.commit()
    db.refresh(tag)
    return tag


@router.put("/{tag_id}", response_model=TagResponse)
def update_tag(
    tag_id: int,
    req: TagUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    tag = db.query(Tag).filter(Tag.id == tag_id, Tag.family_id == user.family_id).first()
    if not tag:
        raise AppError(ErrorCode.TAG_NOT_FOUND)
    if req.name is not None:
        tag.name = req.name
    if req.color is not None:
        tag.color = req.color
    db.commit()
    db.refresh(tag)
    return tag


@router.delete("/{tag_id}")
def delete_tag(
    tag_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    tag = db.query(Tag).filter(Tag.id == tag_id, Tag.family_id == user.family_id).first()
    if not tag:
        raise AppError(ErrorCode.TAG_NOT_FOUND)
    db.delete(tag)
    db.commit()
    return {"detail": "已删除"}
