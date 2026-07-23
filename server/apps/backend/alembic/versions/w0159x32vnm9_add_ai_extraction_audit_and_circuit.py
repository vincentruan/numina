"""add ai_extraction_audit and ai_extraction_circuit tables

Revision ID: w0159x32vnm9
Revises: r9047s21tlm7
Create Date: 2026-05-19

Adds:
- ai_extraction_audits table for tracking each structured extraction attempt
- ai_extraction_circuits table for per-(family, capability) circuit breaker state
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'w0159x32vnm9'
down_revision: str | None = 'r9047s21tlm7'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ai_extraction_audits table
    op.create_table(
        'ai_extraction_audits',
        sa.Column('id', sa.BigInteger(), primary_key=True, nullable=False),
        sa.Column('family_id', sa.BigInteger(), nullable=False),
        sa.Column('capability', sa.String(32), nullable=False),
        sa.Column('task_id', sa.String(64), nullable=True),
        sa.Column('method', sa.String(32), nullable=False),
        sa.Column('extracted_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('error_msg', sa.Text(), nullable=True),
        sa.Column('answer_excerpt', sa.Text(), nullable=True),
    )
    op.create_index('ix_ai_extraction_audits_family_id', 'ai_extraction_audits', ['family_id'])
    op.create_index('ix_ai_extraction_audits_capability', 'ai_extraction_audits', ['capability'])
    op.create_index(
        'ix_ai_extraction_audits_family_capability_time',
        'ai_extraction_audits',
        ['family_id', 'capability', 'extracted_at'],
    )

    # ai_extraction_circuits table
    op.create_table(
        'ai_extraction_circuits',
        sa.Column('id', sa.BigInteger(), primary_key=True, nullable=False),
        sa.Column('family_id', sa.BigInteger(), nullable=False),
        sa.Column('capability', sa.String(32), nullable=False),
        sa.Column('state', sa.String(20), nullable=False, server_default='ok'),
        sa.Column('opened_at', sa.DateTime(), nullable=True),
        sa.Column('opened_until', sa.DateTime(), nullable=True),
        sa.Column('manually_reset_at', sa.DateTime(), nullable=True),
        sa.Column('reset_by_user_id', sa.BigInteger(), nullable=True),
        sa.Column('last_evaluated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('family_id', 'capability', name='uq_extraction_circuit_family_capability'),
    )
    # Note: uq_extraction_circuit_family_constraint declared inline above.
    # SQLite does not support ALTER TABLE ADD CONSTRAINT, so a standalone
    # op.create_unique_constraint would raise NotImplementedError on fresh DBs.


def downgrade() -> None:
    op.drop_table('ai_extraction_circuits')
    op.drop_index('ix_ai_extraction_audits_family_capability_time', table_name='ai_extraction_audits')
    op.drop_index('ix_ai_extraction_audits_capability', table_name='ai_extraction_audits')
    op.drop_index('ix_ai_extraction_audits_family_id', table_name='ai_extraction_audits')
    op.drop_table('ai_extraction_audits')
