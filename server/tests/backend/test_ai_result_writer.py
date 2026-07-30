"""Tests for AI result writer service.

U7: 5 外扩 trigger skill writers (alerts/disposal/spending_leak/allocation/liability)
removed; only ``write_report_results`` remains. ``_validate_asset_ownership`` helper
was deleted with the trigger writers (it had no other callers).
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from apps.backend.app.database import Base
from apps.backend.app.models.ai_report import AIReport
from apps.backend.app.services.ai_result_writer import (
    write_report_results,
    write_skill_results,
)


class TestWriteReportResults:
    """Tests for write_report_results function."""

    def test_writes_valid_report(self, db_session, test_family):
        """Writes valid report."""
        results = {"overall_score": 85, "data_completeness_score": 90}
        count = write_report_results(test_family.id, results, db_session)
        assert count == 1

    def test_handles_empty_results(self, db_session, test_family):
        """Handles empty dict."""
        count = write_report_results(test_family.id, {}, db_session)
        assert count == 0


class TestWriteCapabilityResults:
    """Tests for write_skill_results dispatcher."""

    def test_dispatches_to_correct_writer(self, db_session, test_family):
        """Dispatches to correct writer based on capability."""
        count = write_skill_results("report", test_family.id, {"overall_score": 80}, db_session)
        assert count == 1

    def test_returns_zero_for_unknown_capability(self, db_session, test_family):
        """Returns 0 for unknown capability."""
        count = write_skill_results("unknown", test_family.id, {}, db_session)
        assert count == 0


# ---------------------------------------------------------------------------
# Markdown-path persistence + replace strategy (ported from the former
# apps/backend/tests/unit/test_ai_result_writer.py — U4 step 7). These use an
# in-memory SQLite engine so they don't depend on the conftest db_session
# fixture; the writer's family_id filter + replace logic is what's under test,
# not the FK.
# ---------------------------------------------------------------------------


def _mem_db() -> Session:
    """In-memory SQLite — FKs off by default, so AIReport rows can be inserted
    without a matching families row."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def test_write_report_persists_json_and_markdown_path():
    db = _mem_db()
    results = {"overall_score": 72, "data_completeness_score": 80, "indicators": []}

    count = write_report_results(
        100, results, db, markdown_file_path="report_20260718_100530.md"
    )

    assert count == 1
    row = db.query(AIReport).filter(AIReport.family_id == 100).one()
    assert row.report_json == results
    assert row.overall_score == 72
    assert row.data_completeness_score == 80
    assert row.status == "completed"
    assert row.markdown_file_path == "report_20260718_100530.md"


def test_write_report_markdown_path_defaults_none():
    """markdown_file_path is optional — defaults to None when not passed."""
    db = _mem_db()
    write_report_results(100, {"overall_score": 50}, db)

    row = db.query(AIReport).filter(AIReport.family_id == 100).one()
    assert row.markdown_file_path is None


def test_write_report_replaces_previous_for_family():
    """Replace strategy: a second write clears the first row for the family."""
    db = _mem_db()
    write_report_results(100, {"overall_score": 60}, db, markdown_file_path="old.md")
    write_report_results(100, {"overall_score": 90}, db, markdown_file_path="new.md")

    rows = db.query(AIReport).filter(AIReport.family_id == 100).all()
    assert len(rows) == 1
    assert rows[0].overall_score == 90
    assert rows[0].markdown_file_path == "new.md"

