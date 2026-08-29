"""add rental_contracts table

Revision ID: e5eec29f082a
Revises: 69689ce5e420
Create Date: 2026-08-17 17:29:16.064546

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'e5eec29f082a'
down_revision: Union[str, None] = '69689ce5e420'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if "rental_contracts" in inspector.get_table_names():
        return  # already exists (idempotent for fresh DB)

    op.create_table(
        'rental_contracts',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('family_id', sa.BigInteger(), nullable=False),
        sa.Column('role', sa.String(length=10), nullable=False),
        sa.Column('monthly_rent', sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column('deposit', sa.Numeric(precision=18, scale=2), nullable=False, server_default='0'),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=True),
        sa.Column('linked_asset_id', sa.BigInteger(), nullable=True),
        sa.Column('counterparty', sa.String(length=200), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('currency', sa.String(length=10), nullable=False, server_default='CNY'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['family_id'], ['families.id']),
        sa.ForeignKeyConstraint(['linked_asset_id'], ['assets.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_rental_contracts_family_id'), 'rental_contracts', ['family_id'])
    op.create_index(op.f('ix_rental_contracts_user_id'), 'rental_contracts', ['user_id'])
    op.create_index(op.f('ix_rental_contracts_is_active'), 'rental_contracts', ['is_active'])


def downgrade() -> None:
    op.drop_index(op.f('ix_rental_contracts_is_active'), table_name='rental_contracts')
    op.drop_index(op.f('ix_rental_contracts_user_id'), table_name='rental_contracts')
    op.drop_index(op.f('ix_rental_contracts_family_id'), table_name='rental_contracts')
    op.drop_table('rental_contracts')
