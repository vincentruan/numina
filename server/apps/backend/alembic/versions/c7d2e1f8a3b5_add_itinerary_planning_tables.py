"""add itinerary planning tables

Revision ID: c7d2e1f8a3b5
Revises: b4c8d3e9f2a3
Create Date: 2026-09-22 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c7d2e1f8a3b5'
down_revision: Union[str, None] = 'b4c8d3e9f2a3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


NEW_TABLES = [
    "itinerary_item_types",
    "itinerary_items",
]


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    existing = set(inspector.get_table_names())

    # --- itinerary_item_types ---
    if "itinerary_item_types" not in existing:
        op.create_table(
            "itinerary_item_types",
            sa.Column("id", sa.BigInteger(), nullable=False),
            sa.Column("family_id", sa.BigInteger(), nullable=True),
            sa.Column("name", sa.String(length=50), nullable=False),
            sa.Column("icon", sa.String(length=50), nullable=False, server_default="star"),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["family_id"], ["families.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_itinerary_item_types_family_id", "itinerary_item_types", ["family_id"])

    # --- itinerary_items ---
    if "itinerary_items" not in existing:
        op.create_table(
            "itinerary_items",
            sa.Column("id", sa.BigInteger(), nullable=False),
            sa.Column("trip_id", sa.BigInteger(), nullable=False),
            sa.Column("family_id", sa.BigInteger(), nullable=False),
            sa.Column("date", sa.Date(), nullable=False),
            sa.Column("type", sa.String(length=20), nullable=False),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("start_time", sa.Time(), nullable=True),
            sa.Column("end_time", sa.Time(), nullable=True),
            sa.Column("location", sa.String(length=200), nullable=True),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("cost_amount", sa.Numeric(precision=18, scale=2), nullable=True),
            sa.Column("cost_currency", sa.String(length=10), nullable=True),
            sa.Column("custom_type_id", sa.BigInteger(), nullable=True),
            sa.Column("type_metadata", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["trip_id"], ["trips.id"]),
            sa.ForeignKeyConstraint(["family_id"], ["families.id"]),
            sa.ForeignKeyConstraint(["custom_type_id"], ["itinerary_item_types.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_itinerary_items_trip_id", "itinerary_items", ["trip_id"])
        op.create_index("ix_itinerary_items_family_id", "itinerary_items", ["family_id"])
        op.create_index("ix_itinerary_items_date", "itinerary_items", ["date"])

    # --- add itinerary_item_id to expense_entries ---
    existing_cols = {
        c["name"]
        for c in inspector.get_columns("expense_entries")
    } if inspector.has_table("expense_entries") else set()

    if "itinerary_item_id" not in existing_cols:
        op.add_column(
            "expense_entries",
            sa.Column("itinerary_item_id", sa.BigInteger(), nullable=True),
        )
        op.create_foreign_key(
            "fk_expense_entries_itinerary_item_id",
            "expense_entries",
            "itinerary_items",
            ["itinerary_item_id"],
            ["id"],
        )
        op.create_index(
            "ix_expense_entries_itinerary_item_id",
            "expense_entries",
            ["itinerary_item_id"],
        )


def downgrade() -> None:
    # Drop itinerary_item_id from expense_entries
    if op.get_bind().dialect.has_table(op.get_bind(), "expense_entries"):
        op.drop_index("ix_expense_entries_itinerary_item_id", table_name="expense_entries")
        op.drop_constraint("fk_expense_entries_itinerary_item_id", "expense_entries", type_="foreignkey")
        op.drop_column("expense_entries", "itinerary_item_id")

    # Drop new tables
    for table in reversed(NEW_TABLES):
        op.drop_table(table, if_exists=True)
