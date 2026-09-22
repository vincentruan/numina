"""add wish type-specific fields and trip description

Revision ID: b4c8d3e9f2a3
Revises: a3b7c9d2e8f1
Create Date: 2026-09-21
"""

import sqlalchemy as sa
from alembic import op

revision = "b4c8d3e9f2a3"
down_revision = "a3b7c9d2e8f1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # wishes: add travel/rental-specific fields
    op.add_column("wishes", sa.Column("travel_destination", sa.String(200), nullable=True))
    op.add_column("wishes", sa.Column("travel_duration_days", sa.Integer(), nullable=True))
    op.add_column("wishes", sa.Column("rental_area", sa.String(200), nullable=True))

    # trips: add description (mapped from wish.description on graduation)
    op.add_column("trips", sa.Column("description", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("trips", "description")
    op.drop_column("wishes", "rental_area")
    op.drop_column("wishes", "travel_duration_days")
    op.drop_column("wishes", "travel_destination")
