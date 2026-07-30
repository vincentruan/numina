"""add multi provider fields to ai_provider_configs

Revision ID: p6935q19rjk5
Revises: o5825q08plj5
Create Date: 2026-05-16 10:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'p6935q19rjk5'
down_revision: str | None = 'o5825q08plj5'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('ai_provider_configs', sa.Column('provider_name', sa.String(100), nullable=True))
    op.add_column('ai_provider_configs', sa.Column('display_order', sa.Integer(), nullable=True))
    op.add_column('ai_provider_configs', sa.Column('model_2_id', sa.String(100), nullable=True))
    op.add_column('ai_provider_configs', sa.Column('model_3_id', sa.String(100), nullable=True))
    op.add_column('ai_provider_configs', sa.Column('model_1_capabilities', sa.Text(), nullable=True))
    op.add_column('ai_provider_configs', sa.Column('model_2_capabilities', sa.Text(), nullable=True))
    op.add_column('ai_provider_configs', sa.Column('model_3_capabilities', sa.Text(), nullable=True))
    op.add_column('ai_provider_configs', sa.Column('circuit_open', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('ai_provider_configs', sa.Column('circuit_open_until', sa.DateTime(), nullable=True))
    op.add_column('ai_provider_configs', sa.Column('failure_count', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('ai_provider_configs', sa.Column('last_failure_at', sa.DateTime(), nullable=True))

    # Migrate existing data
    # provider_name = INITCAP(provider) — SQLite compatible
    op.execute(
        "UPDATE ai_provider_configs SET provider_name = UPPER(SUBSTR(provider, 1, 1)) || SUBSTR(provider, 2)"
    )

    # display_order = row number within family_id ordered by created_at
    # SQLite-compatible: use a subquery counting earlier rows
    op.execute("""
        UPDATE ai_provider_configs
        SET display_order = (
            SELECT COUNT(*)
            FROM ai_provider_configs AS t2
            WHERE t2.family_id = ai_provider_configs.family_id
              AND (t2.created_at < ai_provider_configs.created_at
                   OR (t2.created_at = ai_provider_configs.created_at AND t2.id < ai_provider_configs.id))
        )
    """)

    # model_1_capabilities from thinking_supported
    op.execute("""
        UPDATE ai_provider_configs
        SET model_1_capabilities = CASE
            WHEN thinking_supported = 1 THEN '["text_generation","deep_thinking"]'
            ELSE '["text_generation"]'
        END
    """)

    # model_2_capabilities from vision_model_id
    op.execute("""
        UPDATE ai_provider_configs
        SET model_2_capabilities = CASE
            WHEN vision_model_id IS NOT NULL THEN '["vision_understanding"]'
            ELSE NULL
        END
    """)


def downgrade() -> None:
    op.drop_column('ai_provider_configs', 'last_failure_at')
    op.drop_column('ai_provider_configs', 'failure_count')
    op.drop_column('ai_provider_configs', 'circuit_open_until')
    op.drop_column('ai_provider_configs', 'circuit_open')
    op.drop_column('ai_provider_configs', 'model_3_capabilities')
    op.drop_column('ai_provider_configs', 'model_2_capabilities')
    op.drop_column('ai_provider_configs', 'model_1_capabilities')
    op.drop_column('ai_provider_configs', 'model_3_id')
    op.drop_column('ai_provider_configs', 'model_2_id')
    op.drop_column('ai_provider_configs', 'display_order')
    op.drop_column('ai_provider_configs', 'provider_name')
