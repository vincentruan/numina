"""add thinking_supported to ai_provider_configs

Revision ID: o5825q08plj5
Revises: n5724p07oki4
Create Date: 2026-05-15 23:30:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'o5825q08plj5'
down_revision: str | None = 'n5724p07oki4'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add thinking_supported column to ai_provider_configs
    op.add_column(
        'ai_provider_configs',
        sa.Column('thinking_supported', sa.Boolean(), nullable=False, server_default='false')
    )


def downgrade() -> None:
    # Remove thinking_supported column from ai_provider_configs
    op.drop_column('ai_provider_configs', 'thinking_supported')