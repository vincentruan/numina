"""add override fields and consecutive_ai_overrides

Revision ID: 1f05a4b6a5de
Revises: p7a001qhash
Create Date: 2026-10-19 00:50:24.994040

"""
from collections.abc import Sequence

import sqlalchemy as sa

import packages.db.session
from apps.backend.alembic import ddl

# revision identifiers, used by Alembic.
revision: str = '1f05a4b6a5de'
down_revision: str | None = 'p7a001qhash'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    ddl.add_column('child_learning_stats', sa.Column('consecutive_ai_overrides', sa.Integer(), nullable=False, server_default='0'))
    ddl.add_column('learning_progress', sa.Column('overridden_by', sa.BigInteger(), nullable=True))
    ddl.add_column('learning_progress', sa.Column('overridden_at', packages.db.session.UTCDateTime(timezone=True), nullable=True))
    ddl.add_column('learning_progress', sa.Column('override_reason', sa.Text(), nullable=True))


def downgrade() -> None:
    ddl.drop_column('learning_progress', 'override_reason')
    ddl.drop_column('learning_progress', 'overridden_at')
    ddl.drop_column('learning_progress', 'overridden_by')
    ddl.drop_column('child_learning_stats', 'consecutive_ai_overrides')
