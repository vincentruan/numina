"""add override fields and consecutive_ai_overrides

Revision ID: 1f05a4b6a5de
Revises: p7a001qhash
Create Date: 2026-10-19 00:50:24.994040

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import packages.db.session

# revision identifiers, used by Alembic.
revision: str = '1f05a4b6a5de'
down_revision: str | None = 'p7a001qhash'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('child_learning_stats', sa.Column('consecutive_ai_overrides', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('learning_progress', sa.Column('overridden_by', sa.BigInteger(), nullable=True))
    op.add_column('learning_progress', sa.Column('overridden_at', packages.db.session.UTCDateTime(timezone=True), nullable=True))
    op.add_column('learning_progress', sa.Column('override_reason', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('learning_progress', 'override_reason')
    op.drop_column('learning_progress', 'overridden_at')
    op.drop_column('learning_progress', 'overridden_by')
    op.drop_column('child_learning_stats', 'consecutive_ai_overrides')
