"""make literacy_scenario_template_id_nullable

Revision ID: 97d491c0b317
Revises: l1t2e3r4a5c6
Create Date: 2026-07-28 23:18:01.577589

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '97d491c0b317'
down_revision: str | None = 'l1t2e3r4a5c6'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # SQLite requires batch mode for column alterations
    with op.batch_alter_table("literacy_scenarios") as batch_op:
        batch_op.alter_column(
            "template_id",
            existing_type=sa.BigInteger(),
            nullable=True,
        )


def downgrade() -> None:
    # Best-effort: set any NULL template_ids to 0 before re-applying NOT NULL
    op.execute(
        "UPDATE literacy_scenarios SET template_id = 0 WHERE template_id IS NULL"
    )
    with op.batch_alter_table("literacy_scenarios") as batch_op:
        batch_op.alter_column(
            "template_id",
            existing_type=sa.BigInteger(),
            nullable=False,
        )