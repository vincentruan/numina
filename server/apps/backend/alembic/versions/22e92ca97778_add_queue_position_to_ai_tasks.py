"""add_queue_position_to_ai_tasks

Revision ID: 22e92ca97778
Revises: aa91d6ea730d
Create Date: 2026-05-11 20:41:47.684377

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '22e92ca97778'
down_revision: str | None = 'aa91d6ea730d'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('ai_tasks', sa.Column('queue_position', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('ai_tasks', 'queue_position')
