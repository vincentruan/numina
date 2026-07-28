"""Child-facing literacy endpoints — scenario + badge wall.

Mounted at ``/api/v1/child/literacy``. All endpoints require the caller to be
a child user (``get_current_child_user``).
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import desc
from sqlalchemy.orm import Session

from apps.backend.app.auth.deps import get_current_child_user
from apps.backend.app.database import get_db
from apps.backend.app.errors import AppError, ErrorCode
from apps.backend.app.models.literacy_badge import (
    LiteracyBadge,
    LiteracyBadgeDefinition,
)
from apps.backend.app.models.literacy_scenario import LiteracyScenario
from apps.backend.app.models.user import User
from apps.backend.app.schemas.literacy import (
    BadgeDefinitionInfo,
    BadgeDimensionResponse,
    BadgeInfo,
    BadgeWallResponse,
    ChoiceFeedbackResponse,
    ChoiceRequest,
    ScenarioResponse,
)
from apps.backend.app.services.literacy_badge import evaluate_badge_unlocks
from apps.backend.app.services.literacy_scenario import (
    _get_age_group,
    _sunday_of,
    generate_weekly_scenario,
)

router = APIRouter(prefix="/child/literacy", tags=["child-literacy"])

# The 4 growth dimensions used by the badge wall (must match the badge service).
ALL_DIMENSIONS = ("earning", "choosing", "waiting", "caring")
MAX_LEVEL = 3


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_content(content_json: str) -> dict[str, Any]:
    """Safely parse the scenario ``content_json`` blob."""
    try:
        data = json.loads(content_json)
    except (json.JSONDecodeError, TypeError):
        return {"story": "", "choices": []}
    if not isinstance(data, dict):
        return {"story": "", "choices": []}
    return data


async def _get_or_generate_scenario(
    db: Session, child: User
) -> LiteracyScenario:
    """Return the current week's scenario, generating lazily if missing."""
    week_start = _sunday_of(date.today())
    scenario = (
        db.query(LiteracyScenario)
        .filter(
            LiteracyScenario.child_id == child.id,
            LiteracyScenario.week_start == week_start,
        )
        .first()
    )
    if scenario is None:
        scenario = await generate_weekly_scenario(db, child)
    return scenario


def _scenario_to_response(scenario: LiteracyScenario, age_group: str) -> ScenarioResponse:
    content = _parse_content(scenario.content_json)
    return ScenarioResponse(
        id=scenario.id,
        story=content.get("story", ""),
        choices=content.get("choices", []),
        age_group=age_group,
        completed=scenario.completed_at is not None,
    )


# ---------------------------------------------------------------------------
# GET /scenario
# ---------------------------------------------------------------------------


@router.get("/scenario", response_model=ScenarioResponse)
async def get_scenario(
    current_user: User = Depends(get_current_child_user),
    db: Session = Depends(get_db),
):
    """Return the current week's scenario, generating lazily if missing."""
    scenario = await _get_or_generate_scenario(db, current_user)
    age_group = _get_age_group(current_user.birthday)
    return _scenario_to_response(scenario, age_group)


# ---------------------------------------------------------------------------
# POST /scenario/choose
# ---------------------------------------------------------------------------


@router.post("/scenario/choose", response_model=ChoiceFeedbackResponse)
async def post_scenario_choose(
    body: ChoiceRequest,
    current_user: User = Depends(get_current_child_user),
    db: Session = Depends(get_db),
):
    """Record the child's choice and trigger badge evaluation."""
    scenario = await _get_or_generate_scenario(db, current_user)

    if scenario.completed_at is not None:
        raise AppError(ErrorCode.LITERACY_SCENARIO_COMPLETED)

    content = _parse_content(scenario.content_json)
    choices = content.get("choices", [])
    if body.choice_index < 0 or body.choice_index >= len(choices):
        raise AppError(
            ErrorCode.VALIDATION_ERROR,
            details={"choice_index": body.choice_index},
        )

    chosen = choices[body.choice_index]
    feedback_text = chosen.get("feedback", "") if isinstance(chosen, dict) else ""

    # Try to extract a dimension hint from the template (best-effort).
    dimension_hint = ""
    if scenario.template_id:
        try:
            from apps.backend.app.models.literacy_scenario import (
                LiteracyScenarioTemplate,
            )

            dimension_hint = (
                db.query(LiteracyScenarioTemplate.dimension)
                .filter(LiteracyScenarioTemplate.id == scenario.template_id)
                .scalar()
            ) or ""
        except Exception:
            dimension_hint = ""

    try:
        from datetime import UTC, datetime

        scenario.choice_index = body.choice_index
        scenario.feedback_json = json.dumps(
            chosen if isinstance(chosen, dict) else {"feedback": feedback_text},
            ensure_ascii=False,
        )
        scenario.completed_at = datetime.now(UTC)
        db.commit()
    except AppError:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise AppError(ErrorCode.INTERNAL_ERROR) from exc

    # Evaluate badge unlocks — best-effort; never breaks the choice flow.
    unlocked_badges = await evaluate_badge_unlocks(
        db, current_user, "scenario_completed", scenario=scenario
    )

    return ChoiceFeedbackResponse(
        feedback_text=feedback_text,
        dimension_hint=dimension_hint,
        badges_unlocked=[
            b.definition.name
            for b in unlocked_badges
            if hasattr(b, "definition") and b.definition
        ]
        if unlocked_badges
        else _badge_names_from_ids(db, unlocked_badges),
    )


