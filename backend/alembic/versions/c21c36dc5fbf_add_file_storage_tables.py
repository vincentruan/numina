"""add_file_storage_tables

Revision ID: c21c36dc5fbf
Revises: a1b2c3d4e5f6
Create Date: 2026-04-10 10:32:25.644504

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c21c36dc5fbf'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'storage_backends',
        sa.Column('id', sa.String(100), primary_key=True),
        sa.Column('backend_type', sa.String(20), nullable=False),
        sa.Column('display_name', sa.String(200), nullable=True),
        sa.Column('config', sa.Text(), nullable=True),
        sa.Column('is_default', sa.Boolean(), nullable=False, server_default=sa.text('0')),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('1')),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    )

    op.create_table(
        'cached_files',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('family_id', sa.String(36), sa.ForeignKey('families.id'), nullable=False),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('sha256', sa.String(64), nullable=False),
        sa.Column('local_path', sa.String(500), nullable=False),
        sa.Column('original_filename', sa.String(255), nullable=False),
        sa.Column('mime_type', sa.String(100), nullable=True),
        sa.Column('size_bytes', sa.Integer(), nullable=False),
        sa.Column('date_dir', sa.String(8), nullable=False),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.UniqueConstraint('sha256', 'family_id', name='uq_cached_files_sha256_family'),
    )
    op.create_index('ix_cached_files_family_id', 'cached_files', ['family_id'])

    op.create_table(
        'file_remote_locations',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('file_id', sa.String(36), sa.ForeignKey('cached_files.id'), nullable=False),
        sa.Column('backend_id', sa.String(100), sa.ForeignKey('storage_backends.id'), nullable=False),
        sa.Column('remote_path', sa.String(500), nullable=True),
        sa.Column('remote_url', sa.String(1000), nullable=True),
        sa.Column('remote_sha', sa.String(100), nullable=True),
        sa.Column('sync_status', sa.String(20), nullable=False, server_default=sa.text("'pending'")),
        sa.Column('synced_at', sa.DateTime(), nullable=True),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.UniqueConstraint('file_id', 'backend_id', name='uq_file_remote_locations_file_backend'),
    )
    op.create_index('ix_file_remote_locations_file_id', 'file_remote_locations', ['file_id'])
    op.create_index('ix_file_remote_locations_backend_status', 'file_remote_locations', ['backend_id', 'sync_status'])

    op.create_table(
        'sync_events',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('file_id', sa.String(36), sa.ForeignKey('cached_files.id'), nullable=False),
        sa.Column('backend_id', sa.String(100), sa.ForeignKey('storage_backends.id'), nullable=True),
        sa.Column('event_type', sa.String(50), nullable=False),
        sa.Column('detail', sa.Text(), nullable=True),
        sa.Column('occurred_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    )
    op.create_index('ix_sync_events_file_id', 'sync_events', ['file_id'])
    op.create_index('ix_sync_events_backend_occurred', 'sync_events', ['backend_id', 'occurred_at'])


def downgrade() -> None:
    op.drop_index('ix_sync_events_backend_occurred', 'sync_events')
    op.drop_index('ix_sync_events_file_id', 'sync_events')
    op.drop_table('sync_events')

    op.drop_index('ix_file_remote_locations_backend_status', 'file_remote_locations')
    op.drop_index('ix_file_remote_locations_file_id', 'file_remote_locations')
    op.drop_table('file_remote_locations')

    op.drop_index('ix_cached_files_family_id', 'cached_files')
    op.drop_table('cached_files')

    op.drop_table('storage_backends')
