"""Local filesystem storage backend."""
import os
import re
from pathlib import Path

from packages.core.logging import get_logger
from packages.storage.base import StorageBackend

logger = get_logger(__name__)

_SAFE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_\-]+$")


def _validate_id(value: str, label: str) -> None:
    if not value or not _SAFE_ID_PATTERN.match(value):
        raise ValueError(
            f"Invalid {label}: must be alphanumeric/dash/underscore, got {value!r}"
        )


class LocalStorageBackend(StorageBackend):
    """Stores files on the local filesystem under UPLOAD_DIR/{family_id}/upload/{user_id}/{date_dir}/{filename}."""

    def __init__(self, upload_dir: str) -> None:
        self._upload_dir = Path(upload_dir)

    async def save(self, content: bytes, filename: str, date_dir: str, family_id: str = "", user_id: str = "") -> str:
        """Write content to disk and return the relative remote_path."""
        if family_id and user_id:
            _validate_id(family_id, "family_id")
            _validate_id(user_id, "user_id")
            # Files go under {UPLOAD_DIR}/uploads/{family_id}/{user_id}/{date}/
            target_dir = self._upload_dir / "uploads" / family_id / user_id / date_dir
            remote_path = f"{family_id}/{user_id}/{date_dir}/{filename}"
        else:
            # Legacy path: {UPLOAD_DIR}/uploads/images/{date}/
            target_dir = self._upload_dir / "uploads" / "images" / date_dir
            remote_path = f"images/{date_dir}/{filename}"
        target_dir.mkdir(parents=True, exist_ok=True)
        file_path = target_dir / filename
        with open(file_path, "wb") as f:
            f.write(content)
        # Path traversal check
        resolved = file_path.resolve()
        if not str(resolved).startswith(str(self._upload_dir.resolve())):
            os.remove(resolved)
            raise ValueError(f"路径越界，拒绝写入: {filename}")
        return remote_path

    async def delete(self, remote_path: str) -> None:
        """Remove file from disk. Raises ValueError if path escapes upload_dir."""
        file_path = (self._upload_dir / "uploads" / remote_path).resolve()
        if not str(file_path).startswith(str(self._upload_dir.resolve())):
            raise ValueError(f"路径越界，拒绝删除: {remote_path}")
        try:
            os.remove(file_path)
        except FileNotFoundError:
            logger.warning("本地文件不存在，跳过删除: %s", file_path)

    async def load(self, remote_path: str) -> bytes:
        """Read a file back from disk. Raises FileNotFoundError if absent or unsafe."""
        file_path = (self._upload_dir / "uploads" / remote_path).resolve()
        if not str(file_path).startswith(str(self._upload_dir.resolve())):
            raise FileNotFoundError(f"路径越界，拒绝读取: {remote_path}")
        if not file_path.is_file():
            raise FileNotFoundError(f"本地文件不存在: {remote_path}")
        return file_path.read_bytes()

    async def list(self, prefix: str) -> list[dict]:
        """List files under prefix, with size and mtime.

        Files written without a family/user id land under an ``images/``
        segment (the legacy layout ``save()`` still uses), so both locations
        are searched for the same logical prefix.
        """
        base = (self._upload_dir / "uploads").resolve()
        entries: list[dict] = []
        for candidate in (prefix, f"images/{prefix}"):
            target = (base / candidate).resolve()
            if not str(target).startswith(str(base)):
                raise FileNotFoundError(f"路径越界，拒绝列举: {prefix}")
            if not target.is_dir():
                continue
            for path in sorted(target.rglob("*")):
                if not path.is_file():
                    continue
                stat = path.stat()
                entries.append(
                    {
                        "path": str(path.relative_to(base)),
                        "size": stat.st_size,
                        "last_modified": stat.st_mtime,
                    }
                )
        return entries

    def get_url(self, remote_path: str) -> str:
        """Return root-relative URL served by the StaticFiles mount."""
        return f"/uploads/{remote_path}"
