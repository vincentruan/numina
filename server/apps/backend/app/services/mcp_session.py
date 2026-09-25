"""MCP Session — caller-bound tool registry for AI Chat data access.

Tenant + caller isolation via __slots__:
- _family_id, _caller_user_id, _caller_role are captured at construction and frozen
- Tool handlers NEVER read family_id/caller from tool args — only from self
"""

import json
import logging
from datetime import date
from decimal import Decimal
from typing import Any

from mcp.server import Server
from mcp.types import TextContent, Tool
from sqlalchemy import func
from sqlalchemy.orm import Session

from apps.backend.app.database import SessionLocal
from apps.backend.app.errors import AppError
from apps.backend.app.models.user import User

logger = logging.getLogger(__name__)


def _parse_date(value: Any) -> date | None:
    """Parse a YYYY-MM-DD string (or None) into a date; None/invalid → None."""
    if not value:
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except (ValueError, TypeError):
        return None


def _import_assets_batch(
    db: Session, user: User, items: list[dict[str, Any]]
) -> dict[str, Any]:
    """Batch-create financial assets via ``asset.create_asset``.

    Mirrors ``import_report._resolve_category_id``: category_hint → Category.name
    match; items whose hint matches no system category are skipped (status
    "skipped") rather than failing the whole batch — the agent can retry with
    a supported hint. Returns ``{created, skipped, items}`` where each item
    echoes the caller's ``temp_id`` for correlation.
    """
    from apps.backend.app.models.category import Category
    from apps.backend.app.schemas.asset import AssetCreate
    from apps.backend.app.services import asset as asset_service

    results: list[dict[str, Any]] = []
    created = 0
    skipped = 0
    for raw in items:
        temp_id = raw.get("temp_id", "")
        hint = raw.get("category_hint") or ""
        name = raw.get("name")
        if not name:
            skipped += 1
            results.append(
                {
                    "temp_id": temp_id,
                    "name": "",
                    "status": "skipped",
                    "reason": "缺少 name 字段",
                }
            )
            continue
        cat = db.query(Category).filter(Category.name == hint).first() if hint else None
        if not cat:
            skipped += 1
            results.append(
                {
                    "temp_id": temp_id,
                    "name": name,
                    "status": "skipped",
                    "reason": f"未知分类: {hint}",
                }
            )
            continue
        try:
            req = AssetCreate(
                category_id=cat.id,
                name=name,
                asset_type=raw.get("asset_type") or "financial",
                current_value=raw.get("current_value"),
                purchase_price=raw.get("current_value"),
                currency=raw.get("currency", "CNY"),
                notes=raw.get("notes"),
                status="in_use",
            )
            asset = asset_service.create_asset(db, user, req)
            created += 1
            results.append(
                {
                    "temp_id": temp_id,
                    "id": str(asset.id),
                    "name": asset.name,
                    "status": "created",
                }
            )
        except Exception as e:
            skipped += 1
            results.append(
                {
                    "temp_id": temp_id,
                    "name": raw.get("name", ""),
                    "status": "error",
                    "reason": str(e),
                }
            )
    return {"created": created, "skipped": skipped, "items": results}


def _import_liabilities_batch(
    db: Session,
    user: User,
    items: list[dict[str, Any]],
    *,
    category_override: str | None = None,
) -> dict[str, Any]:
    """Batch-create liabilities via ``liability.create_liability``.

    ``category_override`` (used by ``import_credit_cards_batch`` = "credit_card")
    forces the category, ignoring any per-item ``category``. Returns the same
    ``{created, skipped, items}`` shape as the assets batch.
    """
    from apps.backend.app.schemas.liability import LiabilityCreate
    from apps.backend.app.services import liability as liability_service

    results: list[dict[str, Any]] = []
    created = 0
    skipped = 0
    for raw in items:
        temp_id = raw.get("temp_id", "")
        try:
            req = LiabilityCreate(
                category=category_override or raw.get("category", "other"),
                name=raw["name"],
                original_amount=Decimal(str(raw["original_amount"])),
                remaining_amount=Decimal(str(raw["remaining_amount"])),
                monthly_payment=raw.get("monthly_payment"),
                interest_rate=raw.get("interest_rate"),
                start_date=_parse_date(raw.get("start_date")),
                end_date=_parse_date(raw.get("end_date")),
                institution=raw.get("institution"),
                currency=raw.get("currency", "CNY"),
                notes=raw.get("notes"),
            )
            liability = liability_service.create_liability(db, user, req)
            created += 1
            results.append(
                {
                    "temp_id": temp_id,
                    "id": str(liability.id),
                    "name": liability.name,
                    "status": "created",
                }
            )
        except Exception as e:
            skipped += 1
            results.append(
                {
                    "temp_id": temp_id,
                    "name": raw.get("name", ""),
                    "status": "error",
                    "reason": str(e),
                }
            )
    return {"created": created, "skipped": skipped, "items": results}


