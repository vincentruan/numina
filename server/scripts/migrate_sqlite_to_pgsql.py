"""Migrate data from SQLite to PostgreSQL with proper type conversion.

Strategy:
1. Create all tables in PostgreSQL via SQLAlchemy Base.metadata.create_all()
2. Copy data from SQLite → PostgreSQL table by table with type conversion
3. Insert in dependency order to satisfy foreign keys
4. Mark all alembic revisions as applied in postgres

Usage:
    cd server/
    DATABASE_URL=postgresql+psycopg2://user:password@localhost:5432/numina \
    SQLITE_URL=sqlite:///$HOME/.numina/data/db/numina.db \
    uv run python scripts/migrate_sqlite_to_pgsql.py
"""

import json
import os
import sys
from pathlib import Path

import sqlalchemy as sa
from sqlalchemy import inspect, text

# Ensure server/ is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from apps.backend.app.database import Base

# Import all models so they register with Base.metadata
from apps.backend.app.models.ai_agent import AIAgent
from apps.backend.app.models.ai_provider_config import (
    AIProviderConfig,
    AIProviderTestResult,
)
from apps.backend.app.models.asset import Asset
from apps.backend.app.models.asset_lifecycle_event import AssetLifecycleEvent
from apps.backend.app.models.category import Category
from apps.backend.app.models.child_economy_config import ChildEconomyConfig
from apps.backend.app.models.child_wish import ChildWish
from apps.backend.app.models.child_wish_cost_history import ChildWishCostHistory
from apps.backend.app.models.family_invitation_code import FamilyInvitationCode
from apps.backend.app.models.family_mcp_server import FamilyMCPServer
from apps.backend.app.models.family_web_search_provider import FamilyWebSearchProvider
from apps.backend.app.models.liability import Liability
from apps.backend.app.models.payment_record import PaymentRecord
from apps.backend.app.models.skill_registry import SkillRegistry
from apps.backend.app.models.tag import Tag
from apps.backend.app.models.valuation import AssetValuation
from apps.backend.app.models.wish import Wish
from packages.db.models import CachedFile, FileRemoteLocation, StorageBackend
from packages.db.models.ai_task import AITask
from packages.db.models.asset_snapshot import AssetSnapshot
from packages.db.models.currency import Currency
from packages.db.models.device_session import DeviceSession
from packages.db.models.exchange_rate import ExchangeRate
from packages.db.models.family import Family
from packages.db.models.notification_channel import NotificationChannel
from packages.db.models.notification_channel_config import NotificationChannelConfig
from packages.db.models.notification_config import NotificationConfig
from packages.db.models.notification_subscription import NotificationSubscription
from packages.db.models.reminder import Reminder
from packages.db.models.reminder_notification import ReminderNotification
from packages.db.models.revoked_token import RevokedToken
from packages.db.models.security_audit_log import SecurityAuditLog
from packages.db.models.user import User

# Table insertion order (parents before children to satisfy FK constraints)
TABLE_ORDER = [
    # Core entities (no FK dependencies)
    "families",
    "users",
    "categories",
    "tags",
    "currencies",
    "exchange_rates",
    "storage_backends",
    # Dependent entities
    "assets",
    "liabilities",
    "wishes",
    "child_wishes",
    "child_economy_configs",
    "family_invitation_codes",
    "family_web_search_providers",
    "family_mcp_servers",
    "family_debt_thresholds",
    "asset_valuations",
    "asset_snapshots",
    "asset_tags",
    "asset_lifecycle_events",
    "payment_records",
    "reminders",
    "reminder_notifications",
    "notification_channels",
    "notification_channel_configs",
    "notification_configs",
    "notification_subscriptions",
    "device_sessions",
    "cached_files",
    "file_remote_locations",
    "sync_events",
    "revoked_tokens",
    "security_audit_logs",
    # AI-related
    "ai_agents",
    "ai_providers",
    "ai_provider_test_results",
    "ai_skills",
    "ai_extraction_audits",
    "ai_extraction_circuits",
    "ai_reports",
    "ai_tasks",
    "ai_chat_sessions",
    "ai_chat_messages",
    "ai_chat_message_feedback",
    "ai_asset_alerts",
    "ai_disposal_suggestions",
    "ai_allocation_targets",
    "ai_allocation_drift_results",
    "ai_liability_results",
    "ai_mcp_servers",
    "ai_spending_leaks",
    # Child/chore economy
    "child_milestones",
    "child_wish_cost_history",
    "chore_templates",
    "chore_template_assignees",
    "chore_instances",
    "coin_transactions",
    "activities",
    "blind_box_gifts",
    "blind_box_draws",
    "blind_box_config",
    "bonus_draws",
    "challenge_grants",
    # Misc
    "category_financial_defaults",
    "skill_registry",
]


