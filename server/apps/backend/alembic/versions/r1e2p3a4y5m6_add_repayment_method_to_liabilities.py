"""add repayment_method column to liabilities

Revision ID: r1e2p3a4y5m6
Revises: q1w2e3r4t5s6
Create Date: 2026-08-19 15:00:00.000000

Adds a repayment_method column (default "equal_payment") to liabilities.
Supports 5 methods: equal_payment, equal_principal, interest_only,
bullet, minimum_payment.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "r1e2p3a4y5m6"
down_revision: str | None = "q1w2e3r4t5s6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _column_exists(inspector: sa.engine.Inspector, table: str, column: str) -> bool:
    columns = {col["name"] for col in inspector.get_columns(table)}
    return column in columns


def upgrade() -> None:
    """Add repayment_method column with server default 'equal_payment'."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    if not _column_exists(inspector, "liabilities", "repayment_method"):
        with op.batch_alter_table("liabilities") as batch_op:
            batch_op.add_column(
                sa.Column(
                    "repayment_method",
                    sa.String(30),
                    nullable=False,
                    server_default="equal_payment",
                )
            )


def downgrade() -> None:
    """Remove repayment_method column."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    if _column_exists(inspector, "liabilities", "repayment_method"):
        with op.batch_alter_table("liabilities") as batch_op:
            batch_op.drop_column("repayment_method")
