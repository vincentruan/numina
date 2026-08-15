"""add task tracking fields to ai_tasks

Revision ID: x9876y54zqr0
Revises: z4783a86brs1
Create Date: 2026-08-15 12:00:00.000000

Adds fields for StreamBridge task tracking, worker identification, and
lease-based dead-worker detection. Required for AI task resilience (U3).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "x9876y54zqr0"
down_revision: Union[str, None] = "z4783a86brs1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add run_id, worker_id, lease_expires_at, progress columns and composite index."""
    # Use batch_alter_table for SQLite compatibility
    # Check if columns already exist for idempotent migration (fresh DB support)
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_columns = {col["name"] for col in inspector.get_columns("ai_tasks")}

    with op.batch_alter_table("ai_tasks", schema=None) as batch_op:
        # Add run_id column if not exists
        if "run_id" not in existing_columns:
            batch_op.add_column(
                sa.Column(
                    "run_id",
                    sa.String(64),
                    nullable=True,
                    comment="Agent RunRecord ID for bridge reconnection",
                )
            )

        # Add worker_id column if not exists
        if "worker_id" not in existing_columns:
            batch_op.add_column(
                sa.Column(
                    "worker_id",
                    sa.String(128),
                    nullable=True,
                    comment="hostname:uuid of processing worker",
                )
            )

        # Add lease_expires_at column if not exists
        if "lease_expires_at" not in existing_columns:
            batch_op.add_column(
                sa.Column(
                    "lease_expires_at",
                    sa.DateTime(),
                    nullable=True,
                    comment="Heartbeat deadline for dead-worker detection (naive UTC)",
                )
            )

        # Add progress column if not exists
        if "progress" not in existing_columns:
            batch_op.add_column(
                sa.Column(
                    "progress",
                    sa.JSON(),
                    nullable=True,
                    comment="Optional JSON blob (step, percentage, message)",
                )
            )

        # Add index on run_id for bridge reconnection lookup (if not exists)
        existing_indexes = {idx["name"] for idx in inspector.get_indexes("ai_tasks")}
        if "ix_ai_tasks_run_id" not in existing_indexes:
            batch_op.create_index(
                "ix_ai_tasks_run_id",
                ["run_id"],
                unique=False,
            )

        # Add composite index for efficient task queries by family + skill + status
        if "ix_ai_tasks_family_skill_status" not in existing_indexes:
            batch_op.create_index(
                "ix_ai_tasks_family_skill_status",
                ["family_id", "skill_id", "status"],
                unique=False,
            )


def downgrade() -> None:
    """Remove task tracking fields and indexes."""
    with op.batch_alter_table("ai_tasks", schema=None) as batch_op:
        batch_op.drop_index("ix_ai_tasks_family_skill_status")
        batch_op.drop_index("ix_ai_tasks_run_id")
        batch_op.drop_column("progress")
        batch_op.drop_column("lease_expires_at")
        batch_op.drop_column("worker_id")
        batch_op.drop_column("run_id")
