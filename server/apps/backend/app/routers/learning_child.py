"""Child learning endpoints — learning activities for children."""

import contextlib
import json

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from apps.backend.app.auth.deps import get_current_child_user
from apps.backend.app.database import SessionLocal, get_db
from apps.backend.app.errors import AppError, ErrorCode
from apps.backend.app.models.user import User
from apps.backend.app.schemas.learning import (
    AssessStreamRequest,
    AssignmentResponse,
    ChildProgressOverview,
    ProgressResponse,
    SessionCreate,
    SessionResponse,
    TodayLearningResponse,
    TopicResponse,
)
from apps.backend.app.services.learning import (
    assignment_service,
    progress_service,
    session_service,
)
from apps.backend.app.services.notification.dispatcher import (
    notify_learning_submitted_for_review,
)
from packages.db.models.learning.assignment import LearningAssignment
from packages.db.models.learning.progress import LearningProgress
from packages.db.models.learning.session import LearningSession
from packages.db.models.learning.topic import LearningTopic

router = APIRouter(prefix="/child/learning", tags=["learning-child"])


@router.get("/map", response_model=list[ProgressResponse])
def my_knowledge_map(
    db: Session = Depends(get_db),
    child: User = Depends(get_current_child_user),
):
    """Get my knowledge map with mastery levels."""
    return (
        db.query(LearningProgress)
        .filter(LearningProgress.child_id == child.id)
        .all()
    )


@router.get("/assignments", response_model=list[AssignmentResponse])
def my_assignments(
    status: str | None = Query(None),
    db: Session = Depends(get_db),
    child: User = Depends(get_current_child_user),
):
    """Get my learning assignments."""
    return assignment_service.list_assignments(db, child.id, status)


@router.get("/today", response_model=TodayLearningResponse)
def today_learning(
    db: Session = Depends(get_db),
    child: User = Depends(get_current_child_user),
):
    """Today's learning summary — drives the TodayLearningCard on ChildHomePage."""
    # 1. current_topic: first progress with mastery_level=="learning", ORDER BY updated_at DESC
    current_progress = (
        db.query(LearningProgress)
        .filter(
            LearningProgress.child_id == child.id,
            LearningProgress.mastery_level == "learning",
        )
        .order_by(LearningProgress.updated_at.desc())
        .first()
    )
    current_topic = None
    if current_progress:
        current_topic = (
            db.query(LearningTopic)
            .filter(LearningTopic.id == current_progress.topic_id)
            .first()
        )

    # 2. pending_assignment: first with status=="pending", ORDER BY created_at ASC
    pending_assignment_orm = (
        db.query(LearningAssignment)
        .filter(
            LearningAssignment.child_id == child.id,
            LearningAssignment.status == "pending",
        )
        .order_by(LearningAssignment.created_at.asc())
        .first()
    )
    pending_assignment = None
    if pending_assignment_orm:
        a_topic = (
            db.query(LearningTopic)
            .filter(LearningTopic.id == pending_assignment_orm.topic_id)
            .first()
        )
        pending_assignment = AssignmentResponse.model_validate(pending_assignment_orm)
        pending_assignment.topic = a_topic

    # 3. recommended_topic: locked with all hard prereqs met, stable ordering
    recommended_topic = progress_service.find_recommended_topic(db, child.id)

    # 4. study_minutes_today
    study_minutes = progress_service.aggregate_study_minutes(db, child.id)

    return TodayLearningResponse(
        current_topic=current_topic,
        pending_assignment=pending_assignment,
        recommended_topic=recommended_topic,
        study_minutes_today=study_minutes["today_study_minutes"],
    )


@router.get("/topics/{topic_id}", response_model=TopicResponse)
def get_topic_detail(
    topic_id: int,
    db: Session = Depends(get_db),
    child: User = Depends(get_current_child_user),
):
    """Get topic detail — public topic info (no per-child progress embedded)."""
    topic = db.query(LearningTopic).filter(LearningTopic.id == topic_id).first()
    if not topic:
        raise AppError(ErrorCode.LEARNING_TOPIC_NOT_FOUND)
    return topic


@router.post("/sessions", response_model=SessionResponse, status_code=201)
def create_session(
    req: SessionCreate,
    db: Session = Depends(get_db),
    child: User = Depends(get_current_child_user),
):
    """Create a new learning session."""
    return session_service.create_session(db, child.id, req)


@router.get("/sessions/{session_id}", response_model=SessionResponse)
def get_session(
    session_id: int,
    db: Session = Depends(get_db),
    child: User = Depends(get_current_child_user),
):
    """Get a learning session."""
    session = (
        db.query(LearningSession)
        .filter(LearningSession.id == session_id, LearningSession.child_id == child.id)
        .first()
    )
    if not session:
        raise AppError(ErrorCode.LEARNING_SESSION_NOT_FOUND)
    return session


