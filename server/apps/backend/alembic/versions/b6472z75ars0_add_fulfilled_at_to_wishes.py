"""add fulfilled_at to wishes and child_wishes

Revision ID: b6472z75ars0
Revises: a53453cf574b
Create Date: 2026-05-27

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "b6472z75ars0"
down_revision: Union[str, None] = "a53453cf574b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("wishes", sa.Column("fulfilled_at", sa.TIMESTAMP(timezone=True), nullable=True))
    op.add_column("child_wishes", sa.Column("fulfilled_at", sa.TIMESTAMP(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("child_wishes", "fulfilled_at")
    op.drop_column("wishes", "fulfilled_at")
