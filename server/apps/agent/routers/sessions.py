"""Sessions API — list sessions and stream session events."""

import logging

from fastapi import APIRouter, Header, HTTPException, Query
from fastapi.responses import StreamingResponse

from apps.agent.app.config import settings
from apps.agent.services.session_journal import session_journal
from apps.agent.services.session_store import AiSessionRepository

router = APIRouter(prefix="/sessions", tags=["sessions"])
logger = logging.getLogger(__name__)


def _verify_token(x_agent_token: str) -> None:
    if x_agent_token != settings.AGENT_INTERNAL_TOKEN:
        raise HTTPException(status_code=401, detail="invalid token")


@router.get("")
async def list_sessions(
    x_family_id: str = Header(..., alias="X-Family-Id"),
    x_agent_token: str = Header(..., alias="X-Agent-Token"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    _verify_token(x_agent_token)
    repo = AiSessionRepository(x_family_id)
    sessions, total = await repo.list_sessions(x_family_id, limit=limit, offset=offset)
    return {"sessions": sessions, "total": total}


@router.get("/{session_id}/events")
async def stream_session_events(
    session_id: str,
    x_family_id: str = Header(..., alias="X-Family-Id"),
    x_agent_token: str = Header(..., alias="X-Agent-Token"),
):
    _verify_token(x_agent_token)
    repo = AiSessionRepository(x_family_id)
    session = await repo.get_session(session_id, x_family_id)
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")

    async def generate():
        import json
        for event in session_journal.iter_events(x_family_id, session_id):
            if event.get("visibility") == "debug":
                continue
            yield json.dumps(event, ensure_ascii=False) + "\n"

    return StreamingResponse(generate(), media_type="application/x-ndjson; charset=utf-8")
