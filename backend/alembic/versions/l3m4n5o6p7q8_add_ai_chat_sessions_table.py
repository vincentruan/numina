"""add_ai_chat_sessions_table

Revision ID: l3m4n5o6p7q8
Revises: k2l3m4n5o6p7
Create Date: 2026-04-20 10:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "l3m4n5o6p7q8"
down_revision: Union[str, None] = "k2l3m4n5o6p7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_context().connection
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    if "ai_chat_sessions" not in existing_tables:
        op.create_table(
            "ai_chat_sessions",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column(
                "family_id",
                sa.String(36),
                sa.ForeignKey("families.id"),
                nullable=False,
            ),
            sa.Column(
                "user_id",
                sa.String(36),
                sa.ForeignKey("users.id"),
                nullable=True,
            ),
            sa.Column(
                "cached_file_id",
                sa.String(36),
                sa.ForeignKey("cached_files.id"),
                nullable=True,
            ),
            sa.Column("jsonl_path", sa.String(500), nullable=False),
            sa.Column(
                "message_count",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("0"),
            ),
            sa.Column("last_preview", sa.Text(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(),
                server_default=sa.text("(CURRENT_TIMESTAMP)"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(),
                server_default=sa.text("(CURRENT_TIMESTAMP)"),
                nullable=False,
            ),
        )
        op.create_index(
            "ix_ai_chat_sessions_family_id", "ai_chat_sessions", ["family_id"]
        )


def downgrade() -> None:
    op.drop_index("ix_ai_chat_sessions_family_id", table_name="ai_chat_sessions")
    op.drop_table("ai_chat_sessions")
