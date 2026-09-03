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


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        # Set session timezone so any implicit naive→timestamptz casts
        # interpret existing values as UTC (defense-in-depth; the explicit
        # USING clause on each alter_column is the primary mechanism).
        bind.execute(sa.text("SET timezone = 'UTC'"))

    with op.batch_alter_table('activities', schema=None) as batch_op:
        batch_op.alter_column(
            'created_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=False,
            postgresql_using=sa.text("created_at AT TIME ZONE 'UTC'"),
        )

    with op.batch_alter_table('ai_chat_message_feedback', schema=None) as batch_op:
        batch_op.alter_column(
            'created_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=False,
            postgresql_using=sa.text("created_at AT TIME ZONE 'UTC'"),
        )
        batch_op.alter_column(
            'updated_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=False,
            postgresql_using=sa.text("updated_at AT TIME ZONE 'UTC'"),
        )

    with op.batch_alter_table('ai_chat_messages', schema=None) as batch_op:
        batch_op.alter_column(
            'created_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=False,
            postgresql_using=sa.text("created_at AT TIME ZONE 'UTC'"),
        )

    with op.batch_alter_table('ai_chat_sessions', schema=None) as batch_op:
        batch_op.alter_column(
            'created_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=False,
            postgresql_using=sa.text("created_at AT TIME ZONE 'UTC'"),
        )
        batch_op.alter_column(
            'updated_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=False,
            postgresql_using=sa.text("updated_at AT TIME ZONE 'UTC'"),
        )

    with op.batch_alter_table('ai_extraction_audits', schema=None) as batch_op:
        batch_op.alter_column(
            'extracted_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=False,
            postgresql_using=sa.text("extracted_at AT TIME ZONE 'UTC'"),
        )

    with op.batch_alter_table('ai_extraction_circuits', schema=None) as batch_op:
        batch_op.alter_column(
            'opened_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=True,
            postgresql_using=sa.text("opened_at AT TIME ZONE 'UTC'"),
        )
        batch_op.alter_column(
            'opened_until',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=True,
            postgresql_using=sa.text("opened_until AT TIME ZONE 'UTC'"),
        )
        batch_op.alter_column(
            'manually_reset_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=True,
            postgresql_using=sa.text("manually_reset_at AT TIME ZONE 'UTC'"),
        )
        batch_op.alter_column(
            'last_evaluated_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=False,
            postgresql_using=sa.text("last_evaluated_at AT TIME ZONE 'UTC'"),
        )

    with op.batch_alter_table('ai_mcp_servers', schema=None) as batch_op:
        batch_op.alter_column(
            'created_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=False,
            postgresql_using=sa.text("created_at AT TIME ZONE 'UTC'"),
        )
        batch_op.alter_column(
            'updated_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=False,
            postgresql_using=sa.text("updated_at AT TIME ZONE 'UTC'"),
        )

    with op.batch_alter_table('ai_provider_test_results', schema=None) as batch_op:
        batch_op.alter_column(
            'tested_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=False,
            postgresql_using=sa.text("tested_at AT TIME ZONE 'UTC'"),
        )

    with op.batch_alter_table('ai_providers', schema=None) as batch_op:
        batch_op.alter_column(
            'half_open_window_start',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=True,
            postgresql_using=sa.text("half_open_window_start AT TIME ZONE 'UTC'"),
        )
        batch_op.alter_column(
            'circuit_open_until',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=True,
            postgresql_using=sa.text("circuit_open_until AT TIME ZONE 'UTC'"),
        )
        batch_op.alter_column(
            'last_failure_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=True,
            postgresql_using=sa.text("last_failure_at AT TIME ZONE 'UTC'"),
        )
        batch_op.alter_column(
            'created_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=False,
            postgresql_using=sa.text("created_at AT TIME ZONE 'UTC'"),
        )
        batch_op.alter_column(
            'updated_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=False,
            postgresql_using=sa.text("updated_at AT TIME ZONE 'UTC'"),
        )

    with op.batch_alter_table('ai_reports', schema=None) as batch_op:
        batch_op.alter_column(
            'generated_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=False,
            postgresql_using=sa.text("generated_at AT TIME ZONE 'UTC'"),
        )

    with op.batch_alter_table('ai_skills', schema=None) as batch_op:
        batch_op.alter_column(
            'created_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=False,
            postgresql_using=sa.text("created_at AT TIME ZONE 'UTC'"),
        )
        batch_op.alter_column(
            'updated_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=False,
            postgresql_using=sa.text("updated_at AT TIME ZONE 'UTC'"),
        )

    with op.batch_alter_table('ai_tasks', schema=None) as batch_op:
        batch_op.alter_column(
            'started_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=False,
            postgresql_using=sa.text("started_at AT TIME ZONE 'UTC'"),
        )
        batch_op.alter_column(
            'completed_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=True,
            postgresql_using=sa.text("completed_at AT TIME ZONE 'UTC'"),
        )
        batch_op.alter_column(
            'lease_expires_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=True,
            postgresql_using=sa.text("lease_expires_at AT TIME ZONE 'UTC'"),
        )

    with op.batch_alter_table('asr_provider_configs', schema=None) as batch_op:
        batch_op.alter_column(
            'last_failure_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=True,
            postgresql_using=sa.text("last_failure_at AT TIME ZONE 'UTC'"),
        )
        batch_op.alter_column(
            'tested_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=True,
            postgresql_using=sa.text("tested_at AT TIME ZONE 'UTC'"),
        )
        batch_op.alter_column(
            'created_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=False,
            postgresql_using=sa.text("created_at AT TIME ZONE 'UTC'"),
        )
        batch_op.alter_column(
            'updated_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=False,
            postgresql_using=sa.text("updated_at AT TIME ZONE 'UTC'"),
        )

    with op.batch_alter_table('asset_lifecycle_events', schema=None) as batch_op:
        batch_op.alter_column(
            'created_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=False,
            postgresql_using=sa.text("created_at AT TIME ZONE 'UTC'"),
        )

    with op.batch_alter_table('asset_snapshots', schema=None) as batch_op:
        batch_op.alter_column(
            'created_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=False,
            postgresql_using=sa.text("created_at AT TIME ZONE 'UTC'"),
        )

    with op.batch_alter_table('asset_valuations', schema=None) as batch_op:
        batch_op.alter_column(
            'valued_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=False,
            postgresql_using=sa.text("valued_at AT TIME ZONE 'UTC'"),
        )

    with op.batch_alter_table('assets', schema=None) as batch_op:
        batch_op.alter_column(
            'created_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=False,
            postgresql_using=sa.text("created_at AT TIME ZONE 'UTC'"),
        )
        batch_op.alter_column(
            'updated_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=False,
            postgresql_using=sa.text("updated_at AT TIME ZONE 'UTC'"),
        )

    with op.batch_alter_table('balance_corrections', schema=None) as batch_op:
        batch_op.alter_column(
            'created_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=False,
            postgresql_using=sa.text("created_at AT TIME ZONE 'UTC'"),
        )

    with op.batch_alter_table('blind_box_config', schema=None) as batch_op:
        batch_op.alter_column(
            'created_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=False,
            postgresql_using=sa.text("created_at AT TIME ZONE 'UTC'"),
        )
        batch_op.alter_column(
            'updated_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=False,
            postgresql_using=sa.text("updated_at AT TIME ZONE 'UTC'"),
        )

    with op.batch_alter_table('blind_box_draws', schema=None) as batch_op:
        batch_op.alter_column(
            'draw_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=False,
            postgresql_using=sa.text("draw_at AT TIME ZONE 'UTC'"),
        )
        batch_op.alter_column(
            'fulfilled_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=True,
            postgresql_using=sa.text("fulfilled_at AT TIME ZONE 'UTC'"),
        )

    with op.batch_alter_table('blind_box_gifts', schema=None) as batch_op:
        batch_op.alter_column(
            'created_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=False,
            postgresql_using=sa.text("created_at AT TIME ZONE 'UTC'"),
        )
        batch_op.alter_column(
            'updated_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=False,
            postgresql_using=sa.text("updated_at AT TIME ZONE 'UTC'"),
        )

    with op.batch_alter_table('bonus_draws', schema=None) as batch_op:
        batch_op.alter_column(
            'expires_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=False,
            postgresql_using=sa.text("expires_at AT TIME ZONE 'UTC'"),
        )
        batch_op.alter_column(
            'created_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=False,
            postgresql_using=sa.text("created_at AT TIME ZONE 'UTC'"),
        )

    with op.batch_alter_table('cached_files', schema=None) as batch_op:
        batch_op.alter_column(
            'deleted_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=True,
            postgresql_using=sa.text("deleted_at AT TIME ZONE 'UTC'"),
        )
        batch_op.alter_column(
            'created_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=False,
            postgresql_using=sa.text("created_at AT TIME ZONE 'UTC'"),
        )

    with op.batch_alter_table('categories', schema=None) as batch_op:
        batch_op.alter_column(
            'created_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=False,
            postgresql_using=sa.text("created_at AT TIME ZONE 'UTC'"),
        )
        batch_op.alter_column(
            'updated_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=False,
            postgresql_using=sa.text("updated_at AT TIME ZONE 'UTC'"),
        )

    with op.batch_alter_table('challenge_grants', schema=None) as batch_op:
        batch_op.alter_column(
            'deadline',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=False,
            postgresql_using=sa.text("deadline AT TIME ZONE 'UTC'"),
        )
        batch_op.alter_column(
            'completed_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=True,
            postgresql_using=sa.text("completed_at AT TIME ZONE 'UTC'"),
        )
        batch_op.alter_column(
            'created_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=False,
            postgresql_using=sa.text("created_at AT TIME ZONE 'UTC'"),
        )
        batch_op.alter_column(
            'updated_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=False,
            postgresql_using=sa.text("updated_at AT TIME ZONE 'UTC'"),
        )

    with op.batch_alter_table('child_economy_configs', schema=None) as batch_op:
        batch_op.alter_column(
            'created_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=False,
            postgresql_using=sa.text("created_at AT TIME ZONE 'UTC'"),
        )
        batch_op.alter_column(
            'updated_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=False,
            postgresql_using=sa.text("updated_at AT TIME ZONE 'UTC'"),
        )

    with op.batch_alter_table('child_wish_cost_history', schema=None) as batch_op:
        batch_op.alter_column(
            'created_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=False,
            postgresql_using=sa.text("created_at AT TIME ZONE 'UTC'"),
        )

    with op.batch_alter_table('child_wishes', schema=None) as batch_op:
        batch_op.alter_column(
            'created_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=False,
            postgresql_using=sa.text("created_at AT TIME ZONE 'UTC'"),
        )
        batch_op.alter_column(
            'updated_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=False,
            postgresql_using=sa.text("updated_at AT TIME ZONE 'UTC'"),
        )

    with op.batch_alter_table('chore_instances', schema=None) as batch_op:
        batch_op.alter_column(
            'submitted_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=True,
            postgresql_using=sa.text("submitted_at AT TIME ZONE 'UTC'"),
        )
        batch_op.alter_column(
            'approved_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=True,
            postgresql_using=sa.text("approved_at AT TIME ZONE 'UTC'"),
        )
        batch_op.alter_column(
            'claimed_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=True,
            postgresql_using=sa.text("claimed_at AT TIME ZONE 'UTC'"),
        )
        batch_op.alter_column(
            'consumed_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=True,
            postgresql_using=sa.text("consumed_at AT TIME ZONE 'UTC'"),
        )
        batch_op.alter_column(
            'created_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=False,
            postgresql_using=sa.text("created_at AT TIME ZONE 'UTC'"),
        )

    with op.batch_alter_table('chore_templates', schema=None) as batch_op:
        batch_op.alter_column(
            'created_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=False,
            postgresql_using=sa.text("created_at AT TIME ZONE 'UTC'"),
        )
        batch_op.alter_column(
            'updated_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=False,
            postgresql_using=sa.text("updated_at AT TIME ZONE 'UTC'"),
        )

    with op.batch_alter_table('coin_transactions', schema=None) as batch_op:
        batch_op.alter_column(
            'created_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=False,
            postgresql_using=sa.text("created_at AT TIME ZONE 'UTC'"),
        )

    with op.batch_alter_table('device_sessions', schema=None) as batch_op:
        batch_op.alter_column(
            'created_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=False,
            postgresql_using=sa.text("created_at AT TIME ZONE 'UTC'"),
        )
        batch_op.alter_column(
            'last_seen_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=False,
            postgresql_using=sa.text("last_seen_at AT TIME ZONE 'UTC'"),
        )
        batch_op.alter_column(
            'expires_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=False,
            postgresql_using=sa.text("expires_at AT TIME ZONE 'UTC'"),
        )

    with op.batch_alter_table('draft_imports', schema=None) as batch_op:
        batch_op.alter_column(
            'rolled_back_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=True,
            postgresql_using=sa.text("rolled_back_at AT TIME ZONE 'UTC'"),
        )
        batch_op.alter_column(
            'created_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=False,
            postgresql_using=sa.text("created_at AT TIME ZONE 'UTC'"),
        )

    with op.batch_alter_table('exchange_rates', schema=None) as batch_op:
        batch_op.alter_column(
            'fetched_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=False,
            postgresql_using=sa.text("fetched_at AT TIME ZONE 'UTC'"),
        )
        batch_op.alter_column(
            'created_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=False,
            postgresql_using=sa.text("created_at AT TIME ZONE 'UTC'"),
        )

    with op.batch_alter_table('families', schema=None) as batch_op:
        batch_op.alter_column(
            'created_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=False,
            postgresql_using=sa.text("created_at AT TIME ZONE 'UTC'"),
        )
        batch_op.alter_column(
            'updated_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=False,
            postgresql_using=sa.text("updated_at AT TIME ZONE 'UTC'"),
        )

    with op.batch_alter_table('family_debt_thresholds', schema=None) as batch_op:
        batch_op.alter_column(
            'created_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=False,
            postgresql_using=sa.text("created_at AT TIME ZONE 'UTC'"),
        )
        batch_op.alter_column(
            'updated_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=False,
            postgresql_using=sa.text("updated_at AT TIME ZONE 'UTC'"),
        )

    with op.batch_alter_table('family_invitation_codes', schema=None) as batch_op:
        batch_op.alter_column(
            'used_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=True,
            postgresql_using=sa.text("used_at AT TIME ZONE 'UTC'"),
        )
        batch_op.alter_column(
            'revoked_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=True,
            postgresql_using=sa.text("revoked_at AT TIME ZONE 'UTC'"),
        )
        batch_op.alter_column(
            'created_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=False,
            postgresql_using=sa.text("created_at AT TIME ZONE 'UTC'"),
        )

    with op.batch_alter_table('family_manifesto', schema=None) as batch_op:
        batch_op.alter_column(
            'signing_deadline',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=True,
            postgresql_using=sa.text("signing_deadline AT TIME ZONE 'UTC'"),
        )
        batch_op.alter_column(
            'created_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=False,
            postgresql_using=sa.text("created_at AT TIME ZONE 'UTC'"),
        )
        batch_op.alter_column(
            'updated_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=False,
            postgresql_using=sa.text("updated_at AT TIME ZONE 'UTC'"),
        )

    with op.batch_alter_table('family_web_search_providers', schema=None) as batch_op:
        batch_op.alter_column(
            'half_open_window_start',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=True,
            postgresql_using=sa.text("half_open_window_start AT TIME ZONE 'UTC'"),
        )
        batch_op.alter_column(
            'last_failure_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=True,
            postgresql_using=sa.text("last_failure_at AT TIME ZONE 'UTC'"),
        )
        batch_op.alter_column(
            'created_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=False,
            postgresql_using=sa.text("created_at AT TIME ZONE 'UTC'"),
        )
        batch_op.alter_column(
            'updated_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=False,
            postgresql_using=sa.text("updated_at AT TIME ZONE 'UTC'"),
        )

    with op.batch_alter_table('file_remote_locations', schema=None) as batch_op:
        batch_op.alter_column(
            'synced_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=True,
            postgresql_using=sa.text("synced_at AT TIME ZONE 'UTC'"),
        )
        batch_op.alter_column(
            'created_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=False,
            postgresql_using=sa.text("created_at AT TIME ZONE 'UTC'"),
        )
        batch_op.alter_column(
            'updated_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=False,
            postgresql_using=sa.text("updated_at AT TIME ZONE 'UTC'"),
        )

    with op.batch_alter_table('liabilities', schema=None) as batch_op:
        batch_op.alter_column(
            'created_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=False,
            postgresql_using=sa.text("created_at AT TIME ZONE 'UTC'"),
        )
        batch_op.alter_column(
            'updated_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=False,
            postgresql_using=sa.text("updated_at AT TIME ZONE 'UTC'"),
        )

    with op.batch_alter_table('literacy_badge_definitions', schema=None) as batch_op:
        batch_op.alter_column(
            'created_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=False,
            postgresql_using=sa.text("created_at AT TIME ZONE 'UTC'"),
        )

    with op.batch_alter_table('literacy_badges', schema=None) as batch_op:
        batch_op.alter_column(
            'earned_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=False,
            postgresql_using=sa.text("earned_at AT TIME ZONE 'UTC'"),
        )
        batch_op.alter_column(
            'superseded_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=True,
            postgresql_using=sa.text("superseded_at AT TIME ZONE 'UTC'"),
        )

    with op.batch_alter_table('literacy_scenario_templates', schema=None) as batch_op:
        batch_op.alter_column(
            'created_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=False,
            postgresql_using=sa.text("created_at AT TIME ZONE 'UTC'"),
        )

    with op.batch_alter_table('literacy_scenarios', schema=None) as batch_op:
        batch_op.alter_column(
            'completed_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=True,
            postgresql_using=sa.text("completed_at AT TIME ZONE 'UTC'"),
        )

    with op.batch_alter_table('literacy_weekly_reports', schema=None) as batch_op:
        batch_op.alter_column(
            'generated_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=False,
            postgresql_using=sa.text("generated_at AT TIME ZONE 'UTC'"),
        )

    with op.batch_alter_table('manifesto_feedback', schema=None) as batch_op:
        batch_op.alter_column(
            'created_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=False,
            postgresql_using=sa.text("created_at AT TIME ZONE 'UTC'"),
        )

    with op.batch_alter_table('manifesto_signature', schema=None) as batch_op:
        batch_op.alter_column(
            'signed_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=False,
            postgresql_using=sa.text("signed_at AT TIME ZONE 'UTC'"),
        )

    with op.batch_alter_table('manifesto_version', schema=None) as batch_op:
        batch_op.alter_column(
            'signed_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=True,
            postgresql_using=sa.text("signed_at AT TIME ZONE 'UTC'"),
        )
        batch_op.alter_column(
            'created_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=False,
            postgresql_using=sa.text("created_at AT TIME ZONE 'UTC'"),
        )

    with op.batch_alter_table('notification_channel_configs', schema=None) as batch_op:
        batch_op.alter_column(
            'created_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=False,
            postgresql_using=sa.text("created_at AT TIME ZONE 'UTC'"),
        )
        batch_op.alter_column(
            'updated_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=False,
            postgresql_using=sa.text("updated_at AT TIME ZONE 'UTC'"),
        )

    with op.batch_alter_table('notification_channels', schema=None) as batch_op:
        batch_op.alter_column(
            'created_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=False,
            postgresql_using=sa.text("created_at AT TIME ZONE 'UTC'"),
        )
        batch_op.alter_column(
            'updated_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=False,
            postgresql_using=sa.text("updated_at AT TIME ZONE 'UTC'"),
        )

    with op.batch_alter_table('notification_configs', schema=None) as batch_op:
        batch_op.alter_column(
            'created_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=False,
            postgresql_using=sa.text("created_at AT TIME ZONE 'UTC'"),
        )
        batch_op.alter_column(
            'updated_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=False,
            postgresql_using=sa.text("updated_at AT TIME ZONE 'UTC'"),
        )

    with op.batch_alter_table('notification_subscriptions', schema=None) as batch_op:
        batch_op.alter_column(
            'created_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=False,
            postgresql_using=sa.text("created_at AT TIME ZONE 'UTC'"),
        )

    with op.batch_alter_table('payment_records', schema=None) as batch_op:
        batch_op.alter_column(
            'paid_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=False,
            postgresql_using=sa.text("paid_at AT TIME ZONE 'UTC'"),
        )

    with op.batch_alter_table('reconcile_state', schema=None) as batch_op:
        batch_op.alter_column(
            'last_checked_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=True,
            postgresql_using=sa.text("last_checked_at AT TIME ZONE 'UTC'"),
        )
        batch_op.alter_column(
            'last_applied_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=True,
            postgresql_using=sa.text("last_applied_at AT TIME ZONE 'UTC'"),
        )
        batch_op.alter_column(
            'last_verified_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=True,
            postgresql_using=sa.text("last_verified_at AT TIME ZONE 'UTC'"),
        )

    with op.batch_alter_table('reminder_notifications', schema=None) as batch_op:
        batch_op.alter_column(
            'created_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=False,
            postgresql_using=sa.text("created_at AT TIME ZONE 'UTC'"),
        )

    with op.batch_alter_table('reminders', schema=None) as batch_op:
        batch_op.alter_column(
            'dismissed_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=True,
            postgresql_using=sa.text("dismissed_at AT TIME ZONE 'UTC'"),
        )
        batch_op.alter_column(
            'resolved_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=True,
            postgresql_using=sa.text("resolved_at AT TIME ZONE 'UTC'"),
        )
        batch_op.alter_column(
            'created_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=False,
            postgresql_using=sa.text("created_at AT TIME ZONE 'UTC'"),
        )
        batch_op.alter_column(
            'updated_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=False,
            postgresql_using=sa.text("updated_at AT TIME ZONE 'UTC'"),
        )

    with op.batch_alter_table('rental_contracts', schema=None) as batch_op:
        batch_op.alter_column(
            'created_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=False,
            postgresql_using=sa.text("created_at AT TIME ZONE 'UTC'"),
        )
        batch_op.alter_column(
            'updated_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=False,
            postgresql_using=sa.text("updated_at AT TIME ZONE 'UTC'"),
        )

    with op.batch_alter_table('security_audit_logs', schema=None) as batch_op:
        batch_op.alter_column(
            'created_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=False,
            postgresql_using=sa.text("created_at AT TIME ZONE 'UTC'"),
        )

    with op.batch_alter_table('storage_backends', schema=None) as batch_op:
        batch_op.alter_column(
            'created_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=False,
            postgresql_using=sa.text("created_at AT TIME ZONE 'UTC'"),
        )
        batch_op.alter_column(
            'updated_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=False,
            postgresql_using=sa.text("updated_at AT TIME ZONE 'UTC'"),
        )

    with op.batch_alter_table('sync_events', schema=None) as batch_op:
        batch_op.alter_column(
            'occurred_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=False,
            postgresql_using=sa.text("occurred_at AT TIME ZONE 'UTC'"),
        )

    with op.batch_alter_table('tags', schema=None) as batch_op:
        batch_op.alter_column(
            'created_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=False,
            postgresql_using=sa.text("created_at AT TIME ZONE 'UTC'"),
        )

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.alter_column(
            'pin_locked_until',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=True,
            postgresql_using=sa.text("pin_locked_until AT TIME ZONE 'UTC'"),
        )
        batch_op.alter_column(
            'numeric_pin_locked_until',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=True,
            postgresql_using=sa.text("numeric_pin_locked_until AT TIME ZONE 'UTC'"),
        )
        batch_op.alter_column(
            'created_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=False,
            postgresql_using=sa.text("created_at AT TIME ZONE 'UTC'"),
        )
        batch_op.alter_column(
            'updated_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=False,
            postgresql_using=sa.text("updated_at AT TIME ZONE 'UTC'"),
        )
        batch_op.alter_column(
            'ai_chat_last_read_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=True,
            postgresql_using=sa.text("ai_chat_last_read_at AT TIME ZONE 'UTC'"),
        )

    with op.batch_alter_table('wish_savings_logs', schema=None) as batch_op:
        batch_op.alter_column(
            'created_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=False,
            postgresql_using=sa.text("created_at AT TIME ZONE 'UTC'"),
        )

    with op.batch_alter_table('wishes', schema=None) as batch_op:
        batch_op.alter_column(
            'created_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=False,
            postgresql_using=sa.text("created_at AT TIME ZONE 'UTC'"),
        )
        batch_op.alter_column(
            'updated_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=False,
            postgresql_using=sa.text("updated_at AT TIME ZONE 'UTC'"),
        )



