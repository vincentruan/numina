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
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == 'sqlite'

    def _has_column(table: str, col: str) -> bool:
        if not bind.dialect.has_table(bind, table):
            return False
        return any(c['name'] == col for c in bind.dialect.get_columns(bind, table))

    def _has_index(table: str, index: str) -> bool:
        if not bind.dialect.has_table(bind, table):
            return False
        return any(i['name'] == index for i in bind.dialect.get_indexes(bind, table))

    # Add from_wish_id column + FK. SQLite cannot add a column with FK via plain
    # ALTER TABLE, and cannot ALTER TABLE ADD CONSTRAINT — use batch_alter_table
    # with a naming convention (batch reflection requires named constraints).
    if not _has_column('assets', 'from_wish_id'):
        with op.batch_alter_table('assets', naming_convention={
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        }) as batch_op:
            batch_op.add_column(sa.Column("from_wish_id", sa.BigInteger(), nullable=True))
            batch_op.create_foreign_key(
                "fk_assets_from_wish_id",
                "wishes",
                ["from_wish_id"],
                ["id"],
                ondelete="SET NULL",
            )

    if not _has_index('assets', 'ix_assets_family_from_wish'):
        op.create_index("ix_assets_family_from_wish", "assets", ["family_id", "from_wish_id"])

    # Backfill existing assets created from a wish realization. The UPDATE...FROM
    # JOIN is Postgres syntax; SQLite uses a correlated subquery.
    if bind.dialect.has_table(bind, 'assets') and bind.dialect.has_table(bind, 'child_wishes'):
        if is_sqlite:
            op.execute(
                """
                UPDATE assets
                SET from_wish_id = (
                    SELECT child_wishes.id FROM child_wishes
                    WHERE child_wishes.realized_asset_id = assets.id
                )
                WHERE from_wish_id IS NULL
                  AND EXISTS (
                    SELECT 1 FROM child_wishes
                    WHERE child_wishes.realized_asset_id = assets.id
                  )
                """
            )
        else:
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
