"""Family-scoped remote storage backend configuration.

GET    /api/v1/family/storage           — get current family's backend (any adult)
GET    /api/v1/family/storage/status    — lightweight status check (any adult)
POST   /api/v1/family/storage           — create backend (owner only)
PATCH  /api/v1/family/storage/{id}      — update backend (owner only)
DELETE /api/v1/family/storage/{id}      — delete backend (owner only)
POST   /api/v1/family/storage/sync      — trigger immediate sync (owner only)
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from apps.backend.app.auth.deps import require_adult
from apps.backend.app.database import get_db
from apps.backend.app.errors.codes import ErrorCode
from apps.backend.app.errors.exceptions import AppError
from apps.backend.app.models.cached_file import CachedFile
from apps.backend.app.models.file_remote_location import FileRemoteLocation
from apps.backend.app.models.storage_backend import (
    StorageBackend as StorageBackendModel,
)
from apps.backend.app.models.user import User
from apps.backend.app.schemas.storage_backend import (
    StorageBackendCreateRequest,
    StorageBackendResponse,
    StorageBackendStatusResponse,
    StorageBackendUpdateRequest,
)
from apps.backend.app.services.storage.config_crypto import encrypt_config
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
    db.flush()  # Generate backend.id before creating FileRemoteLocation rows

    # Backfill: queue all existing (non-deleted) files for sync to the new backend.
    # Without this, files uploaded before backend configuration are never synced.
    _backfill_pending_sync(db, user.family_id, backend.id)

    db.commit()
    db.refresh(backend)
    return StorageBackendResponse.model_validate(backend)


def _backfill_pending_sync(db: Session, family_id: int, backend_id: int) -> int:
    """Create pending FileRemoteLocation rows for existing CachedFiles.

    Skips files that already have a remote location for this backend
    (defensive — should not happen for a brand-new backend) and soft-deleted files.
    Returns the number of rows created.
    """
    # Find cached files that DON'T already have a location for this backend
    existing_file_ids = {
        row[0]
        for row in db.query(FileRemoteLocation.file_id)
        .filter_by(backend_id=backend_id)
        .all()
    }
    unsynced = (
        db.query(CachedFile)
        .filter_by(family_id=family_id)
        .filter(CachedFile.deleted_at.is_(None))
        .all()
    )
    unsynced = [cf for cf in unsynced if cf.id not in existing_file_ids]
    count = 0
    for cf in unsynced:
        loc = FileRemoteLocation(
            file_id=cf.id,
            backend_id=backend_id,
            sync_status="pending",
        )
        db.add(loc)
        count += 1
    if count > 0:
        from packages.core.logging import get_logger
        get_logger(__name__).info(
            f"存储后端 {backend_id}: 排队 {count} 个历史文件待同步"
        )
    return count


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

    # Orphan remote locations instead of hard-deleting them
    from apps.backend.app.models.file_remote_location import FileRemoteLocation

    db.query(FileRemoteLocation).filter_by(backend_id=backend.id).update(
        {FileRemoteLocation.backend_id: None, FileRemoteLocation.sync_status: "orphaned"},
        synchronize_session="fetch",
    )

    db.delete(backend)
    db.commit()


@router.post("/sync", status_code=200)
def trigger_sync(
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    """Re-queue failed/pending files and backfill unsynced files for immediate sync.

    Resets retry_count on failed locations so the next scheduler cycle picks them up.
    Also backfills any CachedFiles that lack a FileRemoteLocation (e.g. uploaded
    while the backend was inactive).
    """
    _require_owner(user)
    backend = _get_owned_backend(db, user.family_id)
    if backend is None:
        raise AppError(ErrorCode.STORAGE_BACKEND_NOT_FOUND)
    if not backend.is_active:
        raise AppError(ErrorCode.STORAGE_BACKEND_INACTIVE)

    # Reset failed locations so they can be retried
    reset_count = (
        db.query(FileRemoteLocation)
        .filter_by(backend_id=backend.id)
        .filter(FileRemoteLocation.sync_status == "failed")
        .update(
            {FileRemoteLocation.sync_status: "pending", FileRemoteLocation.retry_count: 0},
            synchronize_session="fetch",
        )
    )

    # Backfill any files that lack a remote location
    backfill_count = _backfill_pending_sync(db, user.family_id, backend.id)

    db.commit()
    return {
        "reset_failed": reset_count,
        "backfilled": backfill_count,
    }
