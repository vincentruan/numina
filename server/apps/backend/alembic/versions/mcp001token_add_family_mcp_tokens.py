"""add family_mcp_tokens table

Revision ID: mcp001token
Revises: lrnst001
Create Date: 2026-10-09
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "mcp001token"
down_revision: str | None = "lrnst001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()

    # Widen users.role from String(10) to String(20) to fit 'external_token' (14 chars)
    if bind.dialect.has_table(bind, "users"):
        cols = {c["name"]: c for c in bind.dialect.get_columns(bind, "users")}
        role_col = cols.get("role")
        if role_col is not None:
            # get_columns returns dicts; check type string for VARCHAR(10)
            col_type = str(role_col.get("type", ""))
            if "10" in col_type:
                with op.batch_alter_table("users") as batch_op:
                    batch_op.alter_column(
                        "role",
                        type_=sa.String(20),
                        existing_type=sa.String(10),
                    )

    # Create family_mcp_tokens table (skip if already exists — fresh-DB guard)
    if not bind.dialect.has_table(bind, "family_mcp_tokens"):
        op.create_table(
            "family_mcp_tokens",
            sa.Column("id", sa.BigInteger(), primary_key=True),
            sa.Column("family_id", sa.BigInteger(), nullable=False),
            sa.Column("token_hash", sa.String(64), nullable=False),
            sa.Column("token_prefix", sa.String(8), nullable=False),
            sa.Column("token_last4", sa.String(4), nullable=False),
            sa.Column("allow_external", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("allow_write", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("expires_at", sa.DateTime(), nullable=True),
            sa.Column("last_used_at", sa.DateTime(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
            sa.Column(
                "created_at",
                sa.DateTime(),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(),
                server_default=sa.func.now(),
                nullable=False,
            ),
        )
        op.create_index(
            "ix_family_mcp_tokens_family_id",
            "family_mcp_tokens",
            ["family_id"],
            unique=False,
        )
        op.create_index(
            "ix_family_mcp_tokens_family_prefix",
            "family_mcp_tokens",
            ["family_id", "token_prefix"],
            unique=False,
        )
        # Separate index for POST /messages path (lookup by token_prefix alone, no family_id)
        op.create_index(
            "ix_family_mcp_tokens_token_prefix",
            "family_mcp_tokens",
            ["token_prefix"],
            unique=False,
        )


def downgrade() -> None:
    op.drop_index(
        "ix_family_mcp_tokens_token_prefix", table_name="family_mcp_tokens"
    )
    op.drop_index(
        "ix_family_mcp_tokens_family_prefix", table_name="family_mcp_tokens"
    )
    op.drop_index(
        "ix_family_mcp_tokens_family_id", table_name="family_mcp_tokens"
    )
    op.drop_table("family_mcp_tokens")

    # Before narrowing users.role, delete synthetic external_token users
    # (role='external_token' is 14 chars, won't fit in String(10))
    bind = op.get_bind()
    if bind.dialect.has_table(bind, "users"):
        op.execute("DELETE FROM users WHERE role = 'external_token'")

    # Narrow users.role back to String(10)
    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column(
            "role",
            type_=sa.String(10),
            existing_type=sa.String(20),
        )
