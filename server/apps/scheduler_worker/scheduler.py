"""APScheduler setup for scheduler_worker.

Registers all 7 jobs with their schedules. Uses AsyncIOScheduler
so async jobs (file_sync_job) run natively in the event loop.
"""

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from packages.core.logging import get_logger
from packages.core.settings import settings

logger = get_logger(__name__)

scheduler = AsyncIOScheduler()


def setup_all_jobs() -> None:
    """Register all 8 scheduled jobs."""
    from apps.scheduler_worker.jobs import (
        audit_log_purge_job,
        auto_report_job,
        device_session_cleanup_job,
        fetch_rates_job,
        file_sync_job,
        literacy_report_weekly_job,
        reminder_job,
        revoked_token_cleanup_job,
        snapshot_job,
    )

    # Job 1: Exchange rate — every 2h from 08:00-22:00, 15-min jitter
    scheduler.add_job(
        fetch_rates_job,
        trigger="cron",
        hour="8,10,12,14,16,18,20,22",
        jitter=15 * 60,
        id="exchange_rate",
        name="fetch_rates_job",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    logger.info("汇率定时任务已配置 (Cron: hour='8,10,12,14,16,18,20,22', jitter=900s)")

    # Job 2: File sync — every FILE_SYNC_INTERVAL_MINUTES minutes
    scheduler.add_job(
        file_sync_job,
        trigger="interval",
        minutes=settings.FILE_SYNC_INTERVAL_MINUTES,
        id="file_sync",
        name="file_sync_job",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    logger.info(f"文件同步任务已配置（每 {settings.FILE_SYNC_INTERVAL_MINUTES} 分钟）")

    # Job 3: Audit log purge — daily at 03:00
    scheduler.add_job(
        audit_log_purge_job,
        trigger="cron",
        hour=3,
        minute=0,
        id="audit_log_purge",
        name="audit_log_purge_job",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    logger.info("审计日志清理任务已配置（每日 03:00）")

    # Job 4: Revoked token cleanup — hourly at :30
    scheduler.add_job(
        revoked_token_cleanup_job,
        trigger="cron",
        minute=30,
        id="revoked_token_cleanup",
        name="revoked_token_cleanup_job",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    logger.info("撤销令牌清理任务已配置（每小时 :30）")

    # Job 5: Device session cleanup — hourly at :15
    scheduler.add_job(
        device_session_cleanup_job,
        trigger="cron",
        minute=15,
        id="device_session_cleanup",
        name="device_session_cleanup_job",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    logger.info("设备会话清理任务已配置（每小时 :15）")

    # Job 6: Reminder checks — daily at 09:20
    scheduler.add_job(
        reminder_job,
        trigger="cron",
        hour=9,
        minute=20,
        id="reminder_daily",
        name="reminder_job",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    logger.info("智能提醒定时任务已配置（每日 09:20）")

    # Job 7: Daily snapshot — daily at 00:05
    scheduler.add_job(
        snapshot_job,
        trigger="cron",
        hour=0,
        minute=5,
        id="snapshot_daily",
        name="snapshot_job",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    logger.info("快照定时任务已配置（每日 00:05）")

    # Job 8: Auto report generation — daily at 08:35
    scheduler.add_job(
        auto_report_job,
        trigger="cron",
        hour=8,
        minute=35,
        id="auto_report_daily",
        name="auto_report_job",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    logger.info("自动报告生成任务已配置（每日 08:35）")

    # Job 9: Weekly literacy report — Sunday at 02:00
    scheduler.add_job(
        literacy_report_weekly_job,
        trigger="cron",
        day_of_week="sun",
        hour=2,
        minute=0,
        id="literacy_report_weekly",
        name="literacy_report_weekly_job",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    logger.info("识字周报生成任务已配置（每周日 02:00）")
