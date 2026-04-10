"""StorageService — orchestrates file upload, dedup, and DB persistence."""
import hashlib
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy.orm import Session

from app.config import settings
from app.models.cached_file import CachedFile
from app.models.file_remote_location import FileRemoteLocation
from app.models.storage_backend import StorageBackend as StorageBackendModel
from app.models.user import User
from app.schemas.file_record import FileRecordResponse
from app.services.storage.local import LocalStorageBackend

_MIME_MAP: dict[str, str] = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}


class StorageService:
    @staticmethod
    async def upload_file(
        content: bytes,
        original_filename: str,
        ext: str,
        user: User,
        db: Session,
    ) -> FileRecordResponse:
        sha256 = hashlib.sha256(content).hexdigest()
        backend = LocalStorageBackend(settings.UPLOAD_DIR)

        # Per-family dedup: return existing record if sha256 + family_id match
        existing = (
            db.query(CachedFile)
            .filter_by(sha256=sha256, family_id=user.family_id)
            .first()
        )
        if existing is not None and existing.deleted_at is None:
            remote_path = str(
                Path(existing.local_path).relative_to(settings.UPLOAD_DIR)
            )
            return FileRecordResponse(
                file_id=existing.id,
                url=backend.get_url(remote_path),
                filename=existing.original_filename,
                size_bytes=existing.size_bytes,
            )

        # New file — persist to disk
        filename = f"{uuid4().hex}{ext}"
        date_dir = datetime.now().strftime("%Y%m%d")
        remote_path = await backend.save(content, filename, date_dir)
        local_path = str(Path(settings.UPLOAD_DIR) / remote_path)

        mime_type = _MIME_MAP.get(ext.lower(), "application/octet-stream")

        cached_file = CachedFile(
            id=str(uuid4()),
            family_id=user.family_id,
            user_id=user.id,
            sha256=sha256,
            local_path=local_path,
            original_filename=original_filename,
            mime_type=mime_type,
            size_bytes=len(content),
            date_dir=date_dir,
        )
        db.add(cached_file)

        # Optionally queue sync to default remote backend
        default_backend = (
            db.query(StorageBackendModel)
            .filter_by(is_default=True, is_active=True)
            .first()
        )
        if default_backend is not None:
            remote_loc = FileRemoteLocation(
                file_id=cached_file.id,
                backend_id=default_backend.id,
                sync_status="pending",
            )
            db.add(remote_loc)

        db.commit()

        return FileRecordResponse(
            file_id=cached_file.id,
            url=backend.get_url(remote_path),
            filename=original_filename,
            size_bytes=len(content),
        )
