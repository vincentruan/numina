"""Practice system API endpoints."""

import json

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, or_
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from apps.backend.app.auth.deps import get_current_user_or_child, require_owner
from apps.backend.app.database import get_db
from apps.backend.app.errors import AppError, ErrorCode
from apps.backend.app.models.user import User
from apps.backend.app.schemas.practice import (
    BatchReviewRequest,
    CoverageResponse,
    PracticeAttemptResponse,
    PracticeQuestionWithAnswer,
    PracticeResultResponse,
    PracticeSessionResponse,
    QuestionPublicResponse,
    RecommendResponse,
    ReviewQuestionRequest,
    SessionCreateRequest,
    SessionDetailResponse,
    SessionListItem,
    SubmitAnswerRequest,
    WeakTopicResponse,
)
from apps.backend.app.services.learning.adaptive_service import (
    BayesianKnowledgeTracingEstimator,
    get_ability_dimensions,
    get_progress_trend,
    select_questions,
)
from apps.backend.app.services.learning.practice_service import (
    create_session,
    finish_session,
    get_session,
    get_session_detail,
    get_weak_topics,
    list_sessions,
    submit_answer,
)
from apps.backend.app.services.learning.progress_service import (
    get_or_create_progress,
)
from apps.backend.app.services.learning.question_service import (
    get_coverage_stats,
    list_questions,
    review_question,
)
from packages.core.logging import get_logger
from packages.db.models.learning.practice import PracticeSession
from packages.db.models.learning.question import Question as QuestionModel
from packages.db.models.learning.topic import LearningTopic

logger = get_logger(__name__)

router = APIRouter(prefix="/practice", tags=["practice"])


class BatchQuestionsRequest(BaseModel):
    question_ids: list[int] = Field(..., max_length=100)


@router.get("/questions", response_model=list[QuestionPublicResponse])
def list_practice_questions(
    topic_id: int | None = None,
    difficulty: int | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user_or_child),
):
    """List approved questions (without answers), optionally filtered by topic/difficulty."""
    questions = list_questions(
        db=db, topic_id=topic_id, difficulty=difficulty, limit=limit
    )
    return questions


@router.put("/questions/{question_id}/review", response_model=QuestionPublicResponse)
def review_question_endpoint(
    question_id: int,
    req: ReviewQuestionRequest,
    db: Session = Depends(get_db),
    _user: User = Depends(require_owner),
):
    """Review a pending question (owner only) — approve or reject.

    Template-generated questions are auto-approved; LLM/external-source
    questions start as 'pending' and require human review before entering
    the child-facing question bank.
    """
    question = review_question(db, question_id=question_id, decision=req.decision)
    return QuestionPublicResponse.model_validate(question)


@router.post("/questions/batch")
def batch_get_questions(
    req: BatchQuestionsRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_or_child),
):
    """Fetch specific questions by ID list.

    Returns questions with answers ONLY if the user has an active (non-ended)
    session containing those question IDs. Otherwise returns public view (no answers).
    """
    questions = (
        db.query(QuestionModel)
        .filter(
            QuestionModel.id.in_(req.question_ids),
            QuestionModel.review_status == "approved",
        )
        .all()
    )

    # Check if user has an active session containing these question IDs
    requested_ids = set(req.question_ids)
    has_session_context = False

    active_sessions = (
        db.query(PracticeSession)
        .filter(
            PracticeSession.child_id == user.id,
            PracticeSession.ended_at.is_(None),
        )
        .all()
    )
    for s in active_sessions:
        session_qids = set(json.loads(s.question_ids_json) if s.question_ids_json else [])
        if requested_ids & session_qids:
            has_session_context = True
            break

    if has_session_context:
        return [
            PracticeQuestionWithAnswer.model_validate(q) for q in questions
        ]
    else:
        return [QuestionPublicResponse.model_validate(q) for q in questions]


@router.post("/sessions", response_model=PracticeSessionResponse)
def create_practice_session(
    req: SessionCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_or_child),
):
    """Create a new practice session with adaptive question selection."""
    topic = db.query(LearningTopic).filter_by(id=req.topic_id).first()
    if not topic:
        raise AppError(ErrorCode.PRACTICE_TOPIC_NOT_FOUND)

    # Get child's mastery level for adaptive selection
    progress = get_or_create_progress(db, user.id, req.topic_id)

    # Block locked topics
    if progress.mastery_level == "locked":
        raise AppError(ErrorCode.PRACTICE_TOPIC_LOCKED)

    # Select questions — use BKT estimator for adaptive difficulty
    # (BKT auto-falls back to RuleBased when < 5 attempts)
    questions = select_questions(
        db=db,
        topic_id=req.topic_id,
        mastery_level=progress.mastery_level,
        count=req.count,
        exclude_question_ids=[],
        exclude_recent_days=7,
        child_id=user.id,
        estimator=BayesianKnowledgeTracingEstimator(),
        session_mode=req.session_mode,
    )

    if not questions:
        raise AppError(ErrorCode.PRACTICE_NO_QUESTIONS_AVAILABLE)

    session = create_session(
        db=db,
        child_id=user.id,
        topic_id=req.topic_id,
        session_mode=req.session_mode,
        question_ids=[q.id for q in questions],
    )
    return session


