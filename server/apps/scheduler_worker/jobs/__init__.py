"""scheduler_worker job registry.

Each job function is a plain callable (sync or async) that APScheduler invokes.
All jobs create their own SessionLocal() and close it in a finally block.
No module-level app.* imports — lazy imports inside job bodies only.
"""

import asyncio
import random
from datetime import datetime
from pathlib import Path

from packages.core.logging import get_logger
from packages.core.settings import settings
from packages.db.session import SessionLocal

logger = get_logger(__name__)


# ── Job 1: Exchange rate fetch ────────────────────────────────────────────────

def fetch_rates_job() -> None:
    """Fetch and store latest exchange rates from exchangerate-api.com."""
    from packages.domain.exchange_rate.service import (
        ExchangeRateService,
    )

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
    from packages.db.models.cached_file import CachedFile
    from packages.db.models.file_remote_location import (
        FileRemoteLocation,
    )
    from packages.db.models.storage_backend import (
        StorageBackend as StorageBackendModel,
    )
    from packages.storage.base import StorageError
    from packages.storage.config_crypto import decrypt_config
    from packages.storage.factory import get_backend_for_type

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
            .filter(FileRemoteLocation.sync_status.in_(["pending", "failed"]))
            .filter(FileRemoteLocation.retry_count < 3)
            .limit(50)
            .all()
        )

        # Pre-fetch all CachedFile rows in one query to avoid N+1
        file_ids = [loc.file_id for loc in pending]
        cached_files: dict = {
            cf.id: cf
            for cf in db.query(CachedFile).filter(CachedFile.id.in_(file_ids)).all()
        }

        upload_dir = Path(settings.UPLOAD_DIR).resolve()

        for loc in pending:
            cached_file = cached_files.get(loc.file_id)
            if cached_file is None or cached_file.deleted_at is not None:
                loc.sync_status = "failed"
                loc.last_error = "本地文件记录不存在或已删除"
                db.commit()
                continue

            # Guard against path traversal: local_path must resolve within UPLOAD_DIR
            resolved_path = Path(cached_file.local_path).resolve()
            if not resolved_path.is_relative_to(upload_dir):
                loc.sync_status = "failed"
                loc.last_error = f"路径越界，拒绝访问: {cached_file.local_path}"
                db.commit()
                logger.warning(f"文件同步路径越界: {cached_file.id} -> {cached_file.local_path}")
                continue

            try:
                filename = Path(cached_file.local_path).name
                content = await asyncio.to_thread(_read_file, cached_file.local_path)

                remote_path = await asyncio.wait_for(
                    backend.save(content, filename, cached_file.date_dir),
                    timeout=30,
                )
                loc.sync_status = "synced"
                loc.remote_path = remote_path
                loc.remote_url = backend.get_url(remote_path)
                loc.synced_at = datetime.now()
                db.commit()
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
                logger.warning(f"文件同步本地文件不存在: {cached_file.id}")
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
    from packages.domain.audit.service import purge_old_audit_logs

    purge_old_audit_logs(retention_days=90)


# ── Job 4: Revoked token cleanup ──────────────────────────────────────────────

def revoked_token_cleanup_job() -> None:
    """Purge expired revoked token records."""
    from packages.security.revoke_jti import (
        cleanup_expired_revoked_tokens,
    )

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
    from packages.domain.device.service import (
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
    from packages.domain.notification.service import (
        run_scheduled_checks,
    )

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
    from packages.domain.snapshot.service import (
        auto_generate_daily_snapshots,
    )

    db = SessionLocal()
    try:
        auto_generate_daily_snapshots(db)
        logger.info("每日快照生成完成")
    except Exception as e:
        logger.exception(f"每日快照生成失败: {e}")
    finally:
        db.close()


# ── Job 8: Auto report generation ─────────────────────────────────────────────

async def auto_report_job() -> None:
    """Trigger report generation for eligible families (daily 8:35)."""
    import httpx

    try:
        async with httpx.AsyncClient(timeout=60.0, trust_env=False) as client:
            resp = await client.post(
                f"{settings.BACKEND_BASE_URL}/api/v1/internal/ai/auto-generate-reports",
                headers={
                    "Authorization": f"Bearer {settings.AGENT_INTERNAL_TOKEN}",
                },
            )
        if resp.status_code == 200:
            data = resp.json()
            logger.info(
                f"自动报告生成完成: 触发 {data.get('triggered', 0)} 个家庭, "
                f"跳过 {data.get('skipped', 0)} 个"
            )
        else:
            logger.warning(f"自动报告生成请求失败: status={resp.status_code}")
    except Exception as e:
        logger.exception(f"自动报告生成任务异常: {e}")


def _read_file(local_path: str) -> bytes:
    with open(local_path, "rb") as f:
        return f.read()


# ── Job 9: Weekly literacy report generation ──────────────────────────────

def literacy_report_weekly_job() -> None:
    """Generate weekly literacy reports for all children in all families."""
    from datetime import date, timedelta

    from packages.db.models.user import User

    db = SessionLocal()
    try:
        # Compute last Sunday (start of current week)
        today = date.today()
        days_since_sunday = (today.weekday() + 1) % 7
        week_start = today - timedelta(days=days_since_sunday)

        children = (
            db.query(User)
            .filter(User.role == "child", User.is_active.is_(True))
            .all()
        )

        if not children:
            logger.info("识字周报: 无活跃儿童用户")
            return

        # Lazy import the async service — run via asyncio
        import asyncio

        from apps.backend.app.services.literacy_report import (
            generate_weekly_report,
        )

        async def _generate_all():
            count = 0
            for child in children:
                try:
                    await generate_weekly_report(db, child, week_start)
                    count += 1
                except Exception as e:
                    logger.warning(
                        f"识字周报生成失败 (child_id={child.id}): {e}"
                    )
            return count

        count = asyncio.run(_generate_all())
        logger.info(f"识字周报生成完成: {count}/{len(children)} 位儿童")
    except Exception as e:
        logger.exception(f"识字周报定时任务异常: {e}")
    finally:
        db.close()
