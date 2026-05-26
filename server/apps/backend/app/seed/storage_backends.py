"""Seed storage backends from environment variables."""
from sqlalchemy.orm import Session

from apps.backend.app.core.logging_config import get_logger
from apps.backend.app.models.storage_backend import StorageBackend
from apps.backend.app.services.storage.config_crypto import encrypt_config
from packages.core.settings import settings

logger = get_logger(__name__)


def seed_storage_backends(db: Session) -> None:
    """Load storage backend from environment variables and sync to database.

    - Creates new backend if STORAGE_BACKEND_TYPE is set and backend doesn't exist
    - Updates existing backend's config if changed
    - Preserves backends that exist in DB but not configured via env vars
    - Encrypts credentials before storing
    """
    backend_type = settings.STORAGE_BACKEND_TYPE
    if not backend_type:
        logger.info("STORAGE_BACKEND_TYPE 未设置，跳过远程存储后端加载")
        return

    if backend_type not in ("github", "webdav"):
        logger.warning(f"不支持的存储后端类型: {backend_type}，跳过")
        return

    # Build config dict based on backend type
    config_dict: dict[str, str] = {}
    if backend_type == "github":
        if not all([
            settings.STORAGE_GITHUB_REPO_OWNER,
            settings.STORAGE_GITHUB_REPO_NAME,
            settings.STORAGE_GITHUB_TOKEN,
        ]):
            logger.warning("GitHub 存储后端缺少必要配置（REPO_OWNER/REPO_NAME/TOKEN），跳过")
            return
        config_dict = {
            "repo_owner": settings.STORAGE_GITHUB_REPO_OWNER,
            "repo_name": settings.STORAGE_GITHUB_REPO_NAME,
            "branch": settings.STORAGE_GITHUB_BRANCH,
            "token": settings.STORAGE_GITHUB_TOKEN,
        }
    elif backend_type == "webdav":
        if not all([
            settings.STORAGE_WEBDAV_BASE_URL,
            settings.STORAGE_WEBDAV_USERNAME,
            settings.STORAGE_WEBDAV_PASSWORD,
        ]):
            logger.warning("WebDAV 存储后端缺少必要配置（BASE_URL/USERNAME/PASSWORD），跳过")
            return
        config_dict = {
            "base_url": settings.STORAGE_WEBDAV_BASE_URL,
            "username": settings.STORAGE_WEBDAV_USERNAME,
            "password": settings.STORAGE_WEBDAV_PASSWORD,
        }

    name = settings.STORAGE_BACKEND_NAME or backend_type.upper()
    is_default = settings.STORAGE_BACKEND_IS_DEFAULT
    is_active = settings.STORAGE_BACKEND_IS_ACTIVE

    # Check if backend already exists by display_name
    existing = db.query(StorageBackend).filter_by(display_name=name).first()

    config_encrypted = encrypt_config(config_dict)

    if existing:
        needs_update = False
        # Update existing backend if config changed
        if existing.config != config_encrypted:
            existing.config = config_encrypted
            existing.backend_type = backend_type
            needs_update = True
            logger.info(f"更新存储后端配置: {name}")
        # Update flags if changed
        if existing.is_default != is_default or existing.is_active != is_active:
            existing.is_default = is_default
            existing.is_active = is_active
            needs_update = True
        if needs_update:
            db.commit()
    else:
        # Create new backend
        new_backend = StorageBackend(
            backend_type=backend_type,
            display_name=name,
            config=config_encrypted,
            is_default=is_default,
            is_active=is_active,
        )
        db.add(new_backend)
        db.commit()
        logger.info(f"创建存储后端: {name} (类型: {backend_type})")

    # Validate: only one default backend
    defaults = db.query(StorageBackend).filter_by(is_default=True, is_active=True).all()
    if len(defaults) > 1:
        names = [b.display_name for b in defaults]
        logger.warning(f"存在多个默认存储后端: {names}，只有第一个会被用于同步")