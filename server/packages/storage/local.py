"""Local filesystem storage backend."""
import os
from pathlib import Path

from packages.core.logging import get_logger
from packages.storage.base import StorageBackend

logger = get_logger(__name__)


class LocalStorageBackend(StorageBackend):
    """Stores files on the local filesystem under UPLOAD_DIR/images/{date_dir}/{filename}."""

    def __init__(self, upload_dir: str) -> None:
        self._upload_dir = Path(upload_dir)

    async def save(self, content: bytes, filename: str, date_dir: str) -> str:
        """Write content to disk and return the relative remote_path."""
        target_dir = self._upload_dir / "images" / date_dir
        target_dir.mkdir(parents=True, exist_ok=True)
        file_path = target_dir / filename
        with open(file_path, "wb") as f:
            f.write(content)
        return f"images/{date_dir}/{filename}"

    async def delete(self, remote_path: str) -> None:
        """Remove file from disk. Raises ValueError if path escapes upload_dir."""
        file_path = (self._upload_dir / remote_path).resolve()
        if not str(file_path).startswith(str(self._upload_dir.resolve())):
            raise ValueError(f"路径越界，拒绝删除: {remote_path}")
        try:
            os.remove(file_path)
        except FileNotFoundError:
            logger.warning(f"本地文件不存在，跳过删除: {file_path}")

    def get_url(self, remote_path: str) -> str:
        """Return root-relative URL served by the StaticFiles mount."""
        return f"/uploads/{remote_path}"
