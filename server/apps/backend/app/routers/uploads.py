"""Authenticated file serving — replaces unauthenticated StaticFiles mount.

Every request to ``/uploads/{family_id}/{user_id}/{date}/{filename}`` now
requires a valid JWT and enforces family-level tenant isolation.

The ``CachedFile`` table is the source of truth: we look up the record by
its on-disk ``local_path``, verify ``family_id`` matches the caller, and
only then serve the file.  This prevents cross-tenant access even if an
attacker guesses or obtains a URL from another family.
"""

import mimetypes
from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from apps.backend.app.auth.deps import require_adult
from apps.backend.app.config import settings
from apps.backend.app.database import get_db
from apps.backend.app.errors import AppError, ErrorCode
from apps.backend.app.models.cached_file import CachedFile
from apps.backend.app.models.user import User

router = APIRouter(prefix="/uploads", tags=["uploads"])


@router.get("/{file_path:path}")
async def serve_uploaded_file(
    file_path: str,
    user: User = Depends(require_adult),
    db: Session = Depends(get_db),
):
    """Serve an uploaded file with authentication and tenant isolation.

    URL structure: ``/{family_id}/{user_id}/{date_dir}/{filename}``

    Security guarantees:
    - Caller must be authenticated (JWT cookie or Bearer token)
    - ``family_id`` in URL must match caller's ``family_id``
    - File must exist in ``cached_files`` table and not be soft-deleted
    - File must exist on disk
    - Path traversal is blocked at segment level
    """
    parts = file_path.split("/")
    if len(parts) < 4:
        raise AppError(ErrorCode.FILE_NOT_FOUND)

    # Path traversal guard — reject unsafe segments
    for segment in parts:
        if not segment or segment in (".", ".."):
            raise AppError(ErrorCode.FILE_PATH_INVALID)

    family_id_str = parts[0]

    # Tenant isolation — URL family must match authenticated user's family
    if family_id_str != str(user.family_id):
        raise AppError(ErrorCode.FILE_NOT_FOUND)

    # Reconstruct the absolute disk path
    local_path = str(Path(settings.UPLOAD_DIR) / "uploads" / file_path)

    # Look up the cached file record and verify ownership
    cached_file = (
        db.query(CachedFile)
        .filter(
            CachedFile.local_path == local_path,
            CachedFile.family_id == user.family_id,
            CachedFile.deleted_at.is_(None),
        )
        .first()
    )
    if cached_file is None:
        raise AppError(ErrorCode.FILE_NOT_FOUND)

    # Verify file exists on disk
    if not Path(local_path).is_file():
        raise AppError(ErrorCode.FILE_NOT_FOUND)

    # Determine content type from stored MIME or filename extension
    media_type = cached_file.mime_type or mimetypes.guess_type(local_path)[0] or "application/octet-stream"

    # 30-day immutable cache — UUID filenames are content-addressed, safe to cache
    return FileResponse(
        path=local_path,
        media_type=media_type,
        headers={
            "Cache-Control": "public, max-age=2592000, immutable",
        },
    )
