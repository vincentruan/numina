"""add end_date and purchase_date to itinerary_items

Revision ID: a8b3c9d2e1f7
Revises: 7fc4e7ea69ca
Create Date: 2026-09-26 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a8b3c9d2e1f7'
down_revision: Union[str, None] = '7fc4e7ea69ca'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())

    existing_cols = {
        c["name"]
        for c in inspector.get_columns("itinerary_items")
    } if inspector.has_table("itinerary_items") else set()

    if "end_date" not in existing_cols:
        op.add_column(
            "itinerary_items",
            sa.Column("end_date", sa.Date(), nullable=True),
        )

    if "purchase_date" not in existing_cols:
        op.add_column(
            "itinerary_items",
            sa.Column("purchase_date", sa.Date(), nullable=True),
        )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())

    if inspector.has_table("itinerary_items"):
        existing_cols = {c["name"] for c in inspector.get_columns("itinerary_items")}
        if "purchase_date" in existing_cols:
            op.drop_column("itinerary_items", "purchase_date")
        if "end_date" in existing_cols:
            op.drop_column("itinerary_items", "end_date")