@router.post("/sessions/{session_id}/answer", response_model=PracticeAttemptResponse)
def submit_practice_answer(
    session_id: int,
    req: SubmitAnswerRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_or_child),
):
    """Submit an answer for a question in a practice session."""
    session = get_session(db, session_id)
    if not session or session.child_id != user.id:
        raise AppError(ErrorCode.PRACTICE_SESSION_NOT_FOUND)
    if session.ended_at is not None:
        raise AppError(ErrorCode.PRACTICE_SESSION_ALREADY_ENDED)

    attempt = submit_answer(
        db=db,
        session_id=session_id,
        question_id=req.question_id,
        child_id=user.id,
        topic_id=session.topic_id,
        user_answer=req.user_answer,
        time_spent_seconds=req.time_spent_seconds,
        _session=session,
    )
    return attempt


@router.post("/sessions/{session_id}/finish", response_model=PracticeResultResponse)
def finish_practice_session(
    session_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_or_child),
):
    """Finish a practice session and calculate final score."""
    # Verify ownership first
    session = get_session(db, session_id)
    if not session or session.child_id != user.id:
        raise AppError(ErrorCode.PRACTICE_SESSION_NOT_FOUND)

    result = finish_session(db=db, session_id=session_id, child_id=user.id)

    # Try to update progress state machine
    mastery_changed = False
    new_mastery_level = None
    try:
        from apps.backend.app.services.learning.practice_progress_integration import (
            update_progress_from_session,
        )

        progress_result = update_progress_from_session(
            db=db, session_id=session_id, child_id=user.id
        )
        mastery_changed = progress_result["mastery_changed"]
        new_mastery_level = progress_result["new_mastery_level"]
    except Exception:
        logger.warning(
            "Progress integration failed for session %s", session_id, exc_info=True
        )

    # Award XP and coins if mastery changed
    xp_earned = 0
    coins_earned = 0
    if mastery_changed:
        # Award XP (10 XP for mastery advancement)
        try:
            from apps.backend.app.services.learning.stats_service import award_xp

            xp_result = award_xp(db, child_id=user.id, family_id=user.family_id, xp_amount=10)
            xp_earned = xp_result["xp_awarded"]
        except Exception:
            logger.warning("XP award failed for session %s", session_id, exc_info=True)

        # Award coins (10 stars for mastery advancement)
        try:
            from packages.db.models.child_economy.coin_transaction import (
                CoinTransaction,
            )

            topic = db.query(LearningTopic).filter_by(id=session.topic_id).first()
            topic_label = (topic.name_zh or topic.name or "learning") if topic else "learning"
            txn = CoinTransaction(
                family_id=user.family_id,
                child_user_id=user.id,
                amount=10,
                transaction_type="learning_earn",
                narrative=f"完成练习掌握知识点：{topic_label}",
                narrative_emoji="🌟",
            )
            db.add(txn)
            db.flush()
            coins_earned = 10
        except Exception:
            logger.warning("Coin award failed for session %s", session_id, exc_info=True)

    return PracticeResultResponse(
        session_id=session_id,
        total_score=result["total_score"],
        correct_count=result["correct_count"],
        total_count=result["total_count"],
        xp_earned=xp_earned,
        coins_earned=coins_earned,
        mastery_changed=mastery_changed,
        new_mastery_level=new_mastery_level,
    )


# --- Phase 5: Weak points + history + recommend ---


@router.get("/weak-topics", response_model=list[WeakTopicResponse])
def get_weak_topics_endpoint(
    limit: int = 10,
    min_attempts: int = Query(default=3, ge=1),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_or_child),
):
    """Get topics where the child has low accuracy, sorted weakest first."""
    return get_weak_topics(db, child_id=user.id, limit=limit, min_attempts=min_attempts)


