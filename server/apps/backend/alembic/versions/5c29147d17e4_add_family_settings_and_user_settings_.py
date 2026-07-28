"""add family_settings and user_settings tables

Revision ID: 5c29147d17e4
Revises: d70b7f8bf50b
Create Date: 2026-07-28 12:59:46.032982

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '5c29147d17e4'
down_revision: Union[str, None] = 'd70b7f8bf50b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Use IF NOT EXISTS guards because some dev databases may already have
    # these tables created by bootstrap / create_all.
    op.execute("""
        CREATE TABLE IF NOT EXISTS family_settings (
            id BIGINT NOT NULL,
            family_id BIGINT NOT NULL,
            "key" VARCHAR(100) NOT NULL,
            value VARCHAR(500),
            updated_at DATETIME DEFAULT (CURRENT_TIMESTAMP) NOT NULL,
            PRIMARY KEY (id),
            CONSTRAINT uq_family_setting_family_key UNIQUE (family_id, "key")
        )
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_family_settings_family_id
        ON family_settings (family_id)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_family_settings_family_key
        ON family_settings (family_id, "key")
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS user_settings (
            id BIGINT NOT NULL,
            user_id BIGINT NOT NULL,
            "key" VARCHAR(100) NOT NULL,
            value VARCHAR(500),
            updated_at DATETIME DEFAULT (CURRENT_TIMESTAMP) NOT NULL,
            PRIMARY KEY (id),
            CONSTRAINT uq_user_setting_user_key UNIQUE (user_id, "key")
        )
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_user_settings_user_id
        ON user_settings (user_id)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_user_settings_user_key
        ON user_settings (user_id, "key")
    """)


def downgrade() -> None:
    op.drop_index(op.f('ix_user_settings_user_key'), table_name='user_settings', if_exists=True)
    op.drop_index(op.f('ix_user_settings_user_id'), table_name='user_settings', if_exists=True)
    op.drop_table('user_settings', if_exists=True)
    op.drop_index(op.f('ix_family_settings_family_key'), table_name='family_settings', if_exists=True)
    op.drop_index(op.f('ix_family_settings_family_id'), table_name='family_settings', if_exists=True)
    op.drop_table('family_settings', if_exists=True)
