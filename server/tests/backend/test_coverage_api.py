"""Tests for coverage API endpoints."""
import pytest
from fastapi.testclient import TestClient

from packages.db.models.learning.question import Question
from packages.db.models.learning.topic import LearningTopic


class TestCoverageSummary:
    """GET /practice/coverage/summary"""

    def test_summary_returns_subject_breakdown(self, client: TestClient, db_session, auth_headers):
        t = LearningTopic(topic_key="math.add", subject="mathematics",
                         domain="number", name="Addition", deprecated=False,
                         topic_type="knowledge", age_group="lower")
        db_session.add(t)
        db_session.flush()
        db_session.add(Question(
            topic_id=t.id, question_type="calculation",
            stem="1+1=?", answer_json='{"answer": 2}',
            difficulty=1, source="template", review_status="approved",
            age_group="lower",
        ))
        db_session.commit()

        resp = client.get("/api/v1/practice/coverage/summary", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "subjects" in data
        assert any(s["subject"] == "mathematics" for s in data["subjects"])


class TestCoverageDetailed:
    """GET /practice/coverage/detailed"""

    def test_detailed_returns_per_topic_scores(self, client: TestClient, db_session, auth_headers):
        t = LearningTopic(topic_key="math.add", subject="mathematics",
                         domain="number", name="Addition", deprecated=False,
                         topic_type="knowledge", age_group="lower")
        db_session.add(t)
        db_session.commit()

        resp = client.get(
            "/api/v1/practice/coverage/detailed?subject=mathematics",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "topics" in data
        assert len(data["topics"]) >= 1


class TestCoverageGapReport:
    """GET /practice/coverage/gap-report"""

    def test_gap_report_returns_uncovered_topics(self, client: TestClient, db_session, auth_headers):
        t = LearningTopic(topic_key="math.add", subject="mathematics",
                         domain="number", name="Addition", deprecated=False,
                         topic_type="knowledge", age_group="lower")
        db_session.add(t)
        db_session.commit()

        resp = client.get(
            "/api/v1/practice/coverage/gap-report?subject=mathematics&threshold=0.5",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "gaps" in data
        assert len(data["gaps"]) >= 1
