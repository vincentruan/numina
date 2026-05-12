"""add_is_pinned_to_ai_chat_sessions

Revision ID: 0b0a9def92f5
Revises: 564e56b7643c
Create Date: 2026-05-12 16:46:26.928279

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0b0a9def92f5'
down_revision: Union[str, None] = '564e56b7643c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'ai_chat_sessions',
        sa.Column('is_pinned', sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column('ai_chat_sessions', 'is_pinned')
