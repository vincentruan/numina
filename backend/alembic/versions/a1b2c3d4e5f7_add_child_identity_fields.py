"""add child identity fields and child_bind_tokens table

Revision ID: a1b2c3d4e5f7
Revises: 2a9cb7dc0b62
Create Date: 2026-04-15 07:45:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f7"
down_revision: Union[str, None] = "2a9cb7dc0b62"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add child identity fields to users table
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(sa.Column("pin_hash", sa.String(255), nullable=True))
        batch_op.add_column(
            sa.Column("pin_fail_count", sa.Integer(), nullable=False, server_default="0")
        )
        batch_op.add_column(sa.Column("pin_locked_until", sa.DateTime(), nullable=True))
        batch_op.add_column(
            sa.Column("token_version", sa.Integer(), nullable=False, server_default="0")
        )
        # Make username and password_hash nullable for child accounts
        batch_op.alter_column("username", nullable=True)
        batch_op.alter_column("password_hash", nullable=True)
        # Drop the existing unique constraint on username
        # SQLite: batch_alter_table handles constraint drop differently
        # We need to recreate the table without the unique constraint
        # For SQLite batch mode, drop the unique constraint explicitly
        batch_op.drop_constraint("username", type_="unique")

    # 2. Create partial unique index on username (WHERE username IS NOT NULL)
    # This allows multiple NULL usernames for child accounts while preserving
    # uniqueness for adult accounts
    # Note: MySQL 8+ requires functional index - document as unsupported for MySQL < 8
    op.create_index(
        "ix_users_username_unique",
        "users",
        ["username"],
        unique=True,
        sqlite_where=text("username IS NOT NULL"),
        postgresql_where=text("username IS NOT NULL"),
    )

    # 3. Create child_bind_tokens table
    op.create_table(
        "child_bind_tokens",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("family_id", sa.String(36), sa.ForeignKey("families.id"), nullable=False),
        sa.Column("token", sa.String(64), unique=True, nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )


def downgrade() -> None:
    # 1. Drop child_bind_tokens table
    op.drop_table("child_bind_tokens")

    # 2. Drop partial unique index
    op.drop_index("ix_users_username_unique", table_name="users")

    # 3. Remove child identity fields and restore constraints on users
    with op.batch_alter_table("users", schema=None) as batch_op:
        # Restore unique constraint on username
        batch_op.create_unique_constraint("username", ["username"])
        # Restore non-null constraints
        batch_op.alter_column("username", nullable=False)
        batch_op.alter_column("password_hash", nullable=False)
        # Drop child identity columns
        batch_op.drop_column("token_version")
        batch_op.drop_column("pin_locked_until")
        batch_op.drop_column("pin_fail_count")
        batch_op.drop_column("pin_hash")