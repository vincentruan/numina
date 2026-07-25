"""Admin endpoints for AI structured extraction monitoring + circuit management.

R5.2 / R5.4 / D7 人工介入 from
docs/brainstorms/2026-05-19-async-agent-task-result-persistence-v2-requirements.md
"""

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func
from sqlalchemy.orm import Session

from apps.backend.app.auth.ai_deps import require_owner
from apps.backend.app.database import get_db
from apps.backend.app.models.ai_extraction_audit import AIExtractionAudit
from apps.backend.app.models.ai_extraction_circuit import AIExtractionCircuit
from apps.backend.app.models.user import User
from apps.backend.app.schemas.base import SnowflakeBase
from apps.backend.app.services.ai_extraction_circuit_service import (
    AIExtractionCircuitService,
)

router = APIRouter(prefix="/admin", tags=["admin-ai-extraction"])


class AuditRow(SnowflakeBase):
    id: int
    family_id: int
    skill_id: str
    task_id: str | None
    method: str
    extracted_at: datetime
    error_msg: str | None
    answer_excerpt: str | None


class AuditAggregates(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    total: int
    regex_html: int
    regex_fence: int
    regex_bare: int
    llm_fallback_hit: int
    failed: int


class AuditResponse(BaseModel):
    rows: list[AuditRow]
    aggregates: AuditAggregates


class CircuitRow(SnowflakeBase):
    family_id: int
    skill_id: str
    state: str
    opened_at: datetime | None
    opened_until: datetime | None
    last_evaluated_at: datetime
    manually_reset_at: datetime | None
    reset_by_user_id: int | None


class CircuitListResponse(BaseModel):
    rows: list[CircuitRow]


class CircuitResetRequest(BaseModel):
    family_id: str
    skill_id: str


class CircuitResetResponse(BaseModel):
    ok: bool
    reset_at: datetime


@router.get("/ai-extraction-audit")
def list_audit(
    family_id: int | None = Query(None),
    skill_id: str | None = Query(None),
    days: int = Query(7, ge=1, le=90),
    limit: int = Query(100, ge=1, le=1000),
    current_user: User = Depends(require_owner),
    db: Session = Depends(get_db),
) -> AuditResponse:
    cutoff = datetime.utcnow() - timedelta(days=days)
    query = db.query(AIExtractionAudit).filter(AIExtractionAudit.extracted_at >= cutoff)
    if family_id is not None:
        query = query.filter(AIExtractionAudit.family_id == family_id)
    if skill_id is not None:
        query = query.filter(AIExtractionAudit.skill_id == skill_id)

    rows = query.order_by(AIExtractionAudit.extracted_at.desc()).limit(limit).all()

    method_counts = (
        query.with_entities(AIExtractionAudit.method, func.count(AIExtractionAudit.id))
        .group_by(AIExtractionAudit.method)
        .all()
    )
    counts: dict[str, int] = {m: c for m, c in method_counts}
    aggregates = AuditAggregates(
        total=sum(counts.values()),
        regex_html=counts.get("regex_html", 0),
        regex_fence=counts.get("regex_fence", 0),
        regex_bare=counts.get("regex_bare", 0),
        llm_fallback_hit=counts.get("llm_fallback_hit", 0),
        failed=counts.get("failed", 0),
    )

    return AuditResponse(
        rows=[AuditRow.model_validate(r) for r in rows],
        aggregates=aggregates,
    )


@router.get("/ai-extraction-circuit")
def list_circuit(
    current_user: User = Depends(require_owner),
    db: Session = Depends(get_db),
) -> CircuitListResponse:
    """List circuits where state != 'ok' (active rate-limited or open circuits)."""
    rows = (
        db.query(AIExtractionCircuit)
        .filter(AIExtractionCircuit.state != "ok")
        .order_by(AIExtractionCircuit.opened_at.desc().nulls_last())
        .all()
    )
    return CircuitListResponse(rows=[CircuitRow.model_validate(r) for r in rows])


@router.post("/ai-extraction-circuit/reset")
def reset_circuit(
    body: CircuitResetRequest,
    current_user: User = Depends(require_owner),
    db: Session = Depends(get_db),
) -> CircuitResetResponse:
    AIExtractionCircuitService.reset(
        family_id=int(body.family_id),
        skill_id=body.skill_id,
        user_id=current_user.id,
        db=db,
    )
    return CircuitResetResponse(ok=True, reset_at=datetime.utcnow())
