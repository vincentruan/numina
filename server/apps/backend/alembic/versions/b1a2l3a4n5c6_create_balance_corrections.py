"""create balance_corrections table

Revision ID: b1a2l3a4n5c6
Revises: s1o2u3r4c5e6
Create Date: 2026-08-19 16:01:00.000000

Creates the balance_corrections table for post-creation liability adjustments
(U3, Path 1 — not used during create_liability).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b1a2l3a4n5c6"
down_revision: str | None = "s1o2u3r4c5e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_exists(inspector: sa.engine.Inspector, table: str) -> bool:
    return table in inspector.get_table_names()


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    if not _table_exists(inspector, "balance_corrections"):
        op.create_table(
            "balance_corrections",
            sa.Column("id", sa.BigInteger, primary_key=True),
            sa.Column(
                "liability_id",
                sa.BigInteger,
                sa.ForeignKey("liabilities.id"),
                nullable=False,
            ),
            sa.Column("amount", sa.Numeric(18, 2), nullable=False),
            sa.Column("reason", sa.Text, nullable=True),
            sa.Column(
                "created_by",
                sa.BigInteger,
                sa.ForeignKey("users.id"),
                nullable=False,
            ),
            sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    if _table_exists(inspector, "balance_corrections"):
        op.drop_table("balance_corrections")
