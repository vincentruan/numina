"""add education reward to child economy config

Revision ID: e5d75abd9827
Revises: 6c8a42d83b59
Create Date: 2026-07-22 12:00:00.000000

B1 教育联动：ChildEconomyConfig 加 2 列
- education_reward_enabled (Boolean, default False) — family 级 opt-in 开关
- coin_to_yuan_rate (Integer, default 1) — 1 星币 = N 元

fresh-DB idempotency guard：检查列是否已存在，已存在则跳过 add_column，
避免 fresh-DB（create_all 已建表含新列）执行 migration 时报错。
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'e5d75abd9827'
down_revision: str | None = '6c8a42d83b59'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _existing_columns(bind, table: str) -> list[str]:
    if not bind.dialect.has_table(bind, table):
        return []
    return [c['name'] for c in bind.dialect.get_columns(bind, table)]


def upgrade() -> None:
    bind = op.get_bind()
    existing = _existing_columns(bind, 'child_economy_configs')

    if 'education_reward_enabled' not in existing:
        op.add_column(
            'child_economy_configs',
            sa.Column('education_reward_enabled', sa.Boolean(), nullable=False, server_default='0'),
        )
    if 'coin_to_yuan_rate' not in existing:
        op.add_column(
            'child_economy_configs',
            sa.Column('coin_to_yuan_rate', sa.Integer(), nullable=False, server_default='1'),
        )


def downgrade() -> None:
    bind = op.get_bind()
    existing = _existing_columns(bind, 'child_economy_configs')

    if 'coin_to_yuan_rate' in existing:
        op.drop_column('child_economy_configs', 'coin_to_yuan_rate')
    if 'education_reward_enabled' in existing:
        op.drop_column('child_economy_configs', 'education_reward_enabled')
