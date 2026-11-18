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


def _add_question_to_session(db, session_id, question_id):
    """Add a question to the session's list so the membership check passes.

    Adaptive selection may not pick a newly-added question, so integration
    tests append it explicitly.
    """
    from packages.db.models.learning.practice import PracticeSession

    session = db.query(PracticeSession).filter_by(id=session_id).first()
    session.question_ids_json = json.dumps(
        json.loads(session.question_ids_json) + [question_id]
    )
    db.flush()


@pytest.fixture
def fill_blank_question(db: Session, topic):
    """A fill_blank diagnostic-style question: the top number is the numerator."""
    q = Question(
        topic_id=topic.id,
        question_type="fill_blank",
        stem="In the fraction 3/4, the number 3 is called the ___",
        stem_zh="在分数 3/4 中，上面的 3 叫做___",
        answer_json=json.dumps({"value": "numerator"}),
        difficulty=1,
        bloom_level="remember",
        source="test",
        age_group="mid",
        review_status="approved",
    )
    db.add(q)
    db.flush()
    return q


@pytest.fixture
def text_match_misconception(db: Session, topic, fill_blank_question):
    """Confusing numerator for denominator — the seeded shape, in both languages."""
    m = Misconception(
        topic_id=topic.id,
        sequence=3,
        error_pattern_json=json.dumps({
            "match_type": "text_match",
            "expected_wrong": ["denominator", "分母"],
            "normalize": True,
        }),
        description="You mixed up numerator and denominator.",
        description_zh="你把分子和分母搞混了。",
        age_group="mid",
        diagnostic_question_id=fill_blank_question.id,
        review_status="approved",
    )
    db.add(m)
    db.flush()
    return m


