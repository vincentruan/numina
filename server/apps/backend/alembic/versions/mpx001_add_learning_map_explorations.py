"""add learning_map_explorations table

Revision ID: mpx001
Revises: (merge of h0011q22r3s4, rwc001)
Create Date: 2026-11-12

Records knowledge-map telemetry per visit: time-on-map before the first topic
selection (R11), zoom depth reached, and whether a topic was selected (R12).
A visit that ends with no selection is still recorded (AE4).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "mpx001"
down_revision: tuple[str, ...] = ("h0011q22r3s4", "rwc001")  # type: ignore[assignment]
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "learning_map_explorations",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("child_id", sa.BigInteger, nullable=False, index=True),
        sa.Column("family_id", sa.BigInteger, nullable=False, index=True),
        sa.Column("duration_ms", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("max_zoom_level", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column(
            "topic_selected", sa.Boolean, nullable=False, server_default=sa.false()
        ),
        sa.Column(
            "interaction_count", sa.Integer, nullable=False, server_default=sa.text("0")
        ),
        sa.Column("selected_topic_id", sa.BigInteger, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_learning_map_explorations_created_at",
        "learning_map_explorations",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_learning_map_explorations_created_at",
        table_name="learning_map_explorations",
    )
    op.drop_table("learning_map_explorations")
