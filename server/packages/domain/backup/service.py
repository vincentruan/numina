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

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from packages.db.models.asset import Asset
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
    "birth_date",
    "created_at",
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
