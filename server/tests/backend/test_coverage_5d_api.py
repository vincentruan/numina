"""Tests for Coverage 5D API endpoint — GET /learning/coverage/report."""

from fastapi.testclient import TestClient

from packages.db.models.learning.question import Question
from packages.db.models.learning.topic import LearningTopic


class TestCoverage5DReport:
    """GET /learning/coverage/report"""

    def test_report_returns_structure(self, client: TestClient, db_session, auth_headers):
        t = LearningTopic(
            topic_key="math.add", subject="mathematics",
            domain="number", name="Addition", deprecated=False,
            topic_type="knowledge", age_group="lower",
        )
        db_session.add(t)
        db_session.commit()

        resp = client.get("/api/v1/learning/coverage/report", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "overall_score" in data
        assert "subjects" in data
        assert "worklist" in data
        assert "total_topics" in data

    def test_report_with_questions(self, client: TestClient, db_session, auth_headers):
        t = LearningTopic(
            topic_key="math.add", subject="mathematics",
            domain="number", name="Addition", deprecated=False,
            topic_type="knowledge", age_group="lower",
        )
        db_session.add(t)
        db_session.flush()
        db_session.add(Question(
            topic_id=t.id, question_type="calculation",
            stem="1+1=?", stem_zh="1+1=?",
            answer_json='{"answer": 2}',
            difficulty=1, bloom_level="apply",
            source="template", review_status="approved",
            age_group="lower",
            correct_count=8, times_used=10,
        ))
        db_session.commit()

        resp = client.get("/api/v1/learning/coverage/report", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total_topics"] >= 1
        assert data["overall_score"] > 0.0

    def test_report_filters_by_subject(self, client: TestClient, db_session, auth_headers):
        t = LearningTopic(
            topic_key="math.add", subject="mathematics",
            domain="number", name="Addition", deprecated=False,
            topic_type="knowledge", age_group="lower",
        )
        db_session.add(t)
        db_session.commit()

        resp = client.get(
            "/api/v1/learning/coverage/report?subject=mathematics",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        subjects = [s["subject"] for s in data["subjects"]]
        assert "mathematics" in subjects

    def test_report_worklist_has_dimension_info(self, client: TestClient, db_session, auth_headers):
        t = LearningTopic(
            topic_key="math.add", subject="mathematics",
            domain="number", name="Addition", deprecated=False,
            topic_type="knowledge", age_group="lower",
        )
        db_session.add(t)
        db_session.commit()

        resp = client.get("/api/v1/learning/coverage/report", headers=auth_headers)
        data = resp.json()["data"]
        # Topic with no questions should be in worklist
        assert len(data["worklist"]) >= 1
        item = data["worklist"][0]
        assert "dimensions" in item
        assert "missing_difficulties" in item
        assert "missing_blooms" in item
        assert "priority" in item
