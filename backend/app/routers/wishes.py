from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.wish import FulfillRequest, WishCreate, WishResponse, WishUpdate
from app.services import wish as wish_service

router = APIRouter(prefix="/wishes", tags=["wishes"])


@router.get("/", response_model=list[WishResponse])
def list_wishes(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return wish_service.list_wishes(db, user)


@router.post("/", response_model=WishResponse, status_code=201)
def create_wish(req: WishCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return wish_service.create_wish(db, user, req)


@router.get("/{wish_id}", response_model=WishResponse)
def get_wish(wish_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return wish_service.get_wish(db, user, wish_id)


@router.put("/{wish_id}", response_model=WishResponse)
def update_wish(wish_id: str, req: WishUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return wish_service.update_wish(db, user, wish_id, req)


@router.delete("/{wish_id}")
def delete_wish(wish_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    wish_service.delete_wish(db, user, wish_id)
    return {"detail": "已删除"}


@router.post("/{wish_id}/fulfill", response_model=WishResponse)
def fulfill_wish(wish_id: str, req: FulfillRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return wish_service.fulfill_wish(db, user, wish_id, req.asset_id)
