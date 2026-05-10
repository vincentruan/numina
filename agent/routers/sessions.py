"""Sessions API — list sessions and stream session events."""

import logging

from fastapi import APIRouter, Header, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.config import settings
from services.session_journal import session_journal
from services.session_store import AiSessionRepository

router = APIRouter(prefix="/sessions", tags=["sessions"])
logger = logging.getLogger(__name__)

# Injected at startup by app/main.py after DB is initialised.
_session_repo: AiSessionRepository | None = None


def set_session_repo(repo: AiSessionRepository) -> None:
    global _session_repo
    _session_repo = repo


@router.get("")
async def list_sessions(
    x_family_id: str = Header(..., alias="X-Family-Id"),
    x_agent_token: str = Header(..., alias="X-Agent-Token"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    if x_agent_token != settings.AGENT_INTERNAL_TOKEN:
        raise HTTPException(status_code=401, detail="invalid token")
    if _session_repo is None:
        raise HTTPException(status_code=503, detail="session store not initialised")

    sessions, total = await _session_repo.list_sessions(
        x_family_id, limit=limit, offset=offset
    )
    return {"sessions": sessions, "total": total}


@router.get("/{session_id}/events")
async def stream_session_events(
    session_id: str,
    x_family_id: str = Header(..., alias="X-Family-Id"),
    x_agent_token: str = Header(..., alias="X-Agent-Token"),
):
    if x_agent_token != settings.AGENT_INTERNAL_TOKEN:
        raise HTTPException(status_code=401, detail="invalid token")
    if _session_repo is None:
        raise HTTPException(status_code=503, detail="session store not initialised")

    # Verify session belongs to this family before streaming
    session = await _session_repo.get_session(session_id, x_family_id)
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")

    async def generate():
        import json
        for event in session_journal.iter_events(x_family_id, session_id):
            # Exclude debug-only events from API responses
            if event.get("visibility") == "debug":
                continue
            yield json.dumps(event, ensure_ascii=False) + "\n"

    return StreamingResponse(generate(), media_type="application/x-ndjson; charset=utf-8")
