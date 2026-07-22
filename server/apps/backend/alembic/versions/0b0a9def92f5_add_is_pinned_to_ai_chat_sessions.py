"""add_is_pinned_to_ai_chat_sessions

Revision ID: 0b0a9def92f5
Revises: 564e56b7643c
Create Date: 2026-05-12 16:46:26.928279

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0b0a9def92f5'
down_revision: str | None = '564e56b7643c'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Fresh-DB guard: bootstrap (b00t5trap0001) already creates ai_chat_sessions
    # with is_pinned. Skip when the column already exists.
    bind = op.get_bind()
    cols = {c['name'] for c in bind.dialect.get_columns(bind, 'ai_chat_sessions')} if bind.dialect.has_table(bind, 'ai_chat_sessions') else set()
    if 'is_pinned' not in cols:
        op.add_column(
            'ai_chat_sessions',
            sa.Column('is_pinned', sa.Boolean(), nullable=False, server_default=sa.false()),
        )


def downgrade() -> None:
    op.drop_column('ai_chat_sessions', 'is_pinned')
