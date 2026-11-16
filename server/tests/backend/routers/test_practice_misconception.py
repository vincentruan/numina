"""Tests for misconception detection integration in the practice API."""

import json

import pytest
from sqlalchemy.orm import Session

from packages.db.models.learning.misconception import Misconception, MisconceptionDetection
from packages.db.models.learning.question import Question
from packages.db.models.learning.topic import LearningTopic


@pytest.fixture
def topic(db: Session):
    t = LearningTopic(
        topic_key="mt_miscon_test",
        topic_type="concept",
        subject="mathematics",
        domain="arithmetic",
        name="Misconception test",
        age_group="mid",
        evidence_json="[]",
        standards_json="[]",
    )
    db.add(t)
    db.flush()
    return t


@pytest.fixture
def fraction_question(db: Session, topic):
    """A fraction addition question: 1/3 + 1/4 = 7/12."""
    q = Question(
        topic_id=topic.id,
        question_type="calculation",
        stem="What is 1/3 + 1/4?",
        stem_zh="1/3 + 1/4 等于多少？",
        answer_json=json.dumps({
            "answer": "7/12",
            "fractions": [[1, 3], [1, 4]],
        }),
        difficulty=2,
        bloom_level="apply",
        source="test",
        age_group="mid",
        review_status="approved",
    )
    db.add(q)
    db.flush()
    return q


@pytest.fixture
def misconception(db: Session, topic):
    m = Misconception(
        topic_id=topic.id,
        sequence=0,
        error_pattern_json=json.dumps({
            "match_type": "parametric",
            "algorithm": "fraction_add_numerators",
        }),
        description="Many students add numerators and denominators separately.",
        description_zh="很多同学会把分子和分母分别相加。",
        age_group="mid",
        review_status="approved",
    )
    db.add(m)
    db.flush()
    return m


