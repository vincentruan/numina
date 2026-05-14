from pathlib import Path

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from apps.backend.app.auth.deps import require_adult
from apps.backend.app.database import get_db
from apps.backend.app.errors import AppError, ErrorCode
from apps.backend.app.models.user import User
from apps.backend.app.schemas.file_record import FileRecordResponse
from apps.backend.app.services.file_validation import detect_image_format, validate_image_magic_bytes
from apps.backend.app.services.security_log import SecurityEventType, _log_security_event
from apps.backend.app.services.storage.service import StorageService

router = APIRouter(prefix="/upload", tags=["upload"])

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB


@router.post("/image", response_model=FileRecordResponse)
async def upload_image(
    file: UploadFile = File(...),
    user: User = Depends(require_adult),
    db: Session = Depends(get_db),
):
    """Upload an image file and return its URL."""
    # Validate file extension
    ext = Path(file.filename).suffix.lower() if file.filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise AppError(ErrorCode.FILE_FORMAT_INVALID)

    # Read file content
    content = await file.read()

    # Validate file size
    if len(content) > MAX_FILE_SIZE:
        raise AppError(ErrorCode.FILE_SIZE_EXCEEDED)

    # Validate magic bytes - security enhancement
    ext_without_dot = ext.lstrip(".")
    if not validate_image_magic_bytes(content, ext_without_dot):
        actual_format = detect_image_format(content)
        _log_security_event(
            SecurityEventType.UPLOAD_MAGIC_BYTES_MISMATCH,
            user_id=user.id,
            claimed_format=ext_without_dot,
            actual_format=actual_format or "unknown",
        )
        raise AppError(ErrorCode.FILE_CONTENT_MISMATCH)

    return await StorageService.upload_file(content, file.filename or "upload", ext, user, db)
