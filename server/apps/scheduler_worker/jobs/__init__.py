"""scheduler_worker job registry.

Each job function is a plain callable (sync or async) that APScheduler invokes.
All jobs create their own SessionLocal() and close it in a finally block.
No module-level app.* imports — lazy imports inside job bodies only.
"""

import asyncio
import random
from datetime import UTC, datetime, timedelta
from pathlib import Path

from packages.core.logging import get_logger
from packages.core.settings import settings
from packages.db.session import SessionLocal

logger = get_logger(__name__)

# Retry budget for transient failures. A file that fails this many times is marked
# "failed" and only re-queued by the auto-recovery sweep below.
_MAX_SYNC_RETRIES = 3

# Sentinel retry_count for failures that can never succeed on retry (e.g. the file
# exceeds the backend's hard size limit). The auto-recovery sweep deliberately
# skips these so they are not retried forever every recovery window.
_PERMANENT_FAILURE_RETRY = 999


# ── Job 1: Exchange rate fetch ────────────────────────────────────────────────


def fetch_rates_job() -> None:
    """Fetch and store latest exchange rates from exchangerate-api.com."""
    from packages.db.exchange_rate_adapter import ExchangeRateAdapter

    db = SessionLocal()
    try:
        adapter = ExchangeRateAdapter()
        success = adapter.fetch_and_store_rates(db)
        if success:
            logger.info("定时汇率更新成功")
    except Exception:
        logger.exception("定时汇率更新失败")
    finally:
        db.close()


# ── Job 2: File sync ──────────────────────────────────────────────────────────


def _requeue_stale_failures(db, backend_id: int) -> int:
    """Re-queue transient sync failures that exhausted their retry budget.

    A file that failed three times is marked ``failed`` and, without this sweep,
    stays failed forever until a user manually calls POST /family/storage/sync.
    That means a transient outage (token rotation, network blip, temporary rate
    limit) permanently strands files with no operator-visible path forward.

    After ``FILE_SYNC_FAILED_RECOVERY_HOURS`` the row returns to ``pending`` with
    a fresh retry budget. Two classes of row are deliberately excluded:

    - ``retry_count >= _PERMANENT_FAILURE_RETRY``: failures that can never
      succeed on retry (file larger than the backend's hard limit). Re-queueing
      them would loop forever and burn API quota.
    - Rows updated more recently than the cutoff: they may still be settling.

    Returns the number of rows re-queued.
    """
    from packages.db.models.file_remote_location import FileRemoteLocation

    cutoff = datetime.now(UTC) - timedelta(hours=settings.FILE_SYNC_FAILED_RECOVERY_HOURS)
    recovered = (
        db.query(FileRemoteLocation)
        .filter_by(backend_id=backend_id)
        .filter(FileRemoteLocation.sync_status == "failed")
        .filter(FileRemoteLocation.retry_count >= _MAX_SYNC_RETRIES)
        .filter(FileRemoteLocation.retry_count < _PERMANENT_FAILURE_RETRY)
        .filter(FileRemoteLocation.updated_at < cutoff)
        .update(
            {
                FileRemoteLocation.sync_status: "pending",
                FileRemoteLocation.retry_count: 0,
            },
            synchronize_session="fetch",
        )
    )
    return int(recovered or 0)


