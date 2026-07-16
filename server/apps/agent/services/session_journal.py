"""Session journal service - stub implementation.

This module was removed but is still referenced by agent_dispatch.py.
Provides no-op implementations to maintain backward compatibility.
"""

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class SessionJournal:
    """Stub session journal - all methods are no-ops."""

    def resolve_path(self, *args: Any, **kwargs: Any) -> Path | None:
        """Return None - journal disabled."""
        return None

    def write_session_start(self, *args: Any, **kwargs: Any) -> None:
        """No-op."""
        pass

    def write_user_message(self, *args: Any, **kwargs: Any) -> None:
        """No-op."""
        pass

    def write_tool_call(self, *args: Any, **kwargs: Any) -> None:
        """No-op."""
        pass

    def write_tool_result(self, *args: Any, **kwargs: Any) -> None:
        """No-op."""
        pass

    def write_assistant_message(self, *args: Any, **kwargs: Any) -> None:
        """No-op."""
        pass

    def write_session_end(self, *args: Any, **kwargs: Any) -> None:
        """No-op."""
        pass

    def append_event(self, *args: Any, **kwargs: Any) -> None:
        """No-op."""
        pass


# Singleton instance
session_journal = SessionJournal()
