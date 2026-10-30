"""Family data export — the payload behind every backup.

Both the API and the scheduler job call this, so the payload shape has one
definition. Two rules govern everything here:

* Every family-scoped table is covered. A table missing from this payload is
  data the family cannot recover after a total loss.
* Secrets are copied as their encrypted blob and never decrypted. The backup
  then inherits the same key requirement as the live database, which is the
  correct property: whoever restores it already had the key.
"""

from __future__ import annotations

import contextlib
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from packages.db.models.asset import Asset, asset_tags
from packages.db.models.asset_snapshot import AssetSnapshot
from packages.db.models.cached_file import CachedFile
from packages.db.models.category import Category
from packages.db.models.child_economy.chore import ChoreInstance, ChoreTemplate
from packages.db.models.child_economy.coin_transaction import CoinTransaction
from packages.db.models.expense_category import ExpenseCategory
from packages.db.models.expense_entry import ExpenseEntry
from packages.db.models.file_remote_location import FileRemoteLocation
from packages.db.models.itinerary_item import ItineraryItem
from packages.db.models.learning.progress import LearningProgress
from packages.db.models.learning.session import (
    LearningAssessmentAttempt,
    LearningSession,
)
from packages.db.models.learning.stats import ChildLearningStats
from packages.db.models.liability import Liability
from packages.db.models.notification_channel import NotificationChannel
from packages.db.models.notification_config import NotificationConfig
from packages.db.models.reminder import Reminder
from packages.db.models.reminder_notification import ReminderNotification
from packages.db.models.rental_contract import RentalContract
from packages.db.models.storage_backend import StorageBackend
from packages.db.models.tag import Tag
from packages.db.models.trip import Trip
from packages.db.models.user import User
from packages.db.models.wish import Wish

EXPORT_VERSION = "2.0"
VALID_EXPORT_VERSIONS: tuple[str, ...] = ("1.0", "2.0")

# Describes the column set captured per table. Dates and money are converted
# by ``_serialize``; anything not listed is copied through unchanged.
_ID_FIELDS = {
    "id",
    "family_id",
    "user_id",
    "child_id",
    "child_user_id",
    "category_id",
    "linked_asset_id",
    "file_id",
    "backend_id",
    "reminder_id",
    "channel_id",
    "trip_id",
    "topic_id",
    "template_id",
    "created_by",
    "session_id",
    "assignment_id",
    "ref_id",
    "wish_id",
    "realized_asset_id",
    "from_wish_id",
    "config_id",
    "asset_id",
    "thread_id",
    "itinerary_item_id",
    "transfer_id",
    "submitted_by_user_id",
    "assigned_by_user_id",
    "overridden_by",
    "custom_type_id",
}


def export_family_data(db: Session, family_id: int) -> dict[str, Any]:
    """Serialize every family-scoped row into a JSON-ready backup payload."""
    # App-owned models are imported here rather than at module scope: domain
    # packages must not import apps, and this mirrors the lazy-import pattern
    # already used by the snapshot and notification subpackages.
    from apps.backend.app.models.ai_provider_config import AIProviderConfig
    from apps.backend.app.models.child_milestone import ChildMilestone

    return {
        "export_version": EXPORT_VERSION,
        "export_date": date.today().isoformat(),
        "family_id": str(family_id),
        "users": [_serialize(u, _USER_FIELDS) for u in _query(db, User, family_id)],
        "assets": [_asset(a) for a in _query(db, Asset, family_id)],
        "liabilities": [
            _serialize(x, _LIABILITY_FIELDS) for x in _query(db, Liability, family_id)
        ],
        "categories": [
            _serialize(c, _CATEGORY_FIELDS) for c in _custom_categories(db, family_id)
        ],
        "tags": [_serialize(t, _TAG_FIELDS) for t in _query(db, Tag, family_id)],
        "wishes": [_serialize(w, _WISH_FIELDS) for w in _query(db, Wish, family_id)],
        "chores": _chores(db, family_id),
        "coin_transactions": [
            _serialize(c, _COIN_FIELDS) for c in _query(db, CoinTransaction, family_id)
        ],
        "milestones": [
            _serialize(m, _MILESTONE_FIELDS)
            for m in _query(db, ChildMilestone, family_id)
        ],
        "rental_contracts": [
            _serialize(r, _RENTAL_FIELDS) for r in _query(db, RentalContract, family_id)
        ],
        "asset_snapshots": [
            _serialize(s, _SNAPSHOT_FIELDS)
            for s in _query(db, AssetSnapshot, family_id)
        ],
        "trips": [_serialize(t, _TRIP_FIELDS) for t in _query(db, Trip, family_id)],
        "itinerary_items": [
            _serialize(i, _ITINERARY_FIELDS)
            for i in _query(db, ItineraryItem, family_id)
        ],
        "expense_entries": [
            _serialize(e, _EXPENSE_FIELDS) for e in _query(db, ExpenseEntry, family_id)
        ],
        "expense_categories": [
            _serialize(c, _EXPENSE_CATEGORY_FIELDS)
            for c in _query(db, ExpenseCategory, family_id)
        ],
        "cached_files": [
            _serialize(f, _CACHED_FILE_FIELDS)
            for f in _query(db, CachedFile, family_id)
        ],
        "file_remote_locations": _remote_locations(db, family_id),
        "storage_backends": [
            _serialize(b, _STORAGE_BACKEND_FIELDS)
            for b in _query(db, StorageBackend, family_id)
        ],
        "learning_progress": [
            _serialize(p, _LEARNING_PROGRESS_FIELDS)
            for p in _learning_progress(db, family_id)
        ],
        "learning_stats": [
            _serialize(s, _LEARNING_STATS_FIELDS)
            for s in _query(db, ChildLearningStats, family_id)
        ],
        "learning_sessions": _learning_sessions(db, family_id),
        "notification_channels": [
            _serialize(n, _NOTIFICATION_CHANNEL_FIELDS)
            for n in _query(db, NotificationChannel, family_id)
        ],
        "notification_configs": [
            _serialize(n, _NOTIFICATION_CONFIG_FIELDS)
            for n in _query(db, NotificationConfig, family_id)
        ],
        "reminders": [
            _serialize(r, _REMINDER_FIELDS) for r in _query(db, Reminder, family_id)
        ],
        "reminder_notifications": _reminder_notifications(db, family_id),
        "ai_provider_configs": [
            _serialize(p, _AI_PROVIDER_FIELDS)
            for p in _query(db, AIProviderConfig, family_id)
        ],
    }


