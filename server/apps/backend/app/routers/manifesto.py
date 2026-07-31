"""Main app router for family manifesto (adult-facing)."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from apps.backend.app.auth.deps import require_adult, require_owner
from apps.backend.app.database import get_db
from apps.backend.app.errors import AppError, ErrorCode
from apps.backend.app.models.manifesto import (
    FamilyManifesto,
    ManifestoSignature,
    ManifestoVersion,
)
from apps.backend.app.models.user import User
from apps.backend.app.schemas.manifesto import (
    ManifestoCreateRequest,
    ManifestoDashboardSummaryResponse,
    ManifestoFeedbackCreateRequest,
    ManifestoFeedbackResponse,
    ManifestoPublishRequest,
    ManifestoResponse,
    ManifestoSignatureItem,
    ManifestoSignRequest,
    ManifestoVersionHistoryItem,
    ManifestoVersionItem,
    UnsignedManifestoCheckResponse,
)
from apps.backend.app.services import manifesto_service

router = APIRouter(prefix="/family/manifesto", tags=["family-manifesto"])


def _build_manifesto_response(
    manifesto: FamilyManifesto,
    version: ManifestoVersion | None,
    signatures: list,
) -> ManifestoResponse:
    return ManifestoResponse(
        id=manifesto.id,
        family_id=manifesto.family_id,
        current_version_id=manifesto.current_version_id,
        status=manifesto.status,
        signing_deadline=manifesto.signing_deadline,
        created_by=manifesto.created_by,
        created_at=manifesto.created_at,
        current_version=ManifestoVersionItem.model_validate(version) if version else None,
        signatures=[ManifestoSignatureItem.model_validate(s) for s in signatures],
    )


@router.post("", response_model=ManifestoResponse, status_code=201)
def create_manifesto(
    req: ManifestoCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
):
    manifesto = manifesto_service.create_manifesto(
        db, family_id=user.family_id, user_id=user.id, req=req
    )
    version = (
        db.query(ManifestoVersion).filter_by(id=manifesto.current_version_id).first()
    )
    signatures: list = []
    return _build_manifesto_response(manifesto, version, signatures)


@router.get("", response_model=ManifestoResponse)
def get_current_manifesto(
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    manifesto = manifesto_service.get_current_manifesto(db, family_id=user.family_id)
    if manifesto is None:
        raise AppError(ErrorCode.MANIFESTO_NOT_FOUND)
    version = (
        db.query(ManifestoVersion).filter_by(id=manifesto.current_version_id).first()
    )
    # Load signatures for current version
    sig_list: list = []
    if manifesto.current_version_id is not None:
        sig_list = (
            db.query(ManifestoSignature)
            .filter_by(version_id=manifesto.current_version_id)
            .all()
        )
    return _build_manifesto_response(manifesto, version, sig_list)


@router.get("/unsigned-check", response_model=UnsignedManifestoCheckResponse)
def unsigned_check(
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    return manifesto_service.get_unsigned_check(
        db, family_id=user.family_id, user_id=user.id
    )


@router.patch("", response_model=ManifestoResponse)
def publish_update(
    req: ManifestoPublishRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
):
    manifesto = manifesto_service.get_current_manifesto(db, family_id=user.family_id)
    if manifesto is None:
        raise AppError(ErrorCode.MANIFESTO_NOT_FOUND)
    updated = manifesto_service.publish_update(
        db, manifesto_id=manifesto.id, user_id=user.id, req=req
    )
    version = (
        db.query(ManifestoVersion).filter_by(id=updated.current_version_id).first()
    )
    sig_list: list = []
    if updated.current_version_id is not None:
        sig_list = (
            db.query(ManifestoSignature)
            .filter_by(version_id=updated.current_version_id)
            .all()
        )
    return _build_manifesto_response(updated, version, sig_list)


@router.post("/sign", response_model=ManifestoSignatureItem, status_code=201)
def sign_manifesto(
    req: ManifestoSignRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
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


@router.get("/history", response_model=list[ManifestoVersionHistoryItem])
def version_history(
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
):
    manifesto = manifesto_service.get_current_manifesto(db, family_id=user.family_id)
    if manifesto is None:
        raise AppError(ErrorCode.MANIFESTO_NOT_FOUND)
    versions = manifesto_service.get_version_history(db, manifesto_id=manifesto.id)
    return [
        ManifestoVersionHistoryItem(
            id=v.id,
            version_number=v.version_number,
            change_type=v.change_type,
            title=v.title,
            created_by=v.created_by,
            created_at=v.created_at,
        )
        for v in versions
    ]


@router.post("/feedback", response_model=ManifestoFeedbackResponse, status_code=201)
def submit_feedback(
    req: ManifestoFeedbackCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    manifesto = manifesto_service.get_current_manifesto(db, family_id=user.family_id)
    if manifesto is None:
        raise AppError(ErrorCode.MANIFESTO_NOT_FOUND)
    feedback = manifesto_service.submit_feedback(
        db,
        manifesto_id=manifesto.id,
        family_id=user.family_id,
        user_id=user.id,
        content=req.content,
    )
    return ManifestoFeedbackResponse.model_validate(feedback)


@router.get("/feedback", response_model=list[ManifestoFeedbackResponse])
def list_feedback(
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
):
    manifesto = manifesto_service.get_current_manifesto(db, family_id=user.family_id)
    if manifesto is None:
        raise AppError(ErrorCode.MANIFESTO_NOT_FOUND)
    feedback_list = manifesto_service.get_feedback_list(db, manifesto_id=manifesto.id)
    return [ManifestoFeedbackResponse.model_validate(f) for f in feedback_list]


@router.get("/dashboard-summary", response_model=ManifestoDashboardSummaryResponse)
def dashboard_summary(
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    return manifesto_service.get_dashboard_summary(db, family_id=user.family_id)
