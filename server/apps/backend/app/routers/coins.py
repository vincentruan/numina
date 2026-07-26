"""Coin ledger endpoints."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from apps.backend.app.auth.deps import get_current_child_user, require_adult
from apps.backend.app.database import get_db
from apps.backend.app.models.user import User
from apps.backend.app.schemas.base import SnowflakeBase
from apps.backend.app.schemas.chore import GrantRequest
from apps.backend.app.schemas.coin import GiftRequest, GiftResponse, SiblingResponse
from apps.backend.app.services import coin_transactions as coin_service

router = APIRouter(tags=["coins"])


class CoinTransactionResponse(SnowflakeBase):
    id: int
    amount: int
    transaction_type: str
    narrative: str | None
    narrative_emoji: str | None
    created_at: datetime
    relative_time: str = ""


def _relative_time(dt: datetime) -> str:
    now = datetime.now(UTC)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    delta = now - dt
    days = delta.days
    if days == 0:
        return "今天"
    elif days == 1:
        return "昨天"
    else:
        return f"{days}天前"


class BalanceResponse(BaseModel):
    balance: int


class GrantResponse(SnowflakeBase):
    id: int
    amount: int
    narrative: str | None


@router.get("/child/coins/balance", response_model=BalanceResponse)
def get_balance(
    db: Session = Depends(get_db),
    child: User = Depends(get_current_child_user),
):
    balance = coin_service.get_balance(db, str(child.id))
    return {"balance": balance}


@router.get("/child/coins/ledger", response_model=list[CoinTransactionResponse])
def get_ledger(
    db: Session = Depends(get_db),
    child: User = Depends(get_current_child_user),
):
    txs = coin_service.list_transactions(db, str(child.id), str(child.family_id))
    result = []
    for tx in txs:
        data = CoinTransactionResponse.model_validate(tx)
        data.relative_time = _relative_time(tx.created_at)
        result.append(data)
    return result


@router.post("/family/coins/grant", response_model=GrantResponse, status_code=201)
def grant_coins(
    req: GrantRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    tx = coin_service.write_parent_grant(db, user, req)
    return {"id": tx.id, "amount": tx.amount, "narrative": tx.narrative}


@router.get("/child/coins/siblings", response_model=list[SiblingResponse])
def list_siblings(
    db: Session = Depends(get_db),
    child: User = Depends(get_current_child_user),
):
    """List other children in the same family (potential gift recipients)."""
    siblings = (
        db.query(User)
        .filter(
            User.family_id == child.family_id,
            User.role == "child",
            User.id != child.id,
            User.is_active == True,
        )
        .all()
    )
    return siblings


@router.post("/child/coins/gift", response_model=GiftResponse, status_code=201)
def gift_coins(
    req: GiftRequest,
    db: Session = Depends(get_db),
    child: User = Depends(get_current_child_user),
):
    """Send coins to a sibling."""
    debit, _, recipient_name = coin_service.gift_coins(db, child, str(req.to_child_id), req.amount, req.emoji_reason)
    return {"sent_amount": req.amount, "to_display_name": recipient_name}
