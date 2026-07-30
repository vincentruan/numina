"""drop_migrated_columns

Revision ID: ac070c6b7aaf
Revises: 3ec41c70c529
Create Date: 2026-04-29 20:48:25.969544

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision: str = 'ac070c6b7aaf'
down_revision: str | None = '3ec41c70c529'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    insp = inspect(bind)
    return any(c["name"] == column for c in insp.get_columns(table))


def _has_table(table: str) -> bool:
    bind = op.get_bind()
    insp = inspect(bind)
    return table in insp.get_table_names()


def _drop_if_exists(table: str, column: str) -> None:
    if _has_table(table) and _has_column(table, column):
        op.drop_column(table, column)


def upgrade() -> None:
    # Drop AI config columns migrated to ai_provider_configs table
    for col in [
        'ai_model_id', 'ai_vision_text_test_message', 'ai_vision_test_message',
        'ai_vision_text_test_latency_ms', 'ai_test_timestamp', 'ai_base_url',
        'ai_test_thinking_message', 'ai_vision_text_test_timestamp', 'ai_test_connected',
        'ai_vision_test_latency_ms', 'auto_approve_hours', 'ai_vision_test_timestamp',
        'ai_test_thinking_success', 'ai_test_message', 'ai_provider',
        'ai_test_thinking_timestamp', 'ai_vision_text_test_success', 'ai_api_key_encrypted',
        'ai_enabled', 'ai_test_latency_ms', 'ai_test_thinking_latency_ms',
        'ai_vision_model_id', 'ai_vision_test_success',
        # child economy config columns migrated to child_economy_configs table
        'coin_silver_to_gold', 'coin_copper_to_silver',
    ]:
        _drop_if_exists('families', col)

    # Drop asset lifecycle columns migrated to asset_lifecycle_events table
    for col in ['sell_fee', 'sell_channel', 'retire_date', 'sell_date', 'sell_price']:
        _drop_if_exists('assets', col)

    # Drop child wish cost history column migrated to child_wish_cost_history table
    _drop_if_exists('child_wishes', 'star_coin_cost_history')

    # Drop reminder notification columns migrated to reminder_notifications table
    _drop_if_exists('reminders', 'notified_channels')
    _drop_if_exists('reminders', 'send_retry_count')

    # Drop notification channel config column migrated to notification_channel_configs table
    _drop_if_exists('notification_channels', 'config')


def downgrade() -> None:
    from sqlalchemy.dialects import sqlite

    if _has_table('notification_channels') and not _has_column('notification_channels', 'config'):
        op.add_column('notification_channels', sa.Column('config', sa.TEXT(), nullable=False, server_default='{}'))

    if _has_table('reminders'):
        if not _has_column('reminders', 'send_retry_count'):
            op.add_column('reminders', sa.Column('send_retry_count', sa.INTEGER(), server_default=sa.text('0'), nullable=False))
        if not _has_column('reminders', 'notified_channels'):
            op.add_column('reminders', sa.Column('notified_channels', sa.TEXT(), server_default=sa.text("'[]'"), nullable=False))

    if not _has_column('child_wishes', 'star_coin_cost_history'):
        op.add_column('child_wishes', sa.Column('star_coin_cost_history', sqlite.JSON(), nullable=True))

    for col, col_type in [
        ('sell_price', sa.FLOAT()), ('sell_date', sa.DATE()),
        ('retire_date', sa.DATE()), ('sell_channel', sa.VARCHAR(length=100)),
        ('sell_fee', sa.FLOAT()),
    ]:
        if not _has_column('assets', col):
            op.add_column('assets', sa.Column(col, col_type, nullable=True))  # type: ignore[arg-type]

    for col, col_type, kw in [  # type: ignore[arg-type]
        ('coin_copper_to_silver', sa.INTEGER(), {'server_default': sa.text('(10)'), 'nullable': False}),
        ('coin_silver_to_gold', sa.INTEGER(), {'server_default': sa.text('(10)'), 'nullable': False}),
        ('ai_model_id', sa.VARCHAR(length=100), {'nullable': True}),
        ('ai_vision_text_test_message', sa.TEXT(), {'nullable': True}),
        ('ai_vision_test_message', sa.TEXT(), {'nullable': True}),
        ('ai_vision_text_test_latency_ms', sa.INTEGER(), {'nullable': True}),
        ('ai_test_timestamp', sa.DATETIME(), {'nullable': True}),
        ('ai_base_url', sa.TEXT(), {'nullable': True}),
        ('ai_test_thinking_message', sa.TEXT(), {'nullable': True}),
        ('ai_vision_text_test_timestamp', sa.DATETIME(), {'nullable': True}),
        ('ai_test_connected', sa.BOOLEAN(), {'nullable': True}),
        ('ai_vision_test_latency_ms', sa.INTEGER(), {'nullable': True}),
        ('auto_approve_hours', sa.INTEGER(), {'server_default': sa.text('(24)'), 'nullable': False}),
        ('ai_vision_test_timestamp', sa.DATETIME(), {'nullable': True}),
        ('ai_test_thinking_success', sa.BOOLEAN(), {'nullable': True}),
        ('ai_test_message', sa.TEXT(), {'nullable': True}),
        ('ai_provider', sa.TEXT(), {'nullable': True}),
        ('ai_test_thinking_timestamp', sa.DATETIME(), {'nullable': True}),
        ('ai_vision_text_test_success', sa.BOOLEAN(), {'nullable': True}),
        ('ai_api_key_encrypted', sa.TEXT(), {'nullable': True}),
        ('ai_enabled', sa.BOOLEAN(), {'server_default': sa.text('0'), 'nullable': False}),
        ('ai_test_latency_ms', sa.INTEGER(), {'nullable': True}),
        ('ai_test_thinking_latency_ms', sa.INTEGER(), {'nullable': True}),
        ('ai_vision_model_id', sa.VARCHAR(length=100), {'nullable': True}),
        ('ai_vision_test_success', sa.BOOLEAN(), {'nullable': True}),
    ]:
        if not _has_column('families', col):
            op.add_column('families', sa.Column(col, col_type, **kw))  # type: ignore[arg-type]
