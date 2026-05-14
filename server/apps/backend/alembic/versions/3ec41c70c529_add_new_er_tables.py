"""add_new_er_tables

Revision ID: 3ec41c70c529
Revises: f7946h29ged6
Create Date: 2026-04-29 18:56:45.911335

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '3ec41c70c529'
down_revision: Union[str, None] = 'f7946h29ged6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'ai_provider_configs',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('family_id', sa.BigInteger(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('provider', sa.String(length=20), nullable=False),
        sa.Column('api_key_encrypted', sa.Text(), nullable=True),
        sa.Column('base_url', sa.Text(), nullable=True),
        sa.Column('model_id', sa.String(length=100), nullable=True),
        sa.Column('vision_model_id', sa.String(length=100), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_ai_provider_configs_family_id'), 'ai_provider_configs', ['family_id'], unique=False)

    op.create_table(
        'ai_provider_test_results',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('config_id', sa.BigInteger(), nullable=False),
        sa.Column('test_type', sa.String(length=20), nullable=False),
        sa.Column('success', sa.Boolean(), nullable=True),
        sa.Column('message', sa.Text(), nullable=True),
        sa.Column('latency_ms', sa.Integer(), nullable=True),
        sa.Column('tested_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_ai_provider_test_results_config_id'), 'ai_provider_test_results', ['config_id'], unique=False)

    op.create_table(
        'asset_lifecycle_events',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('asset_id', sa.BigInteger(), nullable=False),
        sa.Column('event_type', sa.String(length=20), nullable=False),
        sa.Column('event_date', sa.Date(), nullable=False),
        sa.Column('sell_price', sa.Float(), nullable=True),
        sa.Column('sell_fee', sa.Float(), nullable=True),
        sa.Column('sell_channel', sa.String(length=100), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_asset_lifecycle_events_asset_id'), 'asset_lifecycle_events', ['asset_id'], unique=False)

    op.create_table(
        'child_economy_configs',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('family_id', sa.BigInteger(), nullable=False),
        sa.Column('auto_approve_hours', sa.Integer(), nullable=False),
        sa.Column('coin_copper_to_silver', sa.Integer(), nullable=False),
        sa.Column('coin_silver_to_gold', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('family_id', name='uq_child_economy_config_family'),
    )
    op.create_index(op.f('ix_child_economy_configs_family_id'), 'child_economy_configs', ['family_id'], unique=False)

    op.create_table(
        'child_wish_cost_history',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('wish_id', sa.BigInteger(), nullable=False),
        sa.Column('old_cost', sa.Integer(), nullable=True),
        sa.Column('new_cost', sa.Integer(), nullable=False),
        sa.Column('changed_by_user_id', sa.BigInteger(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_child_wish_cost_history_wish_id'), 'child_wish_cost_history', ['wish_id'], unique=False)

    op.create_table(
        'notification_channel_configs',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('channel_id', sa.BigInteger(), nullable=False),
        sa.Column('key', sa.String(length=100), nullable=False),
        sa.Column('value_encrypted', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_notification_channel_configs_channel_id'), 'notification_channel_configs', ['channel_id'], unique=False)

    op.create_table(
        'reminder_notifications',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('reminder_id', sa.BigInteger(), nullable=False),
        sa.Column('channel_id', sa.BigInteger(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_reminder_notifications_channel_id'), 'reminder_notifications', ['channel_id'], unique=False)
    op.create_index(op.f('ix_reminder_notifications_reminder_id'), 'reminder_notifications', ['reminder_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_reminder_notifications_reminder_id'), table_name='reminder_notifications')
    op.drop_index(op.f('ix_reminder_notifications_channel_id'), table_name='reminder_notifications')
    op.drop_table('reminder_notifications')

    op.drop_index(op.f('ix_notification_channel_configs_channel_id'), table_name='notification_channel_configs')
    op.drop_table('notification_channel_configs')

    op.drop_index(op.f('ix_child_wish_cost_history_wish_id'), table_name='child_wish_cost_history')
    op.drop_table('child_wish_cost_history')

    op.drop_index(op.f('ix_child_economy_configs_family_id'), table_name='child_economy_configs')
    op.drop_table('child_economy_configs')

    op.drop_index(op.f('ix_asset_lifecycle_events_asset_id'), table_name='asset_lifecycle_events')
    op.drop_table('asset_lifecycle_events')

    op.drop_index(op.f('ix_ai_provider_test_results_config_id'), table_name='ai_provider_test_results')
    op.drop_table('ai_provider_test_results')

    op.drop_index(op.f('ix_ai_provider_configs_family_id'), table_name='ai_provider_configs')
    op.drop_table('ai_provider_configs')
