"""Global learning knowledge graph endpoints (no auth required).

These endpoints expose the shared, read-only knowledge graph (topics, subjects,
clusters) that is the same for all families.  No family-specific data is served
here, so authentication is intentionally omitted — the data is equivalent to a
public curriculum reference.  All write endpoints and any endpoint that touches
family-scoped progress live behind ``require_adult`` / ``get_current_child_user``
in ``learning_family.py`` and ``learning_child.py`` respectively.
"""

import json

import httpx
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from apps.backend.app.auth.deps import get_current_user_or_child, require_adult
from apps.backend.app.database import get_db
from apps.backend.app.errors import AppError, ErrorCode
from apps.backend.app.models.user import User
from apps.backend.app.schemas.learning import (
    ClusterResponse,
    SubjectSummary,
    TopicGraphResponse,
    TopicResponse,
)
from apps.backend.app.services.agent_client import AgentClient
from apps.backend.app.services.learning import topic_service
from apps.backend.app.services.learning.topic_service import (
    locale_to_source_taxonomy,
)
from packages.core.logging import get_logger
from packages.db.models.learning.topic import LearningTopic

logger = get_logger(__name__)

router = APIRouter(prefix="/learning", tags=["learning"])


def _topic_to_response(topic: LearningTopic) -> dict:
    """Convert topic to response dict. Main fields are raw English; _zh fields exposed for frontend locale selection."""
    return {
        "id": topic.id,
        "topic_key": topic.topic_key,
        "topic_type": topic.topic_type,
        "subject": topic.subject,
        "domain": topic.domain,
        "name": topic.name,
        "description": topic.description,
        "age_range_start": topic.age_range_start,
        "age_range_end": topic.age_range_end,
        "age_group": topic.age_group,
        "centrality": topic.centrality,
        "evidence": topic.evidence or [],
        "assessment_prompt": topic.assessment_prompt,
        "standards": topic.standards or [],
        "ability_dimensions": topic.ability_dimensions,
        "curriculum_standards": topic.curriculum_standards,
        "source_taxonomy": topic.source_taxonomy,
        "deprecated": topic.deprecated,
        # Expose raw fields so frontend can detect translation status
        "name_zh": topic.name_zh,
        "description_zh": topic.description_zh,
        "evidence_zh": topic.evidence_zh,
        "assessment_prompt_zh": topic.assessment_prompt_zh,
    }


@router.get("/topics/batch", response_model=list[TopicResponse])
def get_topics_batch(
    ids: str = Query(..., description="Comma-separated topic IDs"),
    source_taxonomy: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_or_child),
):
    """Batch-fetch multiple topics by ID."""
    try:
        topic_ids = [int(x.strip()) for x in ids.split(",") if x.strip()]
    except ValueError:
        raise AppError(ErrorCode.LEARNING_TOPIC_NOT_FOUND) from None
    if not topic_ids:
        return []
    if source_taxonomy is None:
        source_taxonomy = locale_to_source_taxonomy(user.language)
    topics = topic_service.list_topics_by_ids(
        db, topic_ids, source_taxonomy=source_taxonomy
    )
    return [_topic_to_response(t) for t in topics]


@router.get("/topics/index")
def get_topic_index(
    source_taxonomy: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_or_child),
):
    """Lightweight index of all topics for browse UI (index bar).

    Returns only the fields needed to build subject → domain → topic navigation.
    Much smaller payload than the full topic list (~100KB vs ~800KB for 1600 topics).
    """
    if source_taxonomy is None:
        source_taxonomy = locale_to_source_taxonomy(user.language)
    q = db.query(
        LearningTopic.id,
        LearningTopic.subject,
        LearningTopic.domain,
        LearningTopic.name,
        LearningTopic.name_zh,
        LearningTopic.age_group,
    ).filter(LearningTopic.deprecated == False)  # noqa: E712
    if source_taxonomy:
        q = q.filter(LearningTopic.source_taxonomy == source_taxonomy)
    rows = q.order_by(LearningTopic.subject, LearningTopic.domain, LearningTopic.name).all()
    return [
        {
            "id": r.id,
            "subject": r.subject,
            "domain": r.domain or "",
            "name": r.name,
            "name_zh": r.name_zh,
            "age_group": r.age_group,
        }
        for r in rows
    ]