def get_all_revision_ids() -> list[str]:
    """Parse all alembic revision IDs from migration files."""
    import importlib
    import importlib.util
    import pathlib

    versions_dir = pathlib.Path(__file__).parent.parent / "apps" / "backend" / "alembic" / "versions"
    revisions = []
    for f in sorted(versions_dir.glob("*.py")):
        if f.name.startswith("__"):
            continue
        mod_name = f"apps.backend.alembic.versions.{f.stem}"
        try:
            spec = importlib.util.spec_from_file_location(mod_name, f)
            if spec is None or spec.loader is None:
                continue
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            if hasattr(mod, "revision"):
                revisions.append(mod.revision)
        except Exception as e:
            print(f"  ⚠ Could not parse {f.name}: {e}")
    return revisions


def convert_value(value, pg_type: str, col_name: str):
    """Convert SQLite value to PostgreSQL-compatible value based on target column type."""
    if value is None:
        return None

    pg_type_lower = pg_type.lower()

    # Boolean conversion: SQLite stores 0/1, PostgreSQL needs true/false
    if "boolean" in pg_type_lower:
        if isinstance(value, bool):
            return value
        if isinstance(value, int):
            return value != 0
        if isinstance(value, str):
            return value.lower() in ("1", "true", "t", "yes")
        return bool(value)

    # JSON columns: must be JSON string, not Python list/dict
    if "json" in pg_type_lower:
        if isinstance(value, str):
            # Already a string, validate it's JSON
            try:
                parsed = json.loads(value)
                return json.dumps(parsed)  # Re-serialize to ensure valid JSON
            except (json.JSONDecodeError, ValueError):
                return value
        else:
            # Python object, serialize to JSON string
            return json.dumps(value)

    return value


