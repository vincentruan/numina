"""expand invitation code column to 20 chars

Revision ID: d70b7f8bf50b
Revises: a2r3g4n5r6p7
Create Date: 2026-07-27 21:43:25.902860

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'd70b7f8bf50b'
down_revision: str | None = 'a2r3g4n5r6p7'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table('family_invitation_codes') as batch_op:
        batch_op.alter_column(
            'code',
            existing_type=sa.VARCHAR(length=6),
            type_=sa.String(length=20),
            existing_nullable=False,
        )


def downgrade() -> None:
    with op.batch_alter_table('family_invitation_codes') as batch_op:
        batch_op.alter_column(
            'code',
            existing_type=sa.String(length=20),
            type_=sa.VARCHAR(length=6),
            existing_nullable=False,
        )
