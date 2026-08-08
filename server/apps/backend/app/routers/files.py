"""File management endpoints — delete and URL retrieval."""
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from apps.backend.app.auth.deps import require_adult
from apps.backend.app.config import settings
from apps.backend.app.core.logging_config import get_logger
from apps.backend.app.database import get_db
from apps.backend.app.errors import AppError, ErrorCode
from apps.backend.app.models.cached_file import CachedFile
from apps.backend.app.models.file_remote_location import FileRemoteLocation
from apps.backend.app.models.storage_backend import (
    StorageBackend as StorageBackendModel,
)
from apps.backend.app.models.user import User
from apps.backend.app.services.storage.config_crypto import decrypt_config
from apps.backend.app.services.storage.factory import get_backend_for_type
from apps.backend.app.services.storage.local import LocalStorageBackend

logger = get_logger(__name__)

router = APIRouter(prefix="/files", tags=["files"])


def _safe_relative_path(local_path: str, upload_dir: str) -> str:
    """Return the path of local_path relative to upload_dir.

    Raises HTTPException 500 if local_path escapes upload_dir (path traversal guard).
    """
    resolved = Path(local_path).resolve()
    base = Path(upload_dir).resolve()
    if not str(resolved).startswith(str(base)):
        logger.error(f"路径越界检测: {local_path!r} 不在 {upload_dir!r} 内")
        raise AppError(ErrorCode.FILE_PATH_INVALID)
    return str(resolved.relative_to(base))


def _get_owned_file(file_id: int, user: User, db: Session) -> CachedFile:
    """Fetch a CachedFile owned by the user's family, or raise 404."""
    cached_file = (
        db.query(CachedFile)
        .filter_by(id=file_id, family_id=user.family_id)
        .first()
    )
    if cached_file is None or cached_file.deleted_at is not None:
        raise AppError(ErrorCode.FILE_NOT_FOUND)
    return cached_file


@router.delete("/{file_id}", status_code=204)
async def delete_file(
    file_id: int,
    user: User = Depends(require_adult),
    db: Session = Depends(get_db),
):
    """Soft-delete a file: remove from local disk and all synced remote backends."""
    cached_file = _get_owned_file(file_id, user, db)

    # Delete from local disk
    local_backend = LocalStorageBackend(settings.UPLOAD_DIR)
    try:
        remote_path = _safe_relative_path(
            cached_file.local_path, str(Path(settings.UPLOAD_DIR) / "uploads")
        )
        await local_backend.delete(remote_path)
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"本地文件删除失败: {e}")

    # Delete from all synced remote backends
    locations = (
        db.query(FileRemoteLocation)
        .filter_by(file_id=file_id)
        .filter(FileRemoteLocation.sync_status == "synced")
        .all()
    )
    for loc in locations:
        backend_row = db.query(StorageBackendModel).filter_by(id=loc.backend_id).first()
        if backend_row is None:
            continue
        try:
            config = decrypt_config(backend_row.config)
            if config:
                backend = get_backend_for_type(backend_row.backend_type, config)
                await backend.delete(loc.remote_path or "")
                loc.sync_status = "deleted"
            else:
                loc.sync_status = "failed"
                loc.last_error = "无法解密存储后端配置"
        except Exception as e:
            logger.warning(f"远程文件删除失败 [{backend_row.id}]: {e}")
            loc.sync_status = "failed"
            loc.last_error = str(e)

    # Soft-delete the cached_file record
    cached_file.deleted_at = datetime.now()
    db.commit()


@router.get("/{file_id}/url")
def get_file_url(
    file_id: int,
    user: User = Depends(require_adult),
    db: Session = Depends(get_db),
):
    """Return the best available URL for a file.

    Prefers the default backend's synced URL; falls back to local /uploads/ URL.
    Supports historical files uploaded under a now-retired backend.
    """
    cached_file = _get_owned_file(file_id, user, db)

    # Try the family's remote backend first
    family_backend = (
        db.query(StorageBackendModel)
        .filter_by(family_id=user.family_id, is_active=True)
        .first()
    )
    if family_backend is not None:
        loc = (
            db.query(FileRemoteLocation)
            .filter_by(file_id=file_id, backend_id=family_backend.id, sync_status="synced")
            .first()
        )
        if loc is not None and loc.remote_url:
            return {"url": loc.remote_url, "source": "remote"}

    # Fall back to any synced remote location (historical backend compatibility)
    any_synced = (
        db.query(FileRemoteLocation)
        .filter_by(file_id=file_id, sync_status="synced")
        .first()
    )
    if any_synced is not None and any_synced.remote_url:
        return {"url": any_synced.remote_url, "source": "remote"}

    # Fall back to local URL
    local_backend = LocalStorageBackend(settings.UPLOAD_DIR)
    remote_path = _safe_relative_path(
        cached_file.local_path, str(Path(settings.UPLOAD_DIR) / "uploads")
    )
    return {"url": local_backend.get_url(remote_path), "source": "local"}