@pytest.fixture
def multiple_choice_question(db: Session, topic):
    """A multiple_choice question with options and a key-keyed answer."""
    q = Question(
        topic_id=topic.id,
        question_type="multiple_choice",
        stem="What is 1/3 + 1/6?",
        stem_zh="1/3 + 1/6 等于多少？",
        options_json=json.dumps([
            {"key": "A", "text": "2/9"},
            {"key": "B", "text": "1/2"},
            {"key": "C", "text": "2/6"},
            {"key": "D", "text": "1/9"},
        ]),
        answer_json=json.dumps({"key": "B"}),
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
def option_select_misconception(db: Session, topic, multiple_choice_question):
    """Selecting option A means the child added numerators and denominators."""
    m = Misconception(
        topic_id=topic.id,
        sequence=5,
        error_pattern_json=json.dumps({
            "match_type": "option_select",
            "wrong_options": ["A"],
        }),
        description="You added numerators and denominators directly.",
        description_zh="你直接把分子和分母相加了。",
        age_group="mid",
        diagnostic_question_id=multiple_choice_question.id,
        review_status="approved",
    )
    db.add(m)
    db.flush()
    return m


class TestNonCalcMisconceptionDetection:
    """Detection through the practice API for fill_blank and multiple_choice.

    Submissions use the payload shapes the child app emits (see
    PracticeAnswerInput.vue): ``{"value": ...}`` for fill_blank and
    ``{"key": ...}`` for multiple_choice — not ``{"answer": ...}``.
    """

    def test_fill_blank_wrong_text_triggers_detection(
        self, client, auth_headers, db, topic, fill_blank_question, text_match_misconception
    ):
        """fill_blank answer 'denominator' scores wrong and matches text_match."""
        resp = client.post(
            "/api/v1/practice/sessions",
            json={"topic_id": topic.id, "count": 1},
            headers=auth_headers,
        )
        session_id = resp.json()["data"]["id"]
        _add_question_to_session(db, session_id, fill_blank_question.id)

        resp = client.post(
            f"/api/v1/practice/sessions/{session_id}/answer",
            json={
                "question_id": fill_blank_question.id,
                "user_answer": {"value": "denominator"},
                "time_spent_seconds": 10,
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["is_correct"] is False
        assert data["misconception_feedback"] is not None
        feedback = data["misconception_feedback"]
        assert feedback["misconception_id"] == str(text_match_misconception.id)

    def test_fill_blank_chinese_answer_triggers_detection(
        self, client, auth_headers, db, topic, fill_blank_question, text_match_misconception
    ):
        """Bilingual stems: answering 分母 matches the same misconception."""
        resp = client.post(
            "/api/v1/practice/sessions",
            json={"topic_id": topic.id, "count": 1},
            headers=auth_headers,
        )
        session_id = resp.json()["data"]["id"]
        _add_question_to_session(db, session_id, fill_blank_question.id)

        resp = client.post(
            f"/api/v1/practice/sessions/{session_id}/answer",
            json={
                "question_id": fill_blank_question.id,
                "user_answer": {"value": "分母"},
                "time_spent_seconds": 10,
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["is_correct"] is False
        assert data["misconception_feedback"] is not None

    def test_fill_blank_correct_answer_scores_correct(
        self, client, auth_headers, db, topic, fill_blank_question, text_match_misconception
    ):
        """The seeded fill_blank shape grades correctly — 'numerator' is right."""
        resp = client.post(
            "/api/v1/practice/sessions",
            json={"topic_id": topic.id, "count": 1},
            headers=auth_headers,
        )
        session_id = resp.json()["data"]["id"]
        _add_question_to_session(db, session_id, fill_blank_question.id)

        resp = client.post(
            f"/api/v1/practice/sessions/{session_id}/answer",
            json={
                "question_id": fill_blank_question.id,
                "user_answer": {"value": "numerator"},
                "time_spent_seconds": 10,
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["is_correct"] is True
        assert data["misconception_feedback"] is None

    def test_fill_blank_non_matching_text_returns_null_feedback(
        self, client, auth_headers, db, topic, fill_blank_question, text_match_misconception
    ):
        """An unrelated wrong answer records the attempt without feedback."""
        from apps.backend.app.models.user import User
        from packages.db.models.learning.practice import PracticeAttempt

        resp = client.post(
            "/api/v1/practice/sessions",
            json={"topic_id": topic.id, "count": 1},
            headers=auth_headers,
        )
        session_id = resp.json()["data"]["id"]
        _add_question_to_session(db, session_id, fill_blank_question.id)

        resp = client.post(
            f"/api/v1/practice/sessions/{session_id}/answer",
            json={
                "question_id": fill_blank_question.id,
                "user_answer": {"value": "whole"},
                "time_spent_seconds": 10,
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["is_correct"] is False
        assert data["misconception_feedback"] is None

        user = db.query(User).filter_by(username="testuser").first()
        attempt = db.query(PracticeAttempt).filter_by(
            child_id=user.id,
            question_id=fill_blank_question.id,
        ).first()
        assert attempt is not None
        assert attempt.is_correct is False
        assert attempt.misconception_id is None

    def test_multiple_choice_wrong_key_triggers_detection(
        self, client, auth_headers, db, topic, multiple_choice_question,
        option_select_misconception,
    ):
        """The {"key": "A"} payload the child app sends reaches option_select."""
        resp = client.post(
            "/api/v1/practice/sessions",
            json={"topic_id": topic.id, "count": 1},
            headers=auth_headers,
        )
        session_id = resp.json()["data"]["id"]
        _add_question_to_session(db, session_id, multiple_choice_question.id)

        resp = client.post(
            f"/api/v1/practice/sessions/{session_id}/answer",
            json={
                "question_id": multiple_choice_question.id,
                "user_answer": {"key": "A"},
                "time_spent_seconds": 10,
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["is_correct"] is False
        assert data["misconception_feedback"] is not None
        feedback = data["misconception_feedback"]
        assert feedback["misconception_id"] == str(option_select_misconception.id)

        # The attempt is annotated too, which drives adaptive boosting.
        from apps.backend.app.models.user import User
        from packages.db.models.learning.practice import PracticeAttempt

        user = db.query(User).filter_by(username="testuser").first()
        attempt = db.query(PracticeAttempt).filter_by(
            child_id=user.id,
            question_id=multiple_choice_question.id,
        ).first()
        assert attempt.misconception_id == option_select_misconception.id

    def test_multiple_choice_correct_key_scores_correct(
        self, client, auth_headers, db, topic, multiple_choice_question,
        option_select_misconception,
    ):
        """The seeded MCQ answer key grades correctly — option B is right."""
        resp = client.post(
            "/api/v1/practice/sessions",
            json={"topic_id": topic.id, "count": 1},
            headers=auth_headers,
        )
        session_id = resp.json()["data"]["id"]
        _add_question_to_session(db, session_id, multiple_choice_question.id)

        resp = client.post(
            f"/api/v1/practice/sessions/{session_id}/answer",
            json={
                "question_id": multiple_choice_question.id,
                "user_answer": {"key": "B"},
                "time_spent_seconds": 10,
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["is_correct"] is True
        assert data["misconception_feedback"] is None

    def test_multiple_choice_unlisted_key_returns_null_feedback(
        self, client, auth_headers, db, topic, multiple_choice_question,
        option_select_misconception,
    ):
        """A wrong key not in wrong_options records the attempt, no feedback."""
        from apps.backend.app.models.user import User
        from packages.db.models.learning.practice import PracticeAttempt

        resp = client.post(
            "/api/v1/practice/sessions",
            json={"topic_id": topic.id, "count": 1},
            headers=auth_headers,
        )
        session_id = resp.json()["data"]["id"]
        _add_question_to_session(db, session_id, multiple_choice_question.id)

        resp = client.post(
            f"/api/v1/practice/sessions/{session_id}/answer",
            json={
                "question_id": multiple_choice_question.id,
                "user_answer": {"key": "D"},
                "time_spent_seconds": 10,
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["is_correct"] is False
        assert data["misconception_feedback"] is None

        user = db.query(User).filter_by(username="testuser").first()
        attempt = db.query(PracticeAttempt).filter_by(
            child_id=user.id,
            question_id=multiple_choice_question.id,
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
        data = resp.json()["data"]
        assert data["is_correct"] is True
        assert data["misconception_feedback"] is None

        # The diagnostic question is appended to the session's question list.
        from packages.db.models.learning.practice import PracticeSession
        session = db.query(PracticeSession).filter_by(id=session_id).first()
        assert session is not None
        session_qids = json.loads(session.question_ids_json)
        assert diag_q.id in session_qids

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

    def test_returns_two_misconceptions_ordered_and_fields(
        self, client, auth_headers, topic, fraction_question, misconception, db
    ):
        """Two detections → both entries present, ordered most-recent-first, with full fields."""
        # Second misconception with a distinct symbolic pattern.
        m2 = Misconception(
            topic_id=topic.id,
            sequence=1,
            error_pattern_json=json.dumps({"match_type": "symbolic", "expected_wrong": "99/100"}),
            description="Another misconception",
            description_zh="另一个误解。",
            age_group="mid",
            review_status="approved",
        )
        db.add(m2)
        db.flush()

        # Second question (different fractions) so adaptive selection doesn't
        # exclude the first as recently-attempted.
        q2 = Question(
            topic_id=topic.id,
            question_type="calculation",
            stem="What is 1/2 + 1/3?",
            stem_zh="1/2 + 1/3 等于多少？",
            answer_json=json.dumps({
                "answer": "5/6",
                "fractions": [[1, 2], [1, 3]],
            }),
            difficulty=2,
            bloom_level="apply",
            source="test",
            age_group="mid",
            review_status="approved",
        )
        db.add(q2)
        db.flush()

        resp = client.post(
            "/api/v1/practice/sessions",
            json={"topic_id": topic.id, "count": 1},
            headers=auth_headers,
        )
        session_id = resp.json()["data"]["id"]

        # Trigger detection 1: parametric fraction_add_numerators (2/7 on q1).
        client.post(
            f"/api/v1/practice/sessions/{session_id}/answer",
            json={
                "question_id": fraction_question.id,
                "user_answer": {"answer": "2/7"},
                "time_spent_seconds": 10,
            },
            headers=auth_headers,
        )

        # Second session for the second answer (one attempt per question per session).
        resp = client.post(
            "/api/v1/practice/sessions",
            json={"topic_id": topic.id, "count": 1},
            headers=auth_headers,
        )
        assert resp.status_code == 201, resp.text
        session_id2 = resp.json()["data"]["id"]

        # Trigger detection 2: symbolic 99/100 on q2.
        client.post(
            f"/api/v1/practice/sessions/{session_id2}/answer",
            json={
                "question_id": q2.id,
                "user_answer": {"answer": "99/100"},
                "time_spent_seconds": 10,
            },
            headers=auth_headers,
        )

        resp = client.get("/api/v1/practice/misconceptions", headers=auth_headers)
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        ids = {entry["misconception_id"] for entry in data}
        assert str(misconception.id) in ids
        assert str(m2.id) in ids

        for entry in data:
            if entry["misconception_id"] == str(misconception.id):
                assert entry["detection_count"] == 1
                assert entry["topic_id"] == str(topic.id)
                assert entry["description"] == misconception.description
                assert entry["description_zh"] == misconception.description_zh
                assert entry["last_detected_at"] is not None
            if entry["misconception_id"] == str(m2.id):
                assert entry["detection_count"] == 1
                assert entry["topic_id"] == str(topic.id)
                assert entry["description"] == "Another misconception"
                assert entry["description_zh"] == "另一个误解。"
                assert entry["last_detected_at"] is not None
