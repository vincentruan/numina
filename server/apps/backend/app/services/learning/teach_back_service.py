"""Teach-back service — post-mastery child-teaches-AI session logic.

Child who has mastered a topic explains it to an AI student persona.
Preset confusions (misconceptions) drive the dialogue.
"""

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.backend.app.errors import AppError, ErrorCode
from apps.backend.app.models.user import User
from packages.db.models.learning.confusion import TopicConfusion
from packages.db.models.learning.progress import LearningProgress
from packages.db.models.learning.session import LearningSession
from packages.db.models.learning.topic import LearningTopic

# Pilot topic keys — teach-back only enabled for these.
# TODO(issue-216): move to config / feature flag when expanding beyond pilot.
_PILOT_TOPIC_KEYS = frozenset({
    "mt_9KmVWCuh5_",  # Understanding fractions (age 10+)
    "mt_ndGqFPWyen",  # Fractions of a whole
    "mt_FP-mjXaq3B",  # Equivalent fractions (age 8+)
})


def get_approved_confusions(db: Session, topic_id: int, age_group: str = "mid") -> list[TopicConfusion]:
    """Return approved confusions for a topic, ordered by sequence."""
    rows = db.execute(
        select(TopicConfusion)
        .where(
            TopicConfusion.topic_id == topic_id,
            TopicConfusion.age_group == age_group,
            TopicConfusion.review_status == "approved",
        )
        .order_by(TopicConfusion.sequence)
    ).scalars().all()
    return list(rows)


def create_teach_back_session(
    db: Session,
    child: User,
    topic: LearningTopic,
) -> LearningSession:
    """Create a new teach-back LearningSession.

    Bypasses the general session_service.create_session (which auto-creates
    assignments and does available→learning transitions we don't want).
    """
    session = LearningSession(
        child_id=child.id,
        topic_id=topic.id,
        session_type="teach_back",
    )
    db.add(session)
    db.flush()
    # thread_id is set to session id for agent routing (same pattern as smart tutor)
    session.thread_id = str(session.id)
    db.commit()
    db.refresh(session)
    return session


def validate_teach_back_request(
    db: Session,
    child: User,
    session_id: int | None = None,
    topic_id: int | None = None,
    is_follow_up: bool = False,
) -> tuple[LearningSession, LearningTopic, list[TopicConfusion]]:
    """Validate teach-back request and return session, topic, confusions.

    For initial call: topic_id required, creates a new session.
    For follow-up: session_id required, loads existing session.

    Raises:
        AppError: If validation fails (not mastered, not pilot topic, no confusions).
    """
    confusions: list[TopicConfusion] = []
    if is_follow_up:
        if not session_id:
            raise AppError(
                ErrorCode.VALIDATION_ERROR,
                details={"field": "session_id", "message": "session_id required for follow-up"},
            )
        session = db.get(LearningSession, session_id)
        if not session or session.child_id != child.id:
            raise AppError(ErrorCode.LEARNING_SESSION_NOT_FOUND)
        if session.session_type != "teach_back":
            raise AppError(
                ErrorCode.VALIDATION_ERROR,
                details={"field": "session_id", "message": "not a teach-back session"},
            )
        topic = db.get(LearningTopic, session.topic_id)
        if not topic:
            raise AppError(ErrorCode.LEARNING_TOPIC_NOT_FOUND)
    else:
        # Initial call — topic_id required
        if not topic_id:
            raise AppError(
                ErrorCode.VALIDATION_ERROR,
                details={"field": "topic_id", "message": "topic_id required to start teach-back"},
            )
        topic = db.get(LearningTopic, topic_id)
        if not topic:
            raise AppError(ErrorCode.LEARNING_TOPIC_NOT_FOUND)

        # Check pilot scope
        if topic.topic_key not in _PILOT_TOPIC_KEYS:
            raise AppError(
                ErrorCode.VALIDATION_ERROR,
                details={"field": "topic_id", "message": "topic not in teach-back pilot"},
            )

        # Check mastery
        progress = db.execute(
            select(LearningProgress).where(
                LearningProgress.child_id == child.id,
                LearningProgress.topic_id == topic.id,
            )
        ).scalar_one_or_none()
        if not progress or progress.mastery_level != "mastered":
            raise AppError(
                ErrorCode.VALIDATION_ERROR,
                details={"field": "topic_id", "message": "topic not yet mastered"},
            )

        # Check approved confusions BEFORE creating the session (#50: avoid orphan rows)
        confusions = get_approved_confusions(db, topic.id)
        if not confusions:
            raise AppError(
                ErrorCode.LEARNING_TOPIC_NOT_FOUND,
                details={"detail": "no approved confusions for this topic"},
            )

        # Create session only after all validation passes
        session = create_teach_back_session(db, child, topic)

    # Load approved confusions (for follow-up path)
    if is_follow_up:
        confusions = get_approved_confusions(db, topic.id)
        if not confusions:
            raise AppError(
                ErrorCode.LEARNING_TOPIC_NOT_FOUND,
                details={"detail": "no approved confusions for this topic"},
            )

    return session, topic, confusions


