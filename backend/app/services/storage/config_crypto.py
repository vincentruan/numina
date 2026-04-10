"""Storage backend config encryption/decryption utilities."""
import base64
import hashlib
import json

from app.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)


def _fernet_key() -> bytes:
    """Return the Fernet key for storage config encryption.

    Prefers STORAGE_ENCRYPTION_KEY (a raw Fernet key string).
    Falls back to a key derived from SECRET_KEY with a warning — not recommended
    for production because rotating the JWT key would break all stored configs.
    """
    if settings.STORAGE_ENCRYPTION_KEY:
        return settings.STORAGE_ENCRYPTION_KEY.encode()
    logger.warning(
        "STORAGE_ENCRYPTION_KEY 未配置，使用 SECRET_KEY 派生密钥。"
        "生产环境请设置独立的 STORAGE_ENCRYPTION_KEY。"
    )
    return base64.urlsafe_b64encode(
        hashlib.sha256(settings.SECRET_KEY.encode()).digest()
    )


def decrypt_config(config_text: str | None) -> dict | None:
    """Decrypt the storage backend config JSON. Returns None on failure."""
    if not config_text:
        return None
    try:
        data = json.loads(config_text)
        # If config is already plaintext dict (dev/test), return as-is
        if isinstance(data, dict):
            return data
        # If JSON-decoded to a string, treat that string as the encrypted payload
        if isinstance(data, str):
            config_text = data
    except json.JSONDecodeError:
        pass
    # Try Fernet decryption
    try:
        from cryptography.fernet import Fernet
        f = Fernet(_fernet_key())
        decrypted = f.decrypt(config_text.encode())
        return json.loads(decrypted)
    except Exception as e:
        logger.warning(f"存储后端配置解密失败: {e}")
        return None


def encrypt_config(config: dict) -> str:
    """Encrypt a config dict for storage in storage_backends.config."""
    from cryptography.fernet import Fernet
    f = Fernet(_fernet_key())
    return f.encrypt(json.dumps(config).encode()).decode()
