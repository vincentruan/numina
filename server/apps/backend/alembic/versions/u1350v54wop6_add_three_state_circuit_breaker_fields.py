"""add three-state circuit breaker fields to ai_provider_configs

Revision ID: u1350v54wop6
Revises: t1269u43vno9
Create Date: 2026-05-20

Adds three-state circuit breaker fields to ai_provider_configs:
- circuit_state: closed | open | half_open (replaces circuit_open boolean)
- circuit_reason: transient | permanent_auth | permanent_account
- recovery_schedule: comma-separated time patterns like ":01,:31"
- last_failure_type: error type from last failure
- half_open_success_count, half_open_failure_count: tracking for half-open window
- half_open_window_start: start time of half-open testing window

Migration strategy:
1. Add new columns with defaults
2. Migrate circuit_open boolean to circuit_state string
3. Handle expired circuit_open_until case → half_open
4. Retain legacy columns for rollback safety
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = 'u1350v54wop6'
down_revision: Union[str, None] = 't1269u43vno9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new circuit breaker fields
    op.add_column('ai_provider_configs', sa.Column('circuit_state', sa.String(20), nullable=False, server_default='closed'))
    op.add_column('ai_provider_configs', sa.Column('circuit_reason', sa.String(30), nullable=True))
    op.add_column('ai_provider_configs', sa.Column('recovery_schedule', sa.String(100), nullable=True))
    op.add_column('ai_provider_configs', sa.Column('last_failure_type', sa.String(30), nullable=True))
    op.add_column('ai_provider_configs', sa.Column('half_open_success_count', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('ai_provider_configs', sa.Column('half_open_failure_count', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('ai_provider_configs', sa.Column('half_open_window_start', sa.DateTime(), nullable=True))

    # Migrate existing circuit_open boolean to circuit_state string
    # SQLite-compatible: use CASE expression
    # Handle expired circuit_open_until → half_open (from review finding)
    op.execute(text("""
        UPDATE ai_provider_configs
        SET circuit_state = CASE
            WHEN circuit_open = 1 AND circuit_open_until IS NOT NULL AND circuit_open_until <= datetime('now') THEN 'half_open'
            WHEN circuit_open = 1 THEN 'open'
            ELSE 'closed'
        END
    """))

    # Set circuit_reason for existing open circuits (assume transient for legacy)
    op.execute(text("""
        UPDATE ai_provider_configs
        SET circuit_reason = 'transient'
        WHERE circuit_open = 1 AND circuit_reason IS NULL
    """))


def downgrade() -> None:
    # Restore circuit_open from circuit_state for rollback
    op.execute(text("""
        UPDATE ai_provider_configs
        SET circuit_open = CASE
            WHEN circuit_state = 'open' OR circuit_state = 'half_open' THEN 1
            ELSE 0
        END
    """))

    # Drop new columns
    op.drop_column('ai_provider_configs', 'half_open_window_start')
    op.drop_column('ai_provider_configs', 'half_open_failure_count')
    op.drop_column('ai_provider_configs', 'half_open_success_count')
    op.drop_column('ai_provider_configs', 'last_failure_type')
    op.drop_column('ai_provider_configs', 'recovery_schedule')
    op.drop_column('ai_provider_configs', 'circuit_reason')
    op.drop_column('ai_provider_configs', 'circuit_state')