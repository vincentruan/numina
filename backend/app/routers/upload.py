import os
import uuid
from datetime import date, datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user
from app.database import get_db
from app.models.user import User

router = APIRouter(prefix="/upload", tags=["upload"])

# Upload directory - /app/data/uploads/images in Docker, ./data/uploads/images locally
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "./data/uploads")) / "images"
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB


def ensure_upload_dir():
    """Ensure upload directory exists."""
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@router.post("/image")
async def upload_image(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
):
    """Upload an image file and return its URL."""
    # Validate file extension
    ext = Path(file.filename).suffix.lower() if file.filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件格式，仅支持 jpg/png/webp"
        )

    # Read file content
    content = await file.read()

    # Validate file size
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"文件大小超过限制（最大 5MB）"
        )

    # Generate unique filename
    filename = f"{uuid.uuid4().hex}{ext}"

    # Ensure upload directory exists
    ensure_upload_dir()

    # Save file
    file_path = UPLOAD_DIR / filename
    with open(file_path, "wb") as f:
        f.write(content)

    # Return URL path (relative to API base)
    return {"url": f"/uploads/images/{filename}"}