from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from packages.core.path_manager import PathManager

_path_manager: "PathManager | None" = None


def get_path_manager() -> "PathManager":
    """Return the shared PathManager singleton. Created on first call."""
    global _path_manager
    if _path_manager is None:
        from packages.core.path_manager import PathManager
        _path_manager = PathManager()
    return _path_manager