def build_teach_back_payload(
    session: LearningSession,
    topic: LearningTopic,
    child: User,
    confusions: list[TopicConfusion],
    child_answer: str | None = None,
    is_follow_up: bool = False,
) -> dict:
    """Build the agent trigger payload for teach-back.

    Uses the existing ``learning-smart-tutor`` app with a different action.
    """
    confusion_data = [
        {
            "id": c.id,
            "sequence": c.sequence,
            "text": c.confusion_text,
            "text_zh": c.confusion_text_zh,
            "rubric": c.rubric,
            "expected_expression": c.expected_expression,
        }
        for c in confusions
    ]

    if is_follow_up:
        agent_content = json.dumps(
            {
                "action": "answer_confusion",
                "child_answer": child_answer,
                "topic_id": str(topic.id),
                "child_id": str(child.id),
                "session_id": str(session.id),
                "confusions": confusion_data,
            },
            ensure_ascii=False,
        )
    else:
        agent_content = json.dumps(
            {
                "action": "start_teach_back",
                "topic_id": str(topic.id),
                "topic_name": topic.name,
                "topic_name_zh": topic.name_zh,
                "subject": topic.subject,
                "child_id": str(child.id),
                "child_name": child.display_name or child.username or "",
                "session_id": str(session.id),
                "confusions": confusion_data,
            },
            ensure_ascii=False,
        )

    return {
        "family_id": str(child.family_id),
        "user_id": str(child.id),
        "input": {
            "messages": [{"role": "user", "content": agent_content}],
        },
        "on_disconnect": "continue",
        "metadata": {
            "app": "learning-smart-tutor",
            "session_id": str(session.id),
            "topic_id": str(topic.id),
            "language": child.language or "zh-CN",
        },
    }



# ---------------------------------------------------------------------------
# Turn recording (extracted from the MCP handler — see mcp_session.py)
# ---------------------------------------------------------------------------

#: Phase machine for teach-back. Lowercase keys matching the wire format, kept
#: separate from ``VALID_PHASE_TRANSITIONS`` (the smart-tutor machine, which uses
#: uppercase keys).
TEACH_BACK_PHASES: dict[str, set[str]] = {
    "present_confusion": {"evaluate_explanation", "end"},
    "evaluate_explanation": {"present_confusion", "resolve", "end"},
    "resolve": {"end"},
    "end": set(),
}

#: Verdicts the model may report for a single turn.
VALID_VERDICTS = frozenset({"hit", "miss"})

#: Discriminator stored on each persisted turn record.
TEACH_BACK_TURN_TYPE = "teach_back_turn"


