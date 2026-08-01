"""Business logic for family manifesto feature.

Module-level functions (not a class). Session as first arg.
"""

from __future__ import annotations

from sqlalchemy import func as sa_func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from apps.backend.app.errors import AppError, ErrorCode
from apps.backend.app.models.manifesto import (
    FamilyManifesto,
    ManifestoFeedback,
    ManifestoSignature,
    ManifestoVersion,
)
from apps.backend.app.models.user import User
from apps.backend.app.schemas.manifesto import (
    ChildManifestoResponse,
    ChildTrackableClausesResponse,
    ManifestoCreateRequest,
    ManifestoDashboardSummaryResponse,
    ManifestoPublishRequest,
    UnsignedManifestoCheckResponse,
)


def create_manifesto(
    db: Session,
    family_id: int,
    user_id: int,
    req: ManifestoCreateRequest,
) -> FamilyManifesto:
    """Create manifesto + initial version (version_number=1, change_type='initial')."""
    manifesto = FamilyManifesto(
        family_id=family_id,
        status="active",
        signing_deadline=req.signing_deadline,
        created_by=user_id,
    )
    db.add(manifesto)
    db.flush()

    version = ManifestoVersion(
        manifesto_id=manifesto.id,
        version_number=1,
        template_id=req.template_id,
        title=req.title,
        body=req.body,
        change_type="initial",
        trackable_clause_indices=req.trackable_clause_indices,
        created_by=user_id,
    )
    db.add(version)
    db.flush()

    manifesto.current_version_id = version.id
    db.commit()
    db.refresh(manifesto)
    return manifesto


def get_current_manifesto(db: Session, family_id: int) -> FamilyManifesto | None:
    """Return manifesto with current version + signatures loaded."""
    manifesto = (
        db.query(FamilyManifesto)
        .filter_by(family_id=family_id, status="active")
        .first()
    )
    if manifesto is None:
        return None
    return manifesto


def publish_update(
    db: Session,
    manifesto_id: int,
    user_id: int,
    req: ManifestoPublishRequest,
) -> FamilyManifesto:
    """Create new version with incremented version_number.

    CRITICAL P1-7: If change_type='minor', COPY all signatures from previous
    version to new version. For 'major': no signature copy.
    """
    manifesto = db.query(FamilyManifesto).filter_by(id=manifesto_id).first()
    if manifesto is None:
        raise AppError(ErrorCode.MANIFESTO_NOT_FOUND)
    if manifesto.status != "active":
        raise AppError(ErrorCode.MANIFESTO_NOT_ACTIVE)

    prev_version = (
        db.query(ManifestoVersion)
        .filter_by(id=manifesto.current_version_id)
        .first()
    )
    if prev_version is None:
        raise AppError(ErrorCode.MANIFESTO_NOT_FOUND)

    new_version_number = prev_version.version_number + 1
    new_title = req.title if req.title is not None else prev_version.title
    new_body = req.body if req.body is not None else prev_version.body

    new_version = ManifestoVersion(
        manifesto_id=manifesto.id,
        version_number=new_version_number,
        template_id=prev_version.template_id,
        title=new_title,
        body=new_body,
        change_type=req.change_type,
        trackable_clause_indices=req.trackable_clause_indices,
        created_by=user_id,
    )
    db.add(new_version)
    db.flush()

    # P1-7: Copy signatures for minor updates
    if req.change_type == "minor":
        prev_signatures = (
            db.query(ManifestoSignature)
            .filter_by(version_id=prev_version.id)
            .all()
        )
        for sig in prev_signatures:
            copied_sig = ManifestoSignature(
                version_id=new_version.id,
                user_id=sig.user_id,
                signature_data=sig.signature_data,
            )
            db.add(copied_sig)

    manifesto.current_version_id = new_version.id
    db.commit()
    db.refresh(manifesto)
    return manifesto


def sign_manifesto(
    db: Session,
    version_id: int,
    user_id: int,
    signature_data: str | None,
) -> ManifestoSignature:
    """Sign a manifesto version. Raise 409 if already signed."""
    existing = (
        db.query(ManifestoSignature)
        .filter_by(version_id=version_id, user_id=user_id)
        .first()
    )
    if existing is not None:
        raise AppError(ErrorCode.MANIFESTO_ALREADY_SIGNED)

    sig = ManifestoSignature(
        version_id=version_id,
        user_id=user_id,
        signature_data=signature_data,
    )
    db.add(sig)

    # Check if all family members have signed this version
    version = db.query(ManifestoVersion).filter_by(id=version_id).first()
    if version is not None:
        manifesto = (
            db.query(FamilyManifesto).filter_by(id=version.manifesto_id).first()
        )
        if manifesto is not None:
            total_members = (
                db.query(User)
                .filter_by(family_id=manifesto.family_id, is_active=True)
                .filter(User.role != "child")
                .count()
            )
            # Only count adult signatures — total_members excludes children
            adult_signer_ids = (
                db.query(User.id)
                .filter_by(family_id=manifesto.family_id, is_active=True)
                .filter(User.role != "child")
                .subquery()
            )
            adult_signed_count = (
                db.query(ManifestoSignature)
                .filter_by(version_id=version_id)
                .filter(ManifestoSignature.user_id.in_(db.query(adult_signer_ids)))
                .count()
            )
            if adult_signed_count >= total_members and version.signed_at is None:
                version.signed_at = sa_func.now()

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise AppError(ErrorCode.MANIFESTO_ALREADY_SIGNED) from None
    db.refresh(sig)
    return sig