# ── Queries ───────────────────────────────────────────────────────────────────


def _query(db: Session, model, family_id: int) -> list:
    rows: list = db.query(model).filter(model.family_id == family_id).all()
    return rows


def _custom_categories(db: Session, family_id: int) -> list:
    """Only family-owned categories; seeded system rows are recreated on boot."""
    rows: list = db.query(Category).filter(Category.family_id == family_id).all()
    return rows


def _chores(db: Session, family_id: int) -> list[dict]:
    """Templates and their instances are one section, tagged by kind."""
    rows: list[dict] = []
    for template in _query(db, ChoreTemplate, family_id):
        item = _serialize(template, _CHORE_TEMPLATE_FIELDS)
        item["kind"] = "template"
        rows.append(item)
    for instance in _query(db, ChoreInstance, family_id):
        item = _serialize(instance, _CHORE_INSTANCE_FIELDS)
        item["kind"] = "instance"
        rows.append(item)
    return rows


def _remote_locations(db: Session, family_id: int) -> list[dict]:
    """Reached through the owning file, since this table has no family_id."""
    return [
        _serialize(loc, _REMOTE_LOCATION_FIELDS)
        for loc in db.query(FileRemoteLocation)
        .join(CachedFile, CachedFile.id == FileRemoteLocation.file_id)
        .filter(CachedFile.family_id == family_id)
        .all()
    ]


def _learning_progress(db: Session, family_id: int) -> list:
    """Progress rows are keyed by child, which carries the family link."""
    child_ids = [u.id for u in _query(db, User, family_id)]
    if not child_ids:
        return []
    return (
        db.query(LearningProgress)
        .filter(LearningProgress.child_id.in_(child_ids))
        .all()
    )


def _learning_sessions(db: Session, family_id: int) -> list[dict]:
    child_ids = [u.id for u in _query(db, User, family_id)]
    if not child_ids:
        return []
    rows: list[dict] = []
    sessions = (
        db.query(LearningSession).filter(LearningSession.child_id.in_(child_ids)).all()
    )
    for session in sessions:
        item = _serialize(session, _LEARNING_SESSION_FIELDS)
        item["kind"] = "session"
        rows.append(item)
    session_ids = [s.id for s in sessions]
    if session_ids:
        attempts = (
            db.query(LearningAssessmentAttempt)
            .filter(LearningAssessmentAttempt.session_id.in_(session_ids))
            .all()
        )
        for attempt in attempts:
            item = _serialize(attempt, _LEARNING_ATTEMPT_FIELDS)
            item["kind"] = "assessment_attempt"
            rows.append(item)
    return rows


def _reminder_notifications(db: Session, family_id: int) -> list[dict]:
    reminder_ids = [r.id for r in _query(db, Reminder, family_id)]
    if not reminder_ids:
        return []
    return [
        _serialize(n, _REMINDER_NOTIFICATION_FIELDS)
        for n in db.query(ReminderNotification)
        .filter(ReminderNotification.reminder_id.in_(reminder_ids))
        .all()
    ]


# ── Serialization ─────────────────────────────────────────────────────────────


def _asset(asset: Asset) -> dict[str, Any]:
    item = _serialize(asset, _ASSET_FIELDS)
    item["tag_names"] = [t.name for t in asset.tags] if asset.tags else []
    item["category_name"] = asset.category.name if asset.category else None
    item["category_asset_type"] = asset.category.asset_type if asset.category else None
    return item


