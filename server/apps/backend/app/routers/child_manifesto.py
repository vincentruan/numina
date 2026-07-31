"""Child app router for family manifesto (child-facing)."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from apps.backend.app.auth.deps import get_current_child_user
from apps.backend.app.database import get_db
from apps.backend.app.errors import AppError, ErrorCode
from apps.backend.app.models.user import User
from apps.backend.app.schemas.manifesto import (
    ChildManifestoResponse,
    ChildTrackableClausesResponse,
    ManifestoSignatureItem,
    ManifestoSignRequest,
)
from apps.backend.app.services import manifesto_service

router = APIRouter(prefix="/child/manifesto", tags=["child-manifesto"])


@router.get("", response_model=ChildManifestoResponse)
def get_child_manifesto(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_child_user),
):
    return manifesto_service.get_child_manifesto(
        db, family_id=user.family_id, child_user_id=user.id
    )


@router.post("/sign", response_model=ManifestoSignatureItem, status_code=201)
def sign_manifesto(
    req: ManifestoSignRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_child_user),
):
    manifesto = manifesto_service.get_current_manifesto(db, family_id=user.family_id)
    if manifesto is None or manifesto.current_version_id is None:
        raise AppError(ErrorCode.MANIFESTO_NOT_FOUND)
    sig = manifesto_service.sign_manifesto(
        db,
        version_id=manifesto.current_version_id,
        user_id=user.id,
        signature_data=req.signature_data,
    )
    return ManifestoSignatureItem.model_validate(sig)


@router.get("/trackable-clauses", response_model=ChildTrackableClausesResponse)
def get_trackable_clauses(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_child_user),
):
    return manifesto_service.get_trackable_clauses(db, family_id=user.family_id)
