"""mcp token spec alignment: widen prefix, add revocation audit trail

Revision ID: mcp003spec
Revises: ef001sm2fac
Create Date: 2026-10-13

Changes:
- Widen token_prefix from String(8) to String(12) (spec alignment)
- Add revoked_at (DateTime, nullable) for revocation timestamp
- Add revoked_by (BigInteger, nullable) for revoking user FK reference

Backward compat: existing 8-char prefixes remain valid; the model reads the
actual stored prefix length for lookup. New tokens will store 12-char prefixes.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "mcp003spec"
down_revision: str | None = "ef001sm2fac"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()

    if not bind.dialect.has_table(bind, "family_mcp_tokens"):
        return

    cols = {c["name"]: c for c in bind.dialect.get_columns(bind, "family_mcp_tokens")}

    # 1. Widen token_prefix from String(8) to String(12)
    if "token_prefix" in cols:
        existing_type = cols["token_prefix"]["type"]
        # Only alter if not already 12 chars wide
        if "12" not in str(existing_type):
            with op.batch_alter_table("family_mcp_tokens") as batch_op:
                batch_op.alter_column(
                    "token_prefix",
                    existing_type=sa.String(8),
                    type_=sa.String(12),
                    existing_nullable=False,
                )

    # 2. Add revoked_at column
    if "revoked_at" not in cols:
        with op.batch_alter_table("family_mcp_tokens") as batch_op:
            batch_op.add_column(
                sa.Column("revoked_at", sa.DateTime(), nullable=True),
            )

    # 3. Add revoked_by column
    if "revoked_by" not in cols:
        with op.batch_alter_table("family_mcp_tokens") as batch_op:
            batch_op.add_column(
                sa.Column("revoked_by", sa.BigInteger(), nullable=True),
            )


def downgrade() -> None:
    bind = op.get_bind()

    if not bind.dialect.has_table(bind, "family_mcp_tokens"):
        return

    cols = {c["name"]: c for c in bind.dialect.get_columns(bind, "family_mcp_tokens")}

    if "revoked_by" in cols:
        with op.batch_alter_table("family_mcp_tokens") as batch_op:
            batch_op.drop_column("revoked_by")

    if "revoked_at" in cols:
        with op.batch_alter_table("family_mcp_tokens") as batch_op:
            batch_op.drop_column("revoked_at")

    # Note: we do NOT narrow token_prefix back to String(8) in downgrade,
    # because new 12-char prefixes would be silently truncated. Operators
    # should rotate tokens after downgrade if needed.