def _serialize(obj, fields: tuple[str, ...]) -> dict[str, Any]:
    return {name: _coerce(name, getattr(obj, name, None)) for name in fields}


def _coerce(name: str, value: Any) -> Any:
    if value is None:
        return None
    if name in _ID_FIELDS:
        return str(value)
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def _decoerce(name: str, value: Any) -> Any:
    """Turn JSON strings back into ORM-friendly date/datetime values."""
    if value is None:
        return None
    if (name.endswith("_date") or name.endswith("_at")) and isinstance(value, str):
        for parser in (datetime.fromisoformat, date.fromisoformat):
            try:
                return parser(value)
            except ValueError:
                continue
    return value


_ASSET_FIELDS = (
    "id",
    "user_id",
    "family_id",
    "category_id",
    "name",
    "asset_type",
    "purchase_price",
    "current_value",
    "currency",
    "purchase_date",
    "status",
    "location",
    "institution",
    "interest_rate",
    "maturity_date",
    "warranty_expiry_date",
    "expected_lifespan_days",
    "annual_maintenance_cost",
    "usage_frequency",
    "properties",
    "notes",
    "target_daily_cost",
    "image_url",
    "from_wish_id",
    "is_archived",
)
_LIABILITY_FIELDS = (
    "id",
    "user_id",
    "family_id",
    "category",
    "repayment_method",
    "name",
    "original_amount",
    "remaining_amount",
    "monthly_payment",
    "interest_rate",
    "start_date",
    "end_date",
    "institution",
    "linked_asset_id",
    "notes",
    "is_active",
    "is_archived",
    "currency",
)
_CATEGORY_FIELDS = ("id", "family_id", "name", "icon", "color", "asset_type")
_TAG_FIELDS = ("id", "family_id", "name", "color")
_WISH_FIELDS = (
    "id",
    "family_id",
    "user_id",
    "name",
    "description",
    "expected_price",
    "priority",
    "status",
    "category_id",
    "currency",
    "saved_amount",
    "target_date",
    "monthly_saving",
    "ignore_debt_warning",
    "converts_to_asset",
    "realized_asset_id",
    "fulfilled_at",
    "travel_destination",
    "travel_duration_days",
    "rental_area",
)
_USER_FIELDS = (
    "id",
    "family_id",
    "username",
    "role",
    "display_name",
    "avatar_url",
    "is_active",
    "birthday",
    "created_at",
    # Credentials travel with the backup: a restore that leaves nobody able to
    # log in has not restored the family. These are already password/PIN hashes
    # and WebAuthn credential records, inside the same trust boundary as the
    # encrypted config blobs above.
    "password_hash",
    "pin_hash",
    "numeric_pin_hash",
    "second_factor_type",
    "second_factor_enabled",
    "webauthn_credentials",
)
_CHORE_TEMPLATE_FIELDS = (
    "id",
    "family_id",
    "created_by",
    "name",
    "emoji",
    "coin_reward",
    "frequency",
    "assignment_type",
    "is_active",
    "real_reward_enabled",
)
_CHORE_INSTANCE_FIELDS = (
    "id",
    "template_id",
    "family_id",
    "child_user_id",
    "chore_name",
    "chore_emoji",
    "coin_reward",
    "date_bucket",
    "status",
    "submitted_at",
    "approved_at",
    "streak_count",
    "streak_bonus",
    "submitted_by_user_id",
    "assigned_by_user_id",
    "claimed_at",
    "consumed_at",
)
_COIN_FIELDS = (
    "id",
    "family_id",
    "child_user_id",
    "amount",
    "transaction_type",
    "ref_id",
    "narrative",
    "narrative_emoji",
    "streak_bonus",
)
_MILESTONE_FIELDS = (
    "id",
    "family_id",
    "child_user_id",
    "milestone_type",
    "triggered_at",
    "ref_id",
    "ref_type",
)
_RENTAL_FIELDS = (
    "id",
    "user_id",
    "family_id",
    "role",
    "monthly_rent",
    "deposit",
    "start_date",
    "end_date",
    "linked_asset_id",
    "counterparty",
    "notes",
    "currency",
    "is_active",
)
_SNAPSHOT_FIELDS = (
    "id",
    "family_id",
    "user_id",
    "snapshot_date",
    "total_assets",
    "total_liabilities",
    "net_worth",
    "breakdown",
)
_TRIP_FIELDS = (
    "id",
    "family_id",
    "user_id",
    "name",
    "description",
    "destination",
    "departure_date",
    "return_date",
    "status",
    "planned_budget",
    "initial_funding",
    "actual_spend",
    "currency",
    "wish_id",
    "timezone",
    "is_active",
)
_ITINERARY_FIELDS = (
    "id",
    "trip_id",
    "family_id",
    "date",
    "end_date",
    "type",
    "sort_order",
    "start_time",
    "end_time",
    "location",
    "description",
    "cost_amount",
    "cost_currency",
    "purchase_date",
    "custom_type_id",
    "type_metadata",
)
_EXPENSE_FIELDS = (
    "id",
    "family_id",
    "transfer_id",
    "leg_type",
    "ref_id",
    "ref_type",
    "category_id",
    "amount",
    "currency",
    "amount_cny",
    "exchange_rate",
    "expense_date",
    "description",
    "receipt_image_url",
    "split_type",
    "itinerary_item_id",
    "user_id",
)
_EXPENSE_CATEGORY_FIELDS = (
    "id",
    "family_id",
    "name",
    "icon",
    "sort_order",
    "is_system",
)
_CACHED_FILE_FIELDS = (
    "id",
    "family_id",
    "user_id",
    "local_path",
    "original_filename",
    "mime_type",
    "size_bytes",
    "date_dir",
    "deleted_at",
)
_REMOTE_LOCATION_FIELDS = (
    "id",
    "file_id",
    "backend_id",
    "remote_path",
    "remote_url",
    "remote_sha",
    "sync_status",
    "synced_at",
    "last_error",
    "retry_count",
)
_STORAGE_BACKEND_FIELDS = (
    "id",
    "family_id",
    "backend_type",
    "display_name",
    "config",
    "is_active",
)
_LEARNING_PROGRESS_FIELDS = (
    "id",
    "child_id",
    "topic_id",
    "mastery_level",
    "mastery_score",
    "completed_via",
    "attempts",
    "xp_earned",
    "last_practice_at",
    "first_mastered_at",
    "stability",
    "ease_factor",
    "next_review_at",
    "ability_dimensions_score_json",
    "overridden_by",
    "overridden_at",
    "override_reason",
)
_LEARNING_STATS_FIELDS = (
    "id",
    "child_id",
    "family_id",
    "cumulative_xp",
    "level",
    "learning_streak_days",
    "last_learning_date",
    "current_zone",
    "onboarding_completed",
    "xp_today",
    "last_xp_date",
    "consecutive_ai_overrides",
)
_LEARNING_SESSION_FIELDS = (
    "id",
    "assignment_id",
    "child_id",
    "topic_id",
    "thread_id",
    "session_type",
    "ai_evaluation_json",
    "score",
    "duration_seconds",
    "started_at",
    "ended_at",
)
_LEARNING_ATTEMPT_FIELDS = (
    "id",
    "child_id",
    "topic_id",
    "session_id",
    "assessment_type",
    "score",
    "passed",
    "ai_confidence",
    "evidence_results_json",
    "ability_dimensions_delta_json",
    "duration_seconds",
)
_NOTIFICATION_CHANNEL_FIELDS = (
    "id",
    "family_id",
    "channel_type",
    "name",
    "is_enabled",
    "digest_mode",
    "digest_time",
)
_NOTIFICATION_CONFIG_FIELDS = (
    "id",
    "family_id",
    "large_purchase_threshold_fixed",
    "large_purchase_threshold_multiplier",
)
_REMINDER_FIELDS = (
    "id",
    "family_id",
    "reminder_type",
    "title",
    "body",
    "severity",
    "asset_id",
    "child_id",
    "topic_id",
    "status",
    "dismissed_at",
    "resolved_at",
    "digest_sent_at",
)
_REMINDER_NOTIFICATION_FIELDS = ("id", "reminder_id", "channel_id", "status")
_AI_PROVIDER_FIELDS = (
    "id",
    "family_id",
    "name",
    "provider",
    "api_key_encrypted",
    "base_url",
    "model_id",
    "vision_model_id",
    "timeout_seconds",
    "thinking_supported",
    "is_active",
    "max_tokens",
    "provider_name",
    "display_order",
)


