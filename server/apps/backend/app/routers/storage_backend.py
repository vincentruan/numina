"""Family-scoped remote storage backend configuration.

GET    /api/v1/family/storage           — get current family's backend (any adult)
GET    /api/v1/family/storage/status    — lightweight status check (any adult)
POST   /api/v1/family/storage           — create backend (owner only)
PATCH  /api/v1/family/storage/{id}      — update backend (owner only)
DELETE /api/v1/family/storage/{id}      — delete backend (owner only)
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from apps.backend.app.auth.deps import require_adult
from apps.backend.app.database import get_db
from apps.backend.app.errors.codes import ErrorCode
from apps.backend.app.errors.exceptions import AppError
from apps.backend.app.models.storage_backend import StorageBackend as StorageBackendModel
from apps.backend.app.models.user import User
from apps.backend.app.schemas.storage_backend import (
    StorageBackendCreateRequest,
    StorageBackendResponse,
    StorageBackendStatusResponse,
    StorageBackendUpdateRequest,
)
from apps.backend.app.services.storage.config_crypto import decrypt_config, encrypt_config
from apps.backend.app.services.storage.factory import get_backend_for_type
from packages.core.roles import UserRole

router = APIRouter(prefix="/family/storage", tags=["family-storage"])


def _get_owned_backend(db: Session, family_id: int) -> StorageBackendModel | None:
    """Return the family's storage backend row, or None."""
    return (
        db.query(StorageBackendModel)
        .filter_by(family_id=family_id)
        .first()
    )


def _require_owner(user: User) -> None:
    if user.role != UserRole.OWNER:
        raise AppError(ErrorCode.FAMILY_FORBIDDEN)


@router.get("", response_model=StorageBackendResponse | None)
def get_backend(
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    """Return the family's storage backend, or null if not configured."""
    backend = _get_owned_backend(db, user.family_id)
    if backend is None:
        return None
    return StorageBackendResponse.model_validate(backend)


@router.get("/status", response_model=StorageBackendStatusResponse)
def get_status(
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    """Lightweight status for frontend UI state decisions."""
    backend = _get_owned_backend(db, user.family_id)
    if backend is None:
        return StorageBackendStatusResponse(configured=False)
    return StorageBackendStatusResponse(
        configured=True,
        backend_type=backend.backend_type,
        display_name=backend.display_name,
        is_active=backend.is_active,
    )


@router.post("", response_model=StorageBackendResponse, status_code=201)
def create_backend(
    req: StorageBackendCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    """Create a remote storage backend for the family. Owner only."""
    _require_owner(user)

    existing = _get_owned_backend(db, user.family_id)
    if existing is not None:
        raise AppError(ErrorCode.STORAGE_BACKEND_ALREADY_EXISTS)

    # Build config dict from the appropriate config sub-schema
    config_dict = req.config.model_dump()
    config_encrypted = encrypt_config(config_dict)

    backend = StorageBackendModel(
        family_id=user.family_id,
        backend_type=req.backend_type.value,
        display_name=req.display_name,
        config=config_encrypted,
        is_active=req.is_active,
    )
    db.add(backend)
    db.commit()
    db.refresh(backend)
    return StorageBackendResponse.model_validate(backend)


@router.patch("/{backend_id}", response_model=StorageBackendResponse)
def update_backend(
    backend_id: int,
    req: StorageBackendUpdateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    """Update the family's storage backend. Owner only."""
    _require_owner(user)

    backend = _get_owned_backend(db, user.family_id)
    if backend is None or backend.id != backend_id:
        raise AppError(ErrorCode.STORAGE_BACKEND_NOT_FOUND)

    if req.display_name is not None:
        backend.display_name = req.display_name
    if req.is_active is not None:
        backend.is_active = req.is_active
    if req.config is not None:
        config_dict = req.config.model_dump()
        backend.config = encrypt_config(config_dict)

    db.commit()
    db.refresh(backend)
    return StorageBackendResponse.model_validate(backend)


@router.delete("/{backend_id}", status_code=204)
def delete_backend(
    backend_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    """Delete the family's storage backend. Owner only.

    Orphans any synced FileRemoteLocation rows (sets backend_id to NULL,
    sync_status to 'orphaned') so historical records are preserved.
    """
    _require_owner(user)

    backend = _get_owned_backend(db, user.family_id)
    if backend is None or backend.id != backend_id:
        raise AppError(ErrorCode.STORAGE_BACKEND_NOT_FOUND)

    # Verify the backend is reachable before allowing deletion,
    # so we can surface a helpful error if credentials are invalid.
    config = decrypt_config(backend.config)
    if config:
        try:
            storage = get_backend_for_type(backend.backend_type, config)
            # Quick connectivity check — just list root; ignore failures.
            import asyncio
            asyncio.get_event_loop().run_until_complete(storage.list(""))
        except Exception:
            # Non-fatal — proceed with deletion even if backend is unreachable
            pass

    # Orphan remote locations instead of hard-deleting them
    from apps.backend.app.models.file_remote_location import FileRemoteLocation

    db.query(FileRemoteLocation).filter_by(backend_id=backend.id).update(
        {FileRemoteLocation.backend_id: None, FileRemoteLocation.sync_status: "orphaned"},
        synchronize_session="fetch",
    )

    db.delete(backend)
    db.commit()
