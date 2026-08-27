import asyncio
import json
import logging
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from apps.backend.app.auth.deps import require_adult
from apps.backend.app.database import get_db
from apps.backend.app.errors import AppError, ErrorCode
from apps.backend.app.models.ai_chat_session import AIChatSession
from apps.backend.app.models.user import User
from apps.backend.app.responses import SnowflakeResponse
from apps.backend.app.routers._ai_events_helper import check_circuit_blocked
from apps.backend.app.schemas.dashboard import (
    AllocationResponse,
    DailyCostItem,
    EducationRewardSummaryResponse,
    ExpiringSoonItem,
    InsightsResponse,
    InvestmentReturnItem,
    LiabilityAllocationResponse,
    LowUsageItem,
    NewAssetsResponse,
    OverviewResponse,
    TopAssetItem,
    TrendResponse,
    UpcomingPaymentsResponse,
)
from apps.backend.app.services import dashboard as dashboard_service
from apps.backend.app.services.agent_client import AgentClient
from apps.backend.app.services.ai_task_service import AITaskService
from apps.backend.app.services.bridge_consumer import (
    _pump_agent_sse_to_bridge,
    _spawn_lifecycle_consumer,
    consume_task_stream,
    get_shared_bridge,
)
from apps.backend.app.services.chat_session import ChatSessionService
from apps.backend.app.services.subscriber_registry import tracked_sse_stream

router = APIRouter(prefix="/dashboard", tags=["dashboard"])
logger = logging.getLogger(__name__)


