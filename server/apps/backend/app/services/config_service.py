"""Read/write service for family and user configurable settings.

Reads fall back to registry defaults when no DB row exists.
Hot-path reads use a 5-minute LRU cache to avoid per-request DB hits.
"""
import json
import logging
import time
from functools import lru_cache
from typing import Any

from sqlalchemy.orm import Session

from apps.backend.app.errors.codes import ErrorCode
from apps.backend.app.errors.exceptions import AppError
from apps.backend.app.models.family_setting import FamilySetting
from apps.backend.app.models.user_setting import UserSetting
from apps.backend.app.services.config_registry import (
    FAMILY_SETTING_DEFINITIONS,
    USER_SETTING_DEFINITIONS,
    SettingDefinition,
    validate_value,
)
from apps.backend.app.utils.snowflake import next_id

logger = logging.getLogger(__name__)


# --- Internal helpers ---


def _deserialize(value: str | None, defn: SettingDefinition) -> Any:
    """Deserialize a JSON-encoded value string to its typed Python value."""
    if value is None:
        return defn.default
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return defn.default


def _serialize(val: Any) -> str:
    """Serialize a Python value to a JSON string for DB storage."""
    return json.dumps(val)


# --- Family settings ---


def get_family_setting(db: Session, family_id: int, key: str) -> Any:
    """Read a single family setting, falling back to registry default."""
    defn = FAMILY_SETTING_DEFINITIONS[key]
    row = (
        db.query(FamilySetting)
        .filter_by(family_id=family_id, key=key)
        .first()
    )
    return _deserialize(row.value, defn) if row else defn.default


def get_all_family_settings(db: Session, family_id: int) -> dict[str, Any]:
    """Return all family settings merged with defaults."""
    rows = (
        db.query(FamilySetting)
        .filter_by(family_id=family_id)
        .all()
    )
    db_map = {row.key: row.value for row in rows}
    result = {}
    for key, defn in FAMILY_SETTING_DEFINITIONS.items():
        result[key] = _deserialize(db_map.get(key), defn)
    return result


def update_family_settings(
    db: Session, family_id: int, updates: dict[str, Any]
) -> dict[str, Any]:
    """Validate and persist setting updates. Returns merged result.

    Raises AppError(VALIDATION_ERROR) on unknown keys or boundary violations.
    """
    for key, raw_value in updates.items():
        if key not in FAMILY_SETTING_DEFINITIONS:
            raise AppError(
                ErrorCode.VALIDATION_ERROR,
                details=f"未知的家庭配置项: {key}",
            )
        try:
            validated = validate_value("family", key, raw_value)
        except ValueError as e:
            raise AppError(ErrorCode.VALIDATION_ERROR, details=str(e)) from None

        serialized = _serialize(validated)
        row = (
            db.query(FamilySetting)
            .filter_by(family_id=family_id, key=key)
            .first()
        )
        if row is None:
            row = FamilySetting(
                id=next_id(), family_id=family_id, key=key, value=serialized,
            )
            db.add(row)
        else:
            row.value = serialized

    db.commit()
    _invalidate_family_cache(family_id)
    return get_all_family_settings(db, family_id)


# --- User settings ---


def get_user_setting(db: Session, user_id: int, key: str) -> Any:
    """Read a single user setting, falling back to registry default."""
    defn = USER_SETTING_DEFINITIONS[key]
    row = (
        db.query(UserSetting)
        .filter_by(user_id=user_id, key=key)
        .first()
    )
    return _deserialize(row.value, defn) if row else defn.default


def get_all_user_settings(db: Session, user_id: int) -> dict[str, Any]:
    """Return all user settings merged with defaults."""
    rows = (
        db.query(UserSetting)
        .filter_by(user_id=user_id)
        .all()
    )
    db_map = {row.key: row.value for row in rows}
    result = {}
    for key, defn in USER_SETTING_DEFINITIONS.items():
        result[key] = _deserialize(db_map.get(key), defn)
    return result


def update_user_settings(
    db: Session, user_id: int, updates: dict[str, Any]
) -> dict[str, Any]:
    """Validate and persist user setting updates. Returns merged result."""
    for key, raw_value in updates.items():
        if key not in USER_SETTING_DEFINITIONS:
            raise AppError(
                ErrorCode.VALIDATION_ERROR,
                details=f"未知的用户配置项: {key}",
            )
        try:
            validated = validate_value("user", key, raw_value)
        except ValueError as e:
            raise AppError(ErrorCode.VALIDATION_ERROR, details=str(e)) from None

        serialized = _serialize(validated)
        row = (
            db.query(UserSetting)
            .filter_by(user_id=user_id, key=key)
            .first()
        )
        if row is None:
            row = UserSetting(
                id=next_id(), user_id=user_id, key=key, value=serialized,
            )
            db.add(row)
        else:
            row.value = serialized

    db.commit()
    return get_all_user_settings(db, user_id)


# --- Hot-path cache (5-min LRU bucket) ---

_CACHE_TTL_SECONDS = 300  # 5 minutes


def _cache_bucket() -> int:
    """Return current 5-minute time bucket for cache keying."""
    return int(time.time()) // _CACHE_TTL_SECONDS


@lru_cache(maxsize=512)
def _cached_family_setting_raw(family_id: int, key: str, bucket: int) -> Any:  # noqa: ARG001
    """LRU-cached DB read. The bucket param invalidates every 5 minutes."""
    from apps.backend.app.database import SessionLocal

    db = SessionLocal()
    try:
        return get_family_setting(db, family_id, key)
    finally:
        db.close()


def get_family_setting_cached(family_id: int, key: str) -> Any:
    """Read a family setting with 5-minute in-memory cache.

    For hot-path callers that don't have a DB session (e.g. is_cache_fresh).
    Callers must ensure the key exists in FAMILY_SETTING_DEFINITIONS
    (Task 9 callers guard with ``if config_key in FAMILY_SETTING_DEFINITIONS``).
    """
    return _cached_family_setting_raw(family_id, key, _cache_bucket())


def _invalidate_family_cache(family_id: int) -> None:  # noqa: ARG001
    """Clear all cached entries. family_id accepted for future per-family invalidation."""
    _cached_family_setting_raw.cache_clear()
