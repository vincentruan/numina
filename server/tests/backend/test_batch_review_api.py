"""Tests for batch review API and grading explanation endpoint."""

from packages.db.models.learning.question import Question
from packages.db.models.learning.topic import LearningTopic


def _make_question(db_session, **overrides):
    t = db_session.query(LearningTopic).filter(
        LearningTopic.topic_key == "math.add"
    ).one_or_none()
    if t is None:
        t = LearningTopic(topic_key="math.add", subject="mathematics",
                         domain="number", name="Addition", deprecated=False,
                         topic_type="knowledge", age_group="lower")
        db_session.add(t)
        db_session.flush()
    defaults = dict(
        topic_id=t.id, question_type="calculation",
        stem="1+1=?", answer_json='{"answer": 2}',
        difficulty=1, source="llm", review_status="pending",
        age_group="lower",
    )
    defaults.update(overrides)
    q = Question(**defaults)
    db_session.add(q)
    db_session.commit()
    return q


class TestBatchReview:
    """POST /practice/questions/batch-review"""

    def test_batch_approve_multiple(self, client, db_session, auth_headers):
        q1 = _make_question(db_session)
        q2 = _make_question(db_session, stem="2+2=?", answer_json='{"answer": 4}')

        resp = client.post("/api/v1/practice/questions/batch-review", json={
            "question_ids": [str(q1.id), str(q2.id)],
            "decision": "approve",
        }, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["processed"] == 2

    def test_batch_reject_with_notes(self, client, db_session, auth_headers):
        q = _make_question(db_session, stem="bad?", answer_json='{"answer": 0}')

        resp = client.post("/api/v1/practice/questions/batch-review", json={
            "question_ids": [str(q.id)],
            "decision": "reject",
            "notes": "Incorrect answer",
        }, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["data"]["processed"] == 1


class TestSingleReviewIDOR:
    """PUT /practice/questions/{id}/review — cross-family isolation (SEC-001 regression)."""

    def test_owner_can_review_own_family_question(self, client, db_session, auth_headers):
        q = _make_question(db_session, family_id=None)  # template question (no family)
        resp = client.put(
            f"/api/v1/practice/questions/{q.id}/review",
            json={"decision": "approved"},
            headers=auth_headers,
        )
        assert resp.status_code == 200

    def test_cross_family_review_blocked(self, client, db_session, auth_headers, second_user_headers):
        """Owner A cannot review a pending question owned by Family B."""
        from packages.db.models.user import User

        fam_b_user = (
            db_session.query(User)
            .filter(User.username == "testuser2")
            .first()
        )
        family_b_id = fam_b_user.family_id

        # Create a pending question owned by Family B
        q = _make_question(db_session, family_id=family_b_id)

        # Owner A tries to approve Family B's question
        resp = client.put(
            f"/api/v1/practice/questions/{q.id}/review",
            json={"decision": "approved"},
            headers=auth_headers,  # Family A's headers
        )
        # Should get NOT_FOUND (question not visible to Family A)
        assert resp.status_code in (404, 403)
        data = resp.json()
        assert data.get("code") in ("PRACTICE_QUESTION_NOT_FOUND", "PRACTICE_QUESTION_INVALID", "FORBIDDEN")

        # Verify question is still pending (not modified)
        db_session.refresh(q)
        assert q.review_status == "pending"

    def test_invalid_decision_rejected(self, client, db_session, auth_headers):
        """Decision must be 'approved' or 'rejected' — enforced by schema Literal."""
        q = _make_question(db_session)
        resp = client.put(
            f"/api/v1/practice/questions/{q.id}/review",
            json={"decision": "invalid_value"},
            headers=auth_headers,
        )
        assert resp.status_code == 422  # Pydantic validation error


class TestReviewQueue:
    """GET /practice/questions/review-queue"""

    def test_review_queue_returns_pending(self, client, db_session, auth_headers):
        _make_question(db_session)

        resp = client.get("/api/v1/practice/questions/review-queue", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data["questions"]) >= 1


class TestGradingExplanation:
    """GET /practice/questions/{id}/grading-explanation"""

    def test_returns_explanation_when_present(self, client, db_session, auth_headers):
        q = _make_question(
            db_session,
            question_type="ai_graded",
            stem="Explain photosynthesis",
            answer_json='{"rubric": "光合作用"}',
            difficulty=2,
            review_status="approved",
            grading_explanation_json='{"confidence": 0.85, "dimensions": {"topic_match": true}, "reasoning": "正确描述了光合作用过程"}',
        )

        resp = client.get(f"/api/v1/practice/questions/{q.id}/grading-explanation",
                         headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["confidence"] == 0.85
        assert "reasoning" in data

    def test_returns_404_when_no_explanation(self, client, db_session, auth_headers):
        q = _make_question(db_session, review_status="approved")

        resp = client.get(f"/api/v1/practice/questions/{q.id}/grading-explanation",
                         headers=auth_headers)
        assert resp.status_code == 404