async def file_sync_job() -> None:
    """Sync pending file_remote_locations to each family's remote backend."""
    from packages.db.models.cached_file import CachedFile
    from packages.db.models.file_remote_location import (
        FileRemoteLocation,
    )
    from packages.db.models.storage_backend import (
        StorageBackend as StorageBackendModel,
    )
    from packages.storage.base import (
        StorageError,
        StorageFileSizeError,
        StorageRateLimitError,
    )
    from packages.storage.config_crypto import decrypt_config
    from packages.storage.factory import get_backend_for_type

    db = SessionLocal()
    try:
        active_backends = db.query(StorageBackendModel).filter_by(is_active=True).all()
        if not active_backends:
            return

        # Path diagnostics: log the resolved upload dir once per run so that a
        # container path mismatch is immediately visible in the logs.
        upload_dir = Path(settings.UPLOAD_DIR).resolve()
        logger.info(
            "文件同步开始: %s 个活动后端, UPLOAD_DIR=%s (exists=%s)",
            len(active_backends),
            upload_dir,
            upload_dir.exists(),
        )

        for backend_row in active_backends:
            try:
                config = decrypt_config(backend_row.config)
                if config is None:
                    # CRITICAL, not WARNING: every file for this family is blocked
                    # until the encryption key is fixed. Previously this silently
                    # skipped and left files pending forever.
                    logger.critical(
                        "存储后端配置解密失败 (family_id=%s, backend_id=%s, type=%s)。"
                        "该家庭的所有文件同步将停滞 — 请检查 STORAGE_ENCRYPTION_KEY / "
                        "SECRET_KEY 是否与加密时一致。",
                        backend_row.family_id,
                        backend_row.id,
                        backend_row.backend_type,
                    )
                    continue

                backend = get_backend_for_type(backend_row.backend_type, config)
            except Exception as e:
                logger.exception(
                    f"无法初始化存储后端 (family_id={backend_row.family_id}, "
                    f"type={backend_row.backend_type}): {e}"
                )
                continue

            recovered = _requeue_stale_failures(db, backend_row.id)
            if recovered:
                db.commit()
                logger.info(
                    "文件同步自动恢复: %s 个失败文件重新入队 (family_id=%s)",
                    recovered,
                    backend_row.family_id,
                )

            pending = (
                db.query(FileRemoteLocation)
                .filter_by(backend_id=backend_row.id)
                .filter(FileRemoteLocation.sync_status.in_(["pending", "failed"]))
                .filter(FileRemoteLocation.retry_count < _MAX_SYNC_RETRIES)
                .limit(50)
                .all()
            )

            if not pending:
                continue

            # Pre-fetch all CachedFile rows in one query to avoid N+1
            file_ids = [loc.file_id for loc in pending]
            cached_files: dict = {
                cf.id: cf
                for cf in db.query(CachedFile).filter(CachedFile.id.in_(file_ids)).all()
            }

            any_synced = False
            path_mismatch_count = 0

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
                    path_mismatch_count += 1
                    loc.sync_status = "failed"
                    loc.last_error = f"路径越界，拒绝访问: {cached_file.local_path}"
                    db.commit()
                    logger.warning(
                        "文件同步路径越界: file_id=%s local_path=%s UPLOAD_DIR=%s "
                        "(backend 与 scheduler_worker 容器的卷挂载可能不一致)",
                        cached_file.id,
                        cached_file.local_path,
                        upload_dir,
                    )
                    continue

                try:
                    filename = Path(cached_file.local_path).name
                    content = await asyncio.to_thread(
                        _read_file, cached_file.local_path
                    )

                    remote_path = await asyncio.wait_for(
                        backend.save(content, filename, cached_file.date_dir),
                        timeout=30,
                    )
                    loc.sync_status = "synced"
                    loc.remote_path = remote_path
                    loc.remote_url = backend.get_url(remote_path)
                    loc.synced_at = datetime.now(UTC)
                    loc.last_error = None
                    loc.retry_count = 0
                    any_synced = True
                    db.commit()
                except StorageRateLimitError as e:
                    # A rate limit is not the file's fault — do NOT consume a retry.
                    # Stop this backend's batch and wait for the reset window.
                    loc.last_error = f"触发速率限制: {e}"
                    db.commit()
                    logger.warning(
                        "存储后端速率限制 (family_id=%s, reset_at=%s)，本轮停止同步该后端",
                        backend_row.family_id,
                        e.reset_at,
                    )
                    break
                except StorageFileSizeError as e:
                    # Permanent failure: retrying a too-large file will never succeed,
                    # so mark it failed immediately without burning the retry budget.
                    loc.sync_status = "failed"
                    loc.retry_count = _PERMANENT_FAILURE_RETRY
                    loc.last_error = str(e)
                    db.commit()
                    logger.error(
                        "文件超过后端大小限制，已标记失败: file_id=%s size=%s max=%s",
                        cached_file.id,
                        e.file_size,
                        e.max_size,
                    )
                except TimeoutError:
                    loc.retry_count += 1
                    loc.last_error = "上传超时 (30s)"
                    if loc.retry_count >= _MAX_SYNC_RETRIES:
                        loc.sync_status = "failed"
                    db.commit()
                    logger.warning("文件同步超时: %s", cached_file.id)
                except FileNotFoundError:
                    loc.retry_count += 1
                    loc.last_error = f"本地文件不存在: {cached_file.local_path}"
                    if loc.retry_count >= _MAX_SYNC_RETRIES:
                        loc.sync_status = "failed"
                    db.commit()
                    logger.warning("文件同步本地文件不存在: %s", cached_file.id)
                except StorageError as e:
                    loc.retry_count += 1
                    loc.last_error = str(e)
                    if loc.retry_count >= _MAX_SYNC_RETRIES:
                        loc.sync_status = "failed"
                    db.commit()
                    logger.warning("文件同步失败: %s", cached_file.id, exc_info=True)
                except Exception as e:
                    loc.retry_count += 1
                    loc.last_error = str(e)
                    if loc.retry_count >= _MAX_SYNC_RETRIES:
                        loc.sync_status = "failed"
                    db.commit()
                    logger.exception("文件同步异常: %s", cached_file.id)

            if path_mismatch_count:
                logger.error(
                    "文件同步路径越界 %s 个 (family_id=%s, UPLOAD_DIR=%s) — "
                    "检查 scheduler_worker 与 backend 容器的卷挂载是否一致",
                    path_mismatch_count,
                    backend_row.family_id,
                    upload_dir,
                )

            if any_synced:
                backend_row.last_synced_at = datetime.now(UTC)
                db.commit()

            lo, hi = backend.write_delay_range
            await asyncio.sleep(random.uniform(lo, hi))

    except Exception:
        logger.exception("文件同步任务异常")
    finally:
        db.close()


