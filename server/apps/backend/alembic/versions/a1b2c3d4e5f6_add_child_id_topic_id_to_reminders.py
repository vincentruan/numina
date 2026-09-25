"""add child_id and topic_id to reminders

Revision ID: a1b2c3d4e5f6
Revises: z4783a86brs1
Create Date: 2026-09-25
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "a1b2c3d4e5f6"
down_revision = "z4783a86brs1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "reminders",
        sa.Column("child_id", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "reminders",
        sa.Column("topic_id", sa.BigInteger(), nullable=True),
    )
    op.create_index(op.f("ix_reminders_child_id"), "reminders", ["child_id"])
    op.create_index(op.f("ix_reminders_topic_id"), "reminders", ["topic_id"])
    op.create_foreign_key(
        "fk_reminders_child_id_users",
        "reminders",
        "users",
        ["child_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_reminders_child_id_users", "reminders", type_="foreignkey")
    op.drop_index(op.f("ix_reminders_topic_id"), table_name="reminders")
    op.drop_index(op.f("ix_reminders_child_id"), table_name="reminders")
    op.drop_column("reminders", "topic_id")
    op.drop_column("reminders", "child_id")
