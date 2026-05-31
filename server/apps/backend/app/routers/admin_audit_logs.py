"""Admin endpoint for querying security audit logs.

R8: GET /api/v1/admin/audit-logs — owner-only, tenant-isolated, paginated.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from apps.backend.app.auth.deps import require_owner
from apps.backend.app.database import get_db
from apps.backend.app.models.security_audit_log import SecurityAuditLog
from apps.backend.app.models.user import User
from apps.backend.app.schemas.audit_log import AuditLogListResponse, AuditLogResponse

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/audit-logs")
def list_audit_logs(
    event_type: str | None = Query(None),
    user_id: int | None = Query(None),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    current_user: User = Depends(require_owner),
    db: Session = Depends(get_db),
) -> AuditLogListResponse:
    """List security audit logs for the current user's family.

    Always filters by family_id (tenant isolation). Supports optional
    filtering by event_type, user_id, and date range. Results are ordered
    newest-first and paginated.
    """
    query = db.query(SecurityAuditLog).filter(
        SecurityAuditLog.family_id == current_user.family_id
    )

    if event_type is not None:
        query = query.filter(SecurityAuditLog.event_type == event_type)
    if user_id is not None:
        query = query.filter(SecurityAuditLog.user_id == user_id)
    if date_from is not None:
        query = query.filter(SecurityAuditLog.created_at >= date_from)
    if date_to is not None:
        query = query.filter(SecurityAuditLog.created_at <= date_to)

    total = query.count()
    offset = (page - 1) * page_size
    rows = (
        query.order_by(SecurityAuditLog.created_at.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )

    return AuditLogListResponse(
        items=[AuditLogResponse.model_validate(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )
