from sqlalchemy.orm import Session

from apps.backend.app.models.activity import Activity
from apps.backend.app.models.user import User


def record_activity(
    db: Session,
    user: User,
    activity_type: str,
    entity_type: str,
    entity_id: int | str,
    title: str,
    amount: float | None = None,
):
    """Record an activity log entry."""
    activity = Activity(
        family_id=user.family_id,
        user_id=user.id,
        type=activity_type,
        entity_type=entity_type,
        entity_id=entity_id,
        title=title,
        amount=amount,
    )
    db.add(activity)
    db.commit()
