"""add misconception category column and ondelete fix

Revision ID: mc001misc0002
Revises: mc001misc0001
Create Date: 2026-11-16

1. Adds a nullable `category` column to `misconceptions` (Issue #214):
   concept_confusion | procedural_error | carelessness. Existing rows are
   backfilled with 'concept_confusion' — the pilot's fraction
   misconceptions ("add numerators and denominators", "wrong common
   denominator") are conceptual confusions.
2. Makes `misconception_detections.misconception_id` nullable with
   ON DELETE SET NULL. Previously NOT NULL with no ondelete clause —
   topic deletion cascades to misconceptions, which would raise an
   IntegrityError on the orphaned detection rows.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "mc001misc0002"
down_revision: tuple[str, ...] = ("mc001misc0001",)  # type: ignore[assignment]
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"

    if bind.dialect.has_table(bind, "misconceptions"):
        op.add_column(
            "misconceptions",
            sa.Column("category", sa.String(30), nullable=True),
        )
        # Backfill: pilot misconceptions are all conceptual confusions.
        op.execute(
            "UPDATE misconceptions SET category = 'concept_confusion' "
            "WHERE category IS NULL"
        )

    if bind.dialect.has_table(bind, "misconception_detections"):
        if is_sqlite:
            # SQLite cannot ALTER constraints; batch mode rebuilds the table
            # (copy-and-move) applying the nullable flip. SQLite does not
            # enforce ondelete in the same way, so the nullable flip is the
            # operative change here.
            with op.batch_alter_table("misconception_detections") as batch_op:
                batch_op.alter_column(
                    "misconception_id",
                    existing_type=sa.BigInteger(),
                    nullable=True,
                )
        else:
            # Postgres: flip nullable, then rebuild the named FK with
            # ondelete=SET NULL.
            op.execute(
                "ALTER TABLE misconception_detections "
                "ALTER COLUMN misconception_id DROP NOT NULL"
            )
            op.execute(
                "ALTER TABLE misconception_detections "
                "DROP CONSTRAINT IF EXISTS "
                "fk_misconception_detections_misconception_id_misconceptions"
            )
            op.execute(
                "ALTER TABLE misconception_detections "
                "ADD CONSTRAINT "
                "fk_misconception_detections_misconception_id_misconceptions "
                "FOREIGN KEY (misconception_id) REFERENCES misconceptions(id) "
                "ON DELETE SET NULL"
            )


def downgrade() -> None:
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"

    if bind.dialect.has_table(bind, "misconception_detections"):
        if is_sqlite:
            with op.batch_alter_table("misconception_detections") as batch_op:
                batch_op.alter_column(
                    "misconception_id",
                    existing_type=sa.BigInteger(),
                    nullable=False,
                )
        else:
            op.execute(
                "ALTER TABLE misconception_detections "
                "DROP CONSTRAINT IF EXISTS "
                "fk_misconception_detections_misconception_id_misconceptions"
            )
            op.execute(
                "ALTER TABLE misconception_detections "
                "ADD CONSTRAINT "
                "fk_misconception_detections_misconception_id_misconceptions "
                "FOREIGN KEY (misconception_id) REFERENCES misconceptions(id)"
            )
            op.execute(
                "ALTER TABLE misconception_detections "
                "ALTER COLUMN misconception_id SET NOT NULL"
            )

    if bind.dialect.has_table(bind, "misconceptions"):
        op.drop_column("misconceptions", "category")
