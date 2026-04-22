"""add_family_invitation_code_table

Revision ID: bca8da506d29
Revises: 05f7305758db
Create Date: 2026-04-22 18:15:31.934345

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bca8da506d29'
down_revision: Union[str, None] = '05f7305758db'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create family_invitation_codes table for launch control.

    Each code can only be used once to create a family.
    Complete audit trail: tracks who used it, when, and for which family.
    """
    op.create_table(
        'family_invitation_codes',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('code', sa.String(6), unique=True, nullable=False),
        sa.Column('is_used', sa.Boolean(), default=False, nullable=False),
        sa.Column('used_at', sa.DateTime(), nullable=True),
        sa.Column('used_by_family_id', sa.String(36), nullable=True),
        sa.Column('used_by_username', sa.String(50), nullable=True),
        sa.Column('revoked_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['used_by_family_id'], ['families.id'], ),
    )
    op.create_index(op.f('ix_family_invitation_codes_code'), 'family_invitation_codes', ['code'], unique=False)


def downgrade() -> None:
    """Drop family_invitation_codes table."""
    op.drop_index(op.f('ix_family_invitation_codes_code'), table_name='family_invitation_codes')
    op.drop_table('family_invitation_codes')