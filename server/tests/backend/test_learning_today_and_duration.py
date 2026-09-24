"""Tests for GET /child/learning/today and study duration aggregation (Areas A + E)."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from packages.db.models.learning.assignment import LearningAssignment
from packages.db.models.learning.progress import LearningProgress
from packages.db.models.learning.session import LearningSession
from packages.db.models.learning.topic import LearningDependency, LearningTopic
from tests.backend.conftest import child_login_two_phase


# ── helpers ──────────────────────────────────────────────────────────────

PIN = ["🐱", "🌟", "🎈", "🐶"]
CHILD_PASSWORD = "ChildPass1"


def _create_child(client, headers, username="durchild"):
    resp = client.post(
        "/api/v1/family/children",
        headers=headers,
        json={
            "username": username,
            "password": CHILD_PASSWORD,
            "display_name": "Duration Tester",
            "avatar_color": "#FF5733",
            "pin": PIN,
        },
    )
    assert resp.status_code == 201
    return resp.json()["data"]


def _create_topic(db: Session, topic_key: str = "dur_topic", name: str = "Dur Topic") -> LearningTopic:
    t = LearningTopic(
        topic_key=topic_key,
        topic_type="CONCEPTUAL",
        subject="mathematics",
        domain="Test",
        name=name,
        description="Test topic",
        age_group="mid",
        evidence_json="[]",
        standards_json="[]",
    )
    db.add(t)
    db.flush()
    return t


def _child_login(client, username: str):
    """Two-phase child login — returns Bearer headers dict."""
    token = child_login_two_phase(client, username, CHILD_PASSWORD, PIN)
    return {"Authorization": f"Bearer {token}"}


# ── Area E: study duration aggregation ───────────────────────────────────


def test_progress_schema_has_study_minutes(
    client, db: Session, auth_headers,
):
    """ChildProgressOverview returns total_study_minutes and today_study_minutes."""
    child = _create_child(client, auth_headers)
    child_headers = _child_login(client, child["username"])

    resp = client.get("/api/v1/child/learning/progress", headers=child_headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "total_study_minutes" in data
    assert "today_study_minutes" in data
    # No sessions yet → both should be 0
    assert data["total_study_minutes"] == 0
    assert data["today_study_minutes"] == 0


def test_progress_study_minutes_aggregation(
    client, db: Session, auth_headers,
):
    """Sessions contribute to total and today study minutes."""
    child = _create_child(client, auth_headers, username="aggchild")
    child_headers = _child_login(client, child["username"])
    child_id = int(child["id"])

    topic = _create_topic(db, "agg_topic")

    now = datetime.now(UTC)
    # Two sessions: one today, one yesterday
    s1 = LearningSession(
        child_id=child_id, topic_id=topic.id,
        session_type="tutorial", duration_seconds=600,
        started_at=now - timedelta(hours=2), ended_at=now - timedelta(hours=1),
    )
    s2 = LearningSession(
        child_id=child_id, topic_id=topic.id,
        session_type="tutorial", duration_seconds=300,
        started_at=now - timedelta(days=1, hours=2),
        ended_at=now - timedelta(days=1, hours=1),
    )
    db.add_all([s1, s2])
    db.commit()

    resp = client.get("/api/v1/child/learning/progress", headers=child_headers)
    data = resp.json()["data"]
    assert data["total_study_minutes"] == 15  # (600+300)//60
    assert data["today_study_minutes"] == 10  # 600//60


def test_progress_study_minutes_null_ended_at_excluded(
    client, db: Session, auth_headers,
):
    """Sessions with ended_at=None are excluded from aggregation."""
    child = _create_child(client, auth_headers, username="nulchild")
    child_headers = _child_login(client, child["username"])
    child_id = int(child["id"])

    topic = _create_topic(db, "null_topic")

    # Active session — no ended_at
    s = LearningSession(
        child_id=child_id, topic_id=topic.id,
        session_type="tutorial", duration_seconds=999,
        started_at=datetime.now(UTC), ended_at=None,
    )
    db.add(s)
    db.commit()

    resp = client.get("/api/v1/child/learning/progress", headers=child_headers)
    data = resp.json()["data"]
    assert data["total_study_minutes"] == 0
    assert data["today_study_minutes"] == 0


# ── Area A: /today endpoint ─────────────────────────────────────────────


def test_today_study_minutes_zero_when_no_sessions(
    client, db: Session, auth_headers,
):
    """study_minutes_today is 0 (not null) when child has no sessions."""
    child = _create_child(client, auth_headers, username="zerchild")
    child_headers = _child_login(client, child["username"])

    resp = client.get("/api/v1/child/learning/today", headers=child_headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["study_minutes_today"] == 0
    assert data["current_topic"] is None
    assert data["pending_assignment"] is None
    assert data["recommended_topic"] is None


def test_today_returns_current_topic(
    client, db: Session, auth_headers,
):
    """current_topic returns the most recently updated 'learning' progress."""
    child = _create_child(client, auth_headers, username="curchild")
    child_headers = _child_login(client, child["username"])
    child_id = int(child["id"])

    t1 = _create_topic(db, "cur_t1", "Topic One")
    t2 = _create_topic(db, "cur_t2", "Topic Two")

    p1 = LearningProgress(child_id=child_id, topic_id=t1.id, mastery_level="learning")
    p2 = LearningProgress(child_id=child_id, topic_id=t2.id, mastery_level="learning")
    db.add_all([p1, p2])
    db.commit()
    # Force p1 to have a later updated_at
    p1.updated_at = datetime.now(UTC)
    db.commit()

    resp = client.get("/api/v1/child/learning/today", headers=child_headers)
    data = resp.json()["data"]
    assert data["current_topic"] is not None
    assert data["current_topic"]["id"] == str(t1.id)


def test_today_returns_pending_assignment(
    client, db: Session, auth_headers,
):
    """pending_assignment takes priority over current_topic."""
    child = _create_child(client, auth_headers, username="pendchild")
    child_headers = _child_login(client, child["username"])
    child_id = int(child["id"])

    topic = _create_topic(db, "pend_topic")
    # Create a progress so the child has learning context
    p = LearningProgress(child_id=child_id, topic_id=topic.id, mastery_level="learning")
    db.add(p)

    # Get family_id from parent's /me endpoint
    me_resp = client.get("/api/v1/auth/me", headers=auth_headers)
    me_data = me_resp.json()["data"]
    family_id = int(me_data["family_id"])
    parent_id = int(me_data["id"])

    assignment = LearningAssignment(
        family_id=family_id,
        child_id=child_id,
        topic_id=topic.id,
        created_by=parent_id,
        assignment_type="parent_assigned",
        status="pending",
        priority=0,
    )
    db.add(assignment)
    db.commit()

    resp = client.get("/api/v1/child/learning/today", headers=child_headers)
    data = resp.json()["data"]
    assert data["pending_assignment"] is not None
    assert data["pending_assignment"]["topic"]["id"] == str(topic.id)


def test_today_deterministic_ordering(
    client, db: Session, auth_headers,
):
    """Multiple 'learning' progresses → current_topic returns most recently updated."""
    child = _create_child(client, auth_headers, username="detchild")
    child_headers = _child_login(client, child["username"])
    child_id = int(child["id"])

    topics = [_create_topic(db, f"det_t{i}", f"Det Topic {i}") for i in range(3)]
    progresses = [
        LearningProgress(child_id=child_id, topic_id=t.id, mastery_level="learning")
        for t in topics
    ]
    db.add_all(progresses)
    db.commit()

    # Set the SECOND topic as most recently updated
    progresses[1].updated_at = datetime.now(UTC) + timedelta(seconds=10)
    db.commit()

    resp = client.get("/api/v1/child/learning/today", headers=child_headers)
    data = resp.json()["data"]
    assert data["current_topic"]["id"] == str(topics[1].id)


# ── recommended_topic ────────────────────────────────────────────────────


def test_today_recommended_topic_prereqs_met(
    client, db: Session, auth_headers,
):
    """recommended_topic returns a locked topic when all hard prereqs are mastered."""
    child = _create_child(client, auth_headers, username="recchild")
    child_headers = _child_login(client, child["username"])
    child_id = int(child["id"])

    prereq = _create_topic(db, "rec_prereq", "Prereq Topic")
    target = _create_topic(db, "rec_target", "Target Topic")

    # Prereq is mastered
    db.add(LearningProgress(child_id=child_id, topic_id=prereq.id, mastery_level="mastered"))
    # Target is locked
    db.add(LearningProgress(child_id=child_id, topic_id=target.id, mastery_level="locked"))
    # Hard dependency: target requires prereq
    db.add(LearningDependency(
        topic_id=target.id, prerequisite_id=prereq.id, strength="hard",
    ))
    db.commit()

    resp = client.get("/api/v1/child/learning/today", headers=child_headers)
    data = resp.json()["data"]
    assert data["recommended_topic"] is not None
    assert data["recommended_topic"]["id"] == str(target.id)


def test_today_recommended_topic_prereqs_not_met(
    client, db: Session, auth_headers,
):
    """recommended_topic is None when locked topic's hard prereqs are not mastered."""
    child = _create_child(client, auth_headers, username="norechild")
    child_headers = _child_login(client, child["username"])
    child_id = int(child["id"])

    prereq = _create_topic(db, "nore_prereq", "Unmet Prereq")
    target = _create_topic(db, "nore_target", "Locked Target")

    # Prereq is available (not mastered)
    db.add(LearningProgress(child_id=child_id, topic_id=prereq.id, mastery_level="available"))
    # Target is locked
    db.add(LearningProgress(child_id=child_id, topic_id=target.id, mastery_level="locked"))
    # Hard dependency: target requires prereq
    db.add(LearningDependency(
        topic_id=target.id, prerequisite_id=prereq.id, strength="hard",
    ))
    db.commit()

    resp = client.get("/api/v1/child/learning/today", headers=child_headers)
    data = resp.json()["data"]
    assert data["recommended_topic"] is None