@router.get("/overview", response_model=OverviewResponse)
def get_overview(
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    return dashboard_service.get_overview(db, user)


@router.get("/allocation", response_model=AllocationResponse)
def get_allocation(
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    return dashboard_service.get_allocation(db, user)


@router.get("/liability-allocation", response_model=LiabilityAllocationResponse)
def get_liability_allocation(
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    return dashboard_service.get_liability_allocation(db, user)


@router.get("/trend", response_model=TrendResponse)
def get_trend(
    period: Literal["month", "quarter", "year"] = Query("month"),
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    return dashboard_service.get_trend(db, user, period)


@router.get("/top-assets", response_model=list[TopAssetItem])
def get_top_assets(
    limit: int = Query(10),
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    return dashboard_service.get_top_assets(db, user, limit)


@router.get("/daily-cost-ranking", response_model=list[DailyCostItem])
def get_daily_cost_ranking(
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    return dashboard_service.get_daily_cost_ranking(db, user, limit)


@router.get("/low-usage-assets", response_model=list[LowUsageItem])
def get_low_usage_assets(
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    return dashboard_service.get_low_usage_assets(db, user)


@router.get("/investment-returns", response_model=list[InvestmentReturnItem])
def get_investment_returns(
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    return dashboard_service.get_investment_returns(db, user)


@router.get("/education-reward-summary", response_model=EducationRewardSummaryResponse)
def get_education_reward_summary(
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    """B1 教育奖励支出专项统计（累计 + 本月 + 笔数）。"""
    return dashboard_service.get_education_reward_summary(db, user)


@router.get("/states-summary")
def get_states_summary(
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    return dashboard_service.get_states_summary(db, user)


@router.get("/home-assets")
def get_home_assets(
    limit: int = Query(5, ge=1, le=20),
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    """Get assets grouped by status for home page display."""
    return dashboard_service.get_home_assets(db, user, limit)


@router.get("/home-assets/{status}/categories")
def get_home_assets_category_counts(
    status: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    """获取指定状态下各分类的资产数量（用于分类导航）"""
    valid_statuses = ["in_use", "idle", "sold", "retired"]
    if status not in valid_statuses:
        raise AppError(
            ErrorCode.DASHBOARD_INVALID_STATUS,
            details=f"Invalid status: {status}. Must be one of {valid_statuses}",
        )
    return dashboard_service.get_home_assets_category_counts(db, user, status)


@router.get("/home-assets/{status}")
def get_home_assets_paginated(
    status: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    category_id: str | None = Query(None),
    search: str | None = Query(None),
    sort_by: str | None = Query(None),
    sort_order: str = Query("desc"),
    asset_type: str | None = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    """分页获取指定状态的资产列表（支持搜索/排序/类型筛选）"""
    valid_statuses = ["in_use", "idle", "sold", "retired"]
    if status not in valid_statuses:
        raise AppError(
            ErrorCode.DASHBOARD_INVALID_STATUS,
            details=f"Invalid status: {status}. Must be one of {valid_statuses}",
        )
    return dashboard_service.get_home_assets_page(
        db,
        user,
        status,
        page,
        page_size,
        category_id,
        search,
        sort_by,
        sort_order,
        asset_type,
    )


@router.get("/new-assets", response_model=NewAssetsResponse)
def get_new_assets(
    period: Literal["month", "quarter", "year"] = Query("month"),
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    return dashboard_service.get_new_assets(db, user, period)


@router.get("/expiring-soon", response_model=list[ExpiringSoonItem])
def get_expiring_soon(
    days_threshold: int = Query(90, ge=1, le=365),
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    """
    Get assets approaching end of expected lifespan.

    Physical assets (electronics) - normal lifecycle, show with muted color.
    Financial assets (accounts, subscriptions) - needs attention, show with alert color.
    """
    return dashboard_service.get_expiring_soon_assets(db, user, days_threshold)


@router.get("/insights", response_model=InsightsResponse)
def get_insights(
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    """
    Get comprehensive insights data for the Insights tab.
    Returns S0-S5 all sections in one API call for efficiency.
    """
    return dashboard_service.get_insights(db, user)


@router.post("/narrative")
async def generate_narrative(
    request: Request,
    force: bool = Query(False),
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    """Dashboard narrative — AI-generated monthly financial story (R1-R5, U15 bridge consumer).

    Cache hit → JSON ``NarrativeResponse`` (no streaming).
    Cache miss / force → AITask tracking + bridge consumer SSE.
    Threshold gate (asset_count >= 5, history >= 1 month) → empty JSON on miss.
    """
    from apps.backend.app.database import SessionLocal
    from apps.backend.app.services.dashboard_narrative import (
        SKILL_ID,
        _build_narrative_context,
        _check_history_threshold,
    )
    from apps.backend.app.services.finance_coach_cache import (
        is_cache_fresh,
        latest_by_skill,
    )

    family_id = user.family_id

    # Phase 5.2: circuit breaker gate

    blocked_resp = check_circuit_blocked(family_id, "narrative", db)
    if blocked_resp is not None:
        return blocked_resp

    # Dynamic thresholds from family settings, fallback to module defaults
    from apps.backend.app.services.config_service import get_family_setting

    _min_asset_count = get_family_setting(
        db, int(family_id), "dashboard_min_asset_count"
    )
    _min_history_months = get_family_setting(
        db, int(family_id), "dashboard_min_history_months"
    )

    # 1. Cache check (R4) — uses request-scoped db
    if not force:
        cached = latest_by_skill(db, family_id, SKILL_ID)
        if is_cache_fresh(cached, SKILL_ID, family_id=family_id) and cached is not None:
            report = cached.report_json or {}
            narrative = report.get("narrative", "")
            from apps.backend.app.services.dashboard_narrative import (
                _extract_first_sentence,
            )

            return SnowflakeResponse(
                content={
                    "narrative": narrative or None,
                    "first_sentence": report.get(
                        "first_sentence", _extract_first_sentence(narrative)
                    ),
                    "thinking": report.get("thinking", ""),
                    "generated_at": cached.generated_at.isoformat()
                    if cached.generated_at
                    else None,
                }
            )

    # 2. Threshold check (R5) — uses request-scoped db for overview,
    #    then releases it before the history check (which opens its own session).
    overview = dashboard_service.get_overview(db, user)
    if overview.asset_count < _min_asset_count:
        return SnowflakeResponse(
            content={
                "narrative": None,
                "first_sentence": "",
                "thinking": "",
                "generated_at": None,
                "reason": "insufficient_assets",
                "asset_count": overview.asset_count,
                "threshold": _min_asset_count,
            }
        )

    # History check uses a short-lived session (P0 fix — don't hold request db)
    if not _check_history_threshold(
        int(family_id), SessionLocal, min_months=_min_history_months
    ):
        return SnowflakeResponse(
            content={
                "narrative": None,
                "first_sentence": "",
                "thinking": "",
                "generated_at": None,
                "reason": "insufficient_history",
            }
        )

    # 3. Build context — uses request-scoped db for insights
    try:
        insights = dashboard_service.get_insights(db, user)
    except Exception:
        insights = None
    context = _build_narrative_context(overview, insights)

    # 4. AITask tracking + bridge consumer SSE (U15)
    # Check if there's already a running task - resume it
    existing = AITaskService.get_running_task(family_id, SKILL_ID, db)
    if existing:
        task = existing
        session_id = str(task.session_id) if task.session_id else str(task.id)
        session = (
            db.query(AIChatSession)
            .filter_by(id=session_id, family_id=family_id)
            .first()
        )
        if not session:
            raise AppError(ErrorCode.NOT_FOUND)
    else:
        # No running task - create new session and task
        session = await ChatSessionService.create_session(
            family_id=family_id,
            user_id=user.id,
            db=db,
        )
        any_running = AITaskService.get_any_running_task(family_id, db)
        if any_running:
            task = AITaskService.create_queued_task(
                family_id=family_id,
                skill_id=SKILL_ID,
                session_id=session.id,
                db=db,
            )
            return SnowflakeResponse(
                status_code=202,
                content={
                    "status": "queued",
                    "task_id": task.id,
                    "queue_position": task.queue_position,
                },
            )
        task = AITaskService.create_task(
            family_id=family_id,
            skill_id=SKILL_ID,
            session_id=session.id,
            db=db,
        )
        session_id = str(session.id)

    task_id = str(task.id)

    # Trigger agent via single streaming POST (bridge consumer pattern).
    # NOTE: do NOT add a separate agent_client.post here — it would trigger the
    # agent TWICE (once here, once in _pump_agent_sse_to_bridge below), creating
    # two runs with different run_ids.  The interrupt strategy then leaves run 1
    # without an "end" frame, so the AITask never completes and blocks the queue.
    agent_client = AgentClient(
        family_id=str(family_id), user_id=str(user.id), timeout=120.0
    )
    agent_url = f"/internal/gateway/runs/dashboard-narrative/{session_id}"
    run_id: str | None = None

    # Phase 1: Backend-owned buffer.
    shared_bridge = get_shared_bridge()

    if not run_id:
        logger.info(
            "[narrative] task=%s run_id not yet resolved — pump will set it",
            task_id,
        )

    # Lifecycle consumer persistence callback (module-local for closure capture).
    from apps.backend.app.services.finance_coach_cache import upsert_skill_result

    async def _persist_narrative_result(_event_type: str, data: dict) -> None:
        if isinstance(data, dict) and data.get("type") == "dashboard_narrative.result":
            payload = data.get("payload")
            if payload:
                _db = SessionLocal()
                try:
                    upsert_skill_result(_db, family_id, SKILL_ID, payload)
                    _db.commit()
                finally:
                    _db.close()

    # Spawn lifecycle consumer inside the pump's on_authoritative_run_id callback
    # so it subscribes with the correct run_id.  The pump reads the agent's
    # metadata SSE event (which carries the authoritative run_id) before the
    # first publish — Content-Location may carry the first POST's run_id, while
    # the agent's interrupt strategy creates a second run with a different
    # run_id.  Subscribing with the wrong run_id means the lifecycle consumer
    # never sees events and the cache is never written.
    _lc_spawned = False
    _lc_task: asyncio.Task[None] | None = None

    def _on_lc_run_id(cl_url: str) -> None:
        """Called when Content-Location header arrives. Persist to AITask so
        ``consume_task_stream``'s run_id fallback can resolve it."""
        # Content-Location is a URL path — extract the trailing UUID and persist
        # to the AITask row. Without this, ``consume_task_stream`` (passing
        # run_id=None) falls back to AITask.run_id, which stays empty and raises
        # "Task has no run_id" after 10s of retries — the frontend sees nothing.
        nonlocal run_id
        try:
            run_id = AITaskService.extract_and_attach_run_id(
                task_id, cl_url, family_id
            )
        except Exception:
            logger.warning(
                "[narrative] extract_and_attach_run_id failed task=%s",
                task_id,
                exc_info=True,
            )

    def _on_authoritative_run_id(meta_run_id: str) -> None:
        """Called when metadata event arrives with the authoritative run_id."""
        nonlocal _lc_spawned, _lc_task
        if _lc_task is not None and not _lc_task.done():
            _lc_task.cancel()
        _lc_task = _spawn_lifecycle_consumer(
            task_id=task_id,
            family_id=family_id,
            run_id=meta_run_id,
            on_result=_persist_narrative_result,
            bridge=shared_bridge,
        )
        _lc_spawned = True

    # Fallback: if pump never resolves metadata run_id (e.g. stream failure),
    # spawn with the original run_id after a short delay.
    async def _lc_fallback() -> None:
        nonlocal _lc_spawned, _lc_task
        await asyncio.sleep(3)
        if not _lc_spawned:
            _lc_task = _spawn_lifecycle_consumer(
                task_id=task_id,
                family_id=family_id,
                run_id=run_id,
                on_result=_persist_narrative_result,
                bridge=shared_bridge,
            )
            _lc_spawned = True

    asyncio.create_task(_lc_fallback())

    # Spawn background task: consume agent HTTP SSE → publish to shared bridge.
    # This is the SINGLE trigger — no separate agent_client.post above.
    asyncio.create_task(
        _pump_agent_sse_to_bridge(
            agent_client=agent_client,
            agent_url=agent_url,
            json_body={
                "family_id": str(family_id),
                "user_id": str(user.id),
                "language": user.language,
                "on_disconnect": "continue",
                "task_id": task_id,
                "input": {
                    "messages": [
                        {
                            "role": "user",
                            "content": json.dumps(context, ensure_ascii=False),
                        }
                    ]
                },
            },
            bridge=shared_bridge,
            run_id="",
            task_id=task_id,
            on_run_id=_on_lc_run_id,
            on_authoritative_run_id=_on_authoritative_run_id,
        )
    )

    # SSE forwarder: subscribes to shared bridge, yields SSE text to frontend.
    # Same run_id alignment issue — consume_task_stream resolves from DB when
    # run_id is None, so pass None to let the fallback handle it.
    last_event_id = request.headers.get("Last-Event-ID")
    stream_gen = consume_task_stream(
        task_id=task_id,
        family_id=family_id,
        last_event_id=last_event_id,
        run_id=None,  # resolved from AITask.run_id by bridge_consumer fallback
        bridge=shared_bridge,
    )

    return StreamingResponse(
        tracked_sse_stream(task_id, stream_gen),
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no"},
    )


@router.get("/upcoming-payments", response_model=UpcomingPaymentsResponse)
def get_upcoming_payments(
    days: int = Query(7, ge=0, le=365),
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    """获取即将到期的负债还款列表（默认7天内）"""
    return dashboard_service.get_upcoming_payments(db, user, days)
