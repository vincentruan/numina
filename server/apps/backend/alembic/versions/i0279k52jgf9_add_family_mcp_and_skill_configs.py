"""add family_mcp_servers and family_skill_configs tables

Revision ID: i0279k52jgf9
Revises: h9168j41ife8
Create Date: 2026-05-04 12:00:00.000000

Adds:
- family_mcp_servers: per-family MCP server configuration (encrypted env vars)
- family_skill_configs: per-family skill enable/disable and custom prompt overrides
"""

import sqlalchemy as sa
from alembic import op

revision = 'i0279k52jgf9'
down_revision = 'h9168j41ife8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'family_mcp_servers',
        sa.Column('id', sa.BigInteger(), primary_key=True, nullable=False),
        sa.Column('family_id', sa.BigInteger(), sa.ForeignKey('families.id'), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('url', sa.Text(), nullable=False),
        sa.Column('transport', sa.String(20), nullable=False, server_default='sse'),
        sa.Column('env_vars_encrypted', sa.Text(), nullable=True),
        sa.Column('is_enabled', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_family_mcp_servers_family_id', 'family_mcp_servers', ['family_id'])

    op.create_table(
        'family_skill_configs',
        sa.Column('id', sa.BigInteger(), primary_key=True, nullable=False),
        sa.Column('family_id', sa.BigInteger(), sa.ForeignKey('families.id'), nullable=False),
        sa.Column('capability', sa.String(50), nullable=False),
        sa.Column('is_enabled', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('custom_prompt', sa.Text(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('family_id', 'capability', name='uq_family_skill'),
    )
    op.create_index('ix_family_skill_configs_family_id', 'family_skill_configs', ['family_id'])
    # Note: uq_family_skill constraint is declared inline above. SQLite does not
    # support ALTER TABLE ADD CONSTRAINT, so a standalone op.create_unique_constraint
    # would raise NotImplementedError on fresh DBs.


def downgrade() -> None:
    op.drop_index('ix_family_skill_configs_family_id', table_name='family_skill_configs')
    op.drop_table('family_skill_configs')

    op.drop_index('ix_family_mcp_servers_family_id', table_name='family_mcp_servers')
    op.drop_table('family_mcp_servers')
