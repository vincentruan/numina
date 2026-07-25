"""bootstrap missing tables for fresh-DB

Revision ID: b00t5trap0001
Revises: e3cba86157fd
Create Date: 2026-07-22 00:00:00.000000

Creates 17 tables that exist in the current models (Base.metadata) but have NO
create migration anywhere in the alembic upgrade chain. These tables were
historically created via Base.metadata.create_all() (used by tests) or existed
as legacy pre-Alembic UUID tables that aa10837ae378 drops in its upgrade path.

On a fresh DB (seeded from initial_snowflake_schema base), these 17 tables
never come into existence, so every later migration that references them
(batch_alter_table / add_column / rename) fails. This bootstrap creates them
all from the current model definitions, guarded by has_table so it is a no-op
on legacy/prod DBs that already have them.

Tables (17): activities, ai_chat_messages, ai_chat_sessions, ai_reports,
cached_files, category_financial_defaults, child_milestones, chore_instances,
chore_templates, coin_transactions, currencies, exchange_rates,
file_remote_locations, revoked_tokens, security_audit_logs, storage_backends,
sync_events.

Note: ai_chat_sessions.agent_id is created WITHOUT its FK to ai_agents, because
ai_agents is created later in the chain (x2581y64zqr9). The FK is added by
z4783a86brs1 (add agent_id column) — but that migration's add_column would
conflict if the column already exists, so it must be guarded (handled
separately). On fresh DB, agent_id column exists here without FK; the later
add_column migrations are guarded to skip when columns already exist.

Insertion: down_revision = e3cba86157fd (base). 98c68a46add7.down_revision
changed from e3cba86157fd to b00t5trap0001 so this runs first.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'b00t5trap0001'
down_revision: str | None = 'e3cba86157fd'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()

    if not bind.dialect.has_table(bind, 'activities'):
        op.create_table('activities',
            sa.Column('id', sa.BigInteger(), nullable=False, primary_key=True),
            sa.Column('family_id', sa.BigInteger(), sa.ForeignKey('families.id'), nullable=False),
            sa.Column('user_id', sa.BigInteger(), sa.ForeignKey('users.id'), nullable=False),
            sa.Column('type', sa.String(length=30), nullable=False),
            sa.Column('entity_type', sa.String(length=20), nullable=False),
            sa.Column('entity_id', sa.BigInteger(), nullable=False),
            sa.Column('title', sa.String(length=200), nullable=False),
            sa.Column('amount', sa.Float(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()'))
        )

    if not bind.dialect.has_table(bind, 'ai_chat_messages'):
        op.create_table('ai_chat_messages',
            sa.Column('id', sa.BigInteger(), nullable=False, primary_key=True),
            sa.Column('family_id', sa.BigInteger(), sa.ForeignKey('families.id'), nullable=False),
            sa.Column('role', sa.String(length=10), nullable=False),
            sa.Column('content', sa.Text(), nullable=False),
            sa.Column('status', sa.String(length=20), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False)
        )
        op.create_index('ix_ai_chat_messages_family_id', 'ai_chat_messages', ['family_id'])

    if not bind.dialect.has_table(bind, 'ai_chat_sessions'):
        op.create_table('ai_chat_sessions',
            sa.Column('id', sa.BigInteger(), nullable=False, primary_key=True),
            sa.Column('family_id', sa.BigInteger(), sa.ForeignKey('families.id'), nullable=False),
            sa.Column('user_id', sa.BigInteger(), sa.ForeignKey('users.id'), nullable=True),
            sa.Column('agent_id', sa.BigInteger(), nullable=True),
            sa.Column('title', sa.String(length=256), nullable=True),
            sa.Column('original_title', sa.String(length=256), nullable=True),
            sa.Column('status', sa.String(length=20), nullable=False),
            sa.Column('last_message_summary', sa.String(length=200), nullable=True),
            sa.Column('last_model', sa.String(length=128), nullable=True),
            sa.Column('is_pinned', sa.Boolean(), nullable=False),
            sa.Column('source', sa.String(length=32), nullable=True),
            sa.Column('parent_thread_id', sa.String(length=64), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False)
        )
        op.create_index('ix_ai_chat_sessions_family_id', 'ai_chat_sessions', ['family_id'])
        op.create_index('ix_ai_chat_sessions_agent_id', 'ai_chat_sessions', ['agent_id'])

    if not bind.dialect.has_table(bind, 'ai_reports'):
        op.create_table('ai_reports',
            sa.Column('id', sa.BigInteger(), nullable=False, primary_key=True),
            sa.Column('family_id', sa.BigInteger(), sa.ForeignKey('families.id'), nullable=False),
            sa.Column('report_json', sa.JSON(), nullable=False),
            sa.Column('overall_score', sa.Integer(), nullable=True),
            sa.Column('data_completeness_score', sa.Float(), nullable=True),
            sa.Column('generated_at', sa.DateTime(), nullable=False),
            sa.Column('status', sa.String(length=20), nullable=False),
            sa.Column('markdown_file_path', sa.String(length=255), nullable=True),
            sa.Column('capability', sa.String(length=32), nullable=False, server_default=sa.text("'report'"))
        )
        op.create_index('ix_ai_reports_family_id', 'ai_reports', ['family_id'])

    if not bind.dialect.has_table(bind, 'cached_files'):
        op.create_table('cached_files',
            sa.Column('id', sa.BigInteger(), nullable=False, primary_key=True),
            sa.Column('family_id', sa.BigInteger(), sa.ForeignKey('families.id'), nullable=False),
            sa.Column('user_id', sa.BigInteger(), sa.ForeignKey('users.id'), nullable=True),
            sa.Column('sha256', sa.String(length=64), nullable=False),
            sa.Column('local_path', sa.String(length=500), nullable=False),
            sa.Column('original_filename', sa.String(length=255), nullable=False),
            sa.Column('mime_type', sa.String(length=100), nullable=True),
            sa.Column('size_bytes', sa.Integer(), nullable=False),
            sa.Column('date_dir', sa.String(length=8), nullable=False),
            sa.Column('deleted_at', sa.DateTime(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
            sa.UniqueConstraint('sha256', 'family_id', name='uq_cached_files_sha256_family')
        )
        op.create_index('ix_cached_files_family_id', 'cached_files', ['family_id'])

    if not bind.dialect.has_table(bind, 'category_financial_defaults'):
        op.create_table('category_financial_defaults',
            sa.Column('id', sa.BigInteger(), nullable=False, primary_key=True),
            sa.Column('category_id', sa.BigInteger(), sa.ForeignKey('categories.id'), nullable=False),
            sa.Column('default_annual_depreciation', sa.Float(), nullable=False),
            sa.Column('default_annual_return', sa.Float(), nullable=False),
            sa.Column('default_lifespan_years', sa.Integer(), nullable=True),
            sa.UniqueConstraint('category_id')
        )

    if not bind.dialect.has_table(bind, 'child_milestones'):
        op.create_table('child_milestones',
            sa.Column('id', sa.BigInteger(), nullable=False, primary_key=True),
            sa.Column('family_id', sa.BigInteger(), sa.ForeignKey('families.id'), nullable=False),
            sa.Column('child_user_id', sa.BigInteger(), sa.ForeignKey('users.id'), nullable=False),
            sa.Column('milestone_type', sa.String(length=50), nullable=False),
            sa.Column('triggered_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
            sa.Column('ref_id', sa.BigInteger(), nullable=True),
            sa.Column('ref_type', sa.String(length=20), nullable=True)
        )

    if not bind.dialect.has_table(bind, 'chore_templates'):
        op.create_table('chore_templates',
            sa.Column('id', sa.BigInteger(), nullable=False, primary_key=True),
            sa.Column('family_id', sa.BigInteger(), sa.ForeignKey('families.id'), nullable=False),
            sa.Column('created_by', sa.BigInteger(), sa.ForeignKey('users.id'), nullable=False),
            sa.Column('name', sa.String(length=100), nullable=False),
            sa.Column('emoji', sa.String(length=10), nullable=True),
            sa.Column('coin_reward', sa.Integer(), nullable=False),
            sa.Column('frequency', sa.String(length=10), nullable=False),
            sa.Column('assignment_type', sa.String(length=10), nullable=False),
            sa.Column('is_active', sa.Boolean(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()'))
        )

    if not bind.dialect.has_table(bind, 'chore_template_assignees'):
        op.create_table('chore_template_assignees',
            sa.Column('template_id', sa.BigInteger(), sa.ForeignKey('chore_templates.id'), nullable=False),
            sa.Column('child_user_id', sa.BigInteger(), sa.ForeignKey('users.id'), nullable=False),
            sa.PrimaryKeyConstraint('template_id', 'child_user_id')
        )

    if not bind.dialect.has_table(bind, 'chore_instances'):
        op.create_table('chore_instances',
            sa.Column('id', sa.BigInteger(), nullable=False, primary_key=True),
            sa.Column('template_id', sa.BigInteger(), sa.ForeignKey('chore_templates.id'), nullable=False),
            sa.Column('family_id', sa.BigInteger(), sa.ForeignKey('families.id'), nullable=False),
            sa.Column('child_user_id', sa.BigInteger(), sa.ForeignKey('users.id'), nullable=False),
            sa.Column('chore_name', sa.String(length=100), nullable=False),
            sa.Column('chore_emoji', sa.String(length=10), nullable=True),
            sa.Column('coin_reward', sa.Integer(), nullable=False),
            sa.Column('date_bucket', sa.String(length=10), nullable=False),
            sa.Column('status', sa.String(length=20), nullable=False),
            sa.Column('submitted_at', sa.DateTime(), nullable=True),
            sa.Column('approved_at', sa.DateTime(), nullable=True),
            sa.Column('streak_count', sa.Integer(), nullable=False),
            sa.Column('streak_bonus', sa.Integer(), nullable=False),
            sa.Column('submitted_by_user_id', sa.BigInteger(), sa.ForeignKey('users.id'), nullable=True),
            sa.Column('assigned_by_user_id', sa.BigInteger(), sa.ForeignKey('users.id'), nullable=True),
            sa.Column('claimed_at', sa.DateTime(), nullable=True),
            sa.Column('consumed_at', sa.DateTime(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
            sa.UniqueConstraint('template_id', 'child_user_id', 'date_bucket', name='uq_chore_instance')
        )

    if not bind.dialect.has_table(bind, 'coin_transactions'):
        op.create_table('coin_transactions',
            sa.Column('id', sa.BigInteger(), nullable=False, primary_key=True),
            sa.Column('family_id', sa.BigInteger(), sa.ForeignKey('families.id'), nullable=False),
            sa.Column('child_user_id', sa.BigInteger(), sa.ForeignKey('users.id'), nullable=False),
            sa.Column('amount', sa.Integer(), nullable=False),
            sa.Column('transaction_type', sa.String(length=20), nullable=False),
            sa.Column('ref_id', sa.BigInteger(), nullable=True),
            sa.Column('narrative', sa.Text(), nullable=True),
            sa.Column('narrative_emoji', sa.String(length=20), nullable=True),
            sa.Column('streak_bonus', sa.Integer(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
            sa.UniqueConstraint('ref_id', 'transaction_type', name='uq_coin_tx_ref_type')
        )

    if not bind.dialect.has_table(bind, 'currencies'):
        op.create_table('currencies',
            sa.Column('id', sa.BigInteger(), nullable=False, primary_key=True),
            sa.Column('code', sa.String(length=10), nullable=False),
            sa.Column('name_zh', sa.String(length=50), nullable=False),
            sa.Column('name_en', sa.String(length=50), nullable=False),
            sa.Column('symbol', sa.String(length=10), nullable=False),
            sa.Column('flag_emoji', sa.String(length=10), nullable=False),
            sa.Column('is_favorite', sa.Boolean(), nullable=False),
            sa.Column('sort_order', sa.Integer(), nullable=False),
            sa.UniqueConstraint('code')
        )

    if not bind.dialect.has_table(bind, 'exchange_rates'):
        op.create_table('exchange_rates',
            sa.Column('id', sa.BigInteger(), nullable=False, primary_key=True),
            sa.Column('base_currency', sa.String(length=10), nullable=False),
            sa.Column('target_currency', sa.String(length=10), nullable=False),
            sa.Column('rate', sa.Float(), nullable=False),
            sa.Column('fetched_at', sa.DateTime(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
            sa.UniqueConstraint('target_currency', 'fetched_at')
        )

    if not bind.dialect.has_table(bind, 'storage_backends'):
        op.create_table('storage_backends',
            sa.Column('id', sa.BigInteger(), nullable=False, primary_key=True),
            sa.Column('backend_type', sa.String(length=20), nullable=False),
            sa.Column('display_name', sa.String(length=200), nullable=True),
            sa.Column('config', sa.Text(), nullable=True),
            sa.Column('is_default', sa.Boolean(), nullable=False),
            sa.Column('is_active', sa.Boolean(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()'))
        )

    if not bind.dialect.has_table(bind, 'file_remote_locations'):
        op.create_table('file_remote_locations',
            sa.Column('id', sa.BigInteger(), nullable=False, primary_key=True),
            sa.Column('file_id', sa.BigInteger(), sa.ForeignKey('cached_files.id'), nullable=False),
            sa.Column('backend_id', sa.BigInteger(), sa.ForeignKey('storage_backends.id'), nullable=False),
            sa.Column('remote_path', sa.String(length=500), nullable=True),
            sa.Column('remote_url', sa.String(length=1000), nullable=True),
            sa.Column('remote_sha', sa.String(length=100), nullable=True),
            sa.Column('sync_status', sa.String(length=20), nullable=False),
            sa.Column('synced_at', sa.DateTime(), nullable=True),
            sa.Column('last_error', sa.Text(), nullable=True),
            sa.Column('retry_count', sa.Integer(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
            sa.UniqueConstraint('file_id', 'backend_id', name='uq_file_remote_locations_file_backend')
        )
        op.create_index('ix_file_remote_locations_backend_status', 'file_remote_locations', ['backend_id', 'sync_status'])
        op.create_index('ix_file_remote_locations_file_id', 'file_remote_locations', ['file_id'])

    if not bind.dialect.has_table(bind, 'revoked_tokens'):
        op.create_table('revoked_tokens',
            sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
            sa.Column('jti', sa.String(length=36), nullable=True),
            sa.Column('user_id', sa.String(length=36), nullable=True),
            sa.Column('revoked_at', sa.Float(), nullable=False),
            sa.Column('expires_at', sa.Float(), nullable=False)
        )
        op.create_index('ix_revoked_tokens_expires_at', 'revoked_tokens', ['expires_at'])
        op.create_index('ix_revoked_tokens_jti', 'revoked_tokens', ['jti'])
        op.create_index('ix_revoked_tokens_user_expires', 'revoked_tokens', ['user_id', 'expires_at'])
        op.create_index('ix_revoked_tokens_user_id', 'revoked_tokens', ['user_id'])

    if not bind.dialect.has_table(bind, 'security_audit_logs'):
        op.create_table('security_audit_logs',
            sa.Column('id', sa.BigInteger(), nullable=False, primary_key=True),
            sa.Column('event_type', sa.String(length=64), nullable=False),
            sa.Column('user_id', sa.BigInteger(), nullable=True),
            sa.Column('family_id', sa.BigInteger(), nullable=True),
            sa.Column('ip_address', sa.String(length=45), nullable=True),
            sa.Column('user_agent', sa.String(length=512), nullable=True),
            sa.Column('outcome', sa.String(length=16), nullable=False),
            sa.Column('detail', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()'))
        )
        op.create_index('ix_security_audit_logs_family_id', 'security_audit_logs', ['family_id'])
        op.create_index('ix_security_audit_logs_user_id', 'security_audit_logs', ['user_id'])
        op.create_index('ix_security_audit_logs_created_at', 'security_audit_logs', ['created_at'])
        op.create_index('ix_security_audit_logs_event_type', 'security_audit_logs', ['event_type'])

    if not bind.dialect.has_table(bind, 'sync_events'):
        op.create_table('sync_events',
            sa.Column('id', sa.BigInteger(), nullable=False, primary_key=True),
            sa.Column('file_id', sa.BigInteger(), sa.ForeignKey('cached_files.id'), nullable=False),
            sa.Column('backend_id', sa.BigInteger(), sa.ForeignKey('storage_backends.id'), nullable=True),
            sa.Column('event_type', sa.String(length=50), nullable=False),
            sa.Column('detail', sa.Text(), nullable=True),
            sa.Column('occurred_at', sa.DateTime(), nullable=False, server_default=sa.text('now()'))
        )
        op.create_index('ix_sync_events_file_id', 'sync_events', ['file_id'])
        op.create_index('ix_sync_events_backend_occurred', 'sync_events', ['backend_id', 'occurred_at'])


def downgrade() -> None:
    # No-op downgrade: these tables are the current-model baseline. Dropping
    # them on downgrade would diverge from Base.metadata and break create_all.
    # Fresh-DB downgrade to base is not a supported operational path.
    pass
