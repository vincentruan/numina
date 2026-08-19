"""migrate null dates to sentinel 2100-01-01 for "无限期" semantics

Revision ID: q1w2e3r4t5s6
Revises: m7n8o9p0q1r2
Create Date: 2026-08-19 14:00:00.000000

Sets existing NULL values in date columns (liabilities.end_date,
assets.maturity_date, assets.warranty_expiry_date) to the sentinel
value 2100-01-01. After this migration, NULL in these columns carries
the new "无限期" (infinite/no-expiry) semantics.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "q1w2e3r4t5s6"
down_revision: str | None = "m7n8o9p0q1r2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SENTINEL_DATE = "2100-01-01"


def _column_exists(inspector: sa.engine.Inspector, table: str, column: str) -> bool:
    columns = {col["name"] for col in inspector.get_columns(table)}
    return column in columns


def upgrade() -> None:
    """Set existing NULL dates to sentinel 2100-01-01."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    # Use sa.text() with named params for cross-DB compatibility (SQLite + PostgreSQL).
    # exec_driver_sql uses raw DBAPI placeholders (? for SQLite, %s for psycopg2).
    if _column_exists(inspector, "liabilities", "end_date"):
        conn.execute(
            sa.text("UPDATE liabilities SET end_date = :d WHERE end_date IS NULL"),
            {"d": SENTINEL_DATE},
        )

    if _column_exists(inspector, "assets", "maturity_date"):
        conn.execute(
            sa.text("UPDATE assets SET maturity_date = :d WHERE maturity_date IS NULL"),
            {"d": SENTINEL_DATE},
        )

    if _column_exists(inspector, "assets", "warranty_expiry_date"):
        conn.execute(
            sa.text(
                "UPDATE assets SET warranty_expiry_date = :d WHERE warranty_expiry_date IS NULL"
            ),
            {"d": SENTINEL_DATE},
        )


def downgrade() -> None:
    """Restore sentinel 2100-01-01 back to NULL."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    if _column_exists(inspector, "liabilities", "end_date"):
        conn.execute(
            sa.text("UPDATE liabilities SET end_date = NULL WHERE end_date = :d"),
            {"d": SENTINEL_DATE},
        )

    if _column_exists(inspector, "assets", "maturity_date"):
        conn.execute(
            sa.text("UPDATE assets SET maturity_date = NULL WHERE maturity_date = :d"),
            {"d": SENTINEL_DATE},
        )

    if _column_exists(inspector, "assets", "warranty_expiry_date"):
        conn.execute(
            sa.text(
                "UPDATE assets SET warranty_expiry_date = NULL WHERE warranty_expiry_date = :d"
            ),
            {"d": SENTINEL_DATE},
        )
