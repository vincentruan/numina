"""MCP Session — caller-bound tool registry for AI Chat data access.

Tenant + caller isolation via __slots__:
- _family_id, _caller_user_id, _caller_role are captured at construction and frozen
- Tool handlers NEVER read family_id/caller from tool args — only from self
"""

import contextlib
import json
import time
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
from packages.core.logging import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Smart Tutor phase transition rules (Issue #191, Gap 8)
# Mirrors the Socratic Guidance Protocol in SKILL.md.
# ---------------------------------------------------------------------------
VALID_PHASE_TRANSITIONS: dict[str, set[str]] = {
    "DIAGNOSE": {"FOCUSED_GUIDANCE", "PREREQUISITE_RETRACE", "MISCONCEPTION_CORRECTION"},
    "FOCUSED_GUIDANCE": {"VERIFY", "DIAGNOSE"},
    "PREREQUISITE_RETRACE": {"VERIFY", "DIAGNOSE"},
    "MISCONCEPTION_CORRECTION": {"VERIFY", "DIAGNOSE"},
    "VERIFY": {"CONSOLIDATE", "DIAGNOSE"},
    "CONSOLIDATE": set(),  # terminal phase
}


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
        "_allow_write",
        "_allowed_tools",
        "_audit_callback",
    )

    def __init__(
        self,
        family_id: str,
        caller_user_id: str,
        caller_role: str,
        thread_id: str | None = None,
        allow_write: bool = False,
        allowed_tools: list[str] | None = None,
        audit_callback: Any | None = None,
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
        self._allow_write = allow_write
        self._allowed_tools = allowed_tools
        self._audit_callback = audit_callback
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
        from apps.backend.app.services.mcp_tool_registry import (
            TOOL_REGISTRY,
            list_tools_for_role,
        )

        if self._caller_role == "external_token" and self._allow_write:
            # External token with write access: include all tools
            metas = list(TOOL_REGISTRY.values())
        else:
            metas = list_tools_for_role(self._caller_role)

        # Per-tool whitelist filter for external_token callers
        if self._caller_role == "external_token" and self._allowed_tools is not None:
            allowed = set(self._allowed_tools)
            metas = [m for m in metas if m.name in allowed]

        return [
            Tool(
                name=meta.name,
                description=meta.description,
                inputSchema=meta.input_schema,
            )
            for meta in metas
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

        _t0 = time.perf_counter()
        meta = get_tool(name)

        # Re-validate caller on every tool call (fresh role + active check from DB)
        with SessionLocal() as db:
            try:
                user = _get_caller_user(self._family_id, self._caller_user_id, db)
            except RuntimeError:
                logger.warning(
                    "[mcp_session] permission_denied family=%s caller_user_id=%s caller_role=%s tool=%s (caller_invalid)",
                    self._family_id,
                    self._caller_user_id,
                    self._caller_role,
                    name,
                )
                if self._audit_callback is not None:
                    with contextlib.suppress(Exception):
                        self._audit_callback(
                            event_type="tool_call",
                            tool_name=name,
                            status="permission_denied",
                            duration_ms=round((time.perf_counter() - _t0) * 1000),
                            args_digest=arguments,
                            error_code="caller_invalid",
                        )
                return [
                    TextContent(
                        type="text",
                        text=json.dumps(
                            {
                                "error": "permission_denied",
                                "retryable": False,
                                "reason": "调用者身份无效",
                            },
                            ensure_ascii=False,
                        ),
                    )
                ]

            # Role check using fresh user.role (not cached self._caller_role)
            # external_token with allow_write bypasses the role filter
            _role_allowed = (
                user.role in meta.allowed_roles
                if meta
                else False
            )
            _write_bypass = (
                meta is not None
                and user.role == "external_token"
                and self._allow_write
            )
            if not meta or (not _role_allowed and not _write_bypass):
                logger.warning(
                    "[mcp_session] permission_denied family=%s caller_user_id=%s caller_role=%s attempted_tool=%s",
                    self._family_id,
                    self._caller_user_id,
                    user.role,
                    name,
                )
                if self._audit_callback is not None:
                    with contextlib.suppress(Exception):
                        self._audit_callback(
                            event_type="tool_call",
                            tool_name=name,
                            status="permission_denied",
                            duration_ms=round((time.perf_counter() - _t0) * 1000),
                            args_digest=arguments,
                            error_code="role_not_allowed",
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

            # Per-tool whitelist gate for external_token callers
            if (
                user.role == "external_token"
                and self._allowed_tools is not None
                and name not in self._allowed_tools
            ):
                logger.warning(
                    "[mcp_session] permission_denied family=%s caller_user_id=%s caller_role=%s attempted_tool=%s (not in allowed_tools)",
                    self._family_id,
                    self._caller_user_id,
                    user.role,
                    name,
                )
                if self._audit_callback is not None:
                    with contextlib.suppress(Exception):
                        self._audit_callback(
                            event_type="tool_call",
                            tool_name=name,
                            status="permission_denied",
                            duration_ms=round((time.perf_counter() - _t0) * 1000),
                            args_digest=arguments,
                            error_code="not_in_allowed_tools",
                        )
                return [
                    TextContent(
                        type="text",
                        text=json.dumps(
                            {
                                "error": "permission_denied",
                                "retryable": False,
                                "reason": "该工具未对外部客户端开放",
                            },
                            ensure_ascii=False,
                        ),
                    )
                ]

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
                            child_user = (
                                db.query(User)
                                .filter(
                                    User.id == child_id,
                                    User.family_id == int(self._family_id),
                                )
                                .first()
                            )
                            if not child_user:
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
                                    "evidence_criteria": topic.evidence_json or [],
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
                            profile_query = db.query(LearningProgress).filter(
                                LearningProgress.child_id == child_id
                            )
                            if subject:
                                # subject lives on LearningTopic; join to filter
                                profile_query = profile_query.join(
                                    LearningTopic,
                                    LearningProgress.topic_id == LearningTopic.id,
                                ).filter(LearningTopic.subject == subject)
                            profile_progresses: list = profile_query.all()

                            data = {
                                "child_id": str(child_id),
                                "total_topics": len(profile_progresses),
                                "mastered": sum(
                                    1 for p in profile_progresses if p.mastery_level == "mastered"
                                ),
                                "learning": sum(
                                    1 for p in profile_progresses if p.mastery_level == "learning"
                                ),
                                "available": sum(
                                    1 for p in profile_progresses if p.mastery_level == "available"
                                ),
                                "review": sum(
                                    1 for p in profile_progresses if p.mastery_level == "review"
                                ),
                                "locked": sum(
                                    1 for p in profile_progresses if p.mastery_level == "locked"
                                ),
                                "assessing": sum(
                                    1 for p in profile_progresses if p.mastery_level == "assessing"
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
                            session_child = (
                                db.query(User)
                                .filter(
                                    User.id == session.child_id,
                                    User.family_id == int(self._family_id),
                                )
                                .first()
                            )
                            if not session_child:
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
                                    progress_service.check_and_notify_streak(
                                        db, child.id, session.topic_id,
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
                                                # Best-effort: advance learning path if topic is part of one
                                                try:
                                                    from apps.backend.app.services.learning import (
                                                        path_service,
                                                    )

                                                    path_service.try_advance_path_for_topic(
                                                        db,
                                                        child.id,
                                                        int(self._family_id),
                                                        progress.topic_id,
                                                    )
                                                except Exception as e:
                                                    logger.warning(
                                                        "Path advancement failed for topic %s: %s",
                                                        progress.topic_id,
                                                        e,
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

                                # Award XP for AI assessment mastery (best-effort)
                                try:
                                    from apps.backend.app.services.learning import (
                                        stats_service,
                                    )

                                    xp_amount = {"mastered": 20, "needs_review": 10, "keep_learning": 5}.get(rec, 0)
                                    if xp_amount > 0:
                                        stats_service.award_xp(
                                            db, child.id, int(self._family_id), xp_amount=xp_amount
                                        )
                                except Exception:
                                    logger.warning(
                                        "[mcp_session] XP award failed for child=%s (non-blocking)",
                                        child.id,
                                        exc_info=True,
                                    )

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

                                # Commit all progress/coin/XP/milestone changes atomically
                                db.commit()

                                data = {
                                    "ok": True,
                                    "session_id": str(session_id),
                                    "recommendation": rec,
                                    "coins_earned": coins_earned,
                                    "assessment_attempt_id": str(attempt.id),
                                }
                # ── Smart-tutor tools (Issue #191) ─────────────────────
                elif name == "get_guided_question":
                    from apps.backend.app.services.learning.content_safety_filter import (
                        filter_tutor_output,
                    )
                    from packages.db.models.learning.practice import PracticeAttempt
                    from packages.db.models.learning.question import Question
                    from packages.db.models.learning.topic import LearningTopic

                    try:
                        question_id = int(arguments["question_id"])
                        child_id = int(arguments["child_id"])
                        topic_id = int(arguments["topic_id"])
                        if question_id <= 0 or child_id <= 0 or topic_id <= 0:
                            raise ValueError("IDs must be positive integers")
                    except (ValueError, TypeError, KeyError) as exc:
                        data = {"error": "invalid_arguments", "detail": str(exc)}
                    else:
                        # Family-scope validation
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
                            question = (
                                db.query(Question)
                                .filter(Question.id == question_id)
                                .first()
                            )
                            if not question:
                                data = {"error": "question_not_found"}
                            else:
                                topic = (
                                    db.query(LearningTopic)
                                    .filter(LearningTopic.id == topic_id)
                                    .first()
                                )
                                if not topic:
                                    data = {"error": "topic_not_found"}
                                else:
                                    # Gap 7: Content safety filter on question stems (Issue #191)
                                    stem_safe = filter_tutor_output(
                                        question.stem or "", child_id=child_id
                                    )
                                    stem_zh_safe = filter_tutor_output(
                                        question.stem_zh or "", child_id=child_id
                                    )
                                    if not stem_safe.safe or not stem_zh_safe.safe:
                                        data = {
                                            "error": "content_safety_violation",
                                            "detail": "Question content failed safety check",
                                        }
                                    else:
                                        # Recent attempts for this question (error patterns)
                                        recent_attempts = (
                                            db.query(PracticeAttempt)
                                            .filter(
                                                PracticeAttempt.child_id == child_id,
                                                PracticeAttempt.question_id == question_id,
                                            )
                                            .order_by(PracticeAttempt.created_at.desc())
                                            .limit(5)
                                            .all()
                                        )
                                        data = {
                                            "question_id": str(question.id),
                                            "topic_id": str(topic_id),
                                            "stem": question.stem,
                                            "stem_zh": question.stem_zh,
                                            "question_type": question.question_type,
                                            "options": question.options,
                                            "difficulty": question.difficulty,
                                            "bloom_level": question.bloom_level,
                                            "age_group": question.age_group,
                                            # Do NOT expose solution — Socratic method requires
                                            # guiding the child, not giving answers directly
                                            "topic_name": topic.name_zh or topic.name,
                                            "topic_subject": topic.subject,
                                            "recent_attempts": [
                                                {
                                                    "is_correct": a.is_correct,
                                                    "answer": a.user_answer,
                                                    "attempt_number": a.attempt_number,
                                                }
                                                for a in recent_attempts
                                            ],
                                            "attempt_count": len(recent_attempts),
                                        }
                elif name == "submit_guided_answer":
                    try:
                        question_id = int(arguments["question_id"])
                        child_id = int(arguments["child_id"])
                        session_id = int(arguments["session_id"])
                        step_number = int(arguments["step_number"])
                        answer_text = str(arguments["answer_text"]).strip()
                        if (
                            question_id <= 0
                            or child_id <= 0
                            or session_id <= 0
                            or step_number <= 0
                        ):
                            raise ValueError("Numeric IDs must be positive")
                        if not answer_text:
                            raise ValueError("answer_text must not be empty")
                        if step_number > 20:
                            raise ValueError("step_number exceeds maximum (20)")
                    except (ValueError, TypeError, KeyError) as exc:
                        data = {"error": "invalid_arguments", "detail": str(exc)}
                    else:
                        # Family-scope validation
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
                            # Lightweight signal classification — not a correctness
                            # judgement.  The LLM (Socratic skill) decides whether
                            # the answer is right; we only tag structural signals
                            # so the skill prompt has them as context.
                            answer_lower = answer_text.lower()
                            has_numbers = any(c.isdigit() for c in answer_text)
                            has_reasoning = any(
                                kw in answer_lower
                                for kw in ("因为", "所以", "我觉得", "由于", "because", "so", "i think")
                            )
                            is_question = answer_text.endswith(("?", "？"))
                            is_empty_vague = answer_text in (
                                "不知道",
                                "不会",
                                "?",
                                "？",
                                "idk",
                            )

                            if is_empty_vague:
                                quality = "no_response"
                            elif has_numbers or has_reasoning:
                                quality = "attempted"
                            else:
                                quality = "attempted"

                            data = {
                                "question_id": str(question_id),
                                "session_id": str(session_id),
                                "step_number": step_number,
                                "answer_text": answer_text,
                                "quality_assessment": quality,
                                "has_reasoning": has_reasoning,
                                "has_numbers": has_numbers,
                                "is_question": is_question,
                            }
                elif name == "get_knowledge_bridge":
                    from apps.backend.app.services.learning.content_safety_filter import (
                        filter_tutor_output,
                    )
                    from packages.db.models.learning.progress import LearningProgress
                    from packages.db.models.learning.topic import (
                        LearningDependency,
                        LearningTopic,
                    )

                    try:
                        topic_id = int(arguments["topic_id"])
                        child_id = int(arguments["child_id"])
                        depth = int(arguments.get("depth", 2))
                        if topic_id <= 0 or child_id <= 0:
                            raise ValueError("IDs must be positive")
                        depth = max(1, min(depth, 3))  # clamp 1-3
                    except (ValueError, TypeError, KeyError) as exc:
                        data = {"error": "invalid_arguments", "detail": str(exc)}
                    else:
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
                            # Build prerequisite chain via BFS
                            chain = []
                            visited = set()
                            queue = [(topic_id, 0)]  # (topic_id, current_depth)

                            while queue:
                                current_id, current_depth = queue.pop(0)
                                if current_id in visited or current_depth > depth:
                                    continue
                                visited.add(current_id)

                                current_topic = (
                                    db.query(LearningTopic)
                                    .filter(LearningTopic.id == current_id)
                                    .first()
                                )
                                progress = (
                                    db.query(LearningProgress)
                                    .filter_by(
                                        child_id=child_id, topic_id=current_id
                                    )
                                    .first()
                                )

                                chain.append(
                                    {
                                        "topic_id": str(current_id),
                                        "name": (
                                            current_topic.name_zh or current_topic.name
                                            if current_topic
                                            else None
                                        ),
                                        "subject": (
                                            current_topic.subject
                                            if current_topic
                                            else None
                                        ),
                                        "mastery_level": (
                                            progress.mastery_level
                                            if progress
                                            else "locked"
                                        ),
                                        "depth": current_depth,
                                        "is_current": current_id == topic_id,
                                    }
                                )

                                # Find prerequisites
                                if current_depth < depth:
                                    prereqs = (
                                        db.query(LearningDependency)
                                        .filter(
                                            LearningDependency.topic_id == current_id
                                        )
                                        .all()
                                    )
                                    for prereq in prereqs:
                                        if prereq.prerequisite_id not in visited:
                                            queue.append(
                                                (prereq.prerequisite_id, current_depth + 1)
                                            )

                            # Find the first broken prerequisite (knowledge gap)
                            broken_link = None
                            for node in reversed(chain):
                                if node["mastery_level"] in ("locked", "available"):
                                    broken_link = node
                                    break

                            # Gap 7: Content safety filter on topic names (Issue #191)
                            for node in chain:
                                if node["name"]:
                                    result = filter_tutor_output(
                                        node["name"], child_id=child_id
                                    )
                                    if not result.safe:
                                        node["name"] = "[内容已被过滤]"

                            data = {
                                "topic_id": str(topic_id),
                                "child_id": str(child_id),
                                "prerequisite_chain": chain,
                                "broken_link": broken_link,
                                "total_depth": depth,
                            }
                elif name == "get_teacher_persona":
                    # Static persona configuration — no DB query needed
                    _PERSONA_MATRIX = {
                        ("math", "low"): {
                            "style": "故事化具象型",
                            "style_en": "Story-Concrete",
                            "description": "用故事、动物和日常物品（苹果、积木、玩具）来讲解数学概念",
                            "tone": "温暖、耐心、充满鼓励",
                            "max_sentence_length": 15,
                            "use_emoji": True,
                            "strategies": [
                                "visual_analogy",
                                "story_problem",
                                "hands_on_counting",
                            ],
                        },
                        ("math", "mid"): {
                            "style": "逻辑推理趣味型",
                            "style_en": "Logic-Fun",
                            "description": "通过谜题和挑战引入逻辑推理，把学习变成侦探游戏",
                            "tone": "活泼、挑战性、引导思考",
                            "max_sentence_length": 25,
                            "use_emoji": False,
                            "strategies": [
                                "puzzle_framing",
                                "multiple_solutions",
                                "explain_reasoning",
                            ],
                        },
                        ("math", "high"): {
                            "style": "抽象证明方法论型",
                            "style_en": "Abstract-Method",
                            "description": "引导抽象推理和证明，尊重独立思考，引入数学方法论",
                            "tone": "学术对话型、尊重、引导元认知",
                            "max_sentence_length": 40,
                            "use_emoji": False,
                            "strategies": [
                                "proof_guidance",
                                "metacognition",
                                "real_world_connection",
                            ],
                        },
                        ("chinese", "low"): {
                            "style": "感官体验型",
                            "style_en": "Sensory-Experience",
                            "description": "调动五感体验，用生动意象和情感共鸣来教语文",
                            "tone": "感性、温柔、富有画面感",
                            "max_sentence_length": 15,
                            "use_emoji": True,
                            "strategies": [
                                "sensory_language",
                                "emotional_connection",
                                "read_aloud",
                            ],
                        },
                        ("chinese", "mid"): {
                            "style": "文本分析创意型",
                            "style_en": "Text-Analysis-Creative",
                            "description": "引导文本分析和创意表达，培养阅读理解和写作兴趣",
                            "tone": "启发式、创意引导",
                            "max_sentence_length": 25,
                            "use_emoji": False,
                            "strategies": [
                                "text_analysis",
                                "creative_expression",
                                "vocabulary_context",
                            ],
                        },
                        ("chinese", "high"): {
                            "style": "文学鉴赏批判型",
                            "style_en": "Literary-Critical",
                            "description": "深度文学鉴赏和批判性思维，培养独立思考能力",
                            "tone": "学术对话、思辨、尊重",
                            "max_sentence_length": 40,
                            "use_emoji": False,
                            "strategies": [
                                "literary_analysis",
                                "critical_thinking",
                                "cross_discipline",
                            ],
                        },
                        ("english", "low"): {
                            "style": "情境模拟型",
                            "style_en": "Situation-Simulation",
                            "description": "创设真实情境，在场景中自然习得英语",
                            "tone": "活泼、重复、趣味",
                            "max_sentence_length": 15,
                            "use_emoji": True,
                            "strategies": [
                                "role_play",
                                "repetition_variety",
                                "tpr_commands",
                            ],
                        },
                        ("english", "mid"): {
                            "style": "阅读理解语法型",
                            "style_en": "Reading-Comprehension-Grammar",
                            "description": "通过阅读引导理解，在语境中探索语法规律",
                            "tone": "引导式、pattern-based",
                            "max_sentence_length": 25,
                            "use_emoji": False,
                            "strategies": [
                                "comprehension_questions",
                                "pattern_discovery",
                                "word_families",
                            ],
                        },
                        ("english", "high"): {
                            "style": "写作训练文化型",
                            "style_en": "Writing-Culture",
                            "description": "引导写作训练和文化理解，培养英语表达能力",
                            "tone": "对话式、文化引导",
                            "max_sentence_length": 40,
                            "use_emoji": False,
                            "strategies": [
                                "essay_structure",
                                "cultural_context",
                                "authentic_voice",
                            ],
                        },
                        ("science", "low"): {
                            "style": "观察好奇型",
                            "style_en": "Observation-Curiosity",
                            "description": "激发好奇心和观察力，用简单实验探索科学",
                            "tone": "充满好奇、惊叹、引导观察",
                            "max_sentence_length": 15,
                            "use_emoji": True,
                            "strategies": [
                                "wonder_questions",
                                "observation_prompts",
                                "simple_experiments",
                            ],
                        },
                        ("science", "mid"): {
                            "style": "实验归纳型",
                            "style_en": "Experiment-Induction",
                            "description": "引导科学方法和归纳推理，培养系统性思维",
                            "tone": "探索式、引导归纳",
                            "max_sentence_length": 25,
                            "use_emoji": False,
                            "strategies": [
                                "hypothesis_guide",
                                "pattern_recognition",
                                "variable_thinking",
                            ],
                        },
                        ("science", "high"): {
                            "style": "假设检验型",
                            "style_en": "Hypothesis-Testing",
                            "description": "严格的假设检验和数据分析，培养科学方法论",
                            "tone": "严谨、学术、尊重",
                            "max_sentence_length": 40,
                            "use_emoji": False,
                            "strategies": [
                                "rigorous_hypothesis",
                                "data_analysis",
                                "literature_connection",
                            ],
                        },
                    }

                    subject = arguments.get("subject", "math").lower()
                    age_group = arguments.get("age_group", "mid").lower()
                    persona = _PERSONA_MATRIX.get((subject, age_group))

                    if persona is None:
                        # Fallback: use math persona for unknown subjects
                        persona = _PERSONA_MATRIX.get(("math", age_group), _PERSONA_MATRIX[("math", "mid")])

                    data = {
                        "subject": subject,
                        "age_group": age_group,
                        **persona,
                    }
                elif name == "record_tutoring_step":
                    from packages.db.models.learning.session import LearningSession

                    try:
                        session_id = int(arguments["session_id"])
                        question_id = int(arguments["question_id"])
                        step_number = int(arguments["step_number"])
                        phase = arguments["phase"]
                        child_response_quality = arguments["child_response_quality"]
                        next_phase = arguments["next_phase"]
                        if session_id <= 0 or question_id <= 0 or step_number <= 0:
                            raise ValueError("Numeric IDs must be positive")
                    except (ValueError, TypeError, KeyError) as exc:
                        data = {"error": "invalid_arguments", "detail": str(exc)}
                    else:
                        # Family-scope validation
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
                            # Gap 8: Validate Socratic phase transition (Issue #191)
                            if phase not in VALID_PHASE_TRANSITIONS:
                                data = {
                                    "error": "invalid_phase",
                                    "detail": f"Unknown phase: {phase}",
                                    "allowed_phases": list(VALID_PHASE_TRANSITIONS.keys()),
                                }
                            elif next_phase and next_phase not in VALID_PHASE_TRANSITIONS[phase]:
                                data = {
                                    "error": "invalid_phase_transition",
                                    "detail": f"Transition {phase} → {next_phase} is not allowed",
                                    "allowed_next_phases": sorted(VALID_PHASE_TRANSITIONS[phase]),
                                }
                            else:
                                # Store tutoring step data as JSON on the session's
                                # progress field. We accumulate steps in a list.
                                # This avoids a new DB migration for MVP.
                                existing_steps_raw = session.progress_json
                                try:
                                    existing_steps = json.loads(existing_steps_raw) if existing_steps_raw else []
                                    if not isinstance(existing_steps, list):
                                        existing_steps = []
                                except (json.JSONDecodeError, TypeError):
                                    existing_steps = []

                                step_record = {
                                    "step": step_number,
                                    "phase": phase,
                                    "quality": child_response_quality,
                                    "next_phase": next_phase,
                                    "strategy": arguments.get("ai_strategy", ""),
                                    "question_id": str(question_id),
                                }
                                existing_steps.append(step_record)

                                session.progress_json = json.dumps(existing_steps, ensure_ascii=False)
                                db.commit()

                                data = {
                                    "ok": True,
                                    "session_id": str(session_id),
                                    "step_number": step_number,
                                    "total_steps": len(existing_steps),
                                    "phase": phase,
                                    "next_phase": next_phase,
                                }
                elif name == "get_taxonomy_topic":
                    from apps.backend.app.services.learning import topic_service

                    topic_key = arguments.get("topic_key", "")
                    source_taxonomy = arguments.get("source_taxonomy")

                    if not topic_key or not isinstance(topic_key, str):
                        data = {"error": "invalid_arguments", "detail": "topic_key is required and must be a string"}
                    else:
                        topic = topic_service.get_topic_by_key(
                            db, topic_key, source_taxonomy=source_taxonomy
                        )
                        if not topic:
                            data = {"error": "topic_not_found", "topic_key": topic_key}
                        else:
                            data = {
                                "topic_id": str(topic.id),
                                "topic_key": topic.topic_key,
                                "name": topic.name,
                                "name_zh": topic.name_zh,
                                "description": topic.description,
                                "description_zh": topic.description_zh,
                                "subject": topic.subject,
                                "domain": topic.domain,
                                "age_group": topic.age_group,
                                "evidence_criteria": topic.evidence_json or [],
                                "assessment_prompt": topic.assessment_prompt,
                                "source_taxonomy": topic.source_taxonomy,
                            }
                elif name == "get_taxonomy_dependencies":
                    from apps.backend.app.services.learning import topic_service

                    topic_key = arguments.get("topic_key", "")

                    if not topic_key or not isinstance(topic_key, str):
                        data = {"error": "invalid_arguments", "detail": "topic_key is required"}
                    else:
                        topic = topic_service.get_topic_by_key(db, topic_key)
                        if not topic:
                            data = {"error": "topic_not_found", "topic_key": topic_key}
                        else:
                            graph = topic_service.get_topic_graph(
                                db, topic.id, source_taxonomy=topic.source_taxonomy
                            )
                            prereqs = []
                            if graph and "prerequisites" in graph:
                                for p in graph["prerequisites"]:
                                    prereqs.append({
                                        "topic_id": str(p.get("id", "")),
                                        "topic_key": p.get("topic_key", ""),
                                        "name": p.get("name", ""),
                                        "name_zh": p.get("name_zh", ""),
                                        "strength": p.get("strength", "weak"),
                                        "reason": p.get("reason", ""),
                                    })
                            data = {
                                "topic_key": topic_key,
                                "prerequisites": prereqs,
                            }
                elif name == "list_taxonomy_topics":
                    from apps.backend.app.services.learning import topic_service

                    subject = arguments.get("subject", "")
                    domain = arguments.get("domain")
                    age_group = arguments.get("age_group")
                    source_taxonomy = arguments.get("source_taxonomy")
                    try:
                        limit = max(1, min(int(arguments.get("limit", 50)), 200))
                    except (ValueError, TypeError):
                        limit = 50

                    if not subject or not isinstance(subject, str):
                        data = {"error": "invalid_arguments", "detail": "subject is required"}
                    else:
                        topics = topic_service.list_topics(
                            db,
                            subject=subject,
                            domain=domain,
                            age_group=age_group,
                            limit=limit,
                            source_taxonomy=source_taxonomy,
                        )
                        data = {
                            "count": len(topics),
                            "topics": [
                                {
                                    "topic_id": str(t.id),
                                    "topic_key": t.topic_key,
                                    "name": t.name,
                                    "name_zh": t.name_zh,
                                    "subject": t.subject,
                                    "domain": t.domain,
                                    "age_group": t.age_group,
                                }
                                for t in topics
                            ],
                        }
                elif name == "validate_question":
                    from apps.backend.app.services.learning import question_service

                    try:
                        topic_id = int(arguments["topic_id"])
                        question_type = arguments["question_type"]
                        stem = arguments["stem"]
                        answer = arguments["answer"]
                        age_group = arguments["age_group"]
                        options = arguments.get("options")
                    except (ValueError, TypeError, KeyError) as exc:
                        data = {"error": "invalid_arguments", "detail": str(exc)}
                    else:
                        errors = question_service.validate_question(
                            topic_id=topic_id,
                            question_type=question_type,
                            stem=stem,
                            answer=answer,
                            age_group=age_group,
                            db=db,
                            options=options,
                        )
                        data = {
                            "passed": len(errors) == 0,
                            "errors": errors,
                        }
                elif name == "get_child_weak_points":
                    from apps.backend.app.services.learning import zone_service
                    from packages.db.models.learning.progress import LearningProgress
                    from packages.db.models.learning.topic import LearningTopic

                    try:
                        child_id = int(arguments["child_id"])
                        if child_id <= 0:
                            raise ValueError("child_id must be a positive integer")
                    except (ValueError, TypeError, KeyError) as exc:
                        data = {"error": "invalid_arguments", "detail": str(exc)}
                    else:
                        subject = arguments.get("subject")
                        try:
                            limit = max(1, min(int(arguments.get("limit", 10)), 100))
                        except (ValueError, TypeError):
                            limit = 10

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
                            data = {"error": "child_not_in_family", "child_id": str(child_id)}
                        else:
                            # Step 1: Query progress rows with low mastery
                            wp_query = db.query(LearningProgress).filter(
                                LearningProgress.child_id == child_id,
                                LearningProgress.mastery_level.in_(
                                    ["available", "learning", "review"]
                                ),
                            )
                            if subject:
                                wp_query = wp_query.join(
                                    LearningTopic,
                                    LearningProgress.topic_id == LearningTopic.id,
                                ).filter(LearningTopic.subject == subject)
                            wp_progresses: list[LearningProgress] = wp_query.limit(limit).all()

                            # Batch-fetch all topics to avoid N+1 queries
                            topic_ids = {wp.topic_id for wp in wp_progresses}

                            # Build result with mastery_level priority for sorting
                            _LEVEL_PRIORITY = {"available": 0, "learning": 1, "review": 2}
                            result_map: dict[int, dict] = {}

                            if topic_ids:
                                topic_rows = (
                                    db.query(LearningTopic)
                                    .filter(LearningTopic.id.in_(topic_ids))
                                    .all()
                                )
                                topic_by_id = {t.id: t for t in topic_rows}
                            else:
                                topic_by_id = {}

                            for wp in wp_progresses:
                                wp_topic = topic_by_id.get(wp.topic_id)
                                if wp_topic:
                                    result_map[wp.topic_id] = {
                                        "topic_id": str(wp.topic_id),
                                        "topic_key": wp_topic.topic_key,
                                        "name": wp_topic.name,
                                        "name_zh": wp_topic.name_zh,
                                        "mastery_level": wp.mastery_level,
                                        "is_breakpoint": False,
                                    }

                            # Step 2: Get breakpoints from zone_service
                            try:
                                breakpoints = zone_service.find_breakpoint_topics(
                                    db, child_id
                                )
                                for bp in breakpoints:
                                    # Resolve topic from batch cache or DB
                                    bp_topic = topic_by_id.get(bp.topic_id)
                                    if not bp_topic:
                                        bp_topic = (
                                            db.query(LearningTopic)
                                            .filter(LearningTopic.id == bp.topic_id)
                                            .first()
                                        )
                                        if bp_topic:
                                            topic_by_id[bp.topic_id] = bp_topic
                                    # Apply subject filter
                                    if subject and (not bp_topic or bp_topic.subject != subject):
                                        continue
                                    if bp.topic_id not in result_map and bp_topic:
                                        result_map[bp.topic_id] = {
                                            "topic_id": str(bp.topic_id),
                                            "topic_key": bp_topic.topic_key,
                                            "name": bp_topic.name,
                                            "name_zh": bp_topic.name_zh,
                                            "mastery_level": "available",
                                            "is_breakpoint": True,
                                        }
                            except Exception:
                                logger.warning(
                                    "[mcp_session] find_breakpoint_topics failed "
                                    "for child=%s (non-blocking)",
                                    child_id,
                                    exc_info=True,
                                )

                            # Step 3: Sort by mastery_level priority and limit
                            items = sorted(
                                result_map.values(),
                                key=lambda x: _LEVEL_PRIORITY.get(
                                    x["mastery_level"], 99
                                ),
                            )[:limit]

                            data = {
                                "child_id": str(child_id),
                                "count": len(items),
                                "weak_points": items,
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
                if self._audit_callback is not None:
                    with contextlib.suppress(Exception):
                        self._audit_callback(
                            event_type="tool_call",
                            tool_name=name,
                            status="success",
                            duration_ms=round((time.perf_counter() - _t0) * 1000),
                            args_digest=arguments,
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
                if self._audit_callback is not None:
                    with contextlib.suppress(Exception):
                        self._audit_callback(
                            event_type="tool_call",
                            tool_name=name,
                            status="error",
                            duration_ms=round((time.perf_counter() - _t0) * 1000),
                            args_digest=arguments,
                            error_code="tool_execution_error",
                        )
                return [
                    TextContent(
                        type="text",
                        text=json.dumps(
                            {"error": "查询失败，请稍后重试"}, ensure_ascii=False
                        ),
                    )
                ]
