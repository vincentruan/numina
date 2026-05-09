import asyncio
import random

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import settings
from app.core.logging_config import get_logger
from app.database import SessionLocal
from app.services.exchange_rate import ExchangeRateService
from app.services.storage.config_crypto import decrypt_config
from app.services.storage.factory import get_backend_for_type

logger = get_logger(__name__)

scheduler = AsyncIOScheduler()


def fetch_rates_job() -> None:
    """APScheduler job: fetch and store latest exchange rates."""
    db = SessionLocal()
    try:
        success = ExchangeRateService.fetch_and_store_rates(db)
        if success:
            logger.info("定时汇率更新成功")
    except Exception as e:
        logger.exception(f"定时汇率更新失败: {e}")
    finally:
        db.close()


async def file_sync_job() -> None:
    """Sync pending file_remote_locations to the default remote backend."""
    from app.models.cached_file import CachedFile
    from app.models.file_remote_location import FileRemoteLocation
    from app.models.storage_backend import StorageBackend as StorageBackendModel
    from app.services.storage.base import StorageError

    db = SessionLocal()
    try:
        default_backend_row = (
            db.query(StorageBackendModel)
            .filter_by(is_default=True, is_active=True)
            .first()
        )
        if default_backend_row is None:
            return

        # Decrypt config
        config = decrypt_config(default_backend_row.config)
        if config is None:
            logger.warning("无法解密存储后端配置，跳过同步")
            return

        backend = get_backend_for_type(default_backend_row.backend_type, config)

        pending = (
            db.query(FileRemoteLocation)
            .filter_by(backend_id=default_backend_row.id)
            .filter(FileRemoteLocation.sync_status.in_(["pending", "failed"]))
            .filter(FileRemoteLocation.retry_count < 3)
            .all()
        )

        for loc in pending:
            cached_file = db.query(CachedFile).filter_by(id=loc.file_id).first()
            if cached_file is None or cached_file.deleted_at is not None:
                loc.sync_status = "failed"
                loc.last_error = "本地文件记录不存在或已删除"
                db.commit()
                continue

            try:
                content = await asyncio.to_thread(_read_file, cached_file.local_path)

                remote_path = await asyncio.wait_for(
                    backend.save(content, _filename_from_path(cached_file.local_path), cached_file.date_dir),
                    timeout=30,
                )
                loc.sync_status = "synced"
                loc.remote_path = remote_path
                loc.remote_url = backend.get_url(remote_path)
                loc.synced_at = _now()
                db.commit()
                logger.info(f"文件同步成功: {cached_file.id} -> {remote_path}")

            except TimeoutError:
                loc.retry_count += 1
                loc.last_error = "上传超时 (30s)"
                if loc.retry_count >= 3:
                    loc.sync_status = "failed"
                db.commit()
                logger.warning(f"文件同步超时: {cached_file.id}")
            except FileNotFoundError:
                loc.retry_count += 1
                loc.last_error = f"本地文件不存在: {cached_file.local_path}"
                if loc.retry_count >= 3:
                    loc.sync_status = "failed"
                db.commit()
            except StorageError as e:
                loc.retry_count += 1
                loc.last_error = str(e)
                if loc.retry_count >= 3:
                    loc.sync_status = "failed"
                db.commit()
                logger.warning(f"文件同步失败: {cached_file.id}: {e}")
            except Exception as e:
                loc.retry_count += 1
                loc.last_error = str(e)
                if loc.retry_count >= 3:
                    loc.sync_status = "failed"
                db.commit()
                logger.exception(f"文件同步异常: {cached_file.id}: {e}")

            # Jitter between file uploads to avoid fixed-interval patterns
            # that external services (GitHub, WebDAV) may flag as bot traffic.
            # Applied after each file regardless of success/failure to prevent
            # hammering the remote on transient errors.
            lo, hi = backend.write_delay_range
            await asyncio.sleep(random.uniform(lo, hi))

    except Exception as e:
        logger.exception(f"文件同步任务异常: {e}")
    finally:
        db.close()


def _filename_from_path(local_path: str) -> str:
    from pathlib import Path
    return Path(local_path).name


def _read_file(local_path: str) -> bytes:
    with open(local_path, "rb") as f:
        return f.read()


def _now():
    from datetime import datetime
    return datetime.now()



