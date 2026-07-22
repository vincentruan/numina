"""remove capability column from ai_chat_sessions

Revision ID: a5894b97cs2
Revises: z4783a86brs1
Create Date: 2026-06-02
"""
from collections.abc import Sequence

from alembic import op

revision: str = "a5894b97cs2"
down_revision: str | None = "z4783a86brs1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Fresh-DB guard: bootstrap creates ai_chat_sessions without capability
    # (current model). Skip when the column is already absent. SQLite requires
    # batch_alter_table to drop a column (no plain ALTER COLUMN DROP).
    bind = op.get_bind()
    if not bind.dialect.has_table(bind, 'ai_chat_sessions'):
        return
    cols = {c['name'] for c in bind.dialect.get_columns(bind, 'ai_chat_sessions')}
    if 'capability' in cols:
        with op.batch_alter_table('ai_chat_sessions') as batch_op:
            batch_op.drop_column('capability')


def downgrade() -> None:
    import sqlalchemy as sa
    op.add_column(
        "ai_chat_sessions",
        sa.Column("capability", sa.String(32), nullable=False, server_default="chat"),
    )