def migrate_data():
    sqlite_url = os.environ.get("SQLITE_URL")
    if not sqlite_url:
        default_sqlite = Path.home() / ".numina" / "data" / "db" / "numina.db"
        print(f"⚠ SQLITE_URL not set, using default: {default_sqlite}")
        sqlite_url = f"sqlite:///{default_sqlite}"

    pgsql_url = os.environ.get("DATABASE_URL")
    if not pgsql_url:
        print("❌ DATABASE_URL environment variable is required")
        print("   Example: DATABASE_URL=postgresql+psycopg2://user:password@localhost:5432/numina")
        sys.exit(1)

    print(f"📦 SQLite: {sqlite_url}")
    print("🐘 PostgreSQL: [credentials hidden]")

    src = sa.create_engine(sqlite_url)
    dst = sa.create_engine(pgsql_url)

    # Step 1: Create all tables in PostgreSQL from SQLAlchemy models
    print("\n🔨 Step 1: Creating tables in PostgreSQL via Base.metadata.create_all()...")
    Base.metadata.create_all(dst)
    print("   ✅ Tables created")

    # Step 2: Migrate data table by table in dependency order
    src_inspector = inspect(src)
    dst_inspector = inspect(dst)

    src_tables = set(src_inspector.get_table_names())
    dst_tables = set(dst_inspector.get_table_names())

    # Skip internal tables
    skip_tables = {"alembic_version"}

    print("\n📊 Step 2: Migrating data in dependency order...")
    total_rows = 0
    success_count = 0
    empty_count = 0
    error_count = 0

    # Get PostgreSQL column types for all tables
    pg_col_types = {}
    for table_name in dst_tables:
        pg_col_types[table_name] = {c["name"]: str(c["type"]).lower() for c in dst_inspector.get_columns(table_name)}

    with src.connect() as src_conn:
        for table_name in TABLE_ORDER:
            if table_name in skip_tables:
                continue
            if table_name not in src_tables or table_name not in dst_tables:
                continue

            # Get column names from source and destination
            src_columns = [c["name"] for c in src_inspector.get_columns(table_name)]
            dst_columns = [c["name"] for c in dst_inspector.get_columns(table_name)]
            common_cols = [c for c in src_columns if c in dst_columns]

            if not common_cols:
                print(f"   ⏭ {table_name}: no common columns, skipping")
                continue

            # Check if source has data
            col_list = ", ".join(f'"{c}"' for c in common_cols)
            rows = src_conn.execute(text(f'SELECT {col_list} FROM "{table_name}"')).fetchall()

            if not rows:
                print(f"   ⏭ {table_name}: empty")
                empty_count += 1
                continue

            print(f"   🔄 {table_name}: {len(rows)} rows...", end="", flush=True)

            # Convert values for each row
            converted_rows = []
            for row in rows:
                converted_row = {}
                for col_name, value in zip(common_cols, row, strict=True):
                    pg_type = pg_col_types.get(table_name, {}).get(col_name, "")
                    converted_row[col_name] = convert_value(value, pg_type, col_name)
                converted_rows.append(converted_row)

            # Insert into destination - each table in its own transaction
            dst_col_list = ", ".join(f'"{c}"' for c in common_cols)
            param_list = ", ".join(f":{c}" for c in common_cols)
            insert_sql = f'INSERT INTO "{table_name}" ({dst_col_list}) VALUES ({param_list})'

            try:
                with dst.begin() as dst_conn:
                    dst_conn.execute(text(insert_sql), converted_rows)
                print(" ✅")
                total_rows += len(converted_rows)
                success_count += 1
            except Exception as e:
                print(" ❌")
                print(f"      Error: {e}")
                error_count += 1

    print("\n   📊 Summary:")
    print(f"      Success: {success_count} tables")
    print(f"      Empty: {empty_count} tables")
    print(f"      Error: {error_count} tables")
    print(f"      Total rows: {total_rows}")

    # Step 3: Mark all alembic revisions as applied
    print("\n🏷  Step 3: Marking all alembic revisions as applied...")
    revisions = get_all_revision_ids()
    print(f"   Found {len(revisions)} revisions")

    # Create alembic_version table if it doesn't exist
    with dst.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS alembic_version (
                version_num VARCHAR(32) NOT NULL,
                CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
            )
        """))

    with dst.begin() as conn:
        conn.execute(text("DELETE FROM alembic_version"))
        for rev in revisions:
            conn.execute(text("INSERT INTO alembic_version (version_num) VALUES (:v)"), {"v": rev})

    print(f"   ✅ {len(revisions)} revisions marked")

    # Step 4: Verify
    print("\n🔍 Step 4: Verification...")
    with dst.connect() as conn:
        for table in ["users", "families", "assets", "liabilities", "categories", "ai_agents"]:
            try:
                count = conn.execute(text(f'SELECT count(*) FROM "{table}"')).scalar()
                print(f"   {table}: {count} rows")
            except Exception as e:
                print(f"   {table}: ERROR - {e}")

    print("\n🎉 Migration complete!")
    print("\n   To use PostgreSQL, update your DATABASE_URL environment variable.")


if __name__ == "__main__":
    migrate_data()