def setup_exchange_rate_schedule() -> None:
    """Schedule rate updates every 2 hours from 08:00 to 22:00 with random 0-15 min offset (jitter)."""
    scheduler.add_job(
        fetch_rates_job,
        trigger="cron",
        hour="8,10,12,14,16,18,20,22",
        jitter=15 * 60,  # 15 minutes jitter
        id="exchange_rate",
        name="fetch_rates_job (Cron: 08:00-22:00 every 2h, Jitter: 0-15m)",
        replace_existing=True,
    )
    logger.info("汇率定时任务已配置 (Cron: hour='8,10,12,14,16,18,20,22', jitter=900s)")


def setup_file_sync_schedule() -> None:
    """Schedule periodic file sync to the default remote backend."""
    scheduler.add_job(
        file_sync_job,
        trigger="interval",
        minutes=settings.FILE_SYNC_INTERVAL_MINUTES,
        id="file_sync",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    logger.info(f"文件同步任务已配置（每 {settings.FILE_SYNC_INTERVAL_MINUTES} 分钟）")


def audit_log_purge_job() -> None:
    """APScheduler job: purge security audit log entries older than 90 days."""
    from app.services.audit_log import purge_old_audit_logs
    purge_old_audit_logs(retention_days=90)


def revoked_token_cleanup_job() -> None:
    """APScheduler job: purge expired revoked token records."""
    from app.auth.revoke_jti import cleanup_expired_revoked_tokens

    db = SessionLocal()
    try:
        deleted = cleanup_expired_revoked_tokens(db)
        if deleted > 0:
            logger.info(f"清理过期撤销记录: {deleted} 条")
    except Exception as e:
        logger.exception(f"撤销记录清理失败: {e}")
    finally:
        db.close()


def setup_audit_log_purge_schedule() -> None:
    """Schedule daily audit log purge at 03:00."""
    scheduler.add_job(
        audit_log_purge_job,
        trigger="cron",
        hour=3,
        minute=0,
        id="audit_log_purge",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    logger.info("审计日志清理任务已配置（每日 03:00）")


def setup_revoked_token_cleanup_schedule() -> None:
    """Schedule hourly cleanup of expired revoked tokens."""
    scheduler.add_job(
        revoked_token_cleanup_job,
        trigger="cron",
        minute=0,  # Every hour at :00
        id="revoked_token_cleanup",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    logger.info("撤销记录清理任务已配置（每小时）")


def device_session_cleanup_job() -> None:
    """APScheduler job: expire stale DeviceSessions and purge old revoked ones."""
    from app.services.device import (
        cleanup_expired_device_sessions,
        delete_old_revoked_sessions,
    )

    db = SessionLocal()
    try:
        expired = cleanup_expired_device_sessions(db)
        purged = delete_old_revoked_sessions(db)
        if expired > 0 or purged > 0:
            logger.info(f"设备会话清理: 过期 {expired} 条，删除 {purged} 条")
    except Exception as e:
        logger.exception(f"设备会话清理失败: {e}")
    finally:
        db.close()


def setup_device_session_cleanup_schedule() -> None:
    """Schedule hourly cleanup of expired device sessions."""
    scheduler.add_job(
        device_session_cleanup_job,
        trigger="cron",
        minute=15,
        id="device_session_cleanup",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    logger.info("设备会话清理任务已配置（每小时 :15）")


def setup_reminder_schedule() -> None:
    """Schedule daily reminder checks at 09:20."""
    from app.services.notification.dispatcher import run_scheduled_checks

    def _reminder_job() -> None:
        db = SessionLocal()
        try:
            run_scheduled_checks(db)
            logger.info("智能提醒定时检测完成")
        except Exception as e:
            logger.exception(f"智能提醒定时检测失败: {e}")
        finally:
            db.close()

    scheduler.add_job(
        _reminder_job,
        trigger="cron",
        hour=9,
        minute=20,
        id="reminder_daily",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    logger.info("智能提醒定时任务已配置（每日 09:20）")


def snapshot_job() -> None:
    """APScheduler job: generate daily snapshots for all families."""
    from app.services.snapshot import auto_generate_daily_snapshots

    db = SessionLocal()
    try:
        auto_generate_daily_snapshots(db)
        logger.info("每日快照生成完成")
    except Exception as e:
        logger.exception(f"每日快照生成失败: {e}")
    finally:
        db.close()


def setup_snapshot_schedule() -> None:
    """Schedule daily snapshot generation at 00:05."""
    scheduler.add_job(
        snapshot_job,
        trigger="cron",
        hour=0,
        minute=5,
        id="snapshot_daily",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    logger.info("快照定时任务已配置（每日 00:05）")
