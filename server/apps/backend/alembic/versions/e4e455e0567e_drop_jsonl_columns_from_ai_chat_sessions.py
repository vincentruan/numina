"""Drop deprecated JSONL-era columns from ai_chat_sessions

Revision ID: e4e455e0567e
Revises: w7392x85yzq1
Create Date: 2026-07-09

对话消息持久化已迁移至 DeerFlow checkpointer（agent /api/threads/{id}/runs/stream），
ai_chat_sessions 表上以下字段不再使用，予以删除：

- jsonl_path: 旧 JSONL 文件路径（ChatSessionService 已废弃）
- cached_file_id: 旧 JSONL 文件对应的 CachedFile 外键（ChatSessionService 已废弃）
- message_count: 旧 JSONL 消息计数（checkpointer 保存消息，此列不再写）
- last_preview: 旧 JSONL 最后一条消息预览（同上）
- has_attachments: 从未写入，始终为默认值 False

CachedFile / FileRemoteLocation 表本身保留（files/storage 子系统仍在使用），
仅删除 ai_chat_sessions 上对 cached_files 的外键引用。
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e4e455e0567e"
down_revision: str | None = "w7392x85yzq1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Drop the foreign key constraint on cached_file_id first (if present).
    # SQLite cannot drop columns with FK constraints directly; the batch
    # mode below handles table recreation transparently for both SQLite and
    # PostgreSQL. Constraint names are autogen-style on PG; use batch mode
    # to avoid naming fragility.
    #
    # Fresh-DB guard: bootstrap creates ai_chat_sessions from the current model
    # (no jsonl_path/cached_file_id/message_count/last_preview/has_attachments).
    # Only drop columns that actually exist; if none exist, skip batch entirely
    # (batch_alter_table with no ops still does a copy-and-move which is wasteful
    # and can fail on unnamed-constraint reflection).
    bind = op.get_bind()
    if not bind.dialect.has_table(bind, "ai_chat_sessions"):
        return
    existing = {c["name"] for c in bind.dialect.get_columns(bind, "ai_chat_sessions")}
    to_drop = [c for c in ("jsonl_path", "cached_file_id", "message_count", "last_preview", "has_attachments") if c in existing]
    if not to_drop:
        return
    with op.batch_alter_table("ai_chat_sessions", schema=None, naming_convention={
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
    }) as batch_op:
        for col in to_drop:
            batch_op.drop_column(col)


def downgrade() -> None:
    with op.batch_alter_table("ai_chat_sessions", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("has_attachments", sa.Boolean(), nullable=False, server_default=sa.text("0"))
        )
        batch_op.add_column(sa.Column("last_preview", sa.Text(), nullable=True))
        batch_op.add_column(
            sa.Column("message_count", sa.Integer(), nullable=False, server_default=sa.text("0"))
        )
        batch_op.add_column(
            sa.Column(
                "cached_file_id",
                sa.BigInteger(),
                sa.ForeignKey("cached_files.id"),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column("jsonl_path", sa.String(length=512), nullable=False, server_default="")
        )
