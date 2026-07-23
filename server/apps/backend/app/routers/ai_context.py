"""A1b: unified entity-context endpoint for /ai/chat prefill (Plan B T6).

GET /api/v1/ai/context?source={liability_detail|wish_detail|liability_strategy|wish_advice}&id={id}
Returns a sanitized context summary to inject as the first user turn when the
user clicks a passive '问 AI' button. Family-scoped: a cross-family entity id
returns 404 (no data injection).
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from apps.backend.app.auth.deps import require_adult
from apps.backend.app.database import get_db
from apps.backend.app.errors import AppError, ErrorCode
from apps.backend.app.models.user import User
from apps.backend.app.services import ai_context_builder as builder

router = APIRouter(prefix="/ai/context", tags=["ai-context"])

_VALID_SOURCES = {"liability_detail", "wish_detail", "liability_strategy", "wish_advice"}


@router.get("")
def get_ai_context(
    source: str = Query(...),
    id: str = Query("0"),  # "0" for the strategy/advice aggregates (no single entity)
    user: User = Depends(require_adult),
    db: Session = Depends(get_db),
):
    if source not in _VALID_SOURCES:
        raise AppError(ErrorCode.VALIDATION_ERROR)

    if source == "liability_detail":
        summary = builder.build_liability_detail(db, user, id)
        if summary is None:
            raise AppError(ErrorCode.NOT_FOUND)
    elif source == "wish_detail":
        summary = builder.build_wish_detail(db, user, id)
        if summary is None:
            raise AppError(ErrorCode.NOT_FOUND)
    elif source == "liability_strategy":
        summary = builder.build_liability_strategy(db, user)
    else:  # wish_advice
        summary = builder.build_wish_advice(db, user)

    return {"source": source, "summary": summary}
