from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user
from app.database import get_db
from app.models.tag import Tag
from app.models.user import User
from app.schemas.tag import TagCreate, TagResponse, TagUpdate

router = APIRouter(prefix="/tags", tags=["tags"])


@router.get("/", response_model=list[TagResponse])
def list_tags(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return db.query(Tag).filter(Tag.family_id == user.family_id).all()


@router.post("/", response_model=TagResponse, status_code=201)
def create_tag(
    req: TagCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    tag = Tag(family_id=user.family_id, name=req.name, color=req.color)
    db.add(tag)
    db.commit()
    db.refresh(tag)
    return tag


@router.put("/{tag_id}", response_model=TagResponse)
def update_tag(
    tag_id: str,
    req: TagUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    tag = db.query(Tag).filter(Tag.id == tag_id, Tag.family_id == user.family_id).first()
    if not tag:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="标签不存在")
    if req.name is not None:
        tag.name = req.name
    if req.color is not None:
        tag.color = req.color
    db.commit()
    db.refresh(tag)
    return tag


@router.delete("/{tag_id}")
def delete_tag(
    tag_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    tag = db.query(Tag).filter(Tag.id == tag_id, Tag.family_id == user.family_id).first()
    if not tag:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="标签不存在")
    db.delete(tag)
    db.commit()
    return {"detail": "已删除"}
