import asyncio
import json
import random

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import settings
from app.core.logging_config import get_logger
from app.database import SessionLocal
from app.services.exchange_rate import ExchangeRateService
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
        config = _decrypt_config(default_backend_row.config)
        if config is None:
            logger.warning("无法解密存储后端配置，跳过同步")
            return

        backend = get_backend_for_type(default_backend_row.backend_type, config)

        pending = (
            db.query(FileRemoteLocation)
            .filter_by(backend_id=default_backend_row.id, sync_status="pending")
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
                with open(cached_file.local_path, "rb") as f:
                    content = f.read()

                remote_path = await backend.save(content, _filename_from_path(cached_file.local_path), cached_file.date_dir)
                loc.sync_status = "synced"
                loc.remote_path = remote_path
                loc.remote_url = backend.get_url(remote_path)
                loc.synced_at = _now()
                db.commit()
                logger.info(f"文件同步成功: {cached_file.id} -> {remote_path}")

                # Throttle GitHub writes to avoid secondary rate limits
                if default_backend_row.backend_type == "github":
                    await asyncio.sleep(1)

            except FileNotFoundError:
                loc.sync_status = "failed"
                loc.last_error = f"本地文件不存在: {cached_file.local_path}"
                loc.retry_count += 1
                db.commit()
            except StorageError as e:
                loc.sync_status = "failed"
                loc.last_error = str(e)
                loc.retry_count += 1
                db.commit()
                logger.warning(f"文件同步失败: {cached_file.id}: {e}")
            except Exception as e:
                loc.sync_status = "failed"
                loc.last_error = str(e)
                loc.retry_count += 1
                db.commit()
                logger.exception(f"文件同步异常: {cached_file.id}: {e}")

    except Exception as e:
        logger.exception(f"文件同步任务异常: {e}")
    finally:
        db.close()


def _filename_from_path(local_path: str) -> str:
    from pathlib import Path
    return Path(local_path).name


def _now():
    from datetime import datetime
    return datetime.now()


def _decrypt_config(config_text: str | None) -> dict | None:
    """Decrypt the storage backend config JSON. Returns None on failure."""
    if not config_text:
        return None
    try:
        data = json.loads(config_text)
        # If config is already plaintext dict (dev/test), return as-is
        if isinstance(data, dict):
            return data
    except (json.JSONDecodeError, Exception):
        pass
    # Try Fernet decryption
    try:
        import base64
        import hashlib
        from cryptography.fernet import Fernet
        key = base64.urlsafe_b64encode(hashlib.sha256(settings.SECRET_KEY.encode()).digest())
        f = Fernet(key)
        decrypted = f.decrypt(config_text.encode())
        return json.loads(decrypted)
    except Exception as e:
        logger.warning(f"存储后端配置解密失败: {e}")
        return None


def encrypt_config(config: dict) -> str:
    """Encrypt a config dict for storage in storage_backends.config."""
    import base64
    import hashlib
    from cryptography.fernet import Fernet
    key = base64.urlsafe_b64encode(hashlib.sha256(settings.SECRET_KEY.encode()).digest())
    f = Fernet(key)
    return f.encrypt(json.dumps(config).encode()).decode()


def setup_exchange_rate_schedule() -> None:
    """Schedule rate updates every 2 hours from 08:00 to 22:00 with random 0-15 min offset."""
    for hour in [8, 10, 12, 14, 16, 18, 20, 22]:
        offset = random.randint(0, 15)
        scheduler.add_job(
            fetch_rates_job,
            trigger="cron",
            hour=hour,
            minute=offset,
            id=f"exchange_rate_{hour}",
            replace_existing=True,
        )
    logger.info("汇率定时任务已配置（每2小时，08:00-22:00）")


def setup_file_sync_schedule() -> None:
    """Schedule periodic file sync to the default remote backend."""
    scheduler.add_job(
        file_sync_job,
        trigger="interval",
        minutes=settings.FILE_SYNC_INTERVAL_MINUTES,
        id="file_sync",
        replace_existing=True,
    )
    logger.info(f"文件同步任务已配置（每 {settings.FILE_SYNC_INTERVAL_MINUTES} 分钟）")