@router.get("/topics", response_model=list[TopicResponse])
def list_topics(
    subject: str | None = None,
    domain: str | None = None,
    age_group: str | None = None,
    search: str | None = None,
    limit: int = 20,
    source_taxonomy: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_or_child),
):
    """List topics. ``source_taxonomy`` filters by taxonomy source; when
    omitted the requesting user's language selects it
    (zh-CN -> beijing, otherwise -> os-taxonomy).
    """
    if source_taxonomy is None:
        source_taxonomy = locale_to_source_taxonomy(user.language)
    topics = topic_service.list_topics(
        db, subject=subject, domain=domain, age_group=age_group,
        search=search, limit=limit, source_taxonomy=source_taxonomy,
    )
    return [_topic_to_response(t) for t in topics]


@router.get("/topics/{topic_id}", response_model=TopicResponse)
def get_topic(
    topic_id: int,
    source_taxonomy: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_or_child),
):
    topic = topic_service.get_topic_by_id(db, topic_id)
    if not topic:
        raise AppError(ErrorCode.LEARNING_TOPIC_NOT_FOUND)
    if source_taxonomy is None:
        source_taxonomy = locale_to_source_taxonomy(user.language)
    if source_taxonomy and topic.source_taxonomy != source_taxonomy:
        raise AppError(ErrorCode.LEARNING_TOPIC_NOT_FOUND)
    return _topic_to_response(topic)


@router.get("/topics/{topic_id}/graph", response_model=TopicGraphResponse)
def get_topic_graph(
    topic_id: int,
    source_taxonomy: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_or_child),
):
    if source_taxonomy is None:
        source_taxonomy = locale_to_source_taxonomy(user.language)
    graph = topic_service.get_topic_graph(db, topic_id, source_taxonomy=source_taxonomy)
    if not graph:
        raise AppError(ErrorCode.LEARNING_TOPIC_NOT_FOUND)
    return graph


@router.get("/clusters", response_model=list[ClusterResponse])
def list_clusters(
    subject: str | None = None,
    source_taxonomy: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_or_child),
):
    if source_taxonomy is None:
        source_taxonomy = locale_to_source_taxonomy(user.language)
    return topic_service.list_clusters(
        db, subject=subject, source_taxonomy=source_taxonomy
    )


@router.get("/subjects", response_model=list[SubjectSummary])
def list_subjects(
    source_taxonomy: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_or_child),
):
    if source_taxonomy is None:
        source_taxonomy = locale_to_source_taxonomy(user.language)
    return topic_service.list_subjects(db, source_taxonomy=source_taxonomy)


@router.post("/topics/{topic_id}/translate")
async def translate_topic_endpoint(
    topic_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_adult),
):
    """Translate a topic's English content to Chinese on demand.

    Proxies to the agent module which uses the family's configured AI provider
    via ``LLMClient.complete_json()`` (multi-provider, circuit-breaker-aware).
    """
    topic = db.query(LearningTopic).filter(LearningTopic.id == topic_id).first()
    if not topic:
        raise AppError(ErrorCode.LEARNING_TOPIC_NOT_FOUND)

    topic_dict = {
        "name": topic.name or "",
        "description": topic.description or "",
        "evidence": topic.evidence or [],
        "assessment_prompt": topic.assessment_prompt or "",
    }

    try:
        agent_client = AgentClient(
            current_user.family_id, current_user.id, timeout=60.0,
        )
        resp = await agent_client.post("/translate/topic", json=topic_dict)
        resp.raise_for_status()
        translated = resp.json()
    except httpx.TimeoutException:
        raise AppError(ErrorCode.LEARNING_TRANSLATION_UNAVAILABLE) from None
    except Exception:
        logger.exception("Translation proxy call failed for topic %s", topic_id)
        raise AppError(ErrorCode.LEARNING_TRANSLATION_UNAVAILABLE) from None

    # Persist translated fields
    topic.name_zh = translated.get("name_zh")
    topic.description_zh = translated.get("description_zh")
    if translated.get("evidence_zh") is not None:
        topic.evidence_zh_json = json.dumps(translated["evidence_zh"], ensure_ascii=False)
    topic.assessment_prompt_zh = translated.get("assessment_prompt_zh")
    db.flush()

    return {
        "name_zh": topic.name_zh,
        "description_zh": topic.description_zh,
        "evidence_zh": topic.evidence_zh,
        "assessment_prompt_zh": topic.assessment_prompt_zh,
    }
