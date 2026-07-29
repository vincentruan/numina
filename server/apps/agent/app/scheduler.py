"""Agent 定时任务调度器（APScheduler）。

# OD-3: APScheduler async bridge decision
# ─────────────────────────────────────────
# We use AsyncIOScheduler so all jobs run as native coroutines on the FastAPI
# event loop. This avoids the RuntimeError that would occur if jobs were run in
# APScheduler's default ThreadPoolExecutor and tried to call asyncio.wait_for()
# without a running event loop.
#
# When USE_DEERFLOW=True, scheduled jobs must trigger a ``stream_run`` agent run
# (via backend → agent gateway, ``app=<skill_id>`` in run metadata) with an
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

import asyncio
import logging
import random

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from apps.agent.core import backend_client

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone="Asia/Shanghai")


# ---------------------------------------------------------------------------
# Weekly literacy report generation
# ---------------------------------------------------------------------------


async def generate_weekly_literacy_reports() -> None:
    """Weekly cron: generate literacy reports for all AI-enabled families.

    Follows scheduler contract: enumerate families, per-family jitter,
    skip-and-log on failure.
    """
    families = await backend_client.get_ai_enabled_families()
    logger.info("[scheduler] generating literacy reports for %d families", len(families))

    for family_id in families:
        # Jitter per family (scheduler contract: random.uniform(0, 300) for cron jobs)
        await asyncio.sleep(random.uniform(0, 300))

        try:
            children = await backend_client.get_literacy_children(family_id)
        except Exception:
            logger.warning(
                "[scheduler] failed to get children for family %s",
                family_id,
                exc_info=True,
            )
            continue

        for child_info in children:
            child_id = child_info.get("child_id")
            if not child_id:
                continue
            # Per-child delay
            await asyncio.sleep(random.uniform(2, 8))
            try:
                await backend_client.generate_literacy_report(family_id, child_id)
            except Exception:
                logger.warning(
                    "[scheduler] report trigger failed family=%s child=%s",
                    family_id,
                    child_id,
                    exc_info=True,
                )

    logger.info("[scheduler] literacy report generation complete")


# ---------------------------------------------------------------------------
# Schedule registration
# ---------------------------------------------------------------------------


def setup_schedules() -> None:
    """注册所有定时任务。"""
    # 每周 literacy 周报（周日上午 8:00）
    scheduler.add_job(
        generate_weekly_literacy_reports,
        "cron",
        day_of_week="sun",
        hour=8,
        minute=0,
        id="weekly_literacy_report",
    )
    logger.info("定时任务已配置")
