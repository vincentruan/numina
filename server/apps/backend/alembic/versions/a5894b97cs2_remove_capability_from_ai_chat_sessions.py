"""remove capability column from ai_chat_sessions

Revision ID: a5894b97cs2
Revises: z4783a86brs1
Create Date: 2026-06-02
"""
from typing import Sequence, Union

from alembic import op

revision: str = "a5894b97cs2"
down_revision: Union[str, None] = "z4783a86brs1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("ai_chat_sessions", "capability")


def downgrade() -> None:
    import sqlalchemy as sa
    op.add_column(
        "ai_chat_sessions",
        sa.Column("capability", sa.String(32), nullable=False, server_default="chat"),
    )