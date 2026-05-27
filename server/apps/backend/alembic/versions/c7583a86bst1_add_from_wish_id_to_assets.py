"""add from_wish_id to assets

Revision ID: c7583a86bst1
Revises: b6472z75ars0
Create Date: 2026-05-27

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "c7583a86bst1"
down_revision: Union[str, None] = "b6472z75ars0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


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


def downgrade() -> None:
    op.drop_index("ix_assets_family_from_wish", table_name="assets")
    op.drop_constraint("fk_assets_from_wish_id", "assets", type_="foreignkey")
    op.drop_column("assets", "from_wish_id")