@router.post("/sessions/{session_id}/start-assessment", response_model=ProgressResponse)
def start_assessment(
    session_id: int,
    db: Session = Depends(get_db),
    child: User = Depends(get_current_child_user),
):
    """Start an assessment within a session (learning -> assessing)."""
    return session_service.start_assessment(db, session_id, child.id)


@router.post("/sessions/{session_id}/end", response_model=SessionResponse)
def end_session(
    session_id: int,
    db: Session = Depends(get_db),
    child: User = Depends(get_current_child_user),
):
    """End a learning session."""
    # Verify the session belongs to this child before ending
    session = (
        db.query(LearningSession)
        .filter(LearningSession.id == session_id, LearningSession.child_id == child.id)
        .first()
    )
    if not session:
        raise AppError(ErrorCode.LEARNING_SESSION_NOT_FOUND)
    return session_service.end_session(db, session_id)


@router.post("/assignments/{assignment_id}/submit", response_model=ProgressResponse)
def submit_assignment(
    assignment_id: int,
    db: Session = Depends(get_db),
    child: User = Depends(get_current_child_user),
):
    """Submit an assignment for parent review."""
    progress = assignment_service.submit_for_review(db, assignment_id, child.id)
    # Fire notification — parent should review
    assignment = (
        db.query(LearningAssignment)
        .filter(LearningAssignment.id == assignment_id)
        .first()
    )
    if assignment:
        topic = db.query(LearningTopic).filter(LearningTopic.id == assignment.topic_id).first()
        child_name = child.display_name or child.username or ""
        topic_name = (topic.name_zh or topic.name or "") if topic else ""
        with contextlib.suppress(Exception):
            notify_learning_submitted_for_review(
                db, child.family_id, child_name, topic_name
            )
    return progress


@router.get("/progress", response_model=ChildProgressOverview)
def my_overall_progress(
    db: Session = Depends(get_db),
    child: User = Depends(get_current_child_user),
):
    """Get overall progress overview — aggregated mastery counts + study time."""
    overview = progress_service.get_child_progress_overview(db, child.id)
    study_minutes = progress_service.aggregate_study_minutes(db, child.id)
    return ChildProgressOverview(
        mastered_count=overview["mastered"],
        learning_count=overview["learning"],
        available_count=overview["available"],
        locked_count=overview["locked"],
        review_count=overview["review"],
        assessing_count=overview["assessing"],
        parent_review_count=overview["parent_review"],
        **study_minutes,
    )


@router.post("/sessions/{session_id}/assess/stream")
async def stream_assessment(
    session_id: int,
    http_request: Request,
    body: AssessStreamRequest | None = None,
    db: Session = Depends(get_db),
    child: User = Depends(get_current_child_user),
):
    """Start or continue AI assessment session and return SSE stream.

    Flow:
    1. Validate session + transition to 'assessing' (if initial) or continue (if follow-up)
    2. Build agent trigger body (initial: topic context; follow-up: user_message)
    3. Trigger agent (writes to Redis StreamBridge)
    4. Subscribe to Redis Stream -> SSE to frontend
    """
    from apps.backend.app.services.agent_client import AgentClient
    from apps.backend.app.services.ai_task_service import AITaskService
    from apps.backend.app.services.bridge_consumer import (
        _spawn_lifecycle_consumer,
        consume_task_stream,
        get_shared_bridge,
        trigger_agent_run,
    )
    from apps.backend.app.services.learning.session_service import (
        get_thread_id_for_session,
    )

    # 1. Validate ownership
    session = session_service.get_session(db, session_id, child.id)
    thread_id = get_thread_id_for_session(session_id)
    family_id = child.family_id

    is_follow_up = body is not None and body.user_message is not None

    if not is_follow_up:
        # Initial assessment: transition progress to 'assessing'
        session_service.start_assessment(db, session_id, child.id)
        # Persist thread_id so GET /sessions/{id}/status can return it for reconnect
        session.thread_id = thread_id

    # 2. Build agent trigger body
    topic = db.query(LearningTopic).filter(LearningTopic.id == session.topic_id).first()
    if not topic:
        raise AppError(ErrorCode.LEARNING_TOPIC_NOT_FOUND)

    if is_follow_up:
        agent_content = json.dumps(
            {
                "action": "continue_tutoring",
                "user_message": body.user_message,
                "topic_id": str(topic.id),
                "child_id": str(child.id),
                "session_id": str(session_id),
            },
            ensure_ascii=False,
        )
    else:
        agent_content = json.dumps(
            {
                "action": "start_tutoring",
                "topic_id": str(topic.id),
                "topic_name": topic.name,
                "topic_description": topic.description or "",
                "child_id": str(child.id),
                "child_name": child.display_name or child.username or "",
                "session_type": session.session_type,
                "session_id": str(session_id),
            },
            ensure_ascii=False,
        )

    agent_body = {
        "input": {
            "messages": [{"role": "user", "content": agent_content}],
        },
        "on_disconnect": "continue",
        "metadata": {
            "app": "learning-tutor",
            "session_id": str(session_id),
            "topic_id": str(topic.id),
            "language": child.language or "zh-CN",
        },
    }

    # 3. Create AITask record for lifecycle tracking
    task = AITaskService.create_task(
        family_id=family_id,
        skill_id="learning-tutor",
        session_id=None,
        db=db,
    )
    # Store learning session_id in progress JSON for session-scoped status queries
    task.progress = {"learning_session_id": str(session_id)}
    db.commit()
    task_id = str(task.id)

    # 4. Trigger agent (writes to Redis)
    agent_client = AgentClient(family_id=str(family_id), user_id=str(child.id))
    try:
        result = await trigger_agent_run(
            agent_client=agent_client,
            agent_url=f"/internal/gateway/runs/learning-tutor/{thread_id}",
            json_body=agent_body,
            task_id=task_id,
        )
    except Exception as e:
        _fdb = SessionLocal()
        try:
            AITaskService.fail_task(task_id, f"agent trigger failed: {type(e).__name__}", _fdb)
        finally:
            _fdb.close()
        raise AppError(ErrorCode.AI_SERVICE_UNAVAILABLE, details={"reason": str(e)}) from e

    # 5. Persist run_id on AITask + spawn lifecycle consumer (matches ai_report/finance_coach pattern)
    AITaskService.extract_and_attach_run_id(task_id, result["content_location"], family_id)

    # 6. Subscribe to Redis Stream -> SSE
    shared_bridge = get_shared_bridge()
    _spawn_lifecycle_consumer(
        task_id=task_id,
        family_id=family_id,
        run_id=result["run_id"],
        bridge=shared_bridge,
        thread_id=thread_id,
    )

    last_event_id = http_request.headers.get("Last-Event-ID")
    stream_gen = consume_task_stream(
        task_id=task_id,
        family_id=family_id,
        last_event_id=last_event_id,
        run_id=result["run_id"],
        bridge=shared_bridge,
    )

    return StreamingResponse(
        stream_gen,
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no"},
    )


