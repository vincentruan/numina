"""Tests for P7a model field additions."""
from sqlalchemy import inspect

from packages.db.models.learning.practice import PracticeAttempt, PracticeSession
from packages.db.models.learning.question import Question


class TestQuestionModelP7aFields:
    """Question model has P7a new columns."""

    def test_content_hash_column_exists(self):
        columns = {c.name for c in inspect(Question).columns}
        assert "content_hash" in columns

    def test_content_hash_is_nullable(self):
        col = inspect(Question).columns["content_hash"]
        assert col.nullable is True  # existing rows won't have it immediately

    def test_source_metadata_columns_exist(self):
        columns = {c.name for c in inspect(Question).columns}
        assert "source_name" in columns
        assert "source_license" in columns
        assert "imported_at" in columns

    def test_grading_explanation_column_exists(self):
        columns = {c.name for c in inspect(Question).columns}
        assert "grading_explanation_json" in columns

    def test_quality_monitoring_columns_exist(self):
        columns = {c.name for c in inspect(Question).columns}
        assert "suspicious" in columns
        assert "needs_review" in columns
        assert "empirical_difficulty" in columns

    def test_risk_and_family_id_columns_exist(self):
        columns = {c.name for c in inspect(Question).columns}
        assert "risk" in columns
        assert "family_id" in columns


class TestPracticeModelP7aFields:
    """Practice models have P7a new columns."""

    def test_attempt_is_retry_column_exists(self):
        columns = {c.name for c in inspect(PracticeAttempt).columns}
        assert "is_retry" in columns

    def test_session_validity_flag_column_exists(self):
        columns = {c.name for c in inspect(PracticeSession).columns}
        assert "validity_flag" in columns
