"""add draft_imports table and liability is_archived

Revision ID: b1c2d3e4f5g6
Revises: a1b2c3d4e5f7
Create Date: 2026-08-03 10:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b1c2d3e4f5g6"
down_revision: str | None = "a1b2c3d4e5f7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()

    # --- draft_imports table (fresh-DB guard) ---
    if not bind.dialect.has_table(bind, "draft_imports"):
        op.create_table(
            "draft_imports",
            sa.Column("id", sa.BigInteger(), primary_key=True),
            sa.Column("family_id", sa.BigInteger(), nullable=False),
            sa.Column("user_id", sa.BigInteger(), nullable=False),
            sa.Column("source_filename", sa.String(500), nullable=False),
            sa.Column("source_format", sa.String(20), nullable=False),
            sa.Column("file_hash", sa.String(64), nullable=True),
            sa.Column("parsed_items", sa.Text(), nullable=False, server_default="[]"),
            sa.Column("committed_record_ids", sa.Text(), nullable=True),
            sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
            sa.Column("rolled_back_at", sa.DateTime(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(),
                server_default=sa.func.now(),
                nullable=False,
            ),
        )
        op.create_index(
            "ix_draft_imports_family_created",
            "draft_imports",
            ["family_id", "created_at"],
        )

    # --- liability.is_archived (fresh-DB guard) ---
    if bind.dialect.has_table(bind, "liabilities"):
        cols = {c["name"] for c in bind.dialect.get_columns(bind, "liabilities")}
        if "is_archived" not in cols:
            op.add_column(
                "liabilities",
                sa.Column(
                    "is_archived", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")
                ),
            )


def downgrade() -> None:
    bind = op.get_bind()

    # Remove liability.is_archived
    if bind.dialect.has_table(bind, "liabilities"):
        cols = {c["name"] for c in bind.dialect.get_columns(bind, "liabilities")}
        if "is_archived" in cols:
            op.drop_column("liabilities", "is_archived")

    # Drop draft_imports table
    if bind.dialect.has_table(bind, "draft_imports"):
        op.drop_index("ix_draft_imports_family_created", table_name="draft_imports")
        op.drop_table("draft_imports")
