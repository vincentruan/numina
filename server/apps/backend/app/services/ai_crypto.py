"""AI API Key 加密/解密工具（Fernet AES-256）。"""

import logging

from apps.backend.app.config import settings

logger = logging.getLogger(__name__)


def _get_fernet():
    """获取 Fernet 实例，懒加载。"""
    try:
        from cryptography.fernet import Fernet
        if not settings.AI_ENCRYPTION_KEY:
            return None
        return Fernet(settings.AI_ENCRYPTION_KEY.encode() if isinstance(settings.AI_ENCRYPTION_KEY, str) else settings.AI_ENCRYPTION_KEY)
    except Exception as e:
        logger.warning(f"Fernet 初始化失败: {e}")
        return None


def encrypt_api_key(api_key: str) -> str | None:
    """加密 API Key，返回 base64 密文字符串。AI_ENCRYPTION_KEY 未配置时返回 None。"""
    fernet = _get_fernet()
    if not fernet:
        return None
    return fernet.encrypt(api_key.encode()).decode()


def decrypt_api_key(encrypted: str) -> str | None:
    """解密 API Key，失败时返回 None。"""
    fernet = _get_fernet()
    if not fernet or not encrypted:
        return None
    try:
        return fernet.decrypt(encrypted.encode()).decode()
    except Exception as e:
        logger.error(f"API Key 解密失败: {e}")
        return None


def mask_api_key(api_key: str) -> str:
    """脱敏展示 API Key，如 sk-2b353***********************6acb。"""
    if len(api_key) <= 11:
        return "****"
    hidden_len = len(api_key) - 7 - 4
    return api_key[:7] + "*" * hidden_len + api_key[-4:]