# ── Restore ───────────────────────────────────────────────────────────────────


def validate_backup_data(payload: Any) -> list[str]:
    """Validate a backup payload without writing.

    Returns a list of error strings; an empty list means the payload is valid.
    """
    if not isinstance(payload, dict):
        return ["备份不是有效的字典"]
    version = payload.get("export_version")
    if version not in VALID_EXPORT_VERSIONS:
        supported = ", ".join(VALID_EXPORT_VERSIONS)
        return [f"不支持的备份版本: {version}，当前支持: {supported}"]

    errors: list[str] = []
    categories_in_payload: set[str] = set()
    for cat in payload.get("categories", []):
        cat_id = cat.get("id")
        if cat_id is not None:
            categories_in_payload.add(str(cat_id))

    # Orphan check: category_id references must be satisfied by the payload or
    # by a system row (family_id IS NULL) already in the database.
    system_category_ids: set[str] = set()
    try:
        from packages.db.session import SessionLocal

        db = SessionLocal()
        try:
            system_category_ids = {
                str(row.id)
                for row in db.query(Category).filter(Category.family_id.is_(None)).all()
            }
        finally:
            db.close()
    except Exception:
        # No live database available — skip system-row resolution. The caller
        # (import_family_data) will validate with the session it owns.
        pass

    for section_name in (
        "assets",
        "liabilities",
        "wishes",
        "rental_contracts",
        "expense_entries",
        "itinerary_items",
    ):
        for row in payload.get(section_name, []):
            cat_id = row.get("category_id")
            if cat_id is None:
                continue
            if (
                str(cat_id) not in categories_in_payload
                and str(cat_id) not in system_category_ids
            ):
                errors.append(
                    f"{section_name} 引用了不存在的分类: category_id={cat_id}"
                )
                break
    return errors