def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        # Reverse: when casting timestamptz back to naive timestamp, ensure
        # the session interprets the conversion as UTC.
        bind.execute(sa.text("SET timezone = 'UTC'"))

    with op.batch_alter_table('wishes', schema=None) as batch_op:
        batch_op.alter_column(
            'created_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=False,
        )
        batch_op.alter_column(
            'updated_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=False,
        )

    with op.batch_alter_table('wish_savings_logs', schema=None) as batch_op:
        batch_op.alter_column(
            'created_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=False,
        )

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.alter_column(
            'pin_locked_until',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=True,
        )
        batch_op.alter_column(
            'numeric_pin_locked_until',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=True,
        )
        batch_op.alter_column(
            'created_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=False,
        )
        batch_op.alter_column(
            'updated_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=False,
        )
        batch_op.alter_column(
            'ai_chat_last_read_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=True,
        )

    with op.batch_alter_table('tags', schema=None) as batch_op:
        batch_op.alter_column(
            'created_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=False,
        )

    with op.batch_alter_table('sync_events', schema=None) as batch_op:
        batch_op.alter_column(
            'occurred_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=False,
        )

    with op.batch_alter_table('storage_backends', schema=None) as batch_op:
        batch_op.alter_column(
            'created_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=False,
        )
        batch_op.alter_column(
            'updated_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=False,
        )

    with op.batch_alter_table('security_audit_logs', schema=None) as batch_op:
        batch_op.alter_column(
            'created_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=False,
        )

    with op.batch_alter_table('rental_contracts', schema=None) as batch_op:
        batch_op.alter_column(
            'created_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=False,
        )
        batch_op.alter_column(
            'updated_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=False,
        )

    with op.batch_alter_table('reminders', schema=None) as batch_op:
        batch_op.alter_column(
            'dismissed_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=True,
        )
        batch_op.alter_column(
            'resolved_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=True,
        )
        batch_op.alter_column(
            'created_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=False,
        )
        batch_op.alter_column(
            'updated_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=False,
        )

    with op.batch_alter_table('reminder_notifications', schema=None) as batch_op:
        batch_op.alter_column(
            'created_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=False,
        )

    with op.batch_alter_table('reconcile_state', schema=None) as batch_op:
        batch_op.alter_column(
            'last_checked_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=True,
        )
        batch_op.alter_column(
            'last_applied_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=True,
        )
        batch_op.alter_column(
            'last_verified_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=True,
        )

    with op.batch_alter_table('payment_records', schema=None) as batch_op:
        batch_op.alter_column(
            'paid_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=False,
        )

    with op.batch_alter_table('notification_subscriptions', schema=None) as batch_op:
        batch_op.alter_column(
            'created_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=False,
        )

    with op.batch_alter_table('notification_configs', schema=None) as batch_op:
        batch_op.alter_column(
            'created_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=False,
        )
        batch_op.alter_column(
            'updated_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=False,
        )

    with op.batch_alter_table('notification_channels', schema=None) as batch_op:
        batch_op.alter_column(
            'created_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=False,
        )
        batch_op.alter_column(
            'updated_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=False,
        )

    with op.batch_alter_table('notification_channel_configs', schema=None) as batch_op:
        batch_op.alter_column(
            'created_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=False,
        )
        batch_op.alter_column(
            'updated_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=False,
        )

    with op.batch_alter_table('manifesto_version', schema=None) as batch_op:
        batch_op.alter_column(
            'signed_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=True,
        )
        batch_op.alter_column(
            'created_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=False,
        )

    with op.batch_alter_table('manifesto_signature', schema=None) as batch_op:
        batch_op.alter_column(
            'signed_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=False,
        )

    with op.batch_alter_table('manifesto_feedback', schema=None) as batch_op:
        batch_op.alter_column(
            'created_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=False,
        )

    with op.batch_alter_table('literacy_weekly_reports', schema=None) as batch_op:
        batch_op.alter_column(
            'generated_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=False,
        )

    with op.batch_alter_table('literacy_scenarios', schema=None) as batch_op:
        batch_op.alter_column(
            'completed_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=True,
        )

    with op.batch_alter_table('literacy_scenario_templates', schema=None) as batch_op:
        batch_op.alter_column(
            'created_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=False,
        )

    with op.batch_alter_table('literacy_badges', schema=None) as batch_op:
        batch_op.alter_column(
            'earned_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=False,
        )
        batch_op.alter_column(
            'superseded_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=True,
        )

    with op.batch_alter_table('literacy_badge_definitions', schema=None) as batch_op:
        batch_op.alter_column(
            'created_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=False,
        )

    with op.batch_alter_table('liabilities', schema=None) as batch_op:
        batch_op.alter_column(
            'created_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=False,
        )
        batch_op.alter_column(
            'updated_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=False,
        )

    with op.batch_alter_table('file_remote_locations', schema=None) as batch_op:
        batch_op.alter_column(
            'synced_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=True,
        )
        batch_op.alter_column(
            'created_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=False,
        )
        batch_op.alter_column(
            'updated_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=False,
        )

    with op.batch_alter_table('family_web_search_providers', schema=None) as batch_op:
        batch_op.alter_column(
            'half_open_window_start',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=True,
        )
        batch_op.alter_column(
            'last_failure_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=True,
        )
        batch_op.alter_column(
            'created_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=False,
        )
        batch_op.alter_column(
            'updated_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=False,
        )

    with op.batch_alter_table('family_manifesto', schema=None) as batch_op:
        batch_op.alter_column(
            'signing_deadline',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=True,
        )
        batch_op.alter_column(
            'created_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=False,
        )
        batch_op.alter_column(
            'updated_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=False,
        )

    with op.batch_alter_table('family_invitation_codes', schema=None) as batch_op:
        batch_op.alter_column(
            'used_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=True,
        )
        batch_op.alter_column(
            'revoked_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=True,
        )
        batch_op.alter_column(
            'created_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=False,
        )

    with op.batch_alter_table('family_debt_thresholds', schema=None) as batch_op:
        batch_op.alter_column(
            'created_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=False,
        )
        batch_op.alter_column(
            'updated_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=False,
        )

    with op.batch_alter_table('families', schema=None) as batch_op:
        batch_op.alter_column(
            'created_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=False,
        )
        batch_op.alter_column(
            'updated_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=False,
        )

    with op.batch_alter_table('exchange_rates', schema=None) as batch_op:
        batch_op.alter_column(
            'fetched_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=False,
        )
        batch_op.alter_column(
            'created_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=False,
        )

    with op.batch_alter_table('draft_imports', schema=None) as batch_op:
        batch_op.alter_column(
            'rolled_back_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=True,
        )
        batch_op.alter_column(
            'created_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=False,
        )

    with op.batch_alter_table('device_sessions', schema=None) as batch_op:
        batch_op.alter_column(
            'created_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=False,
        )
        batch_op.alter_column(
            'last_seen_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=False,
        )
        batch_op.alter_column(
            'expires_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=False,
        )

    with op.batch_alter_table('coin_transactions', schema=None) as batch_op:
        batch_op.alter_column(
            'created_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=False,
        )

    with op.batch_alter_table('chore_templates', schema=None) as batch_op:
        batch_op.alter_column(
            'created_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=False,
        )
        batch_op.alter_column(
            'updated_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=False,
        )

    with op.batch_alter_table('chore_instances', schema=None) as batch_op:
        batch_op.alter_column(
            'submitted_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=True,
        )
        batch_op.alter_column(
            'approved_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=True,
        )
        batch_op.alter_column(
            'claimed_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=True,
        )
        batch_op.alter_column(
            'consumed_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=True,
        )
        batch_op.alter_column(
            'created_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=False,
        )

    with op.batch_alter_table('child_wishes', schema=None) as batch_op:
        batch_op.alter_column(
            'created_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=False,
        )
        batch_op.alter_column(
            'updated_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=False,
        )

    with op.batch_alter_table('child_wish_cost_history', schema=None) as batch_op:
        batch_op.alter_column(
            'created_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=False,
        )

    with op.batch_alter_table('child_economy_configs', schema=None) as batch_op:
        batch_op.alter_column(
            'created_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=False,
        )
        batch_op.alter_column(
            'updated_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=False,
        )

    with op.batch_alter_table('challenge_grants', schema=None) as batch_op:
        batch_op.alter_column(
            'deadline',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=False,
        )
        batch_op.alter_column(
            'completed_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=True,
        )
        batch_op.alter_column(
            'created_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=False,
        )
        batch_op.alter_column(
            'updated_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=False,
        )

    with op.batch_alter_table('categories', schema=None) as batch_op:
        batch_op.alter_column(
            'created_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=False,
        )
        batch_op.alter_column(
            'updated_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=False,
        )

    with op.batch_alter_table('cached_files', schema=None) as batch_op:
        batch_op.alter_column(
            'deleted_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=True,
        )
        batch_op.alter_column(
            'created_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=False,
        )

    with op.batch_alter_table('bonus_draws', schema=None) as batch_op:
        batch_op.alter_column(
            'expires_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=False,
        )
        batch_op.alter_column(
            'created_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=False,
        )

    with op.batch_alter_table('blind_box_gifts', schema=None) as batch_op:
        batch_op.alter_column(
            'created_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=False,
        )
        batch_op.alter_column(
            'updated_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=False,
        )

    with op.batch_alter_table('blind_box_draws', schema=None) as batch_op:
        batch_op.alter_column(
            'draw_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=False,
        )
        batch_op.alter_column(
            'fulfilled_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=True,
        )

    with op.batch_alter_table('blind_box_config', schema=None) as batch_op:
        batch_op.alter_column(
            'created_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=False,
        )
        batch_op.alter_column(
            'updated_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=False,
        )

    with op.batch_alter_table('balance_corrections', schema=None) as batch_op:
        batch_op.alter_column(
            'created_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=False,
        )

    with op.batch_alter_table('assets', schema=None) as batch_op:
        batch_op.alter_column(
            'created_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=False,
        )
        batch_op.alter_column(
            'updated_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=False,
        )

    with op.batch_alter_table('asset_valuations', schema=None) as batch_op:
        batch_op.alter_column(
            'valued_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=False,
        )

    with op.batch_alter_table('asset_snapshots', schema=None) as batch_op:
        batch_op.alter_column(
            'created_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=False,
        )

    with op.batch_alter_table('asset_lifecycle_events', schema=None) as batch_op:
        batch_op.alter_column(
            'created_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=False,
        )

    with op.batch_alter_table('asr_provider_configs', schema=None) as batch_op:
        batch_op.alter_column(
            'last_failure_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=True,
        )
        batch_op.alter_column(
            'tested_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=True,
        )
        batch_op.alter_column(
            'created_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=False,
        )
        batch_op.alter_column(
            'updated_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=False,
        )

    with op.batch_alter_table('ai_tasks', schema=None) as batch_op:
        batch_op.alter_column(
            'started_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=False,
        )
        batch_op.alter_column(
            'completed_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=True,
        )
        batch_op.alter_column(
            'lease_expires_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=True,
        )

    with op.batch_alter_table('ai_skills', schema=None) as batch_op:
        batch_op.alter_column(
            'created_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=False,
        )
        batch_op.alter_column(
            'updated_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=False,
        )

    with op.batch_alter_table('ai_reports', schema=None) as batch_op:
        batch_op.alter_column(
            'generated_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=False,
        )

    with op.batch_alter_table('ai_providers', schema=None) as batch_op:
        batch_op.alter_column(
            'half_open_window_start',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=True,
        )
        batch_op.alter_column(
            'circuit_open_until',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=True,
        )
        batch_op.alter_column(
            'last_failure_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=True,
        )
        batch_op.alter_column(
            'created_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=False,
        )
        batch_op.alter_column(
            'updated_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=False,
        )

    with op.batch_alter_table('ai_provider_test_results', schema=None) as batch_op:
        batch_op.alter_column(
            'tested_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=False,
        )

    with op.batch_alter_table('ai_mcp_servers', schema=None) as batch_op:
        batch_op.alter_column(
            'created_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=False,
        )
        batch_op.alter_column(
            'updated_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=False,
        )

    with op.batch_alter_table('ai_extraction_circuits', schema=None) as batch_op:
        batch_op.alter_column(
            'opened_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=True,
        )
        batch_op.alter_column(
            'opened_until',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=True,
        )
        batch_op.alter_column(
            'manually_reset_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=True,
        )
        batch_op.alter_column(
            'last_evaluated_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=False,
        )

    with op.batch_alter_table('ai_extraction_audits', schema=None) as batch_op:
        batch_op.alter_column(
            'extracted_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=False,
        )

    with op.batch_alter_table('ai_chat_sessions', schema=None) as batch_op:
        batch_op.alter_column(
            'created_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=False,
        )
        batch_op.alter_column(
            'updated_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=False,
        )

    with op.batch_alter_table('ai_chat_messages', schema=None) as batch_op:
        batch_op.alter_column(
            'created_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=False,
        )

    with op.batch_alter_table('ai_chat_message_feedback', schema=None) as batch_op:
        batch_op.alter_column(
            'created_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=False,
        )
        batch_op.alter_column(
            'updated_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=False,
        )

    with op.batch_alter_table('activities', schema=None) as batch_op:
        batch_op.alter_column(
            'created_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=False,
        )