def _validate_evaluation_schema(evaluation: Any) -> None:
    """Validate LLM-produced evaluation structure.

    LLM output is untrusted; this prevents malformed JSON from corrupting
    the progress state machine or crashing downstream consumers.
    """
    if not isinstance(evaluation, dict):
        raise ValueError("evaluation must be a dict")
    if "evidence_results" not in evaluation or not isinstance(
        evaluation["evidence_results"], list
    ):
        raise ValueError("evaluation must contain evidence_results array")
    for i, item in enumerate(evaluation["evidence_results"]):
        if not isinstance(item, dict):
            raise ValueError(f"evidence_results[{i}] must be a dict")
        if "evidence" not in item or not isinstance(item["evidence"], str):
            raise ValueError(f"evidence_results[{i}] must contain 'evidence' (string)")
        if "met" not in item or not isinstance(item["met"], bool):
            raise ValueError(f"evidence_results[{i}] must contain 'met' (boolean)")
    score = evaluation.get("overall_score")
    if isinstance(score, bool) or not isinstance(score, (int, float)) or not (0.0 <= score <= 1.0):
        raise ValueError("overall_score must be a number between 0.0 and 1.0")
    rec = evaluation.get("recommendation")
    if rec not in ("mastered", "needs_review", "keep_learning"):
        raise ValueError(
            f"recommendation must be mastered/needs_review/keep_learning, got {rec!r}"
        )


def _get_caller_user(family_id: str, caller_user_id: str, db: Session) -> User:
    """Return the caller user, validating family membership and active status."""
    user = db.query(User).filter(User.id == caller_user_id).first()
    if not user or not user.is_active or str(user.family_id) != str(family_id):
        raise RuntimeError(
            f"caller invalid: user_id={caller_user_id} family={family_id}"
        )
    return user