# ── Job 3: Audit log purge ────────────────────────────────────────────────────


def audit_log_purge_job() -> None:
    """Purge security audit log entries older than 90 days."""
    from packages.domain.audit.service import purge_old_audit_logs

    purge_old_audit_logs(retention_days=90)


def mcp_anomaly_scan_job() -> None:
    """Scan MCP access logs for anomalies and alert the owner."""
    from apps.backend.app.services.mcp_anomaly import (  # noqa: PLC0415
        scan_mcp_anomalies,
    )

    scan_mcp_anomalies()


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
            logger.info("清理过期撤销记录: %s 条", deleted)
    except Exception:
        logger.exception("撤销记录清理失败")
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
            logger.info("设备会话清理: 过期 %s 条，删除 %s 条", expired, purged)
    except Exception:
        logger.exception("设备会话清理失败")
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
    except Exception:
        logger.exception("智能提醒定时检测失败")
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
    except Exception:
        logger.exception("每日快照生成失败")
    finally:
        db.close()


# ── Job 8: Auto report generation ─────────────────────────────────────────────


async def auto_report_job() -> None:
    """Trigger report generation for eligible families (daily 8:35)."""
    import httpx

    try:
        async with httpx.AsyncClient(timeout=60.0, trust_env=False) as client:
            from packages.security.service_auth.agent_jwt import create_system_token

            resp = await client.post(
                f"{settings.BACKEND_BASE_URL}/api/v1/internal/ai/auto-generate-reports",
                headers={
                    "Authorization": f"Bearer {create_system_token()}",
                },
            )
        if resp.status_code == 200:
            data = resp.json()
            logger.info(
                f"自动报告生成完成: 触发 {data.get('triggered', 0)} 个家庭, "
                f"跳过 {data.get('skipped', 0)} 个"
            )
        else:
            logger.warning("自动报告生成请求失败: status=%s", resp.status_code)
    except Exception:
        logger.exception("自动报告生成任务异常")


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
            db.query(User).filter(User.role == "child", User.is_active.is_(True)).all()
        )

        if not children:
            logger.info("识字周报: 无活跃儿童用户")
            return

        # Lazy import the async service — run via asyncio
        import asyncio

        from packages.domain.literacy.service import (
            generate_weekly_report,
        )

        async def _generate_all():
            count = 0
            for child in children:
                try:
                    await generate_weekly_report(db, child, week_start)
                    count += 1
                except Exception as e:
                    logger.warning(f"识字周报生成失败 (child_id={child.id}): {e}")
            return count

        count = asyncio.run(_generate_all())
        logger.info("识字周报生成完成: %s/%s 位儿童", count, len(children))
    except Exception:
        logger.exception("识字周报定时任务异常")
    finally:
        db.close()


