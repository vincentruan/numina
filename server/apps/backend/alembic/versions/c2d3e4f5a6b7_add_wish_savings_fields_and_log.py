"""add wish savings fields + wish_savings_log table

Revision ID: c2d3e4f5a6b7
Revises: b9c7d2e4f6a8
Create Date: 2026-07-19

Plan B W1: wish savings progress. Adds saved_amount (derived cache)/target_date/
monthly_saving/ignore_debt_warning to wishes, migrates expected_price Float→
NUMERIC(18,2) (spec §2.1 "一次性统一"), and creates wish_savings_log as the
source of truth. saved_amount is maintained in-transaction by the savings CRUD
(Plan B W1 service); a recompute_saved_amount helper + CI assertion guard drift.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c2d3e4f5a6b7"
down_revision: str | None = "b9c7d2e4f6a8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. wish: add savings fields. SQLite ALTER TABLE can't change a column type
    #    in-place, so batch mode recreates the table. Adding columns is a safe
    #    batch op on its own (no type swap mixing in).
    with op.batch_alter_table("wishes") as batch:
        batch.add_column(sa.Column("saved_amount", sa.Numeric(18, 2), nullable=False, server_default="0"))
        batch.add_column(sa.Column("target_date", sa.Date(), nullable=True))
        batch.add_column(sa.Column("monthly_saving", sa.Numeric(18, 2), nullable=False, server_default="0"))
        batch.add_column(sa.Column("ignore_debt_warning", sa.Boolean(), nullable=False, server_default="0"))

    # 2. Migrate expected_price Float → NUMERIC(18,2) in its own batch. Mixing
    #    add_column + alter_column in one SQLite batch recreate triggers a
    #    CircularDependencyError on the added columns' server_defaults; two
    #    separate batches avoids it. Existing float values coerce to Decimal on read.
    with op.batch_alter_table("wishes") as batch:
        batch.alter_column("expected_price",
                           existing_type=sa.Float(),
                           type_=sa.Numeric(18, 2),
                           existing_nullable=True)

    # 3. wish_savings_log: source of truth.
    op.create_table(
        "wish_savings_logs",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("wish_id", sa.BigInteger(), sa.ForeignKey("wishes.id"), nullable=False),
        sa.Column("family_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("log_date", sa.Date(), nullable=False),
        sa.Column("note", sa.String(length=200), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "ix_wish_savings_logs_wish_logdate",
        "wish_savings_logs",
        ["wish_id", sa.text("log_date DESC")],
    )
    op.create_index(
        "ix_wish_savings_logs_family_created",
        "wish_savings_logs",
        ["family_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_wish_savings_logs_family_created", table_name="wish_savings_logs")
    op.drop_index("ix_wish_savings_logs_wish_logdate", table_name="wish_savings_logs")
    op.drop_table("wish_savings_logs")
    with op.batch_alter_table("wishes") as batch:
        batch.alter_column("expected_price",
                           existing_type=sa.Numeric(18, 2),
                           type_=sa.Float(),
                           existing_nullable=True)
    with op.batch_alter_table("wishes") as batch:
        batch.drop_column("ignore_debt_warning")
        batch.drop_column("monthly_saving")
        batch.drop_column("target_date")
        batch.drop_column("saved_amount")