class TestMisconceptionDetectionInPracticeAPI:
    def test_wrong_answer_matching_misconception_returns_feedback(
        self, client, auth_headers, topic, fraction_question, misconception
    ):
        """Wrong answer '2/7' triggers misconception detection."""
        # Create session.
        resp = client.post(
            "/api/v1/practice/sessions",
            json={"topic_id": topic.id, "count": 1},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        session_id = resp.json()["data"]["id"]

        # Submit wrong answer matching the misconception.
        resp = client.post(
            f"/api/v1/practice/sessions/{session_id}/answer",
            json={
                "question_id": fraction_question.id,
                "user_answer": {"answer": "2/7"},
                "time_spent_seconds": 10,
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["is_correct"] is False
        assert data["misconception_feedback"] is not None
        feedback = data["misconception_feedback"]
        assert feedback["misconception_id"] == str(misconception.id)

    def test_wrong_answer_not_matching_returns_null_feedback(
        self, client, auth_headers, topic, fraction_question, misconception
    ):
        """Wrong answer that doesn't match returns null feedback."""
        resp = client.post(
            "/api/v1/practice/sessions",
            json={"topic_id": topic.id, "count": 1},
            headers=auth_headers,
        )
        session_id = resp.json()["data"]["id"]

        resp = client.post(
            f"/api/v1/practice/sessions/{session_id}/answer",
            json={
                "question_id": fraction_question.id,
                "user_answer": {"answer": "5/12"},
                "time_spent_seconds": 10,
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["is_correct"] is False
        assert data["misconception_feedback"] is None

    def test_correct_answer_returns_null_feedback(
        self, client, auth_headers, topic, fraction_question, misconception
    ):
        """Correct answer never triggers detection."""
        resp = client.post(
            "/api/v1/practice/sessions",
            json={"topic_id": topic.id, "count": 1},
            headers=auth_headers,
        )
        session_id = resp.json()["data"]["id"]

        resp = client.post(
            f"/api/v1/practice/sessions/{session_id}/answer",
            json={
                "question_id": fraction_question.id,
                "user_answer": {"answer": "7/12"},
                "time_spent_seconds": 10,
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["is_correct"] is True
        assert data["misconception_feedback"] is None

    def test_detection_record_created_on_match(
        self, client, auth_headers, topic, fraction_question, misconception, db
    ):
        """Detection row is persisted when misconception matches."""
        resp = client.post(
            "/api/v1/practice/sessions",
            json={"topic_id": topic.id, "count": 1},
            headers=auth_headers,
        )
        session_id = resp.json()["data"]["id"]

        client.post(
            f"/api/v1/practice/sessions/{session_id}/answer",
            json={
                "question_id": fraction_question.id,
                "user_answer": {"answer": "2/7"},
                "time_spent_seconds": 10,
            },
            headers=auth_headers,
        )

        # Check the auth_headers fixture's user ID.
        from apps.backend.app.models.user import User
        user = db.query(User).filter_by(username="testuser").first()

        detections = db.query(MisconceptionDetection).filter_by(
            child_id=user.id,
            misconception_id=misconception.id,
        ).all()
        assert len(detections) == 1

        # The PracticeAttempt is also annotated with the misconception_id
        # (drives cross-session adaptive boosting — U1/U2).
        from packages.db.models.learning.practice import PracticeAttempt
        attempt = db.query(PracticeAttempt).filter_by(
            child_id=user.id,
            question_id=fraction_question.id,
        ).first()
        assert attempt is not None
        assert attempt.misconception_id == misconception.id

    def test_attempt_misconception_id_null_when_no_match(
        self, client, auth_headers, topic, fraction_question, db
    ):
        """Wrong answer that doesn't match any pattern → misconception_id null."""
        from apps.backend.app.models.user import User
        from packages.db.models.learning.practice import PracticeAttempt

        resp = client.post(
            "/api/v1/practice/sessions",
            json={"topic_id": topic.id, "count": 1},
            headers=auth_headers,
        )
        session_id = resp.json()["data"]["id"]

        client.post(
            f"/api/v1/practice/sessions/{session_id}/answer",
            json={
                "question_id": fraction_question.id,
                "user_answer": {"answer": "99/100"},  # no matching pattern
                "time_spent_seconds": 10,
            },
            headers=auth_headers,
        )

        user = db.query(User).filter_by(username="testuser").first()
        attempt = db.query(PracticeAttempt).filter_by(
            child_id=user.id,
            question_id=fraction_question.id,
        ).first()
        assert attempt is not None
        assert attempt.misconception_id is None


class TestDiagnosticQuestionSubmission:
    def test_diagnostic_question_bypasses_session_check(
        self, client, auth_headers, topic, fraction_question, db
    ):
        """is_diagnostic=True allows answering a legitimate diagnostic question."""
        # Create a diagnostic question NOT in the session.
        diag_q = Question(
            topic_id=topic.id,
            question_type="calculation",
            stem="Diagnostic: What is 1/2 + 1/3?",
            answer_json=json.dumps({"answer": "5/6"}),
            difficulty=2,
            bloom_level="apply",
            source="test",
            age_group="mid",
            review_status="approved",
        )
        db.add(diag_q)
        db.flush()

        # Create a misconception that links to this diagnostic question —
        # the is_diagnostic validation requires a legitimate link.
        from packages.db.models.learning.misconception import Misconception
        m = Misconception(
            topic_id=topic.id,
            sequence=99,
            error_pattern_json=json.dumps({"match_type": "symbolic", "expected_wrong": "2/5"}),
            description="Test misconception",
            age_group="mid",
            diagnostic_question_id=diag_q.id,
            review_status="approved",
        )
        db.add(m)
        db.flush()

        resp = client.post(
            "/api/v1/practice/sessions",
            json={"topic_id": topic.id, "count": 1},
            headers=auth_headers,
        )
        session_id = resp.json()["data"]["id"]

        # Without is_diagnostic — should fail (question not in session).
        resp = client.post(
            f"/api/v1/practice/sessions/{session_id}/answer",
            json={
                "question_id": diag_q.id,
                "user_answer": {"answer": "5/6"},
                "time_spent_seconds": 10,
                "is_diagnostic": False,
            },
            headers=auth_headers,
        )
        assert resp.status_code == 400

        # With is_diagnostic — should succeed (linked diagnostic question).
        resp = client.post(
            f"/api/v1/practice/sessions/{session_id}/answer",
            json={
                "question_id": diag_q.id,
                "user_answer": {"answer": "5/6"},
                "time_spent_seconds": 10,
                "is_diagnostic": True,
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200, resp.text

    def test_arbitrary_question_rejected_with_is_diagnostic(
        self, client, auth_headers, topic, fraction_question, db
    ):
        """is_diagnostic=True with a non-diagnostic question_id is rejected."""
        # Create a regular question NOT linked to any misconception.
        arbitrary_q = Question(
            topic_id=topic.id,
            question_type="calculation",
            stem="Arbitrary: What is 2+3?",
            answer_json=json.dumps({"answer": "5"}),
            difficulty=1,
            bloom_level="apply",
            source="test",
            age_group="mid",
            review_status="approved",
        )
        db.add(arbitrary_q)
        db.flush()

        resp = client.post(
            "/api/v1/practice/sessions",
            json={"topic_id": topic.id, "count": 1},
            headers=auth_headers,
        )
        session_id = resp.json()["data"]["id"]

        # is_diagnostic=True with non-diagnostic question — should be rejected.
        resp = client.post(
            f"/api/v1/practice/sessions/{session_id}/answer",
            json={
                "question_id": arbitrary_q.id,
                "user_answer": {"answer": "5"},
                "time_spent_seconds": 10,
                "is_diagnostic": True,
            },
            headers=auth_headers,
        )
        assert resp.status_code == 400


class TestGetChildMisconceptions:
    def test_returns_empty_when_no_detections(self, client, auth_headers):
        """GET /misconceptions returns empty list when no detections exist."""
        resp = client.get("/api/v1/practice/misconceptions", headers=auth_headers)
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert isinstance(data, list)

    def test_returns_detections_after_matching(
        self, client, auth_headers, topic, fraction_question, misconception
    ):
        """After a detection, GET /misconceptions includes it."""
        # Trigger a detection.
        resp = client.post(
            "/api/v1/practice/sessions",
            json={"topic_id": topic.id, "count": 1},
            headers=auth_headers,
        )
        session_id = resp.json()["data"]["id"]

        client.post(
            f"/api/v1/practice/sessions/{session_id}/answer",
            json={
                "question_id": fraction_question.id,
                "user_answer": {"answer": "2/7"},
                "time_spent_seconds": 10,
            },
            headers=auth_headers,
        )

        # Query misconceptions.
        resp = client.get("/api/v1/practice/misconceptions", headers=auth_headers)
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert len(data) >= 1
        entry = data[0]
        assert entry["misconception_id"] == str(misconception.id)
        assert entry["detection_count"] >= 1