def get_unsigned_check(
    db: Session, family_id: int, user_id: int
) -> UnsignedManifestoCheckResponse:
    """Check if current active manifesto has been signed by this user."""
    manifesto = (
        db.query(FamilyManifesto)
        .filter_by(family_id=family_id, status="active")
        .first()
    )
    if manifesto is None or manifesto.current_version_id is None:
        return UnsignedManifestoCheckResponse(has_unsigned=False)

    existing = (
        db.query(ManifestoSignature)
        .filter_by(version_id=manifesto.current_version_id, user_id=user_id)
        .first()
    )
    if existing is not None:
        return UnsignedManifestoCheckResponse(has_unsigned=False)

    version = (
        db.query(ManifestoVersion).filter_by(id=manifesto.current_version_id).first()
    )
    return UnsignedManifestoCheckResponse(
        has_unsigned=True,
        manifesto_id=manifesto.id,
        title=version.title if version else None,
    )


def get_version_history(
    db: Session, manifesto_id: int
) -> list[ManifestoVersion]:
    """All versions ordered by version_number desc."""
    return (
        db.query(ManifestoVersion)
        .filter_by(manifesto_id=manifesto_id)
        .order_by(ManifestoVersion.version_number.desc())
        .all()
    )


def submit_feedback(
    db: Session,
    manifesto_id: int,
    family_id: int,
    user_id: int,
    content: str,
) -> ManifestoFeedback:
    """Submit feedback for a manifesto."""
    feedback = ManifestoFeedback(
        manifesto_id=manifesto_id,
        family_id=family_id,
        user_id=user_id,
        content=content,
    )
    db.add(feedback)
    db.commit()
    db.refresh(feedback)
    return feedback


def get_feedback_list(
    db: Session, manifesto_id: int
) -> list[ManifestoFeedback]:
    """Ordered by created_at desc."""
    return (
        db.query(ManifestoFeedback)
        .filter_by(manifesto_id=manifesto_id)
        .order_by(ManifestoFeedback.created_at.desc())
        .all()
    )


def get_dashboard_summary(
    db: Session, family_id: int
) -> ManifestoDashboardSummaryResponse:
    """Count total family members, count signatures on current version."""
    manifesto = (
        db.query(FamilyManifesto)
        .filter_by(family_id=family_id, status="active")
        .first()
    )
    if manifesto is None or manifesto.current_version_id is None:
        return ManifestoDashboardSummaryResponse(
            manifesto_id=None,
            title="",
            total_members=0,
            signed_count=0,
            status=manifesto.status if manifesto else "none",
        )

    version = (
        db.query(ManifestoVersion).filter_by(id=manifesto.current_version_id).first()
    )
    total_members = (
        db.query(User)
        .filter_by(family_id=family_id, is_active=True)
        .filter(User.role != "child")
        .count()
    )
    signed_count = (
        db.query(ManifestoSignature)
        .filter_by(version_id=manifesto.current_version_id)
        .count()
    )
    return ManifestoDashboardSummaryResponse(
        manifesto_id=manifesto.id,
        title=version.title if version else "",
        total_members=total_members,
        signed_count=signed_count,
        status=manifesto.status,
    )


def get_child_manifesto(
    db: Session, family_id: int, child_user_id: int
) -> ChildManifestoResponse:
    """Return manifesto data + whether child has signed + signer names."""
    manifesto = (
        db.query(FamilyManifesto)
        .filter_by(family_id=family_id, status="active")
        .first()
    )
    if manifesto is None or manifesto.current_version_id is None:
        return ChildManifestoResponse(
            manifesto_id=None,
            title="",
            body="",
            template_id="",
            signed=False,
        )

    version = (
        db.query(ManifestoVersion).filter_by(id=manifesto.current_version_id).first()
    )
    if version is None:
        return ChildManifestoResponse(
            manifesto_id=manifesto.id,
            title="",
            body="",
            template_id="",
            signed=False,
        )

    child_signed = (
        db.query(ManifestoSignature)
        .filter_by(version_id=version.id, user_id=child_user_id)
        .first()
    ) is not None

    # Get signer names
    signatures = (
        db.query(ManifestoSignature).filter_by(version_id=version.id).all()
    )
    signer_ids = [s.user_id for s in signatures]
    signer_names: list[str] = []
    if signer_ids:
        users = db.query(User).filter(User.id.in_(signer_ids)).all()
        signer_names = [u.display_name for u in users]

    return ChildManifestoResponse(
        manifesto_id=manifesto.id,
        title=version.title,
        body=version.body,
        template_id=version.template_id,
        signed=child_signed,
        signer_names=signer_names,
    )


def get_trackable_clauses(
    db: Session, family_id: int
) -> ChildTrackableClausesResponse:
    """Return trackable clause indices from current version."""
    manifesto = (
        db.query(FamilyManifesto)
        .filter_by(family_id=family_id, status="active")
        .first()
    )
    if manifesto is None or manifesto.current_version_id is None:
        return ChildTrackableClausesResponse(has_trackable=False)

    version = (
        db.query(ManifestoVersion).filter_by(id=manifesto.current_version_id).first()
    )
    if version is None or not version.trackable_clause_indices:
        return ChildTrackableClausesResponse(has_trackable=False)

    return ChildTrackableClausesResponse(
        has_trackable=True,
        trackable_clause_indices=version.trackable_clause_indices,
    )
