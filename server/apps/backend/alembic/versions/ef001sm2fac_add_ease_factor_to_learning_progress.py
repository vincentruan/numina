"""add ease_factor to learning_progress

Revision ID: ef001sm2fac
Revises: 6861f2ca98ef
Create Date: 2026-10-12

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "ef001sm2fac"
down_revision: Union[str, None] = "6861f2ca98ef"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    cols = {c["name"] for c in bind.dialect.get_columns(bind, "learning_progress")}
    if "ease_factor" not in cols:
        with op.batch_alter_table("learning_progress", schema=None) as batch_op:
            batch_op.add_column(
                sa.Column("ease_factor", sa.Float(), nullable=True, server_default="2.5")
            )


def downgrade() -> None:
    with op.batch_alter_table("learning_progress", schema=None) as batch_op:
        batch_op.drop_column("ease_factor")
