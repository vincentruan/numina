"""add_notification_enhancements

Revision ID: 75e411962098
Revises: a7b8c9d0e1f2
Create Date: 2026-09-14 22:38:18.261048

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from packages.db.session import UTCDateTime


# revision identifiers, used by Alembic.
revision: str = '75e411962098'
down_revision: Union[str, None] = 'a7b8c9d0e1f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'notification_channels',
        sa.Column('digest_mode', sa.String(length=20), server_default='immediate', nullable=False),
    )
    op.add_column(
        'notification_channels',
        sa.Column('digest_time', sa.String(length=10), server_default='21:00', nullable=False),
    )
    op.add_column(
        'reminders',
        sa.Column('digest_sent_at', UTCDateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('reminders', 'digest_sent_at')
    op.drop_column('notification_channels', 'digest_time')
    op.drop_column('notification_channels', 'digest_mode')
