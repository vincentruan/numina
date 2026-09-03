"""unify datetime columns to timestamp with time zone

Converts all naive ``DateTime`` columns (TIMESTAMP WITHOUT TIME ZONE)
to ``DateTime(timezone=True)`` (TIMESTAMP WITH TIME ZONE). Existing data
is reinterpreted as UTC via ``AT TIME ZONE 'UTC'`` on PostgreSQL.
SQLite uses batch_alter_table (table-recreate dance) and preserves values
as-is (SQLite stores datetimes as strings without timezone semantics).

Revision ID: c7timestz01
Revises: b1a2l3a4n5c6
Create Date: 2026-09-03

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c7timestz01"
down_revision: str | None = "b1a2l3a4n5c6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# All (table, column) pairs to convert from naive DateTime to tz-aware.
# Extracted from the ORM models — every DateTime column across all tables.
COLUMNS: list[tuple[str, str]] = [
    ("activities", "created_at"),
    ("ai_chat_message_feedback", "created_at"),
    ("ai_chat_message_feedback", "updated_at"),
    ("ai_chat_messages", "created_at"),
    ("ai_chat_sessions", "created_at"),
    ("ai_chat_sessions", "updated_at"),
    ("ai_extraction_audits", "extracted_at"),
    ("ai_extraction_circuits", "opened_at"),
    ("ai_extraction_circuits", "opened_until"),
    ("ai_extraction_circuits", "manually_reset_at"),
    ("ai_extraction_circuits", "last_evaluated_at"),
    ("ai_mcp_servers", "created_at"),
    ("ai_mcp_servers", "updated_at"),
    ("ai_provider_test_results", "tested_at"),
    ("ai_providers", "half_open_window_start"),
    ("ai_providers", "circuit_open_until"),
    ("ai_providers", "last_failure_at"),
    ("ai_providers", "created_at"),
    ("ai_providers", "updated_at"),
    ("ai_reports", "generated_at"),
    ("ai_skills", "created_at"),
    ("ai_skills", "updated_at"),
    ("ai_tasks", "started_at"),
    ("ai_tasks", "completed_at"),
    ("ai_tasks", "lease_expires_at"),
    ("asr_provider_configs", "last_failure_at"),
    ("asr_provider_configs", "tested_at"),
    ("asr_provider_configs", "created_at"),
    ("asr_provider_configs", "updated_at"),
    ("asset_lifecycle_events", "created_at"),
    ("asset_snapshots", "created_at"),
    ("asset_valuations", "valued_at"),
    ("assets", "created_at"),
    ("assets", "updated_at"),
    ("balance_corrections", "created_at"),
    ("blind_box_config", "created_at"),
    ("blind_box_config", "updated_at"),
    ("blind_box_draws", "draw_at"),
    ("blind_box_draws", "fulfilled_at"),
    ("blind_box_gifts", "created_at"),
    ("blind_box_gifts", "updated_at"),
    ("bonus_draws", "expires_at"),
    ("bonus_draws", "created_at"),
    ("cached_files", "deleted_at"),
    ("cached_files", "created_at"),
    ("categories", "created_at"),
    ("categories", "updated_at"),
    ("challenge_grants", "deadline"),
    ("challenge_grants", "completed_at"),
    ("challenge_grants", "created_at"),
    ("challenge_grants", "updated_at"),
    ("child_economy_configs", "created_at"),
    ("child_economy_configs", "updated_at"),
    ("child_wish_cost_history", "created_at"),
    ("child_wishes", "created_at"),
    ("child_wishes", "updated_at"),
    ("chore_instances", "submitted_at"),
    ("chore_instances", "approved_at"),
    ("chore_instances", "claimed_at"),
    ("chore_instances", "consumed_at"),
    ("chore_instances", "created_at"),
    ("chore_templates", "created_at"),
    ("chore_templates", "updated_at"),
    ("coin_transactions", "created_at"),
    ("device_sessions", "created_at"),
    ("device_sessions", "last_seen_at"),
    ("device_sessions", "expires_at"),
    ("draft_imports", "rolled_back_at"),
    ("draft_imports", "created_at"),
    ("exchange_rates", "fetched_at"),
    ("exchange_rates", "created_at"),
    ("families", "created_at"),
    ("families", "updated_at"),
    ("family_debt_thresholds", "created_at"),
    ("family_debt_thresholds", "updated_at"),
    ("family_invitation_codes", "used_at"),
    ("family_invitation_codes", "revoked_at"),
    ("family_invitation_codes", "created_at"),
    ("family_manifesto", "signing_deadline"),
    ("family_manifesto", "created_at"),
    ("family_manifesto", "updated_at"),
    ("family_settings", "updated_at"),
    ("family_web_search_providers", "half_open_window_start"),
    ("family_web_search_providers", "last_failure_at"),
    ("family_web_search_providers", "created_at"),
    ("family_web_search_providers", "updated_at"),
    ("file_remote_locations", "synced_at"),
    ("file_remote_locations", "created_at"),
    ("file_remote_locations", "updated_at"),
    ("liabilities", "created_at"),
    ("liabilities", "updated_at"),
    ("literacy_badge_definitions", "created_at"),
    ("literacy_badges", "earned_at"),
    ("literacy_badges", "superseded_at"),
    ("literacy_scenario_templates", "created_at"),
    ("literacy_scenarios", "completed_at"),
    ("literacy_weekly_reports", "generated_at"),
    ("manifesto_feedback", "created_at"),
    ("manifesto_signature", "signed_at"),
    ("manifesto_version", "signed_at"),
    ("manifesto_version", "created_at"),
    ("notification_channel_configs", "created_at"),
    ("notification_channel_configs", "updated_at"),
    ("notification_channels", "created_at"),
    ("notification_channels", "updated_at"),
    ("notification_configs", "created_at"),
    ("notification_configs", "updated_at"),
    ("notification_subscriptions", "created_at"),
    ("payment_records", "paid_at"),
    ("reconcile_state", "last_checked_at"),
    ("reconcile_state", "last_applied_at"),
    ("reconcile_state", "last_verified_at"),
    ("reminder_notifications", "created_at"),
    ("reminders", "dismissed_at"),
    ("reminders", "resolved_at"),
    ("reminders", "created_at"),
    ("reminders", "updated_at"),
    ("rental_contracts", "created_at"),
    ("rental_contracts", "updated_at"),
    ("security_audit_logs", "created_at"),
    ("storage_backends", "created_at"),
    ("storage_backends", "updated_at"),
    ("sync_events", "occurred_at"),
    ("tags", "created_at"),
    ("users", "pin_locked_until"),
    ("users", "numeric_pin_locked_until"),
    ("users", "created_at"),
    ("users", "updated_at"),
    ("users", "ai_chat_last_read_at"),
    ("user_settings", "updated_at"),
    ("wish_savings_logs", "created_at"),
    ("wishes", "created_at"),
    ("wishes", "updated_at"),
]


def upgrade() -> None:
    bind = op.get_bind()

    if bind.dialect.name == "postgresql":
        # PostgreSQL: execute raw DDL directly.
        # We avoid batch_alter_table + postgresql_using because alembic's
        # PostgresqlColumnType visitor uses `if element.using` which fails
        # with SQLAlchemy 2.x clause objects (no __bool__ support).
        bind.execute(sa.text("SET timezone = 'UTC'"))
        for table, column in COLUMNS:
            op.execute(
                f'ALTER TABLE "{table}" '
                f'ALTER COLUMN "{column}" TYPE TIMESTAMP WITH TIME ZONE '
                f'USING "{column}" AT TIME ZONE \'UTC\''
            )
    else:
        # SQLite: batch_alter_table recreates the table.
        # SQLite stores datetimes as strings without timezone semantics,
        # so no USING clause is needed — values are preserved as-is.
        for table, column in COLUMNS:
            with op.batch_alter_table(table, schema=None) as batch_op:
                batch_op.alter_column(
                    column,
                    existing_type=sa.DateTime(),
                    type_=sa.DateTime(timezone=True),
                    existing_nullable=True,
                )


def downgrade() -> None:
    bind = op.get_bind()

    if bind.dialect.name == "postgresql":
        bind.execute(sa.text("SET timezone = 'UTC'"))
        for table, column in reversed(COLUMNS):
            op.execute(
                f'ALTER TABLE "{table}" '
                f'ALTER COLUMN "{column}" TYPE TIMESTAMP WITHOUT TIME ZONE'
            )
    else:
        for table, column in reversed(COLUMNS):
            with op.batch_alter_table(table, schema=None) as batch_op:
                batch_op.alter_column(
                    column,
                    existing_type=sa.DateTime(timezone=True),
                    type_=sa.DateTime(),
                    existing_nullable=True,
                )