def _badge_names_from_ids(db: Session, badges: list) -> list[str]:
    """Best-effort: look up definition names for badges lacking a loaded relationship."""
    names: list[str] = []
    for b in badges:
        defn = (
            db.query(LiteracyBadgeDefinition.name)
            .filter(LiteracyBadgeDefinition.id == b.definition_id)
            .scalar()
        )
        if defn:
            names.append(defn)
    return names


# ---------------------------------------------------------------------------
# GET /badges
# ---------------------------------------------------------------------------


@router.get("/badges", response_model=BadgeWallResponse)
def get_badges(
    current_user: User = Depends(get_current_child_user),
    db: Session = Depends(get_db),
):
    """Return the badge wall: current + history + next for each dimension."""
    dimensions: list[BadgeDimensionResponse] = []

    for dimension in ALL_DIMENSIONS:
        # Current badge: highest non-superseded in this dimension.
        current_row = (
            db.query(LiteracyBadge, LiteracyBadgeDefinition)
            .join(
                LiteracyBadgeDefinition,
                LiteracyBadge.definition_id == LiteracyBadgeDefinition.id,
            )
            .filter(
                LiteracyBadge.child_id == current_user.id,
                LiteracyBadgeDefinition.dimension == dimension,
                LiteracyBadge.superseded_at.is_(None),
            )
            .order_by(desc(LiteracyBadgeDefinition.level))
            .first()
        )
        current_badge: BadgeInfo | None = None
        current_level = 0
        if current_row is not None:
            badge, defn = current_row
            current_level = defn.level
            current_badge = BadgeInfo(
                id=badge.id,
                name=defn.name,
                level=defn.level,
                description=defn.description,
                earned_at=badge.earned_at,
            )

        # History: superseded badges, newest first.
        history_rows = (
            db.query(LiteracyBadge, LiteracyBadgeDefinition)
            .join(
                LiteracyBadgeDefinition,
                LiteracyBadge.definition_id == LiteracyBadgeDefinition.id,
            )
            .filter(
                LiteracyBadge.child_id == current_user.id,
                LiteracyBadgeDefinition.dimension == dimension,
                LiteracyBadge.superseded_at.is_not(None),
            )
            .order_by(desc(LiteracyBadge.earned_at))
            .all()
        )
        history = [
            BadgeInfo(
                id=badge.id,
                name=defn.name,
                level=defn.level,
                earned_at=badge.earned_at,
                superseded_at=badge.superseded_at,
            )
            for badge, defn in history_rows
        ]

        # Next badge: level = current_level + 1 (or level 1 if none).
        next_level = current_level + 1
        next_badge: BadgeDefinitionInfo | None = None
        if next_level <= MAX_LEVEL:
            next_defn = (
                db.query(LiteracyBadgeDefinition)
                .filter(
                    LiteracyBadgeDefinition.dimension == dimension,
                    LiteracyBadgeDefinition.level == next_level,
                )
                .first()
            )
            if next_defn is not None:
                next_badge = BadgeDefinitionInfo(
                    id=next_defn.id,
                    name=next_defn.name,
                    level=next_defn.level,
                    description=next_defn.description,
                    criteria_summary=next_defn.criteria_summary,
                )

        dimensions.append(
            BadgeDimensionResponse(
                dimension=dimension,
                current_badge=current_badge,
                history=history,
                next_badge=next_badge,
            )
        )

    return BadgeWallResponse(dimensions=dimensions)
