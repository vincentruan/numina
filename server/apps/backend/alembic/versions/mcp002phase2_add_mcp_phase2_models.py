"""add mcp phase 2: allowed_tools + mcp_access_logs

Revision ID: mcp002phase2
Revises: mcp001token
Create Date: 2026-10-09
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "mcp002phase2"
down_revision: str | None = "mcp001token"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()

    # ── 1. Add allowed_tools column to family_mcp_tokens ─────────────
    if bind.dialect.has_table(bind, "family_mcp_tokens"):
        cols = {c["name"]: c for c in bind.dialect.get_columns(bind, "family_mcp_tokens")}
        if "allowed_tools" not in cols:
            with op.batch_alter_table("family_mcp_tokens") as batch_op:
                batch_op.add_column(
                    sa.Column("allowed_tools", sa.Text(), nullable=True),
                )

    # ── 2. Create mcp_access_logs table ──────────────────────────────
    if not bind.dialect.has_table(bind, "mcp_access_logs"):
        op.create_table(
            "mcp_access_logs",
            sa.Column("id", sa.BigInteger(), primary_key=True),
            sa.Column("family_id", sa.BigInteger(), nullable=False),
            sa.Column("token_id", sa.BigInteger(), nullable=True),
            sa.Column("session_id", sa.String(64), nullable=True),
            sa.Column("event_type", sa.String(16), nullable=False),
            sa.Column("tool_name", sa.String(64), nullable=True),
            sa.Column("status", sa.String(16), nullable=False),
            sa.Column("duration_ms", sa.Integer(), nullable=True),
            sa.Column("client_ip", sa.String(45), nullable=False),
            sa.Column("user_agent", sa.String(512), nullable=True),
            sa.Column("args_digest", sa.Text(), nullable=True),
            sa.Column("error_code", sa.String(32), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(),
                server_default=sa.func.now(),
                nullable=False,
            ),
        )
        # Indexes
        op.create_index("ix_mcp_access_logs_family_id", "mcp_access_logs", ["family_id"])
        op.create_index("ix_mcp_access_logs_session_id", "mcp_access_logs", ["session_id"])
        op.create_index("ix_mcp_access_logs_event_type", "mcp_access_logs", ["event_type"])
        op.create_index("ix_mcp_access_logs_tool_name", "mcp_access_logs", ["tool_name"])
        op.create_index("ix_mcp_access_logs_created_at", "mcp_access_logs", ["created_at"])
        op.create_index(
            "ix_mcp_access_logs_family_created",
            "mcp_access_logs",
            ["family_id", "created_at"],
        )
        op.create_index(
            "ix_mcp_access_logs_family_event_created",
            "mcp_access_logs",
            ["family_id", "event_type", "created_at"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.has_table(bind, "mcp_access_logs"):
        op.drop_table("mcp_access_logs")

    if bind.dialect.has_table(bind, "family_mcp_tokens"):
        cols = {c["name"]: c for c in bind.dialect.get_columns(bind, "family_mcp_tokens")}
        if "allowed_tools" in cols:
            with op.batch_alter_table("family_mcp_tokens") as batch_op:
                batch_op.drop_column("allowed_tools")
