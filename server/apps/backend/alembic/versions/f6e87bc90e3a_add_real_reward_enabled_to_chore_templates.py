"""add real_reward_enabled to chore_templates

Revision ID: f6e87bc90e3a
Revises: e5d75abd9827
Create Date: 2026-07-22 13:00:00.000000

B1 per-template granularity：ChoreTemplate 加 1 列
- real_reward_enabled (Boolean, default True) — per-template opt-out 开关

审批门控语义变化：family 级 education_reward_enabled（全局门）
× template.real_reward_enabled（per-template 门）。default=True 向后兼容
（所有现有 template 默认参与，opt-out 语义）。

fresh-DB idempotency guard：检查列是否已存在，已存在则跳过 add_column，
避免 fresh-DB（create_all 已建表含新列）执行 migration 时报错。
镜像 e5d75abd9827 的 _existing_columns 模式。
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'f6e87bc90e3a'
down_revision: str | None = 'e5d75abd9827'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _existing_columns(bind, table: str) -> list[str]:
    if not bind.dialect.has_table(bind, table):
        return []
    return [c['name'] for c in bind.dialect.get_columns(bind, table)]


def upgrade() -> None:
    bind = op.get_bind()
    existing = _existing_columns(bind, 'chore_templates')

    if 'real_reward_enabled' not in existing:
        op.add_column(
            'chore_templates',
            sa.Column('real_reward_enabled', sa.Boolean(), nullable=False, server_default='1'),
        )


def downgrade() -> None:
    bind = op.get_bind()
    existing = _existing_columns(bind, 'chore_templates')

    if 'real_reward_enabled' in existing:
        op.drop_column('chore_templates', 'real_reward_enabled')
