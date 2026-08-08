"""StorageService — orchestrates file upload, dedup, and DB persistence."""
import contextlib
import hashlib
import os
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from apps.backend.app.config import settings
from apps.backend.app.models.cached_file import CachedFile
from apps.backend.app.models.file_remote_location import FileRemoteLocation
from apps.backend.app.models.storage_backend import (
    StorageBackend as StorageBackendModel,
)
from apps.backend.app.models.user import User
from apps.backend.app.schemas.file_record import FileRecordResponse
from apps.backend.app.services.storage.local import LocalStorageBackend

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
        if existing is not None:
            if existing.deleted_at is None:
                # Active duplicate — return existing record
                remote_path = str(
                    Path(existing.local_path).relative_to(Path(settings.UPLOAD_DIR) / "uploads")
                )
                return FileRecordResponse(
                    file_id=existing.id,
                    url=backend.get_url(remote_path),
                    filename=existing.original_filename,
                    size_bytes=existing.size_bytes,
                )
            else:
                # Soft-deleted duplicate — resurrect it
                existing.deleted_at = None
                existing.user_id = user.id
                existing.original_filename = original_filename
                db.commit()
                remote_path = str(
                    Path(existing.local_path).relative_to(Path(settings.UPLOAD_DIR) / "uploads")
                )
                return FileRecordResponse(
                    file_id=existing.id,
                    url=backend.get_url(remote_path),
                    filename=original_filename,
                    size_bytes=existing.size_bytes,
                )

        # New file — persist to disk
        filename = f"{uuid4().hex}{ext}"
        date_dir = datetime.now().strftime("%Y%m%d")
        remote_path = await backend.save(content, filename, date_dir, family_id=str(user.family_id), user_id=str(user.id))
        local_path = str(Path(settings.UPLOAD_DIR) / "uploads" / remote_path)

        mime_type = _MIME_MAP.get(ext.lower(), "application/octet-stream")

        cached_file = CachedFile(
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
        db.flush()  # Generate Snowflake ID before using cached_file.id below

        # Optionally queue sync to the family's remote backend (if configured)
        family_backend = (
            db.query(StorageBackendModel)
            .filter_by(family_id=user.family_id, is_active=True)
            .first()
        )
        if family_backend is not None:
            remote_loc = FileRemoteLocation(
                file_id=cached_file.id,
                backend_id=family_backend.id,
                sync_status="pending",
            )
            db.add(remote_loc)

        try:
            db.commit()
        except IntegrityError:
            # Concurrent upload of identical bytes won the race — roll back,
            # clean up the orphaned disk file, and return the winner's record.
            db.rollback()
            with contextlib.suppress(OSError):
                os.remove(local_path)
            winner = (
                db.query(CachedFile)
                .filter_by(sha256=sha256, family_id=user.family_id)
                .filter(CachedFile.deleted_at.is_(None))
                .first()
            )
            if winner is not None:
                winner_path = str(
                    Path(winner.local_path).relative_to(Path(settings.UPLOAD_DIR) / "uploads")
                )
                return FileRecordResponse(
                    file_id=winner.id,
                    url=backend.get_url(winner_path),
                    filename=winner.original_filename,
                    size_bytes=winner.size_bytes,
                )
            # Extremely unlikely: winner was soft-deleted between race and here
            raise

        return FileRecordResponse(
            file_id=cached_file.id,
            url=backend.get_url(remote_path),
            filename=original_filename,
            size_bytes=len(content),
        )
