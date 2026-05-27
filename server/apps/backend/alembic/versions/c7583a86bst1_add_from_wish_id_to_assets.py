"""add from_wish_id to assets

Revision ID: c7583a86bst1
Revises: b6472z75ars0
Create Date: 2026-05-27

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c7583a86bst1"
down_revision: str | None = "b6472z75ars0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("assets", sa.Column("from_wish_id", sa.BigInteger(), nullable=True))
    op.create_foreign_key(
        "fk_assets_from_wish_id",
        "assets",
        "wishes",
        ["from_wish_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_assets_family_from_wish", "assets", ["family_id", "from_wish_id"])
    # Backfill existing assets that were created from a wish realization
    # Relies on child_wishes.realized_asset_id FK integrity — existing realized wishes must have valid asset references.
    # The UPDATE via JOIN matches each asset to its originating wish via the reverse FK link.
    op.execute(
        """
        UPDATE assets
        SET from_wish_id = child_wishes.id
        FROM child_wishes
        WHERE child_wishes.realized_asset_id = assets.id
          AND assets.from_wish_id IS NULL
        """
    )


def downgrade() -> None:
    op.drop_index("ix_assets_family_from_wish", table_name="assets")
    op.drop_constraint("fk_assets_from_wish_id", "assets", type_="foreignkey")
    op.drop_column("assets", "from_wish_id")