def preview_restore(
    db: Session, family_id: int, payload: dict[str, Any]
) -> dict[str, Any]:
    """Count rows that would be deleted and inserted by a restore."""
    delete_counts: dict[str, int] = {}
    for model in _DELETE_ORDER:
        count = _delete_count(db, model, family_id)
        if count:
            delete_counts[_section_name_for(model)] = count

    insert_counts: dict[str, int] = {}
    for section in _INSERT_SECTIONS:
        rows = payload.get(section) or []
        if rows:
            insert_counts[section] = len(rows)

    return {
        "delete": delete_counts,
        "insert": insert_counts,
        "backup_date": payload.get("export_date"),
        "export_version": payload.get("export_version"),
    }


def import_family_data(
    db: Session, family_id: int, user_id: int, payload: dict[str, Any]
) -> dict[str, int]:
    """Restore a family from a backup payload inside a single transaction.

    Raises ``ValueError`` for validation failures — the existing data is left
    untouched in that case.
    """
    from apps.backend.app.models.ai_provider_config import AIProviderConfig
    from apps.backend.app.models.child_milestone import ChildMilestone

    errors = validate_backup_data_with_session(db, payload)
    if errors:
        raise ValueError(errors[0])

    # Delete existing family-scoped rows in FK-safe order.
    for model in _DELETE_ORDER:
        if model is Asset:
            # asset_tags has no family_id of its own, so clear the links for
            # this family's assets before the assets themselves go.
            _clear_asset_tags(db, family_id)
        _delete_all(db, model, family_id)
    db.flush()
    # Bulk delete bypasses identity-map bookkeeping; a new row with the same
    # primary key as a just-deleted one otherwise collides with the stale
    # identity entry. expunge_all clears the stale entries.
    db.expunge_all()

    stats: dict[str, int] = {}
    obj: Any
    # Category and tag remapping — the payload's rows may reference categories
    # and tags by name (composite key for categories) rather than by ID.
    category_map = _remap_categories(db, family_id, payload.get("categories", []))
    tag_map = _remap_tags(db, family_id, payload.get("tags", []))

    stats["categories"] = _insert_rows(
        db, Category, family_id, payload.get("categories", []), category_map
    )
    stats["tags"] = _insert_rows(db, Tag, family_id, payload.get("tags", []), {})
    # Users are identity, not family content: upsert so members who joined after
    # the backup keep their accounts, and so re-inserting a preserved primary key
    # does not collide with the row that is still there.
    stats["users"] = _upsert_users(db, family_id, payload.get("users", []))

    # Assets carry tag_names; resolve them against tag_map.
    for row in payload.get("assets", []):
        row["category_id"] = _resolve_category_id(
            db, family_id, row, category_map
        )
        resolved_tag_names = [
            t for t in (row.pop("tag_names", None) or []) if t in tag_map
        ]
        asset = Asset(**_filter_fields(row, _ASSET_FIELDS))
        asset.user_id = int(asset.user_id) if asset.user_id is not None else user_id
        asset.family_id = (
            int(asset.family_id) if asset.family_id is not None else family_id
        )
        asset.category_id = int(asset.category_id) if asset.category_id else None
        _coerce_asset(asset)
        if resolved_tag_names:
            asset.tags = _tag_objects(db, resolved_tag_names, tag_map)
        db.add(asset)
        stats["assets"] = stats.get("assets", 0) + 1

    model_sections: list[tuple[str, Any, tuple[str, ...]]] = [
        ("liabilities", Liability, _LIABILITY_FIELDS),
        ("wishes", Wish, _WISH_FIELDS),
        ("rental_contracts", RentalContract, _RENTAL_FIELDS),
        ("asset_snapshots", AssetSnapshot, _SNAPSHOT_FIELDS),
        ("trips", Trip, _TRIP_FIELDS),
        ("itinerary_items", ItineraryItem, _ITINERARY_FIELDS),
        ("expense_entries", ExpenseEntry, _EXPENSE_FIELDS),
        ("expense_categories", ExpenseCategory, _EXPENSE_CATEGORY_FIELDS),
        ("cached_files", CachedFile, _CACHED_FILE_FIELDS),
        ("notification_channels", NotificationChannel, _NOTIFICATION_CHANNEL_FIELDS),
        ("notification_configs", NotificationConfig, _NOTIFICATION_CONFIG_FIELDS),
        ("reminders", Reminder, _REMINDER_FIELDS),
    ]
    for model_name, model, fields in model_sections:
        count = 0
        for row in payload.get(model_name, []):
            obj = model(**_filter_fields(row, fields))
            _ensure_family(obj, family_id, user_id)
            _coerce_ids(obj, family_id, category_map)
            db.add(obj)
            count += 1
        stats[model_name] = count

    # App-owned models — imported lazily.
    app_models: list[tuple[str, Any]] = [
        ("milestones", ChildMilestone),
        ("ai_provider_configs", AIProviderConfig),
    ]
    for model_name, model in app_models:
        count = 0
        app_fields = _fields_for(model_name)
        if app_fields is None:
            continue
        for row in payload.get(model_name, []):
            obj = model(**_filter_fields(row, app_fields))
            _ensure_family(obj, family_id, user_id)
            db.add(obj)
            count += 1
        stats[model_name] = count

    # File remote locations — reached through the file_id's family.
    for row in payload.get("file_remote_locations", []):
        obj = FileRemoteLocation(**_filter_fields(row, _REMOTE_LOCATION_FIELDS))
        _coerce_ids(obj, family_id, {})
        db.add(obj)
        stats["file_remote_locations"] = stats.get("file_remote_locations", 0) + 1

    # Storage backend config — encrypted blob preserved verbatim.
    for row in payload.get("storage_backends", []):
        obj = StorageBackend(**_filter_fields(row, _STORAGE_BACKEND_FIELDS))
        _coerce_ids(obj, family_id, {})
        db.add(obj)
        stats["storage_backends"] = stats.get("storage_backends", 0) + 1

    # Learning tables — keyed by child_id, which is already in the payload.
    for row in payload.get("learning_progress", []):
        obj = LearningProgress(**_filter_fields(row, _LEARNING_PROGRESS_FIELDS))
        _coerce_ids(obj, family_id, {})
        db.add(obj)
        stats["learning_progress"] = stats.get("learning_progress", 0) + 1

    for row in payload.get("learning_stats", []):
        obj = ChildLearningStats(**_filter_fields(row, _LEARNING_STATS_FIELDS))
        _coerce_ids(obj, family_id, {})
        db.add(obj)
        stats["learning_stats"] = stats.get("learning_stats", 0) + 1

    for row in payload.get("learning_sessions", []):
        session_obj: Any
        if row.get("kind") == "session":
            session_obj = LearningSession(
                **_filter_fields(row, _LEARNING_SESSION_FIELDS)
            )
        else:
            session_obj = LearningAssessmentAttempt(
                **_filter_fields(row, _LEARNING_ATTEMPT_FIELDS)
            )
        obj = session_obj
        _coerce_ids(obj, family_id, {})
        db.add(obj)
        stats["learning_sessions"] = stats.get("learning_sessions", 0) + 1

    for row in payload.get("chores", []):
        if row.get("kind") == "template":
            obj = ChoreTemplate(**_filter_fields(row, _CHORE_TEMPLATE_FIELDS))
        else:
            obj = ChoreInstance(**_filter_fields(row, _CHORE_INSTANCE_FIELDS))
        _coerce_ids(obj, family_id, {})
        db.add(obj)
        stats["chores"] = stats.get("chores", 0) + 1

    for row in payload.get("coin_transactions", []):
        obj = CoinTransaction(**_filter_fields(row, _COIN_FIELDS))
        _coerce_ids(obj, family_id, {})
        db.add(obj)
        stats["coin_transactions"] = stats.get("coin_transactions", 0) + 1

    for row in payload.get("reminder_notifications", []):
        obj = ReminderNotification(**_filter_fields(row, _REMINDER_NOTIFICATION_FIELDS))
        _coerce_ids(obj, family_id, {})
        db.add(obj)
        stats["reminder_notifications"] = stats.get("reminder_notifications", 0) + 1

    db.flush()
    return stats


