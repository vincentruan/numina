"""Bootstrap builtin skills (system-wide templates, family_id=0).

U5: the ``report`` builtin skill was removed (asset-report is now a system
fixed-flow in RESERVED_NAMES, not a toggleable BUILTIN_CAPABILITY). The
``asset-report``/``chat``/``chat-search`` skills are file-system skills loaded
by the agent's skill scanner at runtime, not rows in this registry. This
function is retained as an idempotent no-op for the bootstrap call site.
"""

from sqlalchemy.orm import Session

from apps.backend.app.core.logging_config import get_logger

logger = get_logger(__name__)

_BUILTIN_SKILLS: list[dict] = []


def bootstrap_skills(db: Session) -> None:
    """Ensure builtin skills exist as system-wide templates. Idempotent.

    U5: no builtin skill rows to insert (report removed; asset-report/chat/
    chat-search are file-system skills, not registry rows). Kept as a no-op
    for the existing bootstrap call site.
    """
    return
