"""add questions and practice tables

Revision ID: 9350dbcfcb04
Revises: mcp002phase2
Create Date: 2026-10-12 11:15:03.818153

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9350dbcfcb04'
down_revision: Union[str, None] = 'mcp002phase2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    # --- questions ---
    if not bind.dialect.has_table(bind, "questions"):
        op.create_table(
            "questions",
            sa.Column("id", sa.BigInteger(), primary_key=True),
            sa.Column("topic_id", sa.BigInteger(), sa.ForeignKey("learning_topics.id"), nullable=False),
            sa.Column("question_type", sa.String(20), nullable=False),
            sa.Column("stem", sa.Text(), nullable=False),
            sa.Column("stem_zh", sa.Text(), nullable=True),
            sa.Column("options_json", sa.Text(), nullable=True),
            sa.Column("answer_json", sa.Text(), nullable=False),
            sa.Column("solution_json", sa.Text(), nullable=True),
            sa.Column("difficulty", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("bloom_level", sa.String(20), nullable=False, server_default="apply"),
            sa.Column("source", sa.String(20), nullable=False),
            sa.Column("source_version", sa.String(50), nullable=True),
            sa.Column("review_status", sa.String(20), nullable=False, server_default="pending"),
            sa.Column("review_notes", sa.Text(), nullable=True),
            sa.Column("age_group", sa.String(10), nullable=False),
            sa.Column("parameters_json", sa.Text(), nullable=True),
            sa.Column("times_used", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("correct_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index("ix_questions_topic_id", "questions", ["topic_id"])
        op.create_index("ix_questions_question_type", "questions", ["question_type"])
        op.create_index("ix_questions_difficulty", "questions", ["difficulty"])
        op.create_index("ix_questions_review_status", "questions", ["review_status"])
        op.create_index("ix_questions_age_group", "questions", ["age_group"])
        op.create_index("ix_questions_source", "questions", ["source"])

    # --- question_knowledge_points ---
    if not bind.dialect.has_table(bind, "question_knowledge_points"):
        op.create_table(
            "question_knowledge_points",
            sa.Column("id", sa.BigInteger(), primary_key=True),
            sa.Column("question_id", sa.BigInteger(), sa.ForeignKey("questions.id"), nullable=False),
            sa.Column("topic_id", sa.BigInteger(), sa.ForeignKey("learning_topics.id"), nullable=False),
            sa.Column("role", sa.String(20), nullable=False, server_default="primary"),
            sa.UniqueConstraint("question_id", "topic_id", name="uq_question_topic"),
        )
        op.create_index("ix_qkp_question_id", "question_knowledge_points", ["question_id"])
        op.create_index("ix_qkp_topic_id", "question_knowledge_points", ["topic_id"])

    # --- practice_sessions ---
    if not bind.dialect.has_table(bind, "practice_sessions"):
        op.create_table(
            "practice_sessions",
            sa.Column("id", sa.BigInteger(), primary_key=True),
            sa.Column("child_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("topic_id", sa.BigInteger(), sa.ForeignKey("learning_topics.id"), nullable=False),
            sa.Column("session_mode", sa.String(20), nullable=False),
            sa.Column("question_ids_json", sa.Text(), nullable=False),
            sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("total_score", sa.Float(), nullable=True),
            sa.Column("completed_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("source", sa.String(20), nullable=False, server_default="adaptive"),
            sa.Column("learning_progress_id", sa.BigInteger(), sa.ForeignKey("learning_progress.id"), nullable=True),
        )
        op.create_index("ix_practice_sessions_child_id", "practice_sessions", ["child_id"])
        op.create_index("ix_practice_sessions_topic_id", "practice_sessions", ["topic_id"])
        op.create_index("ix_practice_sessions_session_mode", "practice_sessions", ["session_mode"])

    # --- practice_attempts ---
    if not bind.dialect.has_table(bind, "practice_attempts"):
        op.create_table(
            "practice_attempts",
            sa.Column("id", sa.BigInteger(), primary_key=True),
            sa.Column("session_id", sa.BigInteger(), sa.ForeignKey("practice_sessions.id"), nullable=False),
            sa.Column("question_id", sa.BigInteger(), sa.ForeignKey("questions.id"), nullable=False),
            sa.Column("child_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("topic_id", sa.BigInteger(), sa.ForeignKey("learning_topics.id"), nullable=False),
            sa.Column("user_answer_json", sa.Text(), nullable=False),
            sa.Column("is_correct", sa.Boolean(), nullable=False),
            sa.Column("time_spent_seconds", sa.Integer(), nullable=True),
            sa.Column("attempt_number", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index("ix_practice_attempts_session_id", "practice_attempts", ["session_id"])
        op.create_index("ix_practice_attempts_question_id", "practice_attempts", ["question_id"])
        op.create_index("ix_practice_attempts_child_id", "practice_attempts", ["child_id"])
        op.create_index(
            "ix_practice_attempt_child_topic_created",
            "practice_attempts",
            ["child_id", "topic_id", "created_at"],
        )
        op.create_unique_constraint(
            "uq_attempt_session_question",
            "practice_attempts",
            ["session_id", "question_id"],
        )


def downgrade() -> None:
    op.drop_table("practice_attempts")
    op.drop_table("practice_sessions")
    op.drop_table("question_knowledge_points")
    op.drop_table("questions")
