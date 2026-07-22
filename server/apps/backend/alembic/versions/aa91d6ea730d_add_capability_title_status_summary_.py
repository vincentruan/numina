"""add capability/title/status/summary/model/attachments to ai_chat_sessions

Revision ID: aa91d6ea730d
Revises: k2491m74lih1
Create Date: 2026-05-11 10:51:01.360104

Changes:
- ai_chat_sessions.id: VARCHAR(36) -> VARCHAR(64)
- ai_chat_sessions.jsonl_path: VARCHAR(500) -> VARCHAR(512)
- ai_chat_sessions: add capability, title, status, last_message_summary, last_model, has_attachments
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'aa91d6ea730d'
down_revision: str | None = 'k2491m74lih1'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # On a fresh DB the bootstrap (b00t5trap0001) creates ai_chat_sessions with
    # the final schema: BigInteger id (not VARCHAR), no jsonl_path column (dropped
    # in current model), and capability/title/status columns absent at model level
    # (removed). This migration's alter_column(id->VARCHAR) + alter_column(jsonl_path)
    # + add_column(capability etc.) would all conflict or corrupt the id type.
    # Skip when the legacy jsonl_path column is absent (fresh-DB / already-migrated).
    bind = op.get_bind()
    if bind.dialect.has_table(bind, 'ai_chat_sessions'):
        cols = {c['name'] for c in bind.dialect.get_columns(bind, 'ai_chat_sessions')}
        if 'jsonl_path' not in cols:
            return  # final schema already; no legacy jsonl_path to alter

    with op.batch_alter_table('ai_chat_sessions', recreate='always') as batch_op:
        batch_op.alter_column('id', type_=sa.String(64), existing_type=sa.String(36), nullable=False)
        batch_op.alter_column('jsonl_path', type_=sa.String(512), existing_type=sa.String(500), nullable=False)
        batch_op.add_column(sa.Column('capability', sa.String(32), nullable=False, server_default='chat'))
        batch_op.add_column(sa.Column('title', sa.String(256), nullable=True))
        batch_op.add_column(sa.Column('status', sa.String(20), nullable=False, server_default='active'))
        batch_op.add_column(sa.Column('last_message_summary', sa.String(200), nullable=True))
        batch_op.add_column(sa.Column('last_model', sa.String(128), nullable=True))
        batch_op.add_column(sa.Column('has_attachments', sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    with op.batch_alter_table('ai_chat_sessions') as batch_op:
        batch_op.drop_column('has_attachments')
        batch_op.drop_column('last_model')
        batch_op.drop_column('last_message_summary')
        batch_op.drop_column('status')
        batch_op.drop_column('title')
        batch_op.drop_column('capability')
        batch_op.alter_column('jsonl_path', type_=sa.String(500), existing_type=sa.String(512), nullable=False)
        batch_op.alter_column('id', type_=sa.String(36), existing_type=sa.String(64), nullable=False)
