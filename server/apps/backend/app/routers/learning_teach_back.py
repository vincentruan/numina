"""Teach-back (child teaches AI) endpoints — Issue #216.

Split out of ``learning_child.py`` so the shared agent-stream plumbing and this
route stay out of a module that had grown past 1000 lines.
"""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from apps.backend.app.auth.deps import get_current_child_user
from apps.backend.app.database import get_db
from apps.backend.app.models.user import User
from apps.backend.app.schemas.learning import TeachBackStreamRequest
from apps.backend.app.services.learning import teach_back_service
from apps.backend.app.services.learning.agent_stream import stream_learning_agent_sse
from apps.backend.app.services.learning.session_service import (
    get_thread_id_for_session,
)

router = APIRouter(prefix="/child/learning", tags=["learning-child"])


@router.post("/teach-back/stream")
async def stream_teach_back(
    http_request: Request,
    body: TeachBackStreamRequest | None = None,
    db: Session = Depends(get_db),
    child: User = Depends(get_current_child_user),
) -> StreamingResponse:
    """Start or continue a teach-back session where the child teaches the AI.

    First call (topic_id provided): starts teach-back on a mastered pilot topic.
    Follow-up calls (session_id + child_answer): continues the dialogue.
    """
    is_follow_up = body is not None and body.child_answer is not None
    topic_id = body.topic_id if body and body.topic_id else None
    session_id = body.session_id if body and body.session_id else None

    session, topic, confusions = teach_back_service.validate_teach_back_request(
        db=db,
        child=child,
        session_id=session_id,
        topic_id=topic_id,
        is_follow_up=is_follow_up,
    )

    agent_body = teach_back_service.build_teach_back_payload(
        session=session,
        topic=topic,
        child=child,
        confusions=confusions,
        child_answer=body.child_answer if body else None,
        is_follow_up=is_follow_up,
    )

    # Emit session_id before the first tool_result so the composable can capture
    # it without waiting for a turn; the stream helper gives it a stable id so a
    # Last-Event-ID reconnect can replay it.
    return await stream_learning_agent_sse(
        http_request=http_request,
        db=db,
        thread_id=get_thread_id_for_session(session.id),
        agent_body=agent_body,
        family_id=child.family_id,
        child=child,
        learning_session_id=session.id,
        prepend_event=(
            "custom",
            {"type": "session_created", "session_id": str(session.id)},
        ),
    )
