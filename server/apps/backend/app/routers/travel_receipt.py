from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from apps.backend.app.auth.deps import require_adult
from apps.backend.app.database import get_db
from apps.backend.app.errors import AppError, ErrorCode
from apps.backend.app.models.user import User
from apps.backend.app.schemas.travel_receipt import TravelReceiptUploadResponse
from apps.backend.app.services.file_validation import (
    detect_image_format,
    validate_image_magic_bytes,
)
from apps.backend.app.services.security_log import (
    SecurityEventType,
    _log_security_event,
)
from apps.backend.app.services.storage.service import StorageService

router = APIRouter(prefix="/import", tags=["travel"])

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".heic"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


@router.post("/parse-travel-receipt", response_model=TravelReceiptUploadResponse, status_code=201)
async def parse_travel_receipt(
    trip_id: str = Form(...),
    file: UploadFile = File(...),
    user: User = Depends(require_adult),
    db: Session = Depends(get_db),
):
    """Upload a travel receipt image for later AI extraction.

    Accepts the image, validates and stores it, then returns the stored URL.
    The actual AI extraction happens asynchronously through the import-parse chat flow.
    """
    # Validate file extension
    ext = Path(file.filename).suffix.lower() if file.filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise AppError(ErrorCode.FILE_FORMAT_INVALID)

    # Read file content
    content = await file.read()

    # Validate file size
    if len(content) > MAX_FILE_SIZE:
        raise AppError(ErrorCode.FILE_SIZE_EXCEEDED)

    # Validate magic bytes (skip for HEIC — no standard magic byte check)
    if ext != ".heic":
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

    # Store the file using the existing storage service
    file_record = await StorageService.upload_file(
        content, file.filename or "receipt.jpg", ext, user, db
    )

    return TravelReceiptUploadResponse(
        receipt_image_url=file_record.url,
        trip_id=trip_id,
        extracted_data=None,
        confidence="pending",
    )
