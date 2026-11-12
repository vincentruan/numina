"""Tests for GET /practice/recommend with the diagnosis=true extension (U3)."""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from packages.db.models.family import Family
from packages.db.models.learning.diagnosis_impression import DiagnosisImpression
from packages.db.models.learning.practice import PracticeAttempt, PracticeSession
from packages.db.models.learning.progress import LearningProgress
from packages.db.models.learning.question import Question
from packages.db.models.learning.topic import LearningDependency, LearningTopic
from packages.db.models.user import User


def _topic(db: Session, id_: int, key: str, **extra) -> LearningTopic:
    t = LearningTopic(
        id=id_,
        topic_key=key,
        topic_type="knowledge_point",
        subject="math",
        name=extra.get("name") or key,
        name_zh=extra.get("name_zh") or key,
        **{k: v for k, v in extra.items() if k not in {"name", "name_zh"}},
    )
    db.add(t)
    db.flush()
    return t


def _session_and_attempts(
    db: Session,
    child: User,
    topic: LearningTopic,
    n_attempts: int,
    correct: int,
):
    from packages.core.snowflake import next_id

    session = PracticeSession(
        id=next_id(),
        child_id=child.id,
        topic_id=topic.id,
        session_mode="practice",
        question_ids_json="[]",
        started_at=datetime.now(UTC),
        completed_count=n_attempts,
        source="adaptive",
    )
    db.add(session)
    db.flush()
    for i in range(n_attempts):
        db.add(
            PracticeAttempt(
                id=next_id(),
                session_id=session.id,
                question_id=next_id(),
                child_id=child.id,
                topic_id=topic.id,
                user_answer_json='{"v":1}',
                is_correct=(i < correct),
                attempt_number=i + 1,
                created_at=datetime.now(UTC) - timedelta(days=n_attempts - i - 1),
            )
        )
    db.flush()


def _question(db: Session, topic: LearningTopic) -> Question:
    from packages.core.snowflake import next_id

    q = Question(
        id=next_id(),
        topic_id=topic.id,
        question_type="calc",
        stem='{"v":1}',
        answer_json='{"v":1}',
        source="test",
        age_group="mid",
        difficulty=2,
        review_status="approved",
    )
    db.add(q)
    db.flush()
    return q


