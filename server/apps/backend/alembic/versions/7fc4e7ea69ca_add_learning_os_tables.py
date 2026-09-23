"""add_learning_os_tables

Revision ID: 7fc4e7ea69ca
Revises: c7d2e1f8a3b5
Create Date: 2026-09-23 00:35:48.285353

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from packages.db.session import UTCDateTime

# revision identifiers, used by Alembic.
revision: str = "7fc4e7ea69ca"
down_revision: Union[str, None] = "c7d2e1f8a3b5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(bind, table_name: str) -> bool:
    return bind.dialect.has_table(bind, table_name)


def upgrade() -> None:
    bind = op.get_bind()

    # --- learning_clusters ---
    if not _table_exists(bind, "learning_clusters"):
        op.create_table(
            "learning_clusters",
            sa.Column("id", sa.BigInteger(), nullable=False),
            sa.Column("subject", sa.String(length=50), nullable=False),
            sa.Column("domain", sa.String(length=100), nullable=False),
            sa.Column("age_range_start", sa.Integer(), nullable=True),
            sa.Column("age_group", sa.String(length=10), nullable=False),
            sa.Column("summary", sa.Text(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            op.f("ix_learning_clusters_subject"),
            "learning_clusters",
            ["subject"],
            unique=False,
        )

    # --- learning_topics ---
    if not _table_exists(bind, "learning_topics"):
        op.create_table(
            "learning_topics",
            sa.Column("id", sa.BigInteger(), nullable=False),
            sa.Column("topic_key", sa.String(length=50), nullable=False),
            sa.Column("topic_type", sa.String(length=20), nullable=False),
            sa.Column("subject", sa.String(length=50), nullable=False),
            sa.Column("domain", sa.String(length=100), nullable=True),
            sa.Column("name", sa.String(length=200), nullable=True),
            sa.Column("name_zh", sa.String(length=200), nullable=True),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column("description_zh", sa.Text(), nullable=True),
            sa.Column("age_range_start", sa.Integer(), nullable=True),
            sa.Column("age_range_end", sa.Integer(), nullable=True),
            sa.Column("centrality", sa.Float(), nullable=True),
            sa.Column("evidence_json", sa.Text(), nullable=False),
            sa.Column("evidence_zh_json", sa.Text(), nullable=True),
            sa.Column("assessment_prompt", sa.Text(), nullable=True),
            sa.Column("assessment_prompt_zh", sa.Text(), nullable=True),
            sa.Column("standards_json", sa.Text(), nullable=False),
            sa.Column("ability_dimensions_json", sa.Text(), nullable=True),
            sa.Column("age_group", sa.String(length=10), nullable=False),
            sa.Column("deprecated", sa.Boolean(), nullable=False),
            sa.Column(
                "created_at",
                UTCDateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                UTCDateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            op.f("ix_learning_topics_subject"),
            "learning_topics",
            ["subject"],
            unique=False,
        )
        op.create_index(
            op.f("ix_learning_topics_topic_key"),
            "learning_topics",
            ["topic_key"],
            unique=True,
        )

    # --- learning_dependencies ---
    if not _table_exists(bind, "learning_dependencies"):
        op.create_table(
            "learning_dependencies",
            sa.Column("id", sa.BigInteger(), nullable=False),
            sa.Column("topic_id", sa.BigInteger(), nullable=False),
            sa.Column("prerequisite_id", sa.BigInteger(), nullable=False),
            sa.Column("strength", sa.String(length=10), nullable=False),
            sa.Column("reason", sa.Text(), nullable=True),
            sa.ForeignKeyConstraint(
                ["prerequisite_id"], ["learning_topics.id"], name="fk_learning_dependencies_prerequisite_id"
            ),
            sa.ForeignKeyConstraint(
                ["topic_id"], ["learning_topics.id"], name="fk_learning_dependencies_topic_id"
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            op.f("ix_learning_dependencies_prerequisite_id"),
            "learning_dependencies",
            ["prerequisite_id"],
            unique=False,
        )
        op.create_index(
            op.f("ix_learning_dependencies_topic_id"),
            "learning_dependencies",
            ["topic_id"],
            unique=False,
        )

    # --- learning_assignments ---
    if not _table_exists(bind, "learning_assignments"):
        op.create_table(
            "learning_assignments",
            sa.Column("id", sa.BigInteger(), nullable=False),
            sa.Column("family_id", sa.BigInteger(), nullable=False),
            sa.Column("child_id", sa.BigInteger(), nullable=False),
            sa.Column("topic_id", sa.BigInteger(), nullable=False),
            sa.Column("path_id", sa.BigInteger(), nullable=True),
            sa.Column("created_by", sa.BigInteger(), nullable=False),
            sa.Column("assignment_type", sa.String(length=20), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("priority", sa.Integer(), nullable=False),
            sa.Column("due_date", sa.Date(), nullable=True),
            sa.Column(
                "created_at",
                UTCDateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.Column("completed_at", UTCDateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(
                ["child_id"], ["users.id"], name="fk_learning_assignments_child_id"
            ),
            sa.ForeignKeyConstraint(
                ["created_by"], ["users.id"], name="fk_learning_assignments_created_by"
            ),
            sa.ForeignKeyConstraint(
                ["family_id"], ["families.id"], name="fk_learning_assignments_family_id"
            ),
            sa.ForeignKeyConstraint(
                ["topic_id"], ["learning_topics.id"], name="fk_learning_assignments_topic_id"
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            op.f("ix_learning_assignments_child_id"),
            "learning_assignments",
            ["child_id"],
            unique=False,
        )
        op.create_index(
            op.f("ix_learning_assignments_family_id"),
            "learning_assignments",
            ["family_id"],
            unique=False,
        )

    # --- learning_progress ---
    if not _table_exists(bind, "learning_progress"):
        op.create_table(
            "learning_progress",
            sa.Column("id", sa.BigInteger(), nullable=False),
            sa.Column("child_id", sa.BigInteger(), nullable=False),
            sa.Column("topic_id", sa.BigInteger(), nullable=False),
            sa.Column("mastery_level", sa.String(length=20), nullable=False),
            sa.Column("mastery_score", sa.Float(), nullable=True),
            sa.Column("completed_via", sa.String(length=20), nullable=True),
            sa.Column("attempts", sa.Integer(), nullable=False),
            sa.Column("xp_earned", sa.Integer(), nullable=False),
            sa.Column("last_practice_at", UTCDateTime(timezone=True), nullable=True),
            sa.Column("first_mastered_at", UTCDateTime(timezone=True), nullable=True),
            sa.Column("stability", sa.Float(), nullable=True),
            sa.Column("next_review_at", UTCDateTime(timezone=True), nullable=True),
            sa.Column("ability_dimensions_score_json", sa.Text(), nullable=True),
            sa.Column(
                "created_at",
                UTCDateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                UTCDateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(
                ["child_id"], ["users.id"], name="fk_learning_progress_child_id"
            ),
            sa.ForeignKeyConstraint(
                ["topic_id"], ["learning_topics.id"], name="fk_learning_progress_topic_id"
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "child_id", "topic_id", name="uq_learning_progress_child_topic"
            ),
        )
        op.create_index(
            op.f("ix_learning_progress_child_id"),
            "learning_progress",
            ["child_id"],
            unique=False,
        )
        op.create_index(
            op.f("ix_learning_progress_mastery_level"),
            "learning_progress",
            ["mastery_level"],
            unique=False,
        )
        op.create_index(
            op.f("ix_learning_progress_topic_id"),
            "learning_progress",
            ["topic_id"],
            unique=False,
        )

    # --- learning_sessions ---
    if not _table_exists(bind, "learning_sessions"):
        op.create_table(
            "learning_sessions",
            sa.Column("id", sa.BigInteger(), nullable=False),
            sa.Column("assignment_id", sa.BigInteger(), nullable=True),
            sa.Column("child_id", sa.BigInteger(), nullable=False),
            sa.Column("topic_id", sa.BigInteger(), nullable=False),
            sa.Column("thread_id", sa.String(length=100), nullable=True),
            sa.Column("session_type", sa.String(length=20), nullable=False),
            sa.Column("ai_evaluation_json", sa.Text(), nullable=True),
            sa.Column("score", sa.Float(), nullable=True),
            sa.Column("duration_seconds", sa.Integer(), nullable=True),
            sa.Column(
                "started_at",
                UTCDateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.Column("ended_at", UTCDateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(
                ["assignment_id"],
                ["learning_assignments.id"],
                name="fk_learning_sessions_assignment_id",
            ),
            sa.ForeignKeyConstraint(
                ["child_id"], ["users.id"], name="fk_learning_sessions_child_id"
            ),
            sa.ForeignKeyConstraint(
                ["topic_id"], ["learning_topics.id"], name="fk_learning_sessions_topic_id"
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            op.f("ix_learning_sessions_child_id"),
            "learning_sessions",
            ["child_id"],
            unique=False,
        )

    # --- learning_assessment_attempts ---
    if not _table_exists(bind, "learning_assessment_attempts"):
        op.create_table(
            "learning_assessment_attempts",
            sa.Column("id", sa.BigInteger(), nullable=False),
            sa.Column("child_id", sa.BigInteger(), nullable=False),
            sa.Column("topic_id", sa.BigInteger(), nullable=False),
            sa.Column("session_id", sa.BigInteger(), nullable=True),
            sa.Column("assessment_type", sa.String(length=20), nullable=False),
            sa.Column("score", sa.Float(), nullable=True),
            sa.Column("passed", sa.Boolean(), nullable=False),
            sa.Column("ai_confidence", sa.Float(), nullable=True),
            sa.Column("evidence_results_json", sa.Text(), nullable=True),
            sa.Column("ability_dimensions_delta_json", sa.Text(), nullable=True),
            sa.Column("duration_seconds", sa.Integer(), nullable=True),
            sa.Column(
                "created_at",
                UTCDateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(
                ["child_id"],
                ["users.id"],
                name="fk_learning_assessment_attempts_child_id",
            ),
            sa.ForeignKeyConstraint(
                ["session_id"],
                ["learning_sessions.id"],
                name="fk_learning_assessment_attempts_session_id",
            ),
            sa.ForeignKeyConstraint(
                ["topic_id"],
                ["learning_topics.id"],
                name="fk_learning_assessment_attempts_topic_id",
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_assessment_attempt_child_topic_created",
            "learning_assessment_attempts",
            ["child_id", "topic_id", "created_at"],
            unique=False,
        )
        op.create_index(
            op.f("ix_learning_assessment_attempts_child_id"),
            "learning_assessment_attempts",
            ["child_id"],
            unique=False,
        )
        op.create_index(
            op.f("ix_learning_assessment_attempts_topic_id"),
            "learning_assessment_attempts",
            ["topic_id"],
            unique=False,
        )


def downgrade() -> None:
    # Drop in reverse creation order, without guards (downgrade is explicit).
    op.drop_index(
        op.f("ix_learning_assessment_attempts_topic_id"),
        table_name="learning_assessment_attempts",
    )
    op.drop_index(
        op.f("ix_learning_assessment_attempts_child_id"),
        table_name="learning_assessment_attempts",
    )
    op.drop_index(
        "ix_assessment_attempt_child_topic_created",
        table_name="learning_assessment_attempts",
    )
    op.drop_table("learning_assessment_attempts")

    op.drop_index(
        op.f("ix_learning_sessions_child_id"), table_name="learning_sessions"
    )
    op.drop_table("learning_sessions")

    op.drop_index(
        op.f("ix_learning_progress_topic_id"), table_name="learning_progress"
    )
    op.drop_index(
        op.f("ix_learning_progress_mastery_level"), table_name="learning_progress"
    )
    op.drop_index(
        op.f("ix_learning_progress_child_id"), table_name="learning_progress"
    )
    op.drop_table("learning_progress")

    op.drop_index(
        op.f("ix_learning_assignments_family_id"), table_name="learning_assignments"
    )
    op.drop_index(
        op.f("ix_learning_assignments_child_id"), table_name="learning_assignments"
    )
    op.drop_table("learning_assignments")

    op.drop_index(
        op.f("ix_learning_dependencies_topic_id"),
        table_name="learning_dependencies",
    )
    op.drop_index(
        op.f("ix_learning_dependencies_prerequisite_id"),
        table_name="learning_dependencies",
    )
    op.drop_table("learning_dependencies")

    op.drop_index(op.f("ix_learning_topics_topic_key"), table_name="learning_topics")
    op.drop_index(op.f("ix_learning_topics_subject"), table_name="learning_topics")
    op.drop_table("learning_topics")

    op.drop_index(
        op.f("ix_learning_clusters_subject"), table_name="learning_clusters"
    )
    op.drop_table("learning_clusters")