def validate_backup_data_with_session(
    db: Session, payload: dict[str, Any]
) -> list[str]:
    """Validate a backup using the caller's live session for orphan resolution."""
    if not isinstance(payload, dict):
        return ["备份不是有效的字典"]
    version = payload.get("export_version")
    if version not in VALID_EXPORT_VERSIONS:
        supported = ", ".join(VALID_EXPORT_VERSIONS)
        return [f"不支持的备份版本: {version}，当前支持: {supported}"]

    categories_in_payload: set[str] = {
        str(c.get("id"))
        for c in payload.get("categories", [])
        if c.get("id") is not None
    }
    system_category_ids = {
        str(row.id)
        for row in db.query(Category).filter(Category.family_id.is_(None)).all()
    }
    system_natural_keys = {
        (row.name, row.asset_type)
        for row in db.query(Category).filter(Category.family_id.is_(None)).all()
    }
    errors: list[str] = []
    for row in payload.get("assets", []):
        natural = (row.get("category_name"), row.get("category_asset_type"))
        if natural[0] is not None and natural in system_natural_keys:
            continue
        cat_id = row.get("category_id")
        if cat_id is None:
            continue
        if (
            str(cat_id) not in categories_in_payload
            and str(cat_id) not in system_category_ids
        ):
            errors.append(f"资产引用了不存在的分类: category_id={cat_id}")
    return errors


# ── Delete order ──────────────────────────────────────────────────────────────