# ── Job 10: Daily notification digest ─────────────────────────────────────────


async def notification_digest_job() -> None:
    """Send daily digest notifications for channels with digest_mode='daily'."""
    from packages.db.session import SessionLocal  # noqa: PLC0415

    db = SessionLocal()
    try:
        from apps.backend.app.services.notification.dispatcher import (
            _dispatch_digest,  # noqa: PLC0415
        )
        from packages.db.models.notification_channel import (
            NotificationChannel,  # noqa: PLC0415
        )

        channels = (
            db.query(NotificationChannel)
            .filter_by(digest_mode="daily", is_enabled=True)
            .all()
        )
        for channel in channels:
            try:
                await _dispatch_digest(db, channel)
            except Exception:
                logger.exception("Digest send failed for channel %s", channel.id)
        logger.info("Notification digest job completed")
    except Exception:
        logger.exception("Notification digest job failed")
    finally:
        db.close()


# ── Job 11: Travel trip auto-transitions (R5) ────────────────────────────────


def travel_transition_job() -> None:
    """Auto-transition trip statuses based on dates and send notifications.

    R5: planning → active uses a hybrid model:
    - On departure_date, suggest activation via notification
    - If not activated within 24 hours, auto-transition to active
    - Past return_date with unsettled expenses: show "待结算" notification
    """
    from datetime import date, timedelta  # noqa: PLC0415

    from packages.db.models.trip import Trip  # noqa: PLC0415

    db = SessionLocal()
    try:
        today = date.today()

        # 1. Auto-activate: departure_date was 24+ hours ago and still planning
        auto_activate_cutoff = today - timedelta(days=1)
        stale_planning = (
            db.query(Trip)
            .filter(
                Trip.status == "planning",
                Trip.is_active == True,  # noqa: E712
                Trip.departure_date <= auto_activate_cutoff,
            )
            .all()
        )
        for trip in stale_planning:
            trip.status = "active"
            logger.info(
                "Trip %s (%s) auto-activated (departure_date=%s, >24h overdue)",
                trip.id,
                trip.name,
                trip.departure_date,
            )

        # 2. Notify about trips departing today (activation suggestion)
        today_departures = (
            db.query(Trip)
            .filter(
                Trip.status == "planning",
                Trip.is_active == True,  # noqa: E712
                Trip.departure_date == today,
            )
            .all()
        )
        for trip in today_departures:
            logger.info(
                "Trip %s (%s) departure today — notification suggested for activation",
                trip.id,
                trip.name,
            )
            # TODO: integrate with notification service when travel notifications are registered

        # 3. Notify about unsettled trips past return_date
        unsettled_trips = (
            db.query(Trip)
            .filter(
                Trip.status == "active",
                Trip.is_active == True,  # noqa: E712
                Trip.return_date != None,  # noqa: E711
                Trip.return_date < today,
            )
            .all()
        )
        for trip in unsettled_trips:
            logger.info(
                "Trip %s (%s) past return_date — '待结算' notification suggested",
                trip.id,
                trip.name,
            )
            # TODO: integrate with notification service when travel notifications are registered

        db.commit()
        logger.info(
            "Travel transition job completed: %d auto-activated, %d departing today, %d unsettled",
            len(stale_planning),
            len(today_departures),
            len(unsettled_trips),
        )
    except Exception:
        logger.exception("Travel transition job failed")
    finally:
        db.close()
