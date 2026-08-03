"""Bootstrap per-family backend MCP server records.

Ensures every family has a ``FamilyMCPServer`` row with
``name="Numina Backend MCP"`` so the AI agent can reach the backend's
internal MCP SSE endpoint.  Normally created during ``auth.register()``,
but families seeded or created before this logic existed may be missing
the row — this bootstrap fills the gap.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from apps.backend.app.core.logging_config import get_logger
from apps.backend.app.models.family_mcp_server import FamilyMCPServer

logger = get_logger(__name__)


def bootstrap_family_mcp_servers(db: Session) -> None:
    """Ensure every family has a backend MCP server record. Idempotent.

    The MCP SSE endpoint URL is constructed from ``BACKEND_BASE_URL``.
    Families that already have the record are left untouched.
    """
    from apps.backend.app.models.family import Family
    from apps.backend.app.utils.snowflake import next_id as _next_id
    from packages.core.settings import settings

    backend_url = settings.BACKEND_BASE_URL.rstrip("/")

    # Query all family IDs that lack a backend MCP server record.
    existing_family_ids = {
        row.family_id
        for row in db.query(FamilyMCPServer.family_id).filter(
            FamilyMCPServer.name == "Numina Backend MCP",
        ).all()
    }

    all_family_ids = {
        row.id for row in db.query(Family.id).all()
    }

    missing = all_family_ids - existing_family_ids
    if not missing:
        return

    for family_id in missing:
        mcp_url = f"{backend_url}/api/v1/internal/mcp/{family_id}/sse"
        db.add(FamilyMCPServer(
            id=_next_id(),
            family_id=family_id,
            name="Numina Backend MCP",
            url=mcp_url,
            transport="sse",
            is_enabled=True,
            mcp_type="backend",
        ))
        logger.info("补建 backend MCP server: family=%s url=%s", family_id, mcp_url)

    db.commit()