@router.get("/sessions", response_model=list[SessionListItem])
def list_practice_sessions(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = 0,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_or_child),
):
    """List practice sessions for the current child."""
    sessions = list_sessions(db, child_id=user.id, limit=limit, offset=offset)

    # Batch-load topics to avoid N+1
    topic_ids = {s.topic_id for s in sessions}
    topics_by_id = {}
    if topic_ids:
        for t in db.query(LearningTopic).filter(LearningTopic.id.in_(topic_ids)).all():
            topics_by_id[t.id] = t

    results = []
    for s in sessions:
        topic = topics_by_id.get(s.topic_id)
        question_ids = json.loads(s.question_ids_json) if s.question_ids_json else []
        results.append(
            SessionListItem(
                id=s.id,
                topic_id=s.topic_id,
                topic_name=topic.name if topic else "",
                topic_name_zh=topic.name_zh if topic else None,
                session_mode=s.session_mode,
                total_score=s.total_score,
                completed_count=s.completed_count,
                total_count=len(question_ids),
                started_at=s.started_at,
                ended_at=s.ended_at,
            )
        )
    return results


@router.get("/sessions/{session_id}", response_model=SessionDetailResponse)
def get_practice_session_detail(
    session_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_or_child),
):
    """Get full practice session detail with question-level attempts."""
    detail = get_session_detail(db, session_id=session_id, child_id=user.id)
    if not detail:
        raise AppError(ErrorCode.PRACTICE_SESSION_NOT_FOUND)
    return SessionDetailResponse(**detail)


@router.get("/recommend", response_model=list[RecommendResponse])
def get_practice_recommendations(
    topic_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_or_child),
):
    """Recommend topics for practice — weak prerequisites or weak topics.

    If topic_id is provided, checks for weak prerequisites of that topic.
    Otherwise, returns the child's overall weakest topics.
    """
    if topic_id:
        from apps.backend.app.services.learning.adaptive_service import (
            find_weak_prerequisites,
        )

        weak_prereqs = find_weak_prerequisites(db, topic_id=topic_id, child_id=user.id)
        return [
            RecommendResponse(
                topic_id=r["topic_id"],
                topic_name=r["topic_name"],
                topic_name_zh=r["topic_name_zh"],
                mastery_level=r["mastery_level"],
                accuracy=r["accuracy"],
                is_prerequisite=True,
                prerequisite_of_topic_id=topic_id,
            )
            for r in weak_prereqs
        ]
    else:
        weak = get_weak_topics(db, child_id=user.id, limit=5, min_attempts=1)
        return [
            RecommendResponse(
                topic_id=r["topic_id"],
                topic_name=r["topic_name"],
                topic_name_zh=r["topic_name_zh"],
                mastery_level=r["mastery_level"],
                accuracy=r["accuracy"],
                is_prerequisite=False,
                prerequisite_of_topic_id=None,
            )
            for r in weak
        ]


@router.get("/coverage", response_model=CoverageResponse)
def get_practice_coverage(
    _user: User = Depends(get_current_user_or_child),
    db: Session = Depends(get_db),
):
    """Get knowledge point coverage statistics for the question bank."""
    stats = get_coverage_stats(db)
    return CoverageResponse(**stats)


@router.get("/coverage/summary")
def get_coverage_summary(
    user: User = Depends(get_current_user_or_child),
    db: Session = Depends(get_db),
):
    """Subject-level coverage aggregation (P7a-min)."""
    from apps.backend.app.services.learning.coverage_service import compute_subject_coverage
    from packages.db.models.learning.topic import LearningTopic

    subjects = (
        db.query(LearningTopic.subject)
        .filter(
            LearningTopic.subject.isnot(None),
            LearningTopic.deprecated == False,  # noqa: E712
        )
        .distinct()
        .all()
    )
    subject_list = [s[0] for s in subjects if s[0]]

    results = []
    total_topics = 0
    covered_topics = 0
    for subj in subject_list:
        s = compute_subject_coverage(db, subj, family_id=user.family_id)
        results.append(s)
        total_topics += s["total_topics"]
        covered_topics += s["covered_topics"]

    return {
        "subjects": results,
        "total_topics": total_topics,
        "covered_topics": covered_topics,
        "overall_rate": covered_topics / total_topics if total_topics > 0 else 0.0,
    }


@router.get("/coverage/detailed")
def get_coverage_detailed(
    subject: str | None = None,
    limit: int = 100,
    offset: int = 0,
    user: User = Depends(get_current_user_or_child),
    db: Session = Depends(get_db),
):
    """Per-topic coverage scores (P7a-min)."""
    from apps.backend.app.services.learning.coverage_service import compute_topic_coverage
    from packages.db.models.learning.topic import LearningTopic

    query = db.query(LearningTopic).filter(LearningTopic.deprecated == False)  # noqa: E712
    if subject:
        query = query.filter(LearningTopic.subject == subject)

    topics = query.offset(offset).limit(limit).all()
    details = []
    for t in topics:
        cov = compute_topic_coverage(db, t.id, family_id=user.family_id)
        details.append({
            "topic_id": t.id,
            "topic_key": t.topic_key,
            "name": t.name,
            "subject": t.subject,
            "domain": t.domain,
            "existence": cov["existence"],
            "prerequisite_value": cov["prerequisite_value"],
            "coverage_score": cov["coverage_score"],
            "approved_question_count": cov["approved_question_count"],
        })

    return {"topics": details, "total": len(details)}


