"""p7a001_add_content_hash_and_question_fields

Revision ID: p7a001qhash
Revises: mcp003spec
Create Date: 2026-10-14
"""
from alembic import op
import sqlalchemy as sa

revision: str = "p7a001qhash"
down_revision: str | None = "mcp003spec"
branch_labels: tuple[str] | None = None
depends_on: tuple[str] | None = None


def upgrade() -> None:
    # Questions table extensions
    op.add_column("questions", sa.Column("content_hash", sa.String(64), nullable=True))
    op.create_index(op.f("ix_questions_content_hash"), "questions", ["content_hash"])
    op.add_column("questions", sa.Column("source_name", sa.String(50), nullable=True))
    op.add_column("questions", sa.Column("source_license", sa.String(50), nullable=True))
    op.add_column("questions", sa.Column("imported_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("questions", sa.Column("grading_explanation_json", sa.Text(), nullable=True))
    op.add_column("questions", sa.Column("suspicious", sa.Boolean(), server_default="0"))
    op.add_column("questions", sa.Column("needs_review", sa.Boolean(), server_default="0"))
    op.add_column("questions", sa.Column("empirical_difficulty", sa.Float(), nullable=True))
    # P7b: risk classification for review routing
    op.add_column("questions", sa.Column("risk", sa.String(10), nullable=True))
    op.create_index(op.f("ix_questions_risk"), "questions", ["risk"])
    # P7b: family scoping for review-queue isolation
    op.add_column("questions", sa.Column("family_id", sa.BigInteger(), nullable=True))
    op.create_index(op.f("ix_questions_family_id"), "questions", ["family_id"])

    # Practice tables
    op.add_column("practice_attempts", sa.Column("is_retry", sa.Boolean(), server_default="0"))
    op.add_column("practice_attempts", sa.Column("ai_confidence", sa.Float(), nullable=True))
    op.add_column("practice_attempts", sa.Column("ai_low_confidence", sa.Boolean(), server_default="0"))
    op.add_column("practice_sessions", sa.Column("validity_flag", sa.String(20), nullable=True))


def downgrade() -> None:
    # Questions: risk/family_id first (drop their indexes then columns)
    op.drop_index(op.f("ix_questions_risk"), table_name="questions")
    op.drop_column("questions", "risk")
    op.drop_index(op.f("ix_questions_family_id"), table_name="questions")
    op.drop_column("questions", "family_id")
    # Practice tables
    op.drop_column("practice_sessions", "validity_flag")
    op.drop_column("practice_attempts", "ai_low_confidence")
    op.drop_column("practice_attempts", "ai_confidence")
    op.drop_column("practice_attempts", "is_retry")
    # Questions: original P7a columns
    op.drop_column("questions", "empirical_difficulty")
    op.drop_column("questions", "needs_review")
    op.drop_column("questions", "suspicious")
    op.drop_column("questions", "grading_explanation_json")
    op.drop_column("questions", "imported_at")
    op.drop_column("questions", "source_license")
    op.drop_column("questions", "source_name")
    op.drop_index(op.f("ix_questions_content_hash"), table_name="questions")
    op.drop_column("questions", "content_hash")
