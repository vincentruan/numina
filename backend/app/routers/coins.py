"""Coin ledger endpoints."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.auth.deps import get_current_child_user, require_adult
from app.database import get_db
from app.models.user import User
from app.schemas.chore import GrantRequest
from app.services import coin_transactions as coin_service

router = APIRouter(tags=["coins"])


class CoinTransactionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    amount: int
    transaction_type: str
    narrative: str | None
    narrative_emoji: str | None
    created_at: datetime
    relative_time: str = ""


def _relative_time(dt: datetime) -> str:
    now = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
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


class GrantResponse(BaseModel):
    id: str
    amount: int
    narrative: str | None


@router.get("/child/coins/balance", response_model=BalanceResponse)
def get_balance(
    db: Session = Depends(get_db),
    child: User = Depends(get_current_child_user),
):
    balance = coin_service.get_balance(db, child.id)
    return {"balance": balance}


@router.get("/child/coins/ledger", response_model=list[CoinTransactionResponse])
def get_ledger(
    db: Session = Depends(get_db),
    child: User = Depends(get_current_child_user),
):
    txs = coin_service.list_transactions(db, child.id, child.family_id)
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
