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
    conn = op.get_context().connection
    inspector = sa.inspect(conn)
    existing_cols = {c["name"] for c in inspector.get_columns("users")}

    # 1. Add child identity fields to users table (idempotent)
    new_col_defs = {
        "pin_hash": sa.Column("pin_hash", sa.String(255), nullable=True),
        "pin_fail_count": sa.Column("pin_fail_count", sa.Integer(), nullable=False, server_default="0"),
        "pin_locked_until": sa.Column("pin_locked_until", sa.DateTime(), nullable=True),
        "token_version": sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"),
    }
    cols_to_add = [col for name, col in new_col_defs.items() if name not in existing_cols]

    # Always run batch_alter to ensure nullable changes are applied.
    # batch_alter_table recreates the table, naturally dropping the old unique
    # constraint on username. The partial index below replaces it.
    with op.batch_alter_table("users", schema=None) as batch_op:
        for col in cols_to_add:
            batch_op.add_column(col)
        batch_op.alter_column("username", nullable=True)
        batch_op.alter_column("password_hash", nullable=True)

    # 2. Create partial unique index on username (WHERE username IS NOT NULL)
    # Allows multiple NULL usernames for child accounts while preserving
    # uniqueness for adult accounts.
    existing_indexes = {i["name"] for i in inspector.get_indexes("users")}
    if "ix_users_username_unique" not in existing_indexes:
        op.create_index(
            "ix_users_username_unique",
            "users",
            ["username"],
            unique=True,
            sqlite_where=text("username IS NOT NULL"),
            postgresql_where=text("username IS NOT NULL"),
        )

    # 3. Create child_bind_tokens table (idempotent)
    if "child_bind_tokens" not in inspector.get_table_names():
        op.create_table(
            "child_bind_tokens",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("family_id", sa.String(36), sa.ForeignKey("families.id"), nullable=False),
            sa.Column("token", sa.String(64), nullable=False, unique=True),
            sa.Column("child_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.Column("used_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        )


def downgrade() -> None:
    op.drop_table("child_bind_tokens")
    op.drop_index("ix_users_username_unique", table_name="users")
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("token_version")
        batch_op.drop_column("pin_locked_until")
        batch_op.drop_column("pin_fail_count")
        batch_op.drop_column("pin_hash")
        batch_op.alter_column("username", nullable=False)
        batch_op.alter_column("password_hash", nullable=False)
