"""Global learning knowledge graph endpoints (no auth required)."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from apps.backend.app.database import get_db
from apps.backend.app.errors import AppError, ErrorCode
from apps.backend.app.schemas.learning import (
    ClusterResponse,
    SubjectSummary,
    TopicGraphResponse,
    TopicResponse,
)
from apps.backend.app.services.learning import topic_service

router = APIRouter(prefix="/learning", tags=["learning"])


@router.get("/topics/batch", response_model=list[TopicResponse])
def get_topics_batch(
    ids: str = Query(..., description="Comma-separated topic IDs"),
    db: Session = Depends(get_db),
):
    """Batch-fetch multiple topics by ID."""
    try:
        topic_ids = [int(x.strip()) for x in ids.split(",") if x.strip()]
    except ValueError:
        raise AppError(ErrorCode.LEARNING_TOPIC_NOT_FOUND) from None
    if not topic_ids:
        return []
    return topic_service.list_topics_by_ids(db, topic_ids)


@router.get("/topics", response_model=list[TopicResponse])
def list_topics(
    subject: str | None = None,
    domain: str | None = None,
    age_group: str | None = None,
    search: str | None = None,
    limit: int = 20,
    db: Session = Depends(get_db),
):
    return topic_service.list_topics(
        db, subject=subject, domain=domain, age_group=age_group,
        search=search, limit=limit,
    )


@router.get("/topics/{topic_id}", response_model=TopicResponse)
def get_topic(topic_id: int, db: Session = Depends(get_db)):
    topic = topic_service.get_topic_by_id(db, topic_id)
    if not topic:
        raise AppError(ErrorCode.LEARNING_TOPIC_NOT_FOUND)
    return topic


@router.get("/topics/{topic_id}/graph", response_model=TopicGraphResponse)
def get_topic_graph(topic_id: int, db: Session = Depends(get_db)):
    graph = topic_service.get_topic_graph(db, topic_id)
    if not graph:
        raise AppError(ErrorCode.LEARNING_TOPIC_NOT_FOUND)
    return graph


@router.get("/clusters", response_model=list[ClusterResponse])
def list_clusters(subject: str | None = None, db: Session = Depends(get_db)):
    return topic_service.list_clusters(db, subject=subject)


@router.get("/subjects", response_model=list[SubjectSummary])
def list_subjects(db: Session = Depends(get_db)):
    return topic_service.list_subjects(db)