class MCPSession:
    """Per-connection MCP session bound to a single family_id and caller.

    Tenant + caller isolation via __slots__:
    - _family_id, _caller_user_id, _caller_role are frozen at construction
    - _thread_id is optional; when present, report tools write to per-thread
      sandbox outputs for isolation consistent with DeerFlow's sandbox provider
    - Tool handlers NEVER read these from tool args — only from self
    """

    __slots__ = (
        "_family_id",
        "_caller_user_id",
        "_caller_role",
        "_thread_id",
        "_server",
    )

    def __init__(
        self,
        family_id: str,
        caller_user_id: str,
        caller_role: str,
        thread_id: str | None = None,
    ) -> None:
        if not family_id:
            raise ValueError("family_id must not be empty")
        if not caller_user_id:
            raise ValueError("caller_user_id must not be empty")
        if not caller_role:
            raise ValueError("caller_role must not be empty")
        self._family_id = family_id
        self._caller_user_id = caller_user_id
        self._caller_role = caller_role
        self._thread_id = thread_id
        self._server = Server(f"numina-family-{family_id}")
        self._register_tools()

    @property
    def family_id(self) -> str:
        return self._family_id

    @property
    def caller_user_id(self) -> str:
        return self._caller_user_id

    @property
    def caller_role(self) -> str:
        return self._caller_role

    @property
    def server(self) -> Server:
        return self._server

    def _register_tools(self) -> None:
        server = self._server

        @server.list_tools()
        async def _list_tools() -> list[Tool]:
            return await self.list_tools()

        @server.call_tool()
        async def _call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
            return await self.call_tool(name, arguments)

    async def list_tools(self) -> list[Tool]:
        from apps.backend.app.services.mcp_tool_registry import list_tools_for_role

        return [
            Tool(
                name=meta.name,
                description=meta.description,
                inputSchema=meta.input_schema,
            )
            for meta in list_tools_for_role(self._caller_role)
        ]

    async def call_tool(
        self, name: str, arguments: dict[str, Any]
    ) -> list[TextContent]:
        # SECURITY: ignore any family_id/caller_user_id/role in arguments — slots are the only truth
        from apps.backend.app.services import asset as asset_service
        from apps.backend.app.services import dashboard as dashboard_service
        from apps.backend.app.services import family as family_service
        from apps.backend.app.services import liability as liability_service
        from apps.backend.app.services.mcp_tool_registry import get_tool

        meta = get_tool(name)
        if not meta or self._caller_role not in meta.allowed_roles:
            logger.warning(
                "[mcp_session] permission_denied family=%s caller_user_id=%s caller_role=%s attempted_tool=%s",
                self._family_id,
                self._caller_user_id,
                self._caller_role,
                name,
            )
            return [
                TextContent(
                    type="text",
                    text=json.dumps(
                        {
                            "error": "permission_denied",
                            "retryable": False,
                            "reason": "该工具对当前角色不可用",
                        },
                        ensure_ascii=False,
                    ),
                )
            ]

        with SessionLocal() as db:
            user = _get_caller_user(self._family_id, self._caller_user_id, db)
            try:
                if name == "get_family_overview":
                    data: Any = dashboard_service.get_overview(db, user)
                elif name == "get_assets":
                    category = arguments.get("category")
                    limit = int(arguments.get("limit", 20))
                    data = asset_service.list_assets_for_family(
                        db, self._family_id, user=user, category=category, limit=limit
                    )
                elif name == "get_liabilities":
                    limit = int(arguments.get("limit", 20))
                    data = liability_service.list_liabilities_for_family(
                        db, self._family_id, user=user, limit=limit
                    )
                elif name == "get_members":
                    data = family_service.list_members(db, int(self._family_id))
                elif name == "get_recent_alerts":
                    limit = int(arguments.get("limit", 10))
                    data = dashboard_service.get_recent_alerts(db, user, limit=limit)
                elif name == "import_assets_batch":
                    data = _import_assets_batch(db, user, arguments.get("items") or [])
                elif name == "import_liabilities_batch":
                    data = _import_liabilities_batch(
                        db, user, arguments.get("items") or []
                    )
                elif name == "import_credit_cards_batch":
                    data = _import_liabilities_batch(
                        db,
                        user,
                        arguments.get("items") or [],
                        category_override="credit_card",
                    )
                elif name == "get_child_literacy_profile":
                    from apps.backend.app.models.literacy_report import (
                        LiteracyWeeklyReport,
                    )
                    from apps.backend.app.services.literacy_report import _get_age_group
                    from packages.db.models.literacy_badge import (
                        LiteracyBadge,
                        LiteracyBadgeDefinition,
                    )
                    from packages.db.models.literacy_scenario import LiteracyScenario

                    query = db.query(User).filter(
                        User.family_id == int(self._family_id),
                        User.role == "child",
                        User.is_active.is_(True),
                    )
                    child_id_arg = arguments.get("child_id")
                    if child_id_arg:
                        query = query.filter(User.id == int(child_id_arg))
                    children = query.all()

                    result_children = []
                    for child in children:
                        badges = (
                            db.query(LiteracyBadgeDefinition)
                            .join(
                                LiteracyBadge,
                                LiteracyBadge.definition_id
                                == LiteracyBadgeDefinition.id,
                            )
                            .filter(
                                LiteracyBadge.child_id == child.id,
                                LiteracyBadge.superseded_at.is_(None),
                            )
                            .all()
                        )
                        scenario_count = (
                            db.query(func.count(LiteracyScenario.id))
                            .filter(
                                LiteracyScenario.child_id == child.id,
                                LiteracyScenario.completed_at.is_not(None),
                            )
                            .scalar()
                        ) or 0
                        latest_report = (
                            db.query(LiteracyWeeklyReport.week_start)
                            .filter(LiteracyWeeklyReport.child_id == child.id)
                            .order_by(LiteracyWeeklyReport.week_start.desc())
                            .first()
                        )
                        result_children.append(
                            {
                                "child_id": str(child.id),
                                "display_name": child.display_name,
                                "age_group": _get_age_group(child.birthday),
                                "current_badges": [
                                    {
                                        "dimension": b.dimension,
                                        "level": b.level,
                                        "name": b.name,
                                    }
                                    for b in badges
                                ],
                                "total_scenarios_completed": scenario_count,
                                "latest_report_week": (
                                    latest_report[0].isoformat()
                                    if latest_report
                                    else None
                                ),
                            }
                        )
                    data = {"children": result_children}
                elif name == "get_literacy_weekly_data":
                    from datetime import timedelta

                    from apps.backend.app.services.literacy_report import (
                        _aggregate_signals,
                        _sunday_of,
                    )

                    child_id_lit = int(arguments["child_id"])

                    # Validate child belongs to caller's family
                    child_in_family = (
                        db.query(User.id)
                        .filter(
                            User.id == child_id_lit,
                            User.family_id == int(self._family_id),
                            User.role == "child",
                        )
                        .first()
                    )
                    if not child_in_family:
                        data = {
                            "error": "孩子不属于当前家庭",
                            "child_id": str(child_id_lit),
                        }
                    else:
                        week_start_arg = arguments.get("week_start")
                        week_start = (
                            date.fromisoformat(week_start_arg)
                            if week_start_arg
                            else _sunday_of(date.today())
                        )

                        signals = _aggregate_signals(db, child_id_lit, week_start)
                        prev_week = week_start - timedelta(days=7)
                        prev_signals = _aggregate_signals(db, child_id_lit, prev_week)

                        data = {
                            "child_id": str(child_id_lit),
                            "week_start": week_start.isoformat(),
                            **signals,
                            "trend": {
                                "chores_delta": (
                                    signals["chores_approved"]
                                    - prev_signals["chores_approved"]
                                ),
                                "coins_delta": (
                                    signals["coin_earned"] - prev_signals["coin_earned"]
                                ),
                                "scenario_was_completed_prev": prev_signals[
                                    "scenario_completed"
                                ],
                            },
                        }
                elif name == "get_travel_trips":
                    from apps.backend.app.services import trip as trip_service

                    status_filter = arguments.get("status")
                    limit = int(arguments.get("limit", 20))
                    trips = trip_service.list_trips(
                        db,
                        family_id=int(self._family_id),
                        status=status_filter,
                    )
                    trips = trips[:limit]
                    data = {
                        "trips": [
                            {
                                "id": str(t.id),
                                "name": t.name,
                                "destination": t.destination,
                                "status": t.status,
                                "departure_date": (
                                    t.departure_date.isoformat()
                                    if t.departure_date
                                    else None
                                ),
                                "return_date": (
                                    t.return_date.isoformat() if t.return_date else None
                                ),
                                "planned_budget": (
                                    str(t.planned_budget)
                                    if t.planned_budget is not None
                                    else None
                                ),
                                "actual_spend": str(t.actual_spend),
                                "currency": t.currency,
                            }
                            for t in trips
                        ]
                    }
                elif name == "get_travel_expenses":
                    from apps.backend.app.services import (
                        expense_ledger as expense_ledger_service,
                    )
                    from apps.backend.app.services import trip as trip_service

                    trip_id_str = arguments["trip_id"]
                    trip_id_int = int(trip_id_str)
                    limit = int(arguments.get("limit", 50))
                    # Validate trip belongs to family
                    trip_service.get_trip(db, trip_id_int, int(self._family_id))
                    expenses = expense_ledger_service.list_expenses(
                        db,
                        family_id=int(self._family_id),
                        ref_id=trip_id_int,
                        ref_type="trip",
                        limit=limit,
                    )
                    data = {
                        "trip_id": trip_id_str,
                        "expenses": [
                            {
                                "id": str(e.id),
                                "amount": str(e.amount),
                                "currency": e.currency,
                                "amount_cny": str(e.amount_cny),
                                "expense_date": (
                                    e.expense_date.isoformat()
                                    if e.expense_date
                                    else None
                                ),
                                "description": e.description,
                            }
                            for e in expenses
                        ],
                    }
                elif name == "get_travel_split_balances":
                    from apps.backend.app.services import (
                        expense_ledger as expense_ledger_service,
                    )
                    from apps.backend.app.services import (
                        settlement as settlement_service,
                    )
                    from apps.backend.app.services import trip as trip_service

                    trip_id_str = arguments["trip_id"]
                    trip_id_int = int(trip_id_str)
                    # Validate trip belongs to family
                    trip_obj = trip_service.get_trip(
                        db, trip_id_int, int(self._family_id)
                    )

                    # Get total shared expenses (debit legs only, in CNY)
                    expenses = expense_ledger_service.list_expenses(
                        db,
                        family_id=int(self._family_id),
                        ref_id=trip_id_int,
                        ref_type="trip",
                        limit=1000,
                    )
                    total_shared_cny = sum(
                        (e.amount_cny for e in expenses), Decimal("0")
                    )

                    # Get settlements (sanitized — no external participant names)
                    try:
                        settlements = settlement_service.get_settlements(
                            db, trip_id_int, int(self._family_id)
                        )
                        settlement_data = [
                            {
                                "amount": str(s.amount),
                                "currency": s.currency,
                                "is_complete": s.is_complete,
                            }
                            for s in settlements
                        ]
                    except Exception:
                        # No split group yet — that's fine
                        settlement_data = []

                    data = {
                        "trip_id": trip_id_str,
                        "total_shared_expenses_cny": str(total_shared_cny),
                        "trip_currency": trip_obj.currency,
                        "expense_count": len(expenses),
                        "settlements": settlement_data,
                        "has_split_group": len(settlement_data) > 0,
                    }
                elif name == "get_learning_topic":
                    from packages.db.models.learning.progress import LearningProgress
                    from packages.db.models.learning.topic import LearningTopic

                    try:
                        topic_id = int(arguments["topic_id"])
                        child_id = int(arguments["child_id"])
                        if topic_id <= 0 or child_id <= 0:
                            raise ValueError("topic_id and child_id must be positive integers")
                    except (ValueError, TypeError, KeyError) as exc:
                        data = {"error": "invalid_arguments", "detail": str(exc)}
                    else:
                        topic = (
                            db.query(LearningTopic)
                            .filter(LearningTopic.id == topic_id)
                            .first()
                        )
                        if not topic:
                            data = {"error": "topic_not_found"}
                        else:
                            # Family-scope validation: child must belong to caller's family
                            child = (
                                db.query(User)
                                .filter(
                                    User.id == child_id,
                                    User.family_id == int(self._family_id),
                                )
                                .first()
                            )
                            if not child:
                                data = {"error": "child_not_in_family"}
                            else:
                                progress = (
                                    db.query(LearningProgress)
                                    .filter_by(child_id=child_id, topic_id=topic_id)
                                    .first()
                                )
                                data = {
                                    "topic_id": str(topic.id),
                                    "name": topic.name,
                                    "description": topic.description,
                                    "evidence_criteria": topic.evidence_json,
                                    "assessment_prompt": topic.assessment_prompt,
                                    "mastery_level": (
                                        progress.mastery_level if progress else "locked"
                                    ),
                                }
                elif name == "get_child_learning_profile":
                    from packages.db.models.learning.progress import LearningProgress
                    from packages.db.models.learning.topic import LearningTopic

                    try:
                        child_id = int(arguments["child_id"])
                    except (ValueError, TypeError, KeyError) as exc:
                        data = {"error": "invalid_arguments", "detail": str(exc)}
                    else:
                        subject = arguments.get("subject")

                        # Family-scope validation
                        child_in_family = (
                            db.query(User.id)
                            .filter(
                                User.id == child_id,
                                User.family_id == int(self._family_id),
                                User.role == "child",
                            )
                            .first()
                        )
                        if not child_in_family:
                            data = {
                                "error": "child_not_in_family",
                                "child_id": str(child_id),
                            }
                        else:
                            query = db.query(LearningProgress).filter(
                                LearningProgress.child_id == child_id
                            )
                            if subject:
                                # subject lives on LearningTopic; join to filter
                                query = query.join(
                                    LearningTopic,
                                    LearningProgress.topic_id == LearningTopic.id,
                                ).filter(LearningTopic.subject == subject)
                            progresses = query.all()

                            data = {
                                "child_id": str(child_id),
                                "total_topics": len(progresses),
                                "mastered": sum(
                                    1 for p in progresses if p.mastery_level == "mastered"
                                ),
                                "learning": sum(
                                    1 for p in progresses if p.mastery_level == "learning"
                                ),
                                "available": sum(
                                    1 for p in progresses if p.mastery_level == "available"
                                ),
                                "review": sum(
                                    1 for p in progresses if p.mastery_level == "review"
                                ),
                                "locked": sum(
                                    1 for p in progresses if p.mastery_level == "locked"
                                ),
                                "assessing": sum(
                                    1 for p in progresses if p.mastery_level == "assessing"
                                ),
                            }
                elif name == "record_learning_result":
                    from apps.backend.app.services.learning import session_service
                    from packages.db.models.child_economy.coin_transaction import (
                        CoinTransaction,
                    )
                    from packages.db.models.learning.progress import LearningProgress
                    from packages.db.models.learning.session import (
                        LearningAssessmentAttempt,
                        LearningSession,
                    )

                    # Reward tiers by recommendation (encourages mastery)
                    _REWARD_TIERS = {
                        "mastered": 15,
                        "needs_review": 5,
                        "keep_learning": 2,
                    }

                    try:
                        session_id = int(arguments["session_id"])
                        if session_id <= 0:
                            raise ValueError("session_id must be a positive integer")
                    except (ValueError, TypeError, KeyError) as exc:
                        data = {"error": "invalid_arguments", "detail": str(exc)}
                    else:
                        evaluation = arguments["evaluation"]

                        # Schema validation (LLM output is untrusted)
                        _validate_evaluation_schema(evaluation)

                        # Family-scope validation: session must belong to a child in this family
                        session = (
                            db.query(LearningSession)
                            .join(User, LearningSession.child_id == User.id)
                            .filter(
                                LearningSession.id == session_id,
                                User.family_id == int(self._family_id),
                            )
                            .first()
                        )
                        if not session:
                            data = {"error": "session_not_found"}
                        else:
                            child = (
                                db.query(User)
                                .filter(
                                    User.id == session.child_id,
                                    User.family_id == int(self._family_id),
                                )
                                .first()
                            )
                            if not child:
                                data = {"error": "session_not_in_family"}
                            else:
                                rec = evaluation["recommendation"]

                                # End session with evaluation
                                ended_session = session_service.end_session(
                                    db,
                                    session_id,
                                    score=evaluation["overall_score"],
                                    ai_evaluation=evaluation,
                                )

                                # Create assessment attempt (audit + idempotency key)
                                attempt = LearningAssessmentAttempt(
                                    child_id=child.id,
                                    topic_id=session.topic_id,
                                    session_id=session.id,
                                    assessment_type="ai_assessment",
                                    score=evaluation["overall_score"],
                                    passed=(rec == "mastered"),
                                    evidence_results_json=json.dumps(
                                        evaluation.get("evidence_results", [])
                                    ),
                                )
                                db.add(attempt)
                                db.flush()

                                # Streak detection and notification
                                from apps.backend.app.services.learning import (
                                    progress_service,
                                )

                                if attempt.passed:
                                    progress_service.resolve_streak_reminder_on_pass(
                                        db, child.id, session.topic_id,
                                    )
                                else:
                                    streak = progress_service.check_consecutive_failures(
                                        db, child.id, session.topic_id,
                                    )
                                    if streak == progress_service.STREAK_THRESHOLD:
                                        from apps.backend.app.services.notification.dispatcher import (
                                            notify_learning_streak_3_failures,
                                        )
                                        notify_learning_streak_3_failures(
                                            db, child_id=child.id, topic_id=session.topic_id,
                                        )

                                # Update progress based on recommendation
                                progress = (
                                    db.query(LearningProgress)
                                    .filter_by(
                                        child_id=ended_session.child_id,
                                        topic_id=ended_session.topic_id,
                                    )
                                    .first()
                                )
                                mastery_changed = False
                                if progress:
                                    target_level = (
                                        "mastered"
                                        if rec == "mastered"
                                        else "review"
                                        if rec == "needs_review"
                                        else progress.mastery_level
                                    )
                                    if target_level != progress.mastery_level:
                                        from apps.backend.app.services.learning import (
                                            progress_service,
                                        )

                                        try:
                                            progress_service.validate_transition(
                                                progress.mastery_level, target_level
                                            )
                                            progress.mastery_level = target_level
                                            mastery_changed = True

                                            # Update spaced-repetition bookkeeping on mastery
                                            if target_level == "mastered":
                                                from datetime import UTC, datetime

                                                now = datetime.now(UTC)
                                                if not progress.first_mastered_at:
                                                    progress.first_mastered_at = now
                                                progress.mastery_score = (
                                                    evaluation["overall_score"]
                                                )
                                                progress.stability = (
                                                    progress_service.update_stability(
                                                        progress,
                                                        progress.mastery_score,
                                                    )
                                                )
                                                progress.next_review_at = (
                                                    progress_service.compute_next_review(
                                                        progress
                                                    )
                                                )
                                                # Unlock dependent topics
                                                progress_service.unlock_dependent_topics(
                                                    db, child.id, progress.topic_id
                                                )
                                        except AppError:
                                            data = {
                                                "error": "invalid_mastery_transition",
                                                "detail": (
                                                    f"Cannot transition from "
                                                    f"'{progress.mastery_level}' to "
                                                    f"'{target_level}'. "
                                                    f"Current recommendation: {rec}. "
                                                    f"The session was still recorded successfully."
                                                ),
                                                "session_id": str(session_id),
                                                "recommendation": rec,
                                            }

                                # Dispatch coin reward (tiered by recommendation)
                                coins_earned = 0
                                if mastery_changed or rec != "mastered":
                                    coin_amount = _REWARD_TIERS.get(rec, 0)
                                    if coin_amount > 0:
                                        # Resolve topic name for narrative
                                        from packages.db.models.learning.topic import (
                                            LearningTopic,
                                        )

                                        topic = (
                                            db.query(LearningTopic)
                                            .filter(
                                                LearningTopic.id == session.topic_id
                                            )
                                            .first()
                                        )
                                        topic_label = (
                                            (topic.name_zh or topic.name or "learning")
                                            if topic
                                            else "learning"
                                        )
                                        txn = CoinTransaction(
                                            family_id=int(self._family_id),
                                            child_user_id=child.id,
                                            amount=coin_amount,
                                            transaction_type="learning_earn",
                                            ref_id=attempt.id,
                                            narrative=f"AI辅导：{topic_label}",
                                            narrative_emoji="📚",
                                        )
                                        db.add(txn)
                                        coins_earned = coin_amount

                                # Check milestones + challenges (non-blocking)
                                try:
                                    from apps.backend.app.services.milestones import (
                                        check_and_record_milestones,
                                    )

                                    check_and_record_milestones(
                                        db,
                                        child.id,
                                        int(self._family_id),
                                        {"instance": None, "wish": None},
                                    )
                                except Exception:
                                    logger.warning(
                                        "[mcp_session] milestone check failed "
                                        "for child=%s (non-blocking)",
                                        child.id,
                                        exc_info=True,
                                    )

                                data = {
                                    "ok": True,
                                    "session_id": str(session_id),
                                    "recommendation": rec,
                                    "coins_earned": coins_earned,
                                    "assessment_attempt_id": str(attempt.id),
                                }
                else:
                    raise ValueError(f"Unknown tool: {name}")

                logger.info(
                    "[mcp_session] family=%s caller_user_id=%s caller_role=%s tool=%s args=%s ok",
                    self._family_id,
                    self._caller_user_id,
                    self._caller_role,
                    name,
                    arguments,
                )
                return [
                    TextContent(
                        type="text",
                        text=json.dumps(data, ensure_ascii=False, default=str),
                    )
                ]
            except Exception as e:
                logger.error(
                    "[mcp_session] family=%s caller_user_id=%s caller_role=%s tool=%s failed: %s",
                    self._family_id,
                    self._caller_user_id,
                    self._caller_role,
                    name,
                    e,
                )
                return [
                    TextContent(
                        type="text",
                        text=json.dumps(
                            {"error": "查询失败，请稍后重试"}, ensure_ascii=False
                        ),
                    )
                ]
