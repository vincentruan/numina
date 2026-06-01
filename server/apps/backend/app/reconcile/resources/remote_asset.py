"""RemoteAssetResource — manages files that come from remote URLs (GitHub, etc.)."""

from __future__ import annotations

import hashlib
import logging
import os
import tempfile
from pathlib import Path

from apps.backend.app.reconcile.base import Resource
from apps.backend.app.reconcile.types import (
    FailureAction,
    ResourceResult,
    ResourceType,
)

logger = logging.getLogger(__name__)


class RemoteAssetResource(Resource):
    """Ensures a remote asset is present locally with correct checksum.

    Supports:
    - Fixed URL (pinned commit/tag, not branch HEAD)
    - SHA-256 checksum verification
    - Local cache directory
    - Offline mode (use cache or user-placed file)
    - Graceful degradation for non-critical assets
    """

    def __init__(
        self,
        name: str,
        local_path: str | Path,
        url: str,
        *,
        sha256: str | None = None,
        desired_version: str = "1",
        critical: bool = False,
        failure_action: FailureAction = FailureAction.DISABLE_FEATURE,
        feature_flag: str | None = None,
        cache_dir: str | Path | None = None,
        offline: bool = False,
    ):
        offline_steps = [
            f"On a machine with internet access, download: {url}",
        ]
        if sha256:
            offline_steps.append(f"Verify sha256: {sha256}")
        offline_steps.extend([
            f"Copy the file to: {local_path}",
            "Run: python -m apps.backend.app.reconcile verify",
        ])

        super().__init__(
            name=name,
            resource_type=ResourceType.REMOTE_ASSET,
            desired_version=desired_version,
            critical=critical,
            failure_action=failure_action,
            feature_flag=feature_flag,
            offline_hint=f"Download manually from {url} and place at {local_path}",
        )
        self._local_path = Path(local_path)
        self._url = url
        self._sha256 = sha256
        self._cache_dir = Path(cache_dir) if cache_dir else None
        self._offline = offline
        self._offline_steps = offline_steps

    def _compute_sha256(self, path: Path) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()

    def _cache_path(self) -> Path | None:
        if not self._cache_dir:
            return None
        return self._cache_dir / f"{self.name}.{self._sha256[:12] if self._sha256 else 'latest'}"

    def _verify_checksum(self, path: Path) -> bool:
        if not self._sha256:
            return True
        actual = self._compute_sha256(path)
        return actual == self._sha256

    def check(self, db=None) -> ResourceResult:
        if self._local_path.exists():
            if self._verify_checksum(self._local_path):
                return self._verified(current_version=self.desired_version)
            return self._drifted(
                current_version="checksum_mismatch",
                metadata={"reason": "checksum_mismatch"},
            )

        # Check cache
        cache = self._cache_path()
        if cache and cache.exists() and self._verify_checksum(cache):
            return self._drifted(
                current_version=None,
                metadata={"reason": "missing_but_cached"},
            )

        return self._drifted(
            current_version=None,
            metadata={"reason": "file_missing"},
        )

    def apply(self, db=None) -> ResourceResult:
        # Try cache first
        cache = self._cache_path()
        if cache and cache.exists() and self._verify_checksum(cache):
            return self._install_from(cache)

        # Offline mode — cannot download
        if self._offline:
            result = self._failed(
                error=f"Asset missing and offline mode is active: {self._local_path}",
                offline_steps=self._offline_steps,
            )
            if not self.critical and self.feature_flag:
                result.feature_disabled = self.feature_flag
            return result

        # Attempt download
        try:
            downloaded = self._download()
        except Exception as e:
            result = self._failed(
                error=f"Download failed: {e}",
                offline_steps=self._offline_steps,
            )
            if not self.critical and self.feature_flag:
                result.feature_disabled = self.feature_flag
            return result

        # Verify checksum
        if not self._verify_checksum(downloaded):
            os.unlink(downloaded)
            return self._failed(
                error=f"Checksum mismatch after download (expected {self._sha256})",
                remediation_hint="The remote file may have been tampered with or the expected checksum is outdated.",
            )

        # Cache the download
        if cache:
            cache.parent.mkdir(parents=True, exist_ok=True)
            try:
                import shutil
                shutil.copy2(str(downloaded), str(cache))
            except OSError:
                pass

        return self._install_from(Path(downloaded))

    def _download(self) -> Path:
        """Download URL to a temporary file. Returns the temp path."""
        import httpx

        self._local_path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(
            dir=str(self._local_path.parent),
            prefix=f".{self._local_path.name}.",
        )
        try:
            with httpx.Client(timeout=30.0, follow_redirects=True) as client, client.stream("GET", self._url) as resp:
                resp.raise_for_status()
                for chunk in resp.iter_bytes(8192):
                    os.write(fd, chunk)
            os.fsync(fd)
        except Exception:
            os.close(fd)
            os.unlink(tmp_path)
            raise
        os.close(fd)
        return Path(tmp_path)

    def _install_from(self, source: Path) -> ResourceResult:
        """Move/copy source file to the target local_path atomically."""
        self._local_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            if source.parent == self._local_path.parent:
                os.replace(str(source), str(self._local_path))
            else:
                import shutil
                shutil.copy2(str(source), str(self._local_path))
        except OSError as e:
            return self._failed(error=f"Failed to install asset: {e}")

        return self._verified(current_version=self.desired_version)

    def verify(self, db=None) -> ResourceResult:
        if not self._local_path.exists():
            result = self._failed(
                error=f"Asset file not found: {self._local_path}",
                offline_steps=self._offline_steps,
            )
            if not self.critical and self.feature_flag:
                result.feature_disabled = self.feature_flag
            return result

        if not self._verify_checksum(self._local_path):
            return self._failed(
                error="Asset checksum does not match expected value",
                remediation_hint=f"Re-download from {self._url} or run reconcile in repair mode.",
            )

        return self._verified(current_version=self.desired_version)
