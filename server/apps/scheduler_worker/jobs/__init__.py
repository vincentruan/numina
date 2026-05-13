"""scheduler_worker job registry.

Each job function is a plain callable (sync or async) that APScheduler invokes.
All jobs create their own SessionLocal() and close it in a finally block.
No module-level app.* imports — lazy imports inside job bodies only.
"""

import asyncio
import random

from packages.core.logging import get_logger
from packages.db.session import SessionLocal

logger = get_logger(__name__)


# ── Job 1: Exchange rate fetch ────────────────────────────────────────────────

def fetch_rates_job() -> None:
    """Fetch and store latest exchange rates from exchangerate-api.com."""
    from packages.domain.exchange_rate.service import ExchangeRateService  # noqa: PLC0415

    db = SessionLocal()
    try:
        success = ExchangeRateService.fetch_and_store_rates(db)
        if success:
            logger.info("定时汇率更新成功")
    except Exception as e:
        logger.exception(f"定时汇率更新失败: {e}")
    finally:
        db.close()


# ── Job 2: File sync ──────────────────────────────────────────────────────────

async def file_sync_job() -> None:
    """Sync pending file_remote_locations to the default remote backend."""
    from packages.db.models.cached_file import CachedFile  # noqa: PLC0415
    from packages.db.models.file_remote_location import FileRemoteLocation  # noqa: PLC0415
    from packages.db.models.storage_backend import StorageBackend as StorageBackendModel  # noqa: PLC0415
    from packages.storage.base import StorageError  # noqa: PLC0415
    from packages.storage.config_crypto import decrypt_config  # noqa: PLC0415
    from packages.storage.factory import get_backend_for_type  # noqa: PLC0415

    db = SessionLocal()
    try:
        default_backend_row = (
            db.query(StorageBackendModel)
            .filter_by(is_default=True, is_active=True)
            .first()
        )
        if default_backend_row is None:
            return

        config = decrypt_config(default_backend_row.config)
        if config is None:
            logger.warning("无法解密存储后端配置，跳过同步")
            return

        backend = get_backend_for_type(default_backend_row.backend_type, config)

        pending = (
            db.query(FileRemoteLocation)
            .filter_by(backend_id=default_backend_row.id)
            .filter(FileRemoteLocation.sync_status == "pending")
            .limit(50)
            .all()
        )

        for loc in pending:
            cached_file = db.query(CachedFile).filter_by(id=loc.file_id).first()
            if cached_file is None:
                loc.sync_status = "failed"
                loc.last_error = "cached_file not found"
                db.commit()
                continue

            try:
                from pathlib import Path  # noqa: PLC0415
                filename = Path(cached_file.local_path).name
                with open(cached_file.local_path, "rb") as f:
                    content = f.read()

                remote_path = await backend.save(content, filename, cached_file.date_dir)
                loc.sync_status = "synced"
                loc.remote_path = remote_path
                loc.remote_url = backend.get_url(remote_path)
                from datetime import datetime  # noqa: PLC0415
                loc.synced_at = datetime.now()
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

            lo, hi = backend.write_delay_range
            await asyncio.sleep(random.uniform(lo, hi))

    except Exception as e:
        logger.exception(f"文件同步任务异常: {e}")
    finally:
        db.close()


# ── Job 3: Audit log purge ────────────────────────────────────────────────────

def audit_log_purge_job() -> None:
    """Purge security audit log entries older than 90 days."""
    from packages.domain.audit.service import purge_old_audit_logs  # noqa: PLC0415

    purge_old_audit_logs(retention_days=90)


# ── Job 4: Revoked token cleanup ──────────────────────────────────────────────

def revoked_token_cleanup_job() -> None:
    """Purge expired revoked token records."""
    from packages.security.revoke_jti import cleanup_expired_revoked_tokens  # noqa: PLC0415

    db = SessionLocal()
    try:
        deleted = cleanup_expired_revoked_tokens(db)
        if deleted > 0:
            logger.info(f"清理过期撤销记录: {deleted} 条")
    except Exception as e:
        logger.exception(f"撤销记录清理失败: {e}")
    finally:
        db.close()


# ── Job 5: Device session cleanup ────────────────────────────────────────────

def device_session_cleanup_job() -> None:
    """Expire stale DeviceSessions and purge old revoked ones."""
    from packages.domain.device.service import (  # noqa: PLC0415
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


# ── Job 6: Reminder / notification checks ────────────────────────────────────

def reminder_job() -> None:
    """Run daily notification/reminder checks."""
    from packages.domain.notification.service import run_scheduled_checks  # noqa: PLC0415

    db = SessionLocal()
    try:
        run_scheduled_checks(db)
        logger.info("智能提醒定时检测完成")
    except Exception as e:
        logger.exception(f"智能提醒定时检测失败: {e}")
    finally:
        db.close()


# ── Job 7: Daily snapshot ─────────────────────────────────────────────────────

def snapshot_job() -> None:
    """Generate daily asset snapshots for all families."""
    from packages.domain.snapshot.service import auto_generate_daily_snapshots  # noqa: PLC0415

    db = SessionLocal()
    try:
        auto_generate_daily_snapshots(db)
        logger.info("每日快照生成完成")
    except Exception as e:
        logger.exception(f"每日快照生成失败: {e}")
    finally:
        db.close()
