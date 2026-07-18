"""U4 step 7: write_report_results persists markdown_file_path + report_json.

Verifies the writer stores the indicators JSON, derived scores, and the
step-1 markdown audit path in ``ai_reports``. Replace strategy (clear
previous rows for the family) is also guarded.
"""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from apps.backend.app.database import Base
from apps.backend.app.models.ai_report import AIReport
from apps.backend.app.services.ai_result_writer import write_report_results


def _db() -> Session:
    # SQLite foreign keys are off by default, so AIReport rows can be inserted
    # without a matching families row — the writer's family_id filter + replace
    # logic is what's under test, not the FK.
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def test_write_report_persists_json_and_markdown_path():
    db = _db()
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
    db = _db()
    write_report_results(100, {"overall_score": 50}, db)

    row = db.query(AIReport).filter(AIReport.family_id == 100).one()
    assert row.markdown_file_path is None


def test_write_report_replaces_previous_for_family():
    """Replace strategy: a second write clears the first row for the family."""
    db = _db()
    write_report_results(100, {"overall_score": 60}, db, markdown_file_path="old.md")
    write_report_results(100, {"overall_score": 90}, db, markdown_file_path="new.md")

    rows = db.query(AIReport).filter(AIReport.family_id == 100).all()
    assert len(rows) == 1
    assert rows[0].overall_score == 90
    assert rows[0].markdown_file_path == "new.md"
