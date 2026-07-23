"""Agent 定时任务调度器（APScheduler）。

# OD-3: APScheduler async bridge decision
# ─────────────────────────────────────────
# We use AsyncIOScheduler so all jobs run as native coroutines on the FastAPI
# event loop. This avoids the RuntimeError that would occur if jobs were run in
# APScheduler's default ThreadPoolExecutor and tried to call asyncio.wait_for()
# without a running event loop.
#
# When USE_DEERFLOW=True, scheduled jobs must trigger a ``stream_run`` agent run
# (via backend → agent gateway, ``app=<capability>`` in run metadata) with an
# explicit timeout budget (recommended: 60 s, shorter than DEERFLOW_TIMEOUT_SECONDS)
# to prevent a DeerFlow hang from blocking the scheduler indefinitely.
#
# Scheduler dispatch contract (for future job implementations):
#   async def _stream_run_for_family(family_id: str, app: str) -> None:
#       try:
#           await asyncio.wait_for(
#               _trigger_stream_run(family_id, app),  # POST /internal/gateway/runs/{app}/{thread_id}
#               timeout=60,
#           )
#       except asyncio.TimeoutError:
#           logger.warning(f"[scheduler] stream_run timed out family={family_id} app={app}")
#       except Exception as e:
#           logger.warning(f"[scheduler] stream_run failed family={family_id}: {e}")
#           # Skip this family — do not abort the full scheduled run
#
# Each job must:
#   - Enumerate families one at a time (not batch) to limit blast radius
#   - Skip and log a warning if FamilyContext fetch fails for a family
#   - Scope each FamilyContext to exactly one family_id validated before dispatch
#
# Jitter contract (mandatory for all future job implementations):
# ──────────────────────────────────────────────────────────────
# Jobs that call external APIs or LLMs MUST add per-family random jitter
# before each dispatch to avoid fixed-interval patterns that external
# services may flag as bot traffic.
#
# Jitter must be applied INSIDE the per-family loop so each family gets
# an independent random offset — not once before the loop.
#
# Recommended sleep budgets:
#   - Cron jobs (hourly or less frequent): random.uniform(0, 300)   # up to 5 min
#   - Interval jobs (< 30 min):            random.uniform(0, 60)    # up to 1 min
#   - Per-family inter-request delay:      random.uniform(2, 8)     # 2–8 s
#
# Example skeleton:
#   import random
#   async def generate_monthly_reports() -> None:
#       families = await get_all_families()
#       for family in families:
#           await asyncio.sleep(random.uniform(0, 300))  # ← jitter per family
#           await _stream_run_for_family(family.id, "asset-report")
#
# Human-in-the-loop (HITL) polling jitter contract:
# ──────────────────────────────────────────────────
# When a job suspends and polls for human approval (e.g. waiting for a user
# to confirm a high-risk action before the agent proceeds), the polling loop
# MUST use exponential backoff with jitter — never a fixed interval — to
# avoid hammering the approval endpoint and to prevent detectable patterns.
#
# Recommended polling budgets:
#   - Initial poll delay:   random.uniform(5, 15)          # 5–15 s
#   - Subsequent backoff:   min(base * 2^attempt, cap) + random.uniform(0, base)
#     where base=10 s, cap=300 s (5 min)
#   - Max wait before abort: 3600 s (1 hour); raise TimeoutError after
#
# Example skeleton:
#   import random, asyncio
#   BASE, CAP, MAX_WAIT = 10, 300, 3600
#   async def poll_for_approval(request_id: str) -> bool:
#       elapsed = 0
#       attempt = 0
#       await asyncio.sleep(random.uniform(5, 15))          # initial jitter
#       while elapsed < MAX_WAIT:
#           if await approval_store.is_approved(request_id):
#               return True
#           delay = min(BASE * (2 ** attempt), CAP) + random.uniform(0, BASE)
#           await asyncio.sleep(delay)
#           elapsed += delay
#           attempt += 1
#       raise TimeoutError(f"approval timed out: {request_id}")
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
