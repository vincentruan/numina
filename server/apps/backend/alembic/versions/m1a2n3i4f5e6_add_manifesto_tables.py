"""add manifesto tables

Revision ID: m1a2n3i4f5e6
Revises: 780b6dcce28c
Create Date: 2026-07-31

Adds:
- family_manifesto
- manifesto_version
- manifesto_signature
- manifesto_feedback
"""

import sqlalchemy as sa
from alembic import op

revision = 'm1a2n3i4f5e6'
down_revision = '780b6dcce28c'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'family_manifesto',
        sa.Column('id', sa.BigInteger, primary_key=True),
        sa.Column('family_id', sa.BigInteger, nullable=False, index=True),
        sa.Column('current_version_id', sa.BigInteger, nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='active'),
        sa.Column('signing_deadline', sa.DateTime, nullable=True),
        sa.Column('created_by', sa.BigInteger, nullable=False),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_table(
        'manifesto_version',
        sa.Column('id', sa.BigInteger, primary_key=True),
        sa.Column('manifesto_id', sa.BigInteger, nullable=False, index=True),
        sa.Column('version_number', sa.Integer, nullable=False),
        sa.Column('template_id', sa.String(50), nullable=False),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('body', sa.Text, nullable=False),
        sa.Column('change_type', sa.String(20), nullable=False, server_default='initial'),
        sa.Column('trackable_clause_indices', sa.JSON, nullable=True),
        sa.Column('signed_at', sa.DateTime, nullable=True),
        sa.Column('created_by', sa.BigInteger, nullable=False),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )
    op.create_table(
        'manifesto_signature',
        sa.Column('id', sa.BigInteger, primary_key=True),
        sa.Column('version_id', sa.BigInteger, nullable=False, index=True),
        sa.Column('user_id', sa.BigInteger, nullable=False),
        sa.Column('signature_data', sa.Text, nullable=True),
        sa.Column('signed_at', sa.DateTime, server_default=sa.func.now()),
        sa.UniqueConstraint('version_id', 'user_id', name='uq_manifesto_signature_version_user'),
    )
    op.create_table(
        'manifesto_feedback',
        sa.Column('id', sa.BigInteger, primary_key=True),
        sa.Column('manifesto_id', sa.BigInteger, nullable=False, index=True),
        sa.Column('user_id', sa.BigInteger, nullable=False),
        sa.Column('family_id', sa.BigInteger, nullable=False, index=True),
        sa.Column('content', sa.Text, nullable=False),
        sa.Column('is_read', sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('manifesto_feedback')
    op.drop_table('manifesto_signature')
    op.drop_table('manifesto_version')
    op.drop_table('family_manifesto')
