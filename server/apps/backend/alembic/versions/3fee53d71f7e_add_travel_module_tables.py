"""add travel module tables

Revision ID: 3fee53d71f7e
Revises: e8674585435d
Create Date: 2026-09-21 07:52:25.025258

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '3fee53d71f7e'
down_revision: Union[str, None] = 'e8674585435d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TRAVEL_TABLES = [
    "trips",
    "expense_entries",
    "expense_categories",
    "split_groups",
    "split_participants",
    "split_settlements",
    "trip_co_organizers",
]


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    existing = set(inspector.get_table_names())

    # --- trips ---
    if "trips" not in existing:
        op.create_table(
            "trips",
            sa.Column("id", sa.BigInteger(), nullable=False),
            sa.Column("family_id", sa.BigInteger(), nullable=False),
            sa.Column("user_id", sa.BigInteger(), nullable=False),
            sa.Column("name", sa.String(length=200), nullable=False),
            sa.Column("destination", sa.String(length=200), nullable=False),
            sa.Column("departure_date", sa.Date(), nullable=False),
            sa.Column("return_date", sa.Date(), nullable=True),
            sa.Column("status", sa.String(length=20), server_default="planning", nullable=False),
            sa.Column("planned_budget", sa.Numeric(precision=18, scale=2), nullable=True),
            sa.Column("initial_funding", sa.Numeric(precision=18, scale=2), nullable=True),
            sa.Column("actual_spend", sa.Numeric(precision=18, scale=2), server_default=sa.text("0"), nullable=False),
            sa.Column("currency", sa.String(length=10), server_default="CNY", nullable=False),
            sa.Column("wish_id", sa.BigInteger(), nullable=True),
            sa.Column("timezone", sa.String(length=50), nullable=True),
            sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["family_id"], ["families.id"]),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.ForeignKeyConstraint(["wish_id"], ["wishes.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_trips_family_id", "trips", ["family_id"])
        op.create_index("ix_trips_user_id", "trips", ["user_id"])
        op.create_index("ix_trips_status", "trips", ["status"])

    # --- expense_entries ---
    if "expense_entries" not in existing:
        op.create_table(
            "expense_entries",
            sa.Column("id", sa.BigInteger(), nullable=False),
            sa.Column("family_id", sa.BigInteger(), nullable=False),
            sa.Column("transfer_id", sa.BigInteger(), nullable=False),
            sa.Column("leg_type", sa.String(length=10), nullable=False),
            sa.Column("ref_id", sa.BigInteger(), nullable=True),
            sa.Column("ref_type", sa.String(length=30), nullable=True),
            sa.Column("category_id", sa.BigInteger(), nullable=True),
            sa.Column("amount", sa.Numeric(precision=18, scale=2), nullable=False),
            sa.Column("currency", sa.String(length=10), nullable=False),
            sa.Column("amount_cny", sa.Numeric(precision=18, scale=2), nullable=False, server_default=sa.text("0")),
            sa.Column("exchange_rate", sa.Float(), nullable=True),
            sa.Column("expense_date", sa.Date(), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("receipt_image_url", sa.Text(), nullable=True),
            sa.Column("user_id", sa.BigInteger(), nullable=False),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["category_id"], ["expense_categories.id"]),
            sa.ForeignKeyConstraint(["family_id"], ["families.id"]),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("transfer_id", "leg_type", name="uq_expense_transfer_leg"),
        )
        op.create_index("ix_expense_entries_family_id", "expense_entries", ["family_id"])
        op.create_index("ix_expense_entries_ref", "expense_entries", ["ref_type", "ref_id"])
        op.create_index("ix_expense_entries_transfer_id", "expense_entries", ["transfer_id"])

    # --- expense_categories ---
    if "expense_categories" not in existing:
        op.create_table(
            "expense_categories",
            sa.Column("id", sa.BigInteger(), nullable=False),
            sa.Column("family_id", sa.BigInteger(), nullable=True),
            sa.Column("name", sa.String(length=50), nullable=False),
            sa.Column("icon", sa.String(length=50), nullable=False, server_default="label"),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("is_system", sa.Boolean(), server_default=sa.text("false"), nullable=False),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["family_id"], ["families.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_expense_categories_family_id", "expense_categories", ["family_id"])

    # --- split_groups ---
    if "split_groups" not in existing:
        op.create_table(
            "split_groups",
            sa.Column("id", sa.BigInteger(), nullable=False),
            sa.Column("trip_id", sa.BigInteger(), nullable=False),
            sa.Column("invite_code", sa.String(length=6), nullable=False),
            sa.Column("created_by_user_id", sa.BigInteger(), nullable=False),
            sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["trip_id"], ["trips.id"]),
            sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("invite_code"),
        )
        op.create_index("ix_split_groups_trip_id", "split_groups", ["trip_id"])

    # --- split_participants ---
    if "split_participants" not in existing:
        op.create_table(
            "split_participants",
            sa.Column("id", sa.BigInteger(), nullable=False),
            sa.Column("group_id", sa.BigInteger(), nullable=False),
            sa.Column("name", sa.String(length=200), nullable=False),
            sa.Column("family_id", sa.BigInteger(), nullable=True),
            sa.Column("joined_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["group_id"], ["split_groups.id"]),
            sa.ForeignKeyConstraint(["family_id"], ["families.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_split_participants_group_id", "split_participants", ["group_id"])

    # --- split_settlements ---
    if "split_settlements" not in existing:
        op.create_table(
            "split_settlements",
            sa.Column("id", sa.BigInteger(), nullable=False),
            sa.Column("trip_id", sa.BigInteger(), nullable=False),
            sa.Column("from_participant_name", sa.String(length=200), nullable=False),
            sa.Column("to_participant_name", sa.String(length=200), nullable=False),
            sa.Column("amount", sa.Numeric(precision=18, scale=2), nullable=False),
            sa.Column("currency", sa.String(length=10), nullable=False, server_default="CNY"),
            sa.Column("is_complete", sa.Boolean(), server_default=sa.text("false"), nullable=False),
            sa.Column("settled_at", sa.DateTime(), nullable=True),
            sa.Column("settled_by_user_id", sa.BigInteger(), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["trip_id"], ["trips.id"]),
            sa.ForeignKeyConstraint(["settled_by_user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_split_settlements_trip_id", "split_settlements", ["trip_id"])

    # --- trip_co_organizers ---
    if "trip_co_organizers" not in existing:
        op.create_table(
            "trip_co_organizers",
            sa.Column("id", sa.BigInteger(), nullable=False),
            sa.Column("trip_id", sa.BigInteger(), nullable=False),
            sa.Column("user_id", sa.BigInteger(), nullable=False),
            sa.ForeignKeyConstraint(["trip_id"], ["trips.id"]),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_trip_co_organizers_trip_id", "trip_co_organizers", ["trip_id"])


def downgrade() -> None:
    for table in reversed(TRAVEL_TABLES):
        op.drop_table(table)
