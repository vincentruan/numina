from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.auth.deps import require_adult
from app.database import get_db
from app.models.user import User
from app.schemas.category import CategoryCreate, CategoryResponse, CategoryUpdate
from app.services import category as category_service

router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("", response_model=list[CategoryResponse])
def list_categories(
    response: Response,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    response.headers["Cache-Control"] = "private, max-age=300"
    return category_service.list_categories(db, user)


@router.post("", response_model=CategoryResponse, status_code=201)
def create_category(
    req: CategoryCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    return category_service.create_category(db, user, req)


@router.put("/{category_id}", response_model=CategoryResponse)
def update_category(
    category_id: int,
    req: CategoryUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    return category_service.update_category(db, user, category_id, req)


@router.delete("/{category_id}")
def delete_category(
    category_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    category_service.delete_category(db, user, category_id)
    return {"detail": "已删除"}
