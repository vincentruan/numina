"""Service helpers for per-family scheduled tasks."""

from sqlalchemy.orm import Session

from apps.backend.app.errors import AppError, ErrorCode
from packages.core.cron import compute_next_run_at, is_valid_cron
from packages.core.scheduled_tasks import SYSTEM_SCHEDULED_TASK_DEFAULTS
from packages.db.models.scheduled_task import ScheduledTask


def validate_cron_expression(expression: str) -> tuple[str, object]:
    """Validate a 5-field cron expression and compute its next UTC run time."""
    normalized = expression.strip()
    if not is_valid_cron(normalized):
        raise AppError(ErrorCode.SCHEDULED_TASK_CRON_INVALID)
    try:
        return normalized, compute_next_run_at(normalized)
    except (ValueError, KeyError):
        raise AppError(ErrorCode.SCHEDULED_TASK_CRON_INVALID) from None


def create_default_tasks_if_missing(db: Session, *, family_id: int) -> None:
    """Seed system-default scheduled tasks for a family that has none.

    The caller owns commit/rollback. Existing tasks mean the family has already
    entered the customizable state, so a later delete-all stays intentional.
    """
    has_any = (
        db.query(ScheduledTask.id)
        .filter(ScheduledTask.family_id == family_id)
        .first()
    )
    if has_any is not None:
        return

    for skill_id, config in SYSTEM_SCHEDULED_TASK_DEFAULTS.items():
        cron_expression, next_run_at = validate_cron_expression(
            config["cron_expression"]
        )
        db.add(
            ScheduledTask(
                family_id=family_id,
                skill_id=skill_id,
                cron_expression=cron_expression,
                is_enabled=config["is_enabled"],
                is_default=True,
                next_run_at=next_run_at,
            )
        )
