"""make_cached_files_user_id_nullable

Allow user_id to be NULL in cached_files to support system-generated files
(e.g., chat session JSONL files that have no single owner).

Revision ID: n5o6p7q8r9s0
Revises: m4n5o6p7q8r9
Create Date: 2026-04-20 10:02:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "n5o6p7q8r9s0"
down_revision: Union[str, None] = "l3m4n5o6p7q8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # SQLite does not support ALTER COLUMN directly.
    # We recreate the table with user_id nullable.
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    # Check if cached_files table exists (guard for fresh installs)
    if "cached_files" not in inspector.get_table_names():
        return

    # Check if user_id is already nullable by inspecting columns
    columns = {col["name"]: col for col in inspector.get_columns("cached_files")}
    if columns.get("user_id", {}).get("nullable", True):
        # Already nullable — nothing to do
        return

    # SQLite: recreate table with user_id nullable
    with op.batch_alter_table("cached_files") as batch_op:
        batch_op.alter_column(
            "user_id",
            existing_type=sa.String(36),
            nullable=True,
        )


def downgrade() -> None:
    # Restore user_id as NOT NULL (may fail if NULL values exist)
    with op.batch_alter_table("cached_files") as batch_op:
        batch_op.alter_column(
            "user_id",
            existing_type=sa.String(36),
            nullable=False,
        )
