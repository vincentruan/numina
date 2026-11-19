"""add misconception_id to practice_attempts

Revision ID: mc001misc0003
Revises: mc001misc0002
Create Date: 2026-11-16

Adds a nullable FK column to practice_attempts pointing at the matched
misconception (null when the answer is correct or no pattern matches).
Drives cross-session adaptive question boosting in U3 of the
misconception catalog plan (#214).

Composite index (child_id, topic_id, misconception_id) supports the
"recent misconceptions for this child+topic" query at session creation.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from apps.backend.alembic import ddl

revision: str = "mc001misc0003"
down_revision: tuple[str, ...] = ("mc001misc0002",)  # type: ignore[assignment]
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"

    if bind.dialect.has_table(bind, "practice_attempts"):
        ddl.add_column(
            "practice_attempts",
            sa.Column("misconception_id", sa.BigInteger(), nullable=True),
        )
        if not is_sqlite:
            # SQLite cannot ALTER constraints after table creation.
            # PRAGMA foreign_keys=OFF by default; tests use in-memory
            # create_all which builds the FK via declarative.
            existing_fks = {
                fk["name"]
                for fk in sa.inspect(bind).get_foreign_keys("practice_attempts")
            }
            if "fk_practice_attempt_misconception_id" not in existing_fks:
                op.create_foreign_key(
                    "fk_practice_attempt_misconception_id",
                    "practice_attempts",
                    "misconceptions",
                    ["misconception_id"],
                    ["id"],
                    ondelete="SET NULL",
                )
        ddl.create_index(
            "ix_practice_attempt_child_topic_misconception",
            "practice_attempts",
            ["child_id", "topic_id", "misconception_id"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"

    if bind.dialect.has_table(bind, "practice_attempts"):
        op.drop_index(
            "ix_practice_attempt_child_topic_misconception",
            table_name="practice_attempts",
        )
        if not is_sqlite:
            op.drop_constraint(
                "fk_practice_attempt_misconception_id",
                "practice_attempts",
                type_="foreignkey",
            )
        op.drop_column("practice_attempts", "misconception_id")
