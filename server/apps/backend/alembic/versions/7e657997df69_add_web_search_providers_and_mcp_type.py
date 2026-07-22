"""add_web_search_providers_and_mcp_type

Revision ID: 7e657997df69
Revises: c8a2f1d3e5b7
Create Date: 2026-06-01 21:16:38.990639

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '7e657997df69'
down_revision: str | None = 'c8a2f1d3e5b7'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()

    def _has_column(table: str, col: str) -> bool:
        if not bind.dialect.has_table(bind, table):
            return False
        return any(c['name'] == col for c in bind.dialect.get_columns(bind, table))

    # Create family_web_search_providers table (guard: skip if exists)
    if not bind.dialect.has_table(bind, 'family_web_search_providers'):
        op.create_table('family_web_search_providers',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('family_id', sa.BigInteger(), nullable=False),
        sa.Column('provider_name', sa.String(length=50), nullable=False),
        sa.Column('display_name', sa.String(length=100), nullable=True),
        sa.Column('api_key_encrypted', sa.Text(), nullable=True),
        sa.Column('is_enabled', sa.Boolean(), nullable=False),
        sa.Column('display_order', sa.Integer(), nullable=False),
        sa.Column('max_results', sa.Integer(), nullable=False),
        sa.Column('circuit_state', sa.String(length=20), nullable=False),
        sa.Column('circuit_reason', sa.String(length=30), nullable=True),
        sa.Column('recovery_schedule', sa.String(length=100), nullable=True),
        sa.Column('last_failure_type', sa.String(length=30), nullable=True),
        sa.Column('half_open_success_count', sa.Integer(), nullable=False),
        sa.Column('half_open_failure_count', sa.Integer(), nullable=False),
        sa.Column('half_open_window_start', sa.DateTime(), nullable=True),
        sa.Column('failure_count', sa.Integer(), nullable=False),
        sa.Column('last_failure_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_family_web_search_providers_family_id'), 'family_web_search_providers', ['family_id'], unique=False)

    # Add mcp_type column. The MCP servers table was created as family_mcp_servers
    # (i0279k52jgf9) and renamed to ai_mcp_servers (x2581y64zqr9, which runs
    # before this migration). Target whichever name exists; skip if mcp_type
    # already present (fresh-DB current model).
    for tbl in ('ai_mcp_servers', 'family_mcp_servers'):
        if bind.dialect.has_table(bind, tbl) and not _has_column(tbl, 'mcp_type'):
            op.add_column(tbl, sa.Column('mcp_type', sa.String(length=20), nullable=False, server_default='general'))
            break


def downgrade() -> None:
    # Remove mcp_type column from family_mcp_servers
    op.drop_column('family_mcp_servers', 'mcp_type')

    # Drop family_web_search_providers table
    op.drop_index(op.f('ix_family_web_search_providers_family_id'), table_name='family_web_search_providers')
    op.drop_table('family_web_search_providers')