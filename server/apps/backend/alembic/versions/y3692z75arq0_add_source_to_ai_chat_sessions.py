"""add source column to ai_chat_sessions

Revision ID: y3692z75arq0
Revises: x2581y64zqr9
Create Date: 2026-06-02
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "y3692z75arq0"
down_revision: Union[str, None] = "x2581y64zqr9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "ai_chat_sessions",
        sa.Column("source", sa.String(32), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("ai_chat_sessions", "source")
