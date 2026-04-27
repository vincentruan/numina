"""Seed storage backends from YAML config file."""
from pathlib import Path

import yaml
from sqlalchemy.orm import Session

from app.core.logging_config import get_logger
from app.models.storage_backend import StorageBackend
from app.services.storage.config_crypto import encrypt_config

logger = get_logger(__name__)

CONFIG_FILE = Path(__file__).parent.parent / "config" / "storage_backends.yaml"


def seed_storage_backends(db: Session) -> None:
    """Load storage backends from YAML config and sync to database.

    - Creates new backends that don't exist (by display_name)
    - Updates existing backends' config if changed
    - Preserves backends that exist in DB but not in config
    - Encrypts credentials before storing
    """
    if not CONFIG_FILE.exists():
        logger.info(f"存储后端配置文件不存在: {CONFIG_FILE}，跳过加载")
        return

    try:
        with open(CONFIG_FILE, encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except Exception as e:
        logger.warning(f"存储后端配置文件解析失败: {e}")
        return

    if not data or "backends" not in data:
        logger.info("存储后端配置文件无 backends 条目，跳过加载")
        return

    backends_config = data.get("backends", [])
    if not backends_config:
        logger.info("存储后端配置为空列表，跳过加载")
        return

    for backend_cfg in backends_config:
        name = backend_cfg.get("name")
        backend_type = backend_cfg.get("type")
        is_default = backend_cfg.get("is_default", False)
        is_active = backend_cfg.get("is_active", True)
        config_dict = backend_cfg.get("config", {})

        if not name or not backend_type:
            logger.warning(f"存储后端配置缺少 name 或 type，跳过: {backend_cfg}")
            continue

        if backend_type not in ("github", "webdav"):
            logger.warning(f"不支持的存储后端类型: {backend_type}，跳过")
            continue

        # Check if backend already exists by display_name
        existing = db.query(StorageBackend).filter_by(display_name=name).first()

        if existing:
            # Update existing backend if config changed
            new_config_encrypted = encrypt_config(config_dict)
            if existing.config != new_config_encrypted:
                existing.config = new_config_encrypted
                existing.backend_type = backend_type
                existing.is_default = is_default
                existing.is_active = is_active
                logger.info(f"更新存储后端配置: {name}")
            # Update flags even if config unchanged
            if existing.is_default != is_default or existing.is_active != is_active:
                existing.is_default = is_default
                existing.is_active = is_active
                db.commit()
        else:
            # Create new backend
            config_encrypted = encrypt_config(config_dict)
            new_backend = StorageBackend(
                backend_type=backend_type,
                display_name=name,
                config=config_encrypted,
                is_default=is_default,
                is_active=is_active,
            )
            db.add(new_backend)
            logger.info(f"创建存储后端: {name} (类型: {backend_type})")

    db.commit()
    logger.info(f"存储后端配置已同步，共处理 {len(backends_config)} 条")

    # Validate: only one default backend
    defaults = db.query(StorageBackend).filter_by(is_default=True, is_active=True).all()
    if len(defaults) > 1:
        names = [b.display_name for b in defaults]
        logger.warning(f"存在多个默认存储后端: {names}，只有第一个会被用于同步")