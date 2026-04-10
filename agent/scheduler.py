"""Agent 定时任务调度器（APScheduler）。"""

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
