"""phase4_smart_reminders

Revision ID: b1c2d3e4f5a6
Revises: aa10837ae378
Create Date: 2026-04-27 08:30:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b1c2d3e4f5a6"
down_revision: str | None = "aa10837ae378"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "notification_channels",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("family_id", sa.BigInteger(), nullable=False),
        sa.Column("channel_type", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("config", sa.Text(), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["family_id"], ["families.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_notification_channels_family_id", "notification_channels", ["family_id"])

    op.create_table(
        "notification_subscriptions",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("channel_id", sa.BigInteger(), nullable=False),
        sa.Column("reminder_type", sa.String(length=30), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["channel_id"], ["notification_channels.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("channel_id", "reminder_type", name="uq_channel_reminder_type"),
    )
    op.create_index("ix_notification_subscriptions_channel_id", "notification_subscriptions", ["channel_id"])

    op.create_table(
        "notification_configs",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("family_id", sa.BigInteger(), nullable=False),
        sa.Column("large_purchase_threshold_fixed", sa.Float(), nullable=True),
        sa.Column("large_purchase_threshold_multiplier", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["family_id"], ["families.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("family_id"),
    )
    op.create_index("ix_notification_configs_family_id", "notification_configs", ["family_id"])

    op.create_table(
        "reminders",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("family_id", sa.BigInteger(), nullable=False),
        sa.Column("reminder_type", sa.String(length=30), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("severity", sa.String(length=10), nullable=False, server_default=sa.text("'info'")),
        sa.Column("asset_id", sa.BigInteger(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default=sa.text("'active'")),
        sa.Column("dismissed_at", sa.DateTime(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("notified_channels", sa.Text(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("send_retry_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["family_id"], ["families.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_reminders_family_id", "reminders", ["family_id"])
    op.create_index("ix_reminders_asset_id", "reminders", ["asset_id"])

    op.add_column("assets", sa.Column("warranty_expiry_date", sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column("assets", "warranty_expiry_date")
    op.drop_index("ix_reminders_asset_id", table_name="reminders")
    op.drop_index("ix_reminders_family_id", table_name="reminders")
    op.drop_table("reminders")
    op.drop_index("ix_notification_configs_family_id", table_name="notification_configs")
    op.drop_table("notification_configs")
    op.drop_index("ix_notification_subscriptions_channel_id", table_name="notification_subscriptions")
    op.drop_table("notification_subscriptions")
    op.drop_index("ix_notification_channels_family_id", table_name="notification_channels")
    op.drop_table("notification_channels")
