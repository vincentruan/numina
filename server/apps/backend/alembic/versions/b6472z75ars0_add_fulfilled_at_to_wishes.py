"""add fulfilled_at to wishes and child_wishes

Revision ID: b6472z75ars0
Revises: a53453cf574b
Create Date: 2026-05-27

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b6472z75ars0"
down_revision: str | None = "a53453cf574b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("wishes", sa.Column("fulfilled_at", sa.TIMESTAMP(timezone=True), nullable=True))
    op.add_column("child_wishes", sa.Column("fulfilled_at", sa.TIMESTAMP(timezone=True), nullable=True))
    # Backfill existing realized records using updated_at as a proxy for fulfillment time
    op.execute(
        "UPDATE wishes SET fulfilled_at = updated_at WHERE status = 'realized' AND fulfilled_at IS NULL"
    )
    op.execute(
        "UPDATE child_wishes SET fulfilled_at = updated_at WHERE status = 'realized' AND fulfilled_at IS NULL"
    )


def downgrade() -> None:
    op.drop_column("child_wishes", "fulfilled_at")
    op.drop_column("wishes", "fulfilled_at")