_DELETE_ORDER = (
    ReminderNotification,
    Reminder,
    NotificationChannel,
    NotificationConfig,
    AssetSnapshot,
    ExpenseEntry,
    ItineraryItem,
    Trip,
    CachedFile,
    FileRemoteLocation,
    RentalContract,
    CoinTransaction,
    ChoreInstance,
    ChoreTemplate,
    Liability,
    Asset,
    Wish,
    Tag,
    Category,
)


def _family_predicate(db: Session, model, family_id: int):
    """Return a query filter that selects rows owned by this family."""
    if model is ReminderNotification:
        reminder_ids = [
            r.id for r in db.query(Reminder).filter_by(family_id=family_id).all()
        ]
        return (
            ReminderNotification.reminder_id.in_(reminder_ids) if reminder_ids else None
        )
    if model is FileRemoteLocation:
        file_ids = [
            f.id for f in db.query(CachedFile).filter_by(family_id=family_id).all()
        ]
        return FileRemoteLocation.file_id.in_(file_ids) if file_ids else None
    return model.family_id == family_id


def _delete_count(db: Session, model, family_id: int) -> int:
    predicate = _family_predicate(db, model, family_id)
    if predicate is None:
        return 0
    count = db.query(model).filter(predicate).count()
    return int(count)


def _delete_all(db: Session, model, family_id: int) -> None:
    predicate = _family_predicate(db, model, family_id)
    if predicate is None:
        return
    db.query(model).filter(predicate).delete(synchronize_session=False)


def _clear_asset_tags(db: Session, family_id: int) -> None:
    """Drop asset/tag links for this family before the assets are deleted."""
    asset_ids = [a.id for a in db.query(Asset).filter_by(family_id=family_id).all()]
    if asset_ids:
        db.execute(asset_tags.delete().where(asset_tags.c.asset_id.in_(asset_ids)))


_SECTION_NAMES = {
    Asset: "assets",
    Liability: "liabilities",
    Category: "categories",
    Tag: "tags",
    User: "users",
    Wish: "wishes",
    ChoreTemplate: "chores",
    ChoreInstance: "chores",
    CoinTransaction: "coin_transactions",
    RentalContract: "rental_contracts",
    AssetSnapshot: "asset_snapshots",
    Trip: "trips",
    ItineraryItem: "itinerary_items",
    ExpenseEntry: "expense_entries",
    ExpenseCategory: "expense_categories",
    CachedFile: "cached_files",
    FileRemoteLocation: "file_remote_locations",
    StorageBackend: "storage_backends",
    LearningProgress: "learning_progress",
    ChildLearningStats: "learning_stats",
    NotificationChannel: "notification_channels",
    NotificationConfig: "notification_configs",
    Reminder: "reminders",
    ReminderNotification: "reminder_notifications",
}


def _section_name_for(model) -> str:
    """Map a model to its payload section; app-owned models resolve lazily."""
    name = _SECTION_NAMES.get(model)
    if name is not None:
        return name
    from apps.backend.app.models.ai_provider_config import AIProviderConfig
    from apps.backend.app.models.child_milestone import ChildMilestone

    if model is ChildMilestone:
        return "milestones"
    if model is AIProviderConfig:
        return "ai_provider_configs"
    return str(model.__tablename__)


_INSERT_SECTIONS = (
    "categories",
    "tags",
    "users",
    "assets",
    "liabilities",
    "wishes",
    "rental_contracts",
    "asset_snapshots",
    "trips",
    "itinerary_items",
    "expense_entries",
    "expense_categories",
    "cached_files",
    "notification_channels",
    "notification_configs",
    "reminders",
)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _remap_categories(
    db: Session, family_id: int, payload_categories: list[dict]
) -> dict[str, str]:
    """Build a map of payload category_id -> inserted category_id."""
    existing = {
        (c.name, c.asset_type): c.id
        for c in db.query(Category)
        .filter((Category.family_id == family_id) | (Category.family_id.is_(None)))
        .all()
    }
    system = {
        str(c.id): str(c.id)
        for c in db.query(Category).filter(Category.family_id.is_(None)).all()
    }
    payload_to_inserted: dict[str, str] = {**system}
    for cat in payload_categories:
        key = (cat.get("name"), cat.get("asset_type"))
        cat_id = cat.get("id")
        if key in existing:
            if cat_id is not None:
                payload_to_inserted[str(cat_id)] = str(existing[key])
        else:
            if cat_id is not None:
                payload_to_inserted[str(cat_id)] = str(cat_id)
    return payload_to_inserted


def _resolve_category_id(
    db: Session, family_id: int, row: dict, category_map: dict[str, str]
) -> Any:
    """Pick the category this asset should point at in the restored database.

    Preference order: the natural key carried in the payload (stable across a
    rebuilt database), then the payload id remapped through the categories that
    were just inserted, then the raw id for a system row that survived.
    """
    name = row.get("category_name")
    asset_type = row.get("category_asset_type")
    if name is not None:
        match = (
            db.query(Category)
            .filter(
                Category.name == name,
                Category.asset_type == asset_type,
                (Category.family_id == family_id) | (Category.family_id.is_(None)),
            )
            .first()
        )
        if match is not None:
            return str(match.id)
    raw = row.get("category_id")
    if raw is None:
        return None
    return category_map.get(str(raw), raw)


