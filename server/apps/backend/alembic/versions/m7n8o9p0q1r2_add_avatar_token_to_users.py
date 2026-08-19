"""add avatar_token to users for public pre-auth avatar access

Revision ID: m7n8o9p0q1r2
Revises: e5eec29f082a
Create Date: 2026-08-19 10:00:00.000000

Adds an opaque avatar_token column to users so the login page can display
uploaded avatar images without JWT authentication. The token is unguessable
(~256 bit entropy) and only grants access to the single associated image.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "m7n8o9p0q1r2"
down_revision: str | None = "e5eec29f082a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add avatar_token column with unique constraint to users table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_columns = {col["name"] for col in inspector.get_columns("users")}

    with op.batch_alter_table("users", schema=None) as batch_op:
        if "avatar_token" not in existing_columns:
            batch_op.add_column(
                sa.Column(
                    "avatar_token",
                    sa.String(64),
                    nullable=True,
                    comment="Opaque token for pre-auth avatar access on login page",
                )
            )

        existing_unique_constraints = {
            uc["name"] for uc in inspector.get_unique_constraints("users")
        }
        if "uq_users_avatar_token" not in existing_unique_constraints:
            batch_op.create_unique_constraint("uq_users_avatar_token", ["avatar_token"])


def downgrade() -> None:
    """Remove avatar_token column from users table."""
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_constraint("uq_users_avatar_token", type_="unique")
        batch_op.drop_column("avatar_token")
