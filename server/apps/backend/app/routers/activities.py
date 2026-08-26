from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from apps.backend.app.auth.deps import require_adult
from apps.backend.app.database import get_db
from apps.backend.app.models.activity import Activity
from apps.backend.app.models.user import User
from apps.backend.app.schemas.base import ensure_utc

router = APIRouter(prefix="/activities", tags=["activities"])


@router.get("/recent")
def get_recent_activities(
    limit: int = Query(20, le=50),
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    activities = (
        db.query(Activity)
        .filter(Activity.family_id == user.family_id)
        .order_by(Activity.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": a.id,
            "type": a.type,
            "entity_type": a.entity_type,
            "entity_id": a.entity_id,
            "title": a.title,
            "amount": a.amount,
            "created_at": ensure_utc(a.created_at).isoformat()
            if a.created_at
            else None,
        }
        for a in activities
    ]
