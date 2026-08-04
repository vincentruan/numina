"""Add family_id to storage_backends and drop is_default

Remote storage is now configured per-family via the Settings UI.
Global (env-var-seeded) backends are no longer supported.

Changes:
- Add `family_id` (BigInteger, NOT NULL, indexed, UNIQUE) to storage_backends
- Delete any legacy rows where family_id IS NULL (global backends)
- Drop the `is_default` column (no longer needed; one backend per family)

Revision ID: f5g6h7i8j9k0
Revises: e4f5g6h7i8j9
Create Date: 2026-08-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f5g6h7i8j9k0"
down_revision: str | None = "e4f5g6h7i8j9"
branch_labels: tuple[str, ...] | None = None
depends_on: tuple[str, ...] | None = None


def upgrade() -> None:
    # Step 1: Add family_id column (nullable first, so we can delete legacy rows)
    op.add_column(
        "storage_backends",
        sa.Column("family_id", sa.BigInteger(), nullable=True),
    )

    # Step 2: Remove legacy global backends (no family association)
    op.execute("DELETE FROM storage_backends WHERE family_id IS NULL")

    # Step 3: Make family_id NOT NULL and add FK + index + unique constraint
    with op.batch_alter_table("storage_backends") as batch_op:
        batch_op.alter_column(
            "family_id",
            existing_type=sa.BigInteger(),
            nullable=False,
        )
        batch_op.create_foreign_key(
            "fk_storage_backends_family_id",
            "families",
            ["family_id"],
            ["id"],
        )
        batch_op.create_index("ix_storage_backends_family_id", ["family_id"])
        batch_op.create_unique_constraint(
            "uq_storage_backends_family_id", ["family_id"]
        )

    # Step 4: Drop is_default column (semantics obsolete — one backend per family)
    with op.batch_alter_table("storage_backends") as batch_op:
        batch_op.drop_column("is_default")


def downgrade() -> None:
    # Restore is_default column
    with op.batch_alter_table("storage_backends") as batch_op:
        batch_op.add_column(
            sa.Column(
                "is_default",
                sa.Boolean(),
                nullable=False,
                server_default=sa.true(),
            ),
        )

    # Drop unique constraint, index, FK, and family_id column
    with op.batch_alter_table("storage_backends") as batch_op:
        batch_op.drop_constraint(
            "uq_storage_backends_family_id", type_="unique"
        )
        batch_op.drop_index("ix_storage_backends_family_id")
        batch_op.drop_constraint(
            "fk_storage_backends_family_id", type_="foreignkey"
        )
        batch_op.drop_column("family_id")