class TestDiagnosisEndpoint:
    def test_diagnosis_returns_fields_with_is_diagnosis(
        self, client: TestClient, auth_headers, db: Session
    ):
        family = Family(name="F", invite_code="U31", created_by=1)
        db.add(family)
        db.flush()
        child = User(
            display_name="Child",
            password_hash="x",
            role="child",
            family_id=family.id,
        )
        db.add(child)
        db.flush()

        target = _topic(db, 2_000_001, "target")
        buffer = _topic(db, 2_000_004, "buffer")
        cand = _topic(db, 2_000_002, "cand")
        db.add(LearningDependency(topic_id=target.id, prerequisite_id=buffer.id, strength="hard"))
        db.add(LearningDependency(topic_id=buffer.id, prerequisite_id=cand.id, strength="hard"))
        db.flush()

        _session_and_attempts(db, child, target, 8, 3)
        db.add(LearningProgress(child_id=child.id, topic_id=target.id, mastery_level="learning"))
        _session_and_attempts(db, child, buffer, 8, 7)
        db.add(LearningProgress(child_id=child.id, topic_id=buffer.id, mastery_level="mastered"))
        _question(db, buffer)
        _session_and_attempts(db, child, cand, 6, 2)
        db.add(LearningProgress(child_id=child.id, topic_id=cand.id, mastery_level="learning"))
        _question(db, cand)
        db.commit()

        from apps.backend.app.auth.deps import get_current_user_or_child
        from apps.backend.app.database import get_db

        client.app.dependency_overrides[get_db] = lambda: db
        client.app.dependency_overrides[get_current_user_or_child] = lambda: child
        try:
            before = db.query(DiagnosisImpression).filter_by(child_id=child.id).count()
            resp = client.get(
                "/api/v1/practice/recommend",
                params={"topic_id": target.id, "diagnosis": True},
                headers=auth_headers,
            )
            assert resp.status_code == 200, resp.text
            body = resp.json()["data"]
            assert len(body) == 1
            item = body[0]
            assert item["is_diagnosis"] is True
            assert item["is_prerequisite"] is True
            # buffer is a direct prerequisite the child is weak on, so it is on
            # the page as a prerequisite recommendation: cand is one layer
            # further back than the page already shows.
            assert item["depth"] == 1
            assert item["bkt_mastery"] is not None and item["bkt_mastery"] < 0.60
            assert item["sample_size"] == 6
            assert item["prerequisite_of_topic_id"] == str(target.id)
            after = db.query(DiagnosisImpression).filter_by(child_id=child.id).count()
            assert after - before == 1
        finally:
            client.app.dependency_overrides.clear()

    def test_mastered_direct_pre_requisite_starts_the_backtrace_at_itself(
        self, client: TestClient, auth_headers, db: Session
    ):
        """A mastered direct prerequisite is not a gap, so the backtrace starts
        there and its weak prerequisite is depth 1 — one layer further back
        than the page already shows."""
        family = Family(name="F", invite_code="U34", created_by=1)
        db.add(family)
        db.flush()
        child = User(
            display_name="Child",
            password_hash="x",
            role="child",
            family_id=family.id,
        )
        db.add(child)
        db.flush()

        target = _topic(db, 2_000_001, "target")
        buffer = _topic(db, 2_000_004, "buffer")
        cand = _topic(db, 2_000_002, "cand")
        db.add(LearningDependency(topic_id=target.id, prerequisite_id=buffer.id, strength="hard"))
        db.add(LearningDependency(topic_id=buffer.id, prerequisite_id=cand.id, strength="hard"))
        db.flush()

        _session_and_attempts(db, child, target, 8, 0)
        db.add(LearningProgress(child_id=child.id, topic_id=target.id, mastery_level="learning"))
        _session_and_attempts(db, child, buffer, 8, 7)
        db.add(LearningProgress(child_id=child.id, topic_id=buffer.id, mastery_level="mastered"))
        _question(db, buffer)
        _session_and_attempts(db, child, cand, 6, 2)
        db.add(LearningProgress(child_id=child.id, topic_id=cand.id, mastery_level="learning"))
        _question(db, cand)
        db.commit()

        from apps.backend.app.auth.deps import get_current_user_or_child
        from apps.backend.app.database import get_db

        client.app.dependency_overrides[get_db] = lambda: db
        client.app.dependency_overrides[get_current_user_or_child] = lambda: child
        try:
            resp = client.get(
                "/api/v1/practice/recommend",
                params={"topic_id": target.id, "diagnosis": True},
                headers=auth_headers,
            )
            assert resp.status_code == 200, resp.text
            body = resp.json()["data"]
            assert len(body) == 1, body
            item = body[0]
            assert item["topic_id"] == str(cand.id)
            assert item["depth"] == 1
            assert item["accuracy"] == pytest.approx(2 / 6)
            assert item["mastery_level"] == "learning"
        finally:
            client.app.dependency_overrides.clear()

    def test_weak_direct_pre_requisite_is_its_own_layer(
        self, client: TestClient, auth_headers, db: Session
    ):
        """When the direct prerequisite is itself weak it is on the page as a
        prerequisite recommendation, so its prerequisites are the layer the
        diagnosis reports — at depth 1, one back from what the page shows."""
        family = Family(name="F", invite_code="U36", created_by=1)
        db.add(family)
        db.flush()
        child = User(
            display_name="Child",
            password_hash="x",
            role="child",
            family_id=family.id,
        )
        db.add(child)
        db.flush()

        target = _topic(db, 2_000_001, "target")
        weak_direct = _topic(db, 2_000_002, "weak_direct")
        below = _topic(db, 2_000_003, "below")
        db.add(LearningDependency(topic_id=target.id, prerequisite_id=weak_direct.id, strength="hard"))
        db.add(LearningDependency(topic_id=weak_direct.id, prerequisite_id=below.id, strength="hard"))
        db.flush()

        _session_and_attempts(db, child, target, 8, 0)
        db.add(LearningProgress(child_id=child.id, topic_id=target.id, mastery_level="learning"))
        _session_and_attempts(db, child, weak_direct, 6, 2)
        db.add(LearningProgress(child_id=child.id, topic_id=weak_direct.id, mastery_level="learning"))
        _question(db, weak_direct)
        _session_and_attempts(db, child, below, 8, 0)
        db.add(LearningProgress(child_id=child.id, topic_id=below.id, mastery_level="learning"))
        _question(db, below)
        db.commit()

        from apps.backend.app.auth.deps import get_current_user_or_child
        from apps.backend.app.database import get_db

        client.app.dependency_overrides[get_db] = lambda: db
        client.app.dependency_overrides[get_current_user_or_child] = lambda: child
        try:
            resp = client.get(
                "/api/v1/practice/recommend",
                params={"topic_id": target.id, "diagnosis": True},
                headers=auth_headers,
            )
            assert resp.status_code == 200, resp.text
            body = resp.json()["data"]
            assert [i["topic_id"] for i in body] == [str(below.id)]
            assert body[0]["depth"] == 1
        finally:
            client.app.dependency_overrides.clear()

    def test_weak_direct_pre_requisite_is_excluded_from_diagnosis(
        self, client: TestClient, auth_headers, db: Session
    ):
        """A direct prerequisite the child is weak on is shown by the existing
        prerequisite guidance, so the diagnosis must not repeat it."""
        family = Family(name="F", invite_code="U35", created_by=1)
        db.add(family)
        db.flush()
        child = User(
            display_name="Child",
            password_hash="x",
            role="child",
            family_id=family.id,
        )
        db.add(child)
        db.flush()

        target = _topic(db, 2_000_001, "target")
        weak_direct = _topic(db, 2_000_002, "weak_direct")
        db.add(LearningDependency(topic_id=target.id, prerequisite_id=weak_direct.id, strength="hard"))
        db.flush()

        _session_and_attempts(db, child, target, 8, 0)
        db.add(LearningProgress(child_id=child.id, topic_id=target.id, mastery_level="learning"))
        _session_and_attempts(db, child, weak_direct, 6, 2)
        db.add(LearningProgress(child_id=child.id, topic_id=weak_direct.id, mastery_level="learning"))
        _question(db, weak_direct)
        db.commit()

        from apps.backend.app.auth.deps import get_current_user_or_child
        from apps.backend.app.database import get_db

        client.app.dependency_overrides[get_db] = lambda: db
        client.app.dependency_overrides[get_current_user_or_child] = lambda: child
        try:
            resp = client.get(
                "/api/v1/practice/recommend",
                params={"topic_id": target.id, "diagnosis": True},
                headers=auth_headers,
            )
            assert resp.status_code == 200, resp.text
            assert resp.json()["data"] == []
        finally:
            client.app.dependency_overrides.clear()

    def test_diagnosis_without_topic_id_returns_empty(
        self, client: TestClient, auth_headers, db: Session
    ):
        family = Family(name="F", invite_code="U32", created_by=1)
        db.add(family)
        db.flush()
        child = User(
            display_name="Child",
            password_hash="x",
            role="child",
            family_id=family.id,
        )
        db.add(child)
        db.commit()

        from apps.backend.app.auth.deps import get_current_user_or_child
        from apps.backend.app.database import get_db

        client.app.dependency_overrides[get_db] = lambda: db
        client.app.dependency_overrides[get_current_user_or_child] = lambda: child
        try:
            resp = client.get(
                "/api/v1/practice/recommend",
                params={"diagnosis": True},
                headers=auth_headers,
            )
            assert resp.status_code == 200, resp.text
            assert resp.json()["data"] == []
        finally:
            client.app.dependency_overrides.clear()

    def test_flagless_with_topic_id_returns_accuracy_sorted_list(
        self, client: TestClient, auth_headers, db: Session
    ):
        """Existing post-practice behavior preserved: is_diagnosis is false by default."""
        family = Family(name="F", invite_code="U33", created_by=1)
        db.add(family)
        db.flush()
        child = User(
            display_name="Child",
            password_hash="x",
            role="child",
            family_id=family.id,
        )
        db.add(child)
        db.flush()

        target = _topic(db, 3_000_001, "target")
        cand = _topic(db, 3_000_002, "cand")
        db.add(LearningDependency(topic_id=target.id, prerequisite_id=cand.id, strength="hard"))
        db.flush()

        _session_and_attempts(db, child, target, 5, 1)
        db.add(LearningProgress(child_id=child.id, topic_id=target.id, mastery_level="learning"))
        db.add(LearningProgress(child_id=child.id, topic_id=cand.id, mastery_level="learning"))
        _session_and_attempts(db, child, cand, 4, 1)
        db.commit()

        from apps.backend.app.auth.deps import get_current_user_or_child
        from apps.backend.app.database import get_db

        client.app.dependency_overrides[get_db] = lambda: db
        client.app.dependency_overrides[get_current_user_or_child] = lambda: child
        try:
            resp = client.get(
                "/api/v1/practice/recommend",
                params={"topic_id": target.id},
                headers=auth_headers,
            )
            assert resp.status_code == 200, resp.text
            body = resp.json()["data"]
            # At least one candidate (cand) is present, all is_diagnosis=False.
            assert len(body) >= 1
            assert all(item["is_diagnosis"] is False for item in body)
            # No impression written — this is the flag-less (post-practice) call.
            count = db.query(DiagnosisImpression).count()
            assert count == 0
        finally:
            client.app.dependency_overrides.clear()

    def test_flagless_without_topic_id_returns_weak_topics(
        self, client: TestClient, auth_headers, db: Session
    ):
        family = Family(name="F", invite_code="U34", created_by=1)
        db.add(family)
        db.flush()
        child = User(
            display_name="Child",
            password_hash="x",
            role="child",
            family_id=family.id,
        )
        db.add(child)
        db.commit()

        from apps.backend.app.auth.deps import get_current_user_or_child
        from apps.backend.app.database import get_db

        client.app.dependency_overrides[get_db] = lambda: db
        client.app.dependency_overrides[get_current_user_or_child] = lambda: child
        try:
            resp = client.get("/api/v1/practice/recommend", headers=auth_headers)
            assert resp.status_code == 200, resp.text
            body = resp.json()["data"]
            assert isinstance(body, list)
            assert all(item["is_prerequisite"] is False for item in body)
            assert all(item["is_diagnosis"] is False for item in body)
        finally:
            client.app.dependency_overrides.clear()

    def test_snowflake_ids_serialized_as_strings(
        self, client: TestClient, auth_headers, db: Session
    ):
        """Per project convention, all bigint IDs serialize as strings."""
        family = Family(name="F", invite_code="U35", created_by=1)
        db.add(family)
        db.flush()
        child = User(
            display_name="Child",
            password_hash="x",
            role="child",
            family_id=family.id,
        )
        db.add(child)
        db.flush()

        target = _topic(db, 4_000_001, "target")
        db.commit()

        from apps.backend.app.auth.deps import get_current_user_or_child
        from apps.backend.app.database import get_db

        client.app.dependency_overrides[get_db] = lambda: db
        client.app.dependency_overrides[get_current_user_or_child] = lambda: child
        try:
            resp = client.get(
                "/api/v1/practice/recommend",
                params={"topic_id": target.id},
                headers=auth_headers,
            )
            assert resp.status_code == 200
            # No candidates expected (no prereqs), but the response must still
            # be a list — and any candidate's topic_id must be a string.
            body = resp.json()["data"]
            assert isinstance(body, list)
            for item in body:
                assert isinstance(item["topic_id"], str)
                assert isinstance(item["prerequisite_of_topic_id"], (str, type(None)))
        finally:
            client.app.dependency_overrides.clear()
