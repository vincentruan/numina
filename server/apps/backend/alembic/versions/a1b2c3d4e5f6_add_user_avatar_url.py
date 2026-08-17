"""add user avatar_url

Revision ID: a1b2c3d4e5f6
Revises: f5g6h7i8j9k0
Create Date: 2026-08-15

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = 'ua1v2a3t4r5u'
down_revision = 'f5g6h7i8j9k0'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add avatar_url column to users table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing = {col["name"] for col in inspector.get_columns("users")}
    if "avatar_url" not in existing:
        op.add_column(
            'users',
            sa.Column('avatar_url', sa.String(500), nullable=True)
        )


def downgrade() -> None:
    """Remove avatar_url column from users table."""
    op.drop_column('users', 'avatar_url')
