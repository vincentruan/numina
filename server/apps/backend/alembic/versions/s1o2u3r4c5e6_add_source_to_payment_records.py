"""add source column to payment_records

Revision ID: s1o2u3r4c5e6
Revises: r1e2p3a4y5m6
Create Date: 2026-08-19 16:00:00.000000

Adds a 'source' column to payment_records to distinguish manually-recorded
payments from system-generated retroactive records. Values: "manual" (default)
or "system".
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "s1o2u3r4c5e6"
down_revision: str | None = "r1e2p3a4y5m6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _column_exists(inspector: sa.engine.Inspector, table: str, column: str) -> bool:
    columns = {col["name"] for col in inspector.get_columns(table)}
    return column in columns


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    if not _column_exists(inspector, "payment_records", "source"):
        with op.batch_alter_table("payment_records") as batch_op:
            batch_op.add_column(
                sa.Column(
                    "source",
                    sa.String(20),
                    nullable=False,
                    server_default="manual",
                )
            )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    if _column_exists(inspector, "payment_records", "source"):
        with op.batch_alter_table("payment_records") as batch_op:
            batch_op.drop_column("source")
