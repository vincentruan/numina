"""add push_subscriptions table

Revision ID: a1b2c3d4e5f6
Revises: 05b3d24d6b98
Create Date: 2026-09-10 10:00:00.000000

Adds the push_subscriptions table for Web Push notification support (U4).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "psubscr00001"
down_revision: str | None = "05b3d24d6b98"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create push_subscriptions table."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    if "push_subscriptions" not in existing_tables:
        op.create_table(
            "push_subscriptions",
            sa.Column("id", sa.BigInteger(), nullable=False),
            sa.Column("user_id", sa.BigInteger(), nullable=False),
            sa.Column("family_id", sa.BigInteger(), nullable=False),
            sa.Column("endpoint", sa.Text(), nullable=False),
            sa.Column("p256dh", sa.String(200), nullable=False),
            sa.Column("auth", sa.String(200), nullable=False),
            sa.Column("user_agent", sa.String(500), nullable=True),
            sa.Column("app_type", sa.String(20), nullable=False, server_default="main"),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.ForeignKeyConstraint(["family_id"], ["families.id"], ondelete="CASCADE"),
            sa.UniqueConstraint(
                "user_id", "endpoint", name="uq_push_subscription_user_endpoint"
            ),
        )
        op.create_index("ix_push_subscriptions_user_id", "push_subscriptions", ["user_id"])
        op.create_index("ix_push_subscriptions_family_id", "push_subscriptions", ["family_id"])


def downgrade() -> None:
    """Drop push_subscriptions table."""
    op.drop_index("ix_push_subscriptions_family_id", table_name="push_subscriptions")
    op.drop_index("ix_push_subscriptions_user_id", table_name="push_subscriptions")
    op.drop_table("push_subscriptions")
