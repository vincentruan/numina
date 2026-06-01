"""DirectoryResource — ensures directories exist and are writable."""

from __future__ import annotations

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


class DirectoryResource(Resource):
    """Ensures a directory exists, is writable, and supports atomic operations."""

    def __init__(
        self,
        name: str,
        path: str | Path,
        *,
        desired_version: str = "1",
        critical: bool = True,
        failure_action: FailureAction = FailureAction.FAIL_STARTUP,
        create_parents: bool = True,
    ):
        super().__init__(
            name=name,
            resource_type=ResourceType.DIRECTORY,
            desired_version=desired_version,
            critical=critical,
            failure_action=failure_action,
            offline_hint=f"Ensure directory '{path}' exists and is writable by the application user.",
        )
        self._path = Path(path)
        self._create_parents = create_parents

    def check(self, db=None) -> ResourceResult:
        path = self._path

        if not path.exists():
            return self._drifted(
                current_version=None,
                metadata={"reason": "directory_missing"},
            )

        if not path.is_dir():
            return self._failed(
                error=f"Path exists but is not a directory: {path}",
                remediation_hint=f"Remove the file at '{path}' and restart, or change the configured path.",
            )

        if not os.access(path, os.R_OK):
            return self._failed(
                error=f"Directory not readable: {path}",
                remediation_hint=f"Run: chmod +r '{path}' or check Docker volume mount permissions.",
            )

        if not os.access(path, os.W_OK):
            return self._failed(
                error=f"Directory not writable: {path}",
                remediation_hint=f"Run: chmod +w '{path}' or check Docker volume mount permissions (user: {os.getuid()}).",
            )

        # Verify atomic rename works (critical for safe file writes)
        try:
            fd, tmp_path = tempfile.mkstemp(dir=str(path), prefix=".reconcile_probe_")
            os.close(fd)
            rename_target = tmp_path + ".renamed"
            os.rename(tmp_path, rename_target)
            os.unlink(rename_target)
        except OSError as e:
            return self._failed(
                error=f"Directory does not support atomic rename: {path} ({e})",
                remediation_hint=(
                    f"The filesystem at '{path}' may not support atomic operations. "
                    "Check that it is not a network mount with limited POSIX support."
                ),
            )

        return self._verified(current_version=self.desired_version)

    def apply(self, db=None) -> ResourceResult:
        path = self._path
        try:
            path.mkdir(parents=self._create_parents, exist_ok=True)
        except PermissionError as e:
            return self._failed(
                error=f"Cannot create directory '{path}': {e}",
                remediation_hint=(
                    f"Create the directory manually: mkdir -p '{path}' && "
                    f"chown {os.getuid()}:{os.getgid()} '{path}'"
                ),
            )
        except OSError as e:
            return self._failed(error=f"Failed to create directory '{path}': {e}")

        return self._verified(current_version=self.desired_version)

    def verify(self, db=None) -> ResourceResult:
        return self.check(db)
