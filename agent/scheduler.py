"""Agent 定时任务调度器（APScheduler）。

# OD-3: APScheduler async bridge decision
# ─────────────────────────────────────────
# We use AsyncIOScheduler so all jobs run as native coroutines on the FastAPI
# event loop. This avoids the RuntimeError that would occur if jobs were run in
# APScheduler's default ThreadPoolExecutor and tried to call asyncio.wait_for()
# without a running event loop.
#
# When USE_DEERFLOW=True, scheduled jobs must call orchestrator.dispatch() with
# an explicit timeout budget (recommended: 60 s, shorter than DEERFLOW_TIMEOUT_SECONDS)
# to prevent a DeerFlow hang from blocking the scheduler indefinitely.
#
# Scheduler dispatch contract (for future job implementations):
#   async def _dispatch_for_family(family_id: str, capability: str) -> None:
#       try:
#           await asyncio.wait_for(
#               orchestrator.dispatch(capability, family_id),
#               timeout=60,
#           )
#       except asyncio.TimeoutError:
#           logger.warning(f"[scheduler] dispatch timed out family={family_id} cap={capability}")
#       except Exception as e:
#           logger.warning(f"[scheduler] dispatch failed family={family_id}: {e}")
#           # Skip this family — do not abort the full scheduled run
#
# Each job must:
#   - Enumerate families one at a time (not batch) to limit blast radius
#   - Skip and log a warning if FamilyContext fetch fails for a family
#   - Scope each FamilyContext to exactly one family_id validated before dispatch
"""

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone="Asia/Shanghai")


def setup_schedules() -> None:
    """注册所有定时任务。Phase 1+ 功能实现后逐步添加。"""
    # Phase 1: 月度体检报告（每月 1 日 08:00，随机偏移在任务内部处理）
    # scheduler.add_job(generate_monthly_reports, "cron", day=1, hour=8, minute=0, id="monthly_health_report")

    # Phase 2: 每周预警扫描（每周一 08:00）
    # scheduler.add_job(weekly_alert_scan, "cron", day_of_week="mon", hour=8, minute=0, id="weekly_alert_scan")

    logger.info("定时任务已配置（Phase 0：暂无活跃任务，Phase 1+ 功能实现后启用）")
