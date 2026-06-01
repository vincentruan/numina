"""FileResource — ensures managed files exist with correct content/version."""

from __future__ import annotations

import hashlib
import logging
import os
import shutil
import tempfile
from collections.abc import Callable
from pathlib import Path

from apps.backend.app.reconcile.base import Resource
from apps.backend.app.reconcile.types import (
    FailureAction,
    ResourceResult,
    ResourceStatus,
    ResourceType,
)

logger = logging.getLogger(__name__)

# Marker comment placed in managed files to indicate they are system-managed
MANAGED_MARKER = "# managed-by: numina-reconcile"


class FileResource(Resource):
    """Ensures a file exists with expected content, using checksums to detect drift.

    Rules:
    - File missing → create from source content
    - File exists, matches checksum → verified
    - File exists, checksum differs, has managed marker → update (backup first)
    - File exists, checksum differs, no managed marker → user-modified, skip
    """

    def __init__(
        self,
        name: str,
        path: str | Path,
        *,
        content_provider: Callable[[], str | bytes] | None = None,
        source_path: str | Path | None = None,
        desired_version: str = "1",
        desired_checksum: str | None = None,
        critical: bool = False,
        failure_action: FailureAction = FailureAction.WARN_ONLY,
        add_managed_marker: bool = True,
    ):
        super().__init__(
            name=name,
            resource_type=ResourceType.FILE,
            desired_version=desired_version,
            critical=critical,
            failure_action=failure_action,
            offline_hint=f"Place the expected file at '{path}'.",
        )
        self._path = Path(path)
        self._content_provider = content_provider
        self._source_path = Path(source_path) if source_path else None
        self._desired_checksum = desired_checksum
        self._add_managed_marker = add_managed_marker

    def _get_desired_content(self) -> bytes:
        if self._content_provider:
            content = self._content_provider()
            return content if isinstance(content, bytes) else content.encode("utf-8")
        if self._source_path and self._source_path.exists():
            return self._source_path.read_bytes()
        raise ValueError(f"No content source for file resource '{self.name}'")

    def _compute_checksum(self, data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()[:16]

    def _file_checksum(self, path: Path) -> str:
        return self._compute_checksum(path.read_bytes())

    def _is_managed(self, path: Path) -> bool:
        """Check if the file contains our managed marker."""
        try:
            head = path.read_bytes()[:4096]
            return MANAGED_MARKER.encode() in head
        except OSError:
            return False

    def check(self, db=None) -> ResourceResult:
        if not self._path.exists():
            return self._drifted(
                current_version=None,
                metadata={"reason": "file_missing"},
            )

        current_checksum = self._file_checksum(self._path)

        if self._desired_checksum:
            expected = self._desired_checksum
        else:
            try:
                desired_content = self._get_desired_content()
                expected = self._compute_checksum(desired_content)
            except (ValueError, OSError):
                return self._verified(current_version=current_checksum)

        if current_checksum == expected:
            return self._verified(current_version=current_checksum)

        if not self._is_managed(self._path):
            return self._make_result(
                status=ResourceStatus.SKIPPED,
                current_version=current_checksum,
                metadata={"reason": "user_modified", "hint": "File was modified by user, not overwriting."},
            )

        return self._drifted(
            current_version=current_checksum,
            metadata={"reason": "checksum_mismatch", "expected": expected},
        )

    def apply(self, db=None) -> ResourceResult:
        try:
            desired_content = self._get_desired_content()
        except (ValueError, OSError) as e:
            return self._failed(error=f"Cannot get desired content: {e}")

        # Backup existing file before overwriting
        if self._path.exists():
            backup_path = self._path.with_suffix(self._path.suffix + ".bak")
            try:
                shutil.copy2(str(self._path), str(backup_path))
                logger.info(f"Backed up {self._path} → {backup_path}")
            except OSError as e:
                logger.warning(f"Could not backup {self._path}: {e}")

        # Prepend managed marker if applicable
        if self._add_managed_marker and not desired_content.startswith(MANAGED_MARKER.encode()):
            if desired_content.startswith(b"#"):
                # Insert after shebang/first comment line
                lines = desired_content.split(b"\n", 1)
                desired_content = lines[0] + b"\n" + MANAGED_MARKER.encode() + b"\n" + (lines[1] if len(lines) > 1 else b"")
            else:
                desired_content = MANAGED_MARKER.encode() + b"\n" + desired_content

        # Atomic write: write to temp file then rename
        self._path.parent.mkdir(parents=True, exist_ok=True)
        try:
            fd, tmp_path = tempfile.mkstemp(
                dir=str(self._path.parent),
                prefix=f".{self._path.name}.",
            )
            try:
                os.write(fd, desired_content)
                os.fsync(fd)
            finally:
                os.close(fd)
            os.replace(tmp_path, str(self._path))
        except OSError as e:
            # Clean up temp file on failure
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            return self._failed(error=f"Atomic write failed: {e}")

        checksum = self._compute_checksum(desired_content)
        return self._verified(current_version=checksum)

    def verify(self, db=None) -> ResourceResult:
        return self.check(db)