def _remap_tags(
    db: Session, family_id: int, payload_tags: list[dict]
) -> dict[str, str]:
    existing = {
        t.name: str(t.id)
        for t in db.query(Tag).filter(Tag.family_id == family_id).all()
    }
    tag_map: dict[str, str] = dict(existing)
    for tag in payload_tags:
        name = tag.get("name")
        if name is None:
            continue
        tag_map[name] = str(tag.get("id"))
    return tag_map


def _tag_objects(db: Session, names: list[str], tag_map: dict[str, str]) -> list:
    ids = [int(tag_map[n]) for n in names if n in tag_map]
    if not ids:
        return []
    return db.query(Tag).filter(Tag.id.in_(ids)).all()


def _upsert_users(db: Session, family_id: int, rows: list[dict]) -> int:
    """Merge backed-up users into the family, updating existing rows in place."""
    count = 0
    for row in rows:
        data = _filter_fields(row, _USER_FIELDS)
        user_id = data.get("id")
        existing = None
        if user_id is not None:
            existing = db.query(User).filter(User.id == int(user_id)).one_or_none()
        if existing is None:
            obj = User(**data)
            _ensure_family(obj, family_id, None)
            _coerce_ids(obj, family_id, {})
            db.add(obj)
        else:
            for name, value in data.items():
                if name == "id":
                    continue
                setattr(existing, name, value)
        count += 1
    return count


def _insert_rows(
    db: Session, model, family_id: int, rows: list[dict], remap: dict
) -> int:
    fields = _fields_for_model(model)
    if fields is None:
        return 0
    count = 0
    for row in rows:
        data = dict(_filter_fields(row, fields))
        if "category_id" in data and data["category_id"] is not None:
            data["category_id"] = remap.get(
                str(data["category_id"]), data["category_id"]
            )
        obj = model(**data)
        _ensure_family(obj, family_id, None)
        _coerce_ids(obj, family_id, remap)
        db.add(obj)
        count += 1
    return count


def _fields_for(section: str) -> tuple | None:
    return {
        "milestones": _MILESTONE_FIELDS,
        "ai_provider_configs": _AI_PROVIDER_FIELDS,
    }.get(section)


def _fields_for_model(model) -> tuple | None:
    return {
        Category: _CATEGORY_FIELDS,
        Tag: _TAG_FIELDS,
        User: _USER_FIELDS,
        Liability: _LIABILITY_FIELDS,
        Wish: _WISH_FIELDS,
        RentalContract: _RENTAL_FIELDS,
        AssetSnapshot: _SNAPSHOT_FIELDS,
        Trip: _TRIP_FIELDS,
        ItineraryItem: _ITINERARY_FIELDS,
        ExpenseEntry: _EXPENSE_FIELDS,
        ExpenseCategory: _EXPENSE_CATEGORY_FIELDS,
        CachedFile: _CACHED_FILE_FIELDS,
        NotificationChannel: _NOTIFICATION_CHANNEL_FIELDS,
        NotificationConfig: _NOTIFICATION_CONFIG_FIELDS,
        Reminder: _REMINDER_FIELDS,
    }.get(model)


def _filter_fields(row: dict[str, Any], fields: tuple[str, ...]) -> dict[str, Any]:
    out = {}
    for name in fields:
        value = row.get(name)
        if value is None:
            continue
        out[name] = _decoerce(name, value)
    return out


def _ensure_family(obj, family_id: int, user_id: int | None) -> None:
    if hasattr(obj, "family_id") and obj.family_id is None:
        obj.family_id = family_id
    if user_id is not None and hasattr(obj, "user_id") and obj.user_id is None:
        obj.user_id = user_id


def _coerce_ids(obj, family_id: int, remap: dict) -> None:
    for name in (
        "id",
        "family_id",
        "user_id",
        "child_id",
        "child_user_id",
        "category_id",
        "linked_asset_id",
        "file_id",
        "backend_id",
        "reminder_id",
        "channel_id",
        "trip_id",
        "template_id",
    ):
        value = getattr(obj, name, None)
        if value is None:
            continue
        if name == "category_id":
            value = remap.get(str(value), value)
        with contextlib.suppress(TypeError, ValueError):
            setattr(obj, name, int(value))


def _coerce_asset(asset: Asset) -> None:
    for name in ("id", "family_id", "user_id", "category_id", "from_wish_id"):
        value = getattr(asset, name)
        if value is None:
            continue
        with contextlib.suppress(TypeError, ValueError):
            setattr(asset, name, int(value))
    if asset.purchase_price is not None and isinstance(asset.purchase_price, str):
        asset.purchase_price = Decimal(asset.purchase_price)
    if asset.current_value is not None and isinstance(asset.current_value, str):
        asset.current_value = Decimal(asset.current_value)