@router.get("/coverage/gap-report")
def get_coverage_gap_report(
    subject: str | None = None,
    threshold: float = 0.5,
    limit: int = 100,
    user: User = Depends(get_current_user_or_child),
    db: Session = Depends(get_db),
):
    """Topics below coverage threshold, sorted by prerequisite value (P7a-min)."""
    from apps.backend.app.services.learning.coverage_service import get_gap_report

    gaps = get_gap_report(db, subject=subject, threshold=threshold, limit=limit, family_id=user.family_id)
    return {
        "gaps": gaps,
        "threshold": threshold,
        "total_gaps": len(gaps),
    }


@router.get("/ability-dimensions")
def get_child_ability_dimensions(
    user: User = Depends(get_current_user_or_child),
    db: Session = Depends(get_db),
):
    """Get per-domain accuracy breakdown for the current child."""
    return get_ability_dimensions(db, child_id=user.id)


@router.get("/progress-trend")
def get_child_progress_trend(
    topic_id: int,
    user: User = Depends(get_current_user_or_child),
    db: Session = Depends(get_db),
):
    """Get chronological attempt history for a child+topic."""
    return get_progress_trend(db, child_id=user.id, topic_id=topic_id)


# --- P7b: batch review + grading explanation endpoints ---


@router.get("/questions/review-queue")
def get_review_queue(
    risk: str | None = None,
    limit: int = 50,
    user: User = Depends(require_owner),  # parent-only moderation
    db: Session = Depends(get_db),
):
    """List questions pending review, filtered and ordered by risk level.

    Family-scoped: only questions from the caller's family (or unscoped
    template-seeded questions) are visible.
    """
    from packages.db.models.learning.topic import LearningTopic

    query = (
        db.query(QuestionModel)
        .filter(QuestionModel.review_status == "pending")
        .filter(
            or_(QuestionModel.family_id == user.family_id, QuestionModel.family_id.is_(None))
        )
    )
    if risk:
        query = query.filter(QuestionModel.risk == risk)
    questions = query.order_by(
        case(
            (QuestionModel.risk == "high", 0),
            (QuestionModel.risk == "medium", 1),
            (QuestionModel.risk == "low", 2),
            else_=3,
        ).asc()
    ).limit(limit).all()
    items = []
    for q in questions:
        topic = db.get(LearningTopic, q.topic_id) if q.topic_id else None
        items.append({
            "question_id": q.id,
            "topic_key": topic.topic_key if topic else None,
            "question_type": q.question_type,
            "stem": q.stem,
            "answer_json": json.loads(q.answer_json),
            "source": q.source,
            "review_status": q.review_status,
            "risk": q.risk,
            "grading_explanation": q.grading_explanation,
        })
    return {
        "questions": items,
        "total": len(items),
    }


@router.post("/questions/batch-review")
def batch_review_questions(
    body: BatchReviewRequest,
    user: User = Depends(require_owner),  # parent-only moderation
    db: Session = Depends(get_db),
):
    """Batch approve, reject, or suspend questions. Family-scoped."""
    new_status = {"approve": "approved", "reject": "rejected", "suspend": "suspended"}[body.decision]
    processed = 0
    for qid in body.question_ids:
        q = db.get(QuestionModel, qid)
        if (
            q
            and q.review_status == "pending"
            and (q.family_id is None or q.family_id == user.family_id)
        ):
            q.review_status = new_status
            if body.notes:
                q.review_notes = body.notes
            processed += 1
    db.commit()
    approved = processed if body.decision == "approve" else 0
    rejected = processed if body.decision == "reject" else 0
    suspended = processed if body.decision == "suspend" else 0
    return {
        "processed": processed, "approved": approved,
        "rejected": rejected, "suspended": suspended,
    }


@router.get("/questions/{question_id}/grading-explanation")
def get_grading_explanation(
    question_id: int,
    user: User = Depends(get_current_user_or_child),
    db: Session = Depends(get_db),
):
    """Return AI grading explanation for a question."""
    from apps.backend.app.errors import AppError, ErrorCode

    q = db.get(QuestionModel, question_id)
    if q is None:
        raise AppError(ErrorCode.NOT_FOUND, details="Question not found")
    if q.family_id is not None and q.family_id != user.family_id:
        raise AppError(ErrorCode.NOT_FOUND, details="Question not found")  # family-scoped NOT_FOUND
    if not q.grading_explanation_json:
        raise AppError(ErrorCode.NOT_FOUND, details="No grading explanation available")
    return q.grading_explanation