@router.get("/sessions/{session_id}/status")
async def get_session_status(
    session_id: int,
    db: Session = Depends(get_db),
    child: User = Depends(get_current_child_user),
):
    """Return session run status for frontend reconnection decisions.

    Finds the learning-tutor AITask for this specific session by matching
    the ``learning_session_id`` stored in ``AITask.progress`` JSON.
    The frontend uses this to decide whether to reconnect SSE, reload
    history, or show an interrupted state.
    """
    from packages.db.models.ai_task import AITask
    from packages.db.session import engine

    # Validate session ownership
    session = session_service.get_session(db, session_id, child.id)

    # Find the learning-tutor AITask scoped to THIS session via progress JSON.
    # Filter at DB level using dialect-aware JSON path (was O(n) Python scan).
    session_id_str = str(session_id)
    if engine.dialect.name == "postgresql":
        json_filter = AITask.progress["learning_session_id"].astext == session_id_str
    else:
        from sqlalchemy import func as sa_func

        json_filter = (
            sa_func.json_extract(AITask.progress, "$.learning_session_id")
            == session_id_str
        )

    task = (
        db.query(AITask)
        .filter(
            AITask.family_id == child.family_id,
            AITask.skill_id == "learning-tutor",
            AITask.progress.isnot(None),
            json_filter,
        )
        .order_by(AITask.started_at.desc())
        .first()
    )

    if task is None:
        return {
            "session_id": str(session_id),
            "run_status": "idle",
            "thread_id": session.thread_id,
        }

    # Detect dead-worker: running task with expired lease → treat as interrupted
    from datetime import UTC, datetime

    run_status = task.status
    if (
        run_status == "running"
        and task.lease_expires_at is not None
        and task.lease_expires_at < datetime.now(UTC)
    ):
        run_status = "interrupted"

    return {
        "session_id": str(session_id),
        "run_status": run_status,
        "task_id": str(task.id),
        "thread_id": session.thread_id,
        "last_event_id": task.run_id,
    }


@router.get("/sessions/{session_id}/history")
async def get_session_history(
    session_id: int,
    db: Session = Depends(get_db),
    child: User = Depends(get_current_child_user),
):
    """Load conversation history from DeerFlow checkpointer for reconnection.

    Used by frontend reconnect() when run_status is 'completed' to restore
    the full conversation after a gap or page reload.
    """
    from apps.backend.app.services.agent_client import AgentClient
    from apps.backend.app.services.learning.session_service import (
        get_thread_id_for_session,
    )

    session_service.get_session(db, session_id, child.id)
    thread_id = get_thread_id_for_session(session_id)

    agent_client = AgentClient(
        family_id=str(child.family_id),
        user_id=str(child.id),
    )
    resp = await agent_client.get(f"/internal/gateway/threads/{thread_id}/state")
    messages = resp.json().get("messages", [])

    return {
        "session_id": str(session_id),
        "thread_id": thread_id,
        "messages": messages,
    }