def record_teach_back_turn(
    db: Session,
    *,
    family_id: int,
    caller_user_id: int,
    session_id: int,
    confusion_id: int,
    child_explanation: str,
    verdict: str,
    phase: str,
    next_phase: str | None,
    extracted_expression: str | None = None,
    reasoning_summary: str = "",
) -> dict:
    """Record one teach-back turn, applying the success path on the final resolve.

    Owns the whole post-argument-parsing path: verdict/phase validation, the
    caller-bound session lookup, the confusion scope check, the deterministic
    SymPy grade, turn persistence, the all-confusions-hit gate, the idempotent
    success path, and the parent notification.

    Returns a JSON-serializable dict. On a validation or lookup failure it carries
    an ``error`` key instead of ``ok``.
    """
    from datetime import UTC, datetime

    from apps.backend.app.services.learning import progress_service
    from apps.backend.app.services.learning.teach_back_grading import (
        extract_expression,
        grade_expression,
    )
    from apps.backend.app.services.notification.dispatcher import (
        notify_teach_back_completed,
    )

    if verdict not in VALID_VERDICTS:
        return {
            "error": "invalid_verdict",
            "detail": f"verdict must be 'hit' or 'miss', got {verdict!r}",
            "allowed_verdicts": sorted(VALID_VERDICTS),
        }

    if phase not in TEACH_BACK_PHASES:
        return {
            "error": "invalid_phase",
            "detail": f"Unknown teach-back phase: {phase}",
            "allowed_phases": list(TEACH_BACK_PHASES),
        }

    if next_phase and next_phase not in TEACH_BACK_PHASES[phase]:
        return {
            "error": "invalid_phase_transition",
            "detail": f"Transition {phase} -> {next_phase} not allowed",
            "allowed_next_phases": sorted(TEACH_BACK_PHASES[phase]),
        }

    # Caller-bound, family-scoped, teach-back-only session lookup.
    session = (
        db.query(LearningSession)
        .join(User, LearningSession.child_id == User.id)
        .filter(
            LearningSession.id == session_id,
            User.family_id == family_id,
            LearningSession.child_id == caller_user_id,
            LearningSession.session_type == "teach_back",
        )
        .first()
    )
    if not session:
        return {"error": "session_not_found"}

    # The cited confusion must belong to this session's topic.
    confusion = (
        db.query(TopicConfusion)
        .filter(
            TopicConfusion.id == confusion_id,
            TopicConfusion.topic_id == session.topic_id,
            TopicConfusion.review_status == "approved",
        )
        .first()
    )
    if not confusion:
        return {
            "error": "confusion_not_found",
            "detail": f"confusion_id {confusion_id} not in topic {session.topic_id}",
        }

    # Deterministic SymPy track: the backend computes the expression verdict and
    # overwrites anything the model claimed, so a wrong expression cannot pass.
    if extracted_expression is None:
        extracted_expression = extract_expression(child_explanation)
    computed_verdict = None
    if confusion.expected_expression and extracted_expression:
        computed_verdict = grade_expression(
            confusion.expected_expression, extracted_expression
        )
    expression_verdict = (
        str(computed_verdict).lower() if computed_verdict is not None else None
    )

    existing_steps = _load_turns(session)
    existing_steps.append(
        {
            "type": TEACH_BACK_TURN_TYPE,
            "confusion_id": confusion_id,
            "child_explanation": child_explanation,
            "verdict": verdict,
            "extracted_expression": extracted_expression,
            "expression_verdict": expression_verdict,
            "reasoning_summary": reasoning_summary,
            "phase": phase,
            "next_phase": next_phase,
        }
    )
    session.progress_json = json.dumps(existing_steps, ensure_ascii=False)

    # "All resolved" is expressed by the distinct hit count alone: a miss early in
    # the dialogue must not permanently block a later success.
    unique_confusions = len({
        s.get("confusion_id")
        for s in existing_steps
        if s.get("type") == TEACH_BACK_TURN_TYPE and s.get("verdict") == "hit"
    })
    total_confusions = (
        db.query(TopicConfusion)
        .filter(
            TopicConfusion.topic_id == session.topic_id,
            TopicConfusion.review_status == "approved",
            TopicConfusion.age_group == "mid",
        )
        .count()
    )
    all_confusions_hit = (
        total_confusions > 0 and unique_confusions >= total_confusions
    )

    teach_back_rewards: dict | None = None
    teach_back_success = False
    if (
        all_confusions_hit
        and next_phase == "resolve"
        and session.ended_at is None  # idempotency: a replay must not re-award
    ):
        progress = (
            db.query(LearningProgress)
            .filter(
                LearningProgress.child_id == session.child_id,
                LearningProgress.topic_id == session.topic_id,
            )
            .first()
        )
        if progress:
            progress_service.apply_teach_back_success(
                db, progress, session_id=session_id
            )
            session.ended_at = datetime.now(UTC)
            teach_back_rewards = progress_service.apply_teach_back_rewards(
                db,
                child_id=session.child_id,
                family_id=family_id,
                topic_id=session.topic_id,
                session_id=session_id,
            )
            db.commit()
            _notify_parent(db, family_id, session, notify_teach_back_completed)
        teach_back_success = True

    if next_phase == "end":
        session.ended_at = datetime.now(UTC)

    db.commit()

    return {
        "ok": True,
        "session_id": str(session_id),
        "confusion_id": confusion_id,
        "verdict": verdict,
        "expression_verdict": expression_verdict,
        "phase": phase,
        "next_phase": next_phase,
        "total_turns": sum(
            1 for s in existing_steps if s.get("type") == TEACH_BACK_TURN_TYPE
        ),
        "all_confusions_hit": all_confusions_hit,
        "teach_back_success": teach_back_success,
        "teach_back_rewards": teach_back_rewards,
    }


def _load_turns(session: LearningSession) -> list[dict]:
    """Parse ``progress_json`` into a list of turn dicts, tolerating bad data."""
    raw = session.progress_json
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return []
    return parsed if isinstance(parsed, list) else []


def _notify_parent(db: Session, family_id: int, session: LearningSession, notifier) -> None:
    """Notify the parent that the child completed a teach-back (best-effort)."""
    from packages.core.logging import get_logger

    logger = get_logger(__name__)
    try:
        topic = db.get(LearningTopic, session.topic_id)
        if not topic:
            return
        notifier(
            db=db,
            family_id=family_id,
            child_id=session.child_id,
            topic_name=topic.name_zh or topic.name or "",
        )
    except Exception:
        logger.warning("Teach-back notification failed", exc_info=True)
