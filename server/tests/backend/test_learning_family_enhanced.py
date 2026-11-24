"""Tests for enhanced parent learning endpoints (U8)."""

import pytest
from sqlalchemy.orm import Session

from packages.db.models.learning.progress import LearningProgress
from packages.db.models.learning.session import LearningSession
from packages.db.models.learning.stats import ChildLearningStats
from packages.db.models.learning.topic import LearningTopic


@pytest.fixture
def parent_children_family(db: Session, client, auth_headers):
    """Create parent auth + two children with stats via API."""
    from packages.db.models.user import User

    # Create two children
    child_ids = []
    for name in ["Kid1", "Kid2"]:
        resp = client.post(
            "/api/v1/family/children",
            headers=auth_headers,
            json={
                "username": f"u8child_{name}",
                "password": "ChildPass1",
                "display_name": name,
                "avatar_color": "#FF5733",
                "pin": ["🐱", "🌟", "🎈", "🐶"],
            },
        )
        assert resp.status_code == 201
        child_ids.append(int(resp.json()["data"]["id"]))

    # Add stats for first child
    child1 = db.query(User).filter(User.id == child_ids[0]).first()
    stats = ChildLearningStats(
        child_id=child_ids[0],
        family_id=child1.family_id,
        cumulative_xp=250,
        level=3,
        learning_streak_days=5,
    )
    db.add(stats)
    db.flush()

    return {"child_ids": child_ids, "client": client, "auth_headers": auth_headers}


@pytest.fixture
def topic_for_sessions(db: Session):
    """Create a topic for session tests."""
    t = LearningTopic(
        topic_key="u8_test_topic",
        topic_type="CONCEPTUAL",
        subject="mathematics",
        domain="Test",
        name="U8 Test Topic",
        name_zh="测试知识点",
        description="Test",
        age_group="mid",
        source_taxonomy="beijing",  # matches default user language (zh-CN)
        evidence_json="[]",
        standards_json="[]",
    )
    db.add(t)
    db.flush()
    return t


class TestListChildrenEnhanced:
    def test_includes_xp_level_streak(self, db: Session, parent_children_family):
        resp = parent_children_family["client"].get(
            "/api/v1/family/learning/children",
            headers=parent_children_family["auth_headers"],
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) >= 2

        # First child has stats
        child1_data = next(c for c in data if int(c["child_id"]) == parent_children_family["child_ids"][0])
        assert child1_data["cumulative_xp"] == 250
        assert child1_data["level"] == 3
        assert child1_data["learning_streak_days"] == 5

        # Second child has defaults
        child2_data = next(c for c in data if int(c["child_id"]) == parent_children_family["child_ids"][1])
        assert child2_data["cumulative_xp"] == 0
        assert child2_data["level"] == 1
        assert child2_data["learning_streak_days"] == 0


class TestChildSessionLog:
    def test_returns_session_history(
        self, db: Session, parent_children_family, topic_for_sessions
    ):
        from datetime import UTC, datetime

        child_id = parent_children_family["child_ids"][0]
        session = LearningSession(
            child_id=child_id,
            topic_id=topic_for_sessions.id,
            session_type="tutorial",
            started_at=datetime.now(UTC),
            duration_seconds=300,
            score=0.85,
        )
        db.add(session)
        db.flush()

        resp = parent_children_family["client"].get(
            f"/api/v1/family/learning/children/{child_id}/sessions",
            headers=parent_children_family["auth_headers"],
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) >= 1
        assert data[0]["topic_name"] == "U8 Test Topic"

    def test_rejects_cross_family_access(self, db: Session, parent_children_family):
        resp = parent_children_family["client"].get(
            "/api/v1/family/learning/children/9999999/sessions",
            headers=parent_children_family["auth_headers"],
        )
        assert resp.status_code in (400, 403, 404)


# === U1: Learning Stats Endpoint (TDD — proof-first) ===


@pytest.fixture
def child_of_another_family(client, second_user_headers):
    """Create a child in another family (for cross-family access tests)."""
    resp = client.post(
        "/api/v1/family/children",
        headers=second_user_headers,
        json={
            "username": "other_family_child",
            "password": "ChildPass1",
            "display_name": "Other Child",
            "avatar_color": "#123456",
            "pin": ["🐱", "🌟", "🎈", "🐶"],
        },
    )
    assert resp.status_code == 201
    return int(resp.json()["data"]["id"])


@pytest.fixture
def child_auth_headers(client, parent_children_family):
    """Auth headers for a child user (to test role-based access)."""
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": "u8child_Kid1", "password": "ChildPass1"},
    )
    assert resp.status_code == 200
    data = resp.json().get("data", resp.json())
    return {"Authorization": f"Bearer {data['access_token']}"}


@pytest.fixture
def learning_stats_topic(db: Session):
    """Create a topic for learning stats tests."""
    t = LearningTopic(
        topic_key="u1_stats_topic",
        topic_type="CONCEPTUAL",
        subject="mathematics",
        domain="Test",
        name="U1 Stats Topic",
        name_zh="测试统计知识点",
        description="Test",
        age_group="mid",
        source_taxonomy="beijing",
        evidence_json="[]",
        standards_json="[]",
    )
    db.add(t)
    db.flush()
    return t


class TestChildLearningStats:
    def test_returns_stats_with_xp_level_streak(
        self, db: Session, parent_children_family, learning_stats_topic
    ):
        """Child with stats and finished session returns correct aggregation."""
        from datetime import UTC, datetime, timedelta

        child_id = parent_children_family["child_ids"][0]
        
        # Add a finished learning session (900 seconds = 15 minutes)
        session = LearningSession(
            child_id=child_id,
            topic_id=learning_stats_topic.id,
            session_type="practice",
            started_at=datetime.now(UTC) - timedelta(hours=1),
            ended_at=datetime.now(UTC) - timedelta(minutes=50),
            duration_seconds=900,
        )
        db.add(session)
        db.flush()

        resp = parent_children_family["client"].get(
            f"/api/v1/family/learning/children/{child_id}/learning-stats",
            headers=parent_children_family["auth_headers"],
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        
        # Stats from fixture: XP 250, level 3, streak 5 days
        assert data["cumulative_xp"] == 250
        assert data["level"] == 3
        assert data["learning_streak_days"] == 5
        
        # Total study minutes from finished session
        assert data["total_study_minutes"] == 15
        
        # Level info should match get_level_info(3)
        assert data["level_emoji"] == "🌷"  # Bud emoji
        assert data["level_name_zh"] == "花蕾"
        assert data["level_name_en"] == "Bud"
        
        # Response ID fields are strings (Snowflake serialization)
        assert isinstance(data["child_id"], str)

    def test_creates_stats_for_child_without_existing(
        self, db: Session, parent_children_family
    ):
        """Child without stats row gets auto-created on first access."""
        child_id = parent_children_family["child_ids"][1]  # Second child has no stats

        resp = parent_children_family["client"].get(
            f"/api/v1/family/learning/children/{child_id}/learning-stats",
            headers=parent_children_family["auth_headers"],
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        
        # Defaults
        assert data["level"] == 1
        assert data["cumulative_xp"] == 0
        assert data["learning_streak_days"] == 0
        
        # Verify stats row was created
        stats = db.query(ChildLearningStats).filter_by(child_id=child_id).first()
        assert stats is not None

    def test_rejects_cross_family_child(
        self, db: Session, parent_children_family, child_of_another_family
    ):
        """Requesting stats for child from another family returns 404."""
        resp = parent_children_family["client"].get(
            f"/api/v1/family/learning/children/{child_of_another_family}/learning-stats",
            headers=parent_children_family["auth_headers"],
        )
        assert resp.status_code == 404
        # No stats row should be created
        stats = db.query(ChildLearningStats).filter_by(child_id=child_of_another_family).first()
        assert stats is None

    def test_rejects_nonexistent_child(
        self, db: Session, parent_children_family
    ):
        """Requesting stats for non-existent child returns 404."""
        resp = parent_children_family["client"].get(
            "/api/v1/family/learning/children/9999999/learning-stats",
            headers=parent_children_family["auth_headers"],
        )
        assert resp.status_code == 404

    def test_rejects_child_token(
        self, db: Session, parent_children_family, child_auth_headers
    ):
        """Child token cannot access stats endpoint."""
        child_id = parent_children_family["child_ids"][0]
        resp = parent_children_family["client"].get(
            f"/api/v1/family/learning/children/{child_id}/learning-stats",
            headers=child_auth_headers,
        )
        assert resp.status_code == 403

    def test_returns_null_next_level_at_max(
        self, db: Session, parent_children_family
    ):
        """Child at max level returns null for next_level fields."""
        child_id = parent_children_family["child_ids"][0]
        
        # Set stats to max level (7, XP >= 5000)
        stats = db.query(ChildLearningStats).filter_by(child_id=child_id).first()
        stats.level = 7
        stats.cumulative_xp = 6000
        db.flush()

        resp = parent_children_family["client"].get(
            f"/api/v1/family/learning/children/{child_id}/learning-stats",
            headers=parent_children_family["auth_headers"],
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        
        assert data["next_level_threshold"] is None
        assert data["next_level_name_zh"] is None

    def test_excludes_unfinished_sessions_from_minutes(
        self, db: Session, parent_children_family, learning_stats_topic
    ):
        """Sessions without ended_at don't count toward study minutes."""
        from datetime import UTC, datetime

        child_id = parent_children_family["child_ids"][0]

        # Create a finished session first (15 min)
        finished = LearningSession(
            child_id=child_id,
            topic_id=learning_stats_topic.id,
            session_type="practice",
            started_at=datetime.now(UTC),
            ended_at=datetime.now(UTC),
            duration_seconds=900,  # 15 min
        )
        db.add(finished)

        # Unfinished session (no ended_at)
        unfinished = LearningSession(
            child_id=child_id,
            topic_id=learning_stats_topic.id,
            session_type="practice",
            started_at=datetime.now(UTC),
            duration_seconds=600,  # 10 minutes
        )
        db.add(unfinished)
        db.flush()

        resp = parent_children_family["client"].get(
            f"/api/v1/family/learning/children/{child_id}/learning-stats",
            headers=parent_children_family["auth_headers"],
        )
        assert resp.status_code == 200
        data = resp.json()["data"]

        # Only finished session counts (15 min)
        assert data["total_study_minutes"] == 15

    def test_includes_progress_counts(
        self, db: Session, parent_children_family
    ):
        """Response includes mastered/learning/available/review counts."""
        child_id = parent_children_family["child_ids"][0]

        # Create separate topics for each mastery level (unique constraint on child_id + topic_id)
        topics = []
        for level in ["mastered", "learning", "review"]:
            t = LearningTopic(
                topic_key=f"u1_progress_{level}",
                topic_type="CONCEPTUAL",
                subject="mathematics",
                domain="Test",
                name=f"Progress {level}",
                name_zh=f"进度{level}",
                description="Test",
                age_group="mid",
                source_taxonomy="beijing",
                evidence_json="[]",
                standards_json="[]",
            )
            db.add(t)
            topics.append(t)
        db.flush()

        # Create progress rows with different mastery levels
        for topic, level in zip(topics, ["mastered", "learning", "review"], strict=True):
            p = LearningProgress(
                child_id=child_id,
                topic_id=topic.id,
                mastery_level=level,
            )
            db.add(p)
        db.flush()

        resp = parent_children_family["client"].get(
            f"/api/v1/family/learning/children/{child_id}/learning-stats",
            headers=parent_children_family["auth_headers"],
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        
        assert data["mastered_count"] >= 1
        assert data["learning_count"] >= 1
        assert data["review_count"] >= 1


# === U2: Weak Topics Endpoint (TDD — proof-first) ===


@pytest.fixture
def weak_topics_setup(db: Session, parent_children_family):
    """Create topics and practice attempts for weak topics tests."""
    from datetime import UTC, datetime

    from packages.db.models.learning.practice import PracticeSession

    child_id = parent_children_family["child_ids"][0]

    # Create 3 topics
    topics = []
    for key in ["weak_a", "weak_b", "weak_c"]:
        t = LearningTopic(
            topic_key=f"u2_{key}",
            topic_type="CONCEPTUAL",
            subject="mathematics",
            domain="Test",
            name=f"Weak Topic {key}",
            name_zh=f"薄弱知识点{key}",
            description="Test",
            age_group="mid",
            source_taxonomy="beijing",
            evidence_json="[]",
            standards_json="[]",
        )
        db.add(t)
        topics.append(t)
    db.flush()

    # Create a practice session to link attempts to
    session = PracticeSession(
        child_id=child_id,
        topic_id=topics[0].id,
        session_mode="practice",
        question_ids_json="[]",
        source="adaptive",
        started_at=datetime.now(UTC),
        ended_at=datetime.now(UTC),
    )
    db.add(session)
    db.flush()

    return {"child_id": child_id, "topics": topics, "session": session}


class TestWeakTopics:
    def test_returns_weak_topics_sorted_by_accuracy(
        self, db: Session, parent_children_family, weak_topics_setup
    ):
        """Weak topics are returned sorted by accuracy ascending."""
        from packages.db.models.learning.practice import PracticeAttempt

        child_id = weak_topics_setup["child_id"]
        topics = weak_topics_setup["topics"]
        session = weak_topics_setup["session"]

        # Topic A: 4 attempts, 1 correct (accuracy 0.25) — weak
        for i in range(4):
            db.add(PracticeAttempt(
                session_id=session.id,
                question_id=100 + i,
                child_id=child_id,
                topic_id=topics[0].id,
                user_answer_json="{}",
                is_correct=(i == 0),
                attempt_number=i + 1,
            ))

        # Topic B: 3 attempts, 2 correct (accuracy 0.667) — NOT weak (>= 0.6)
        for i in range(3):
            db.add(PracticeAttempt(
                session_id=session.id,
                question_id=200 + i,
                child_id=child_id,
                topic_id=topics[1].id,
                user_answer_json="{}",
                is_correct=(i < 2),
                attempt_number=i + 1,
            ))

        # Topic C: 3 attempts, 1 correct (accuracy 0.333) — weak
        for i in range(3):
            db.add(PracticeAttempt(
                session_id=session.id,
                question_id=300 + i,
                child_id=child_id,
                topic_id=topics[2].id,
                user_answer_json="{}",
                is_correct=(i == 0),
                attempt_number=i + 1,
            ))
        db.flush()

        resp = parent_children_family["client"].get(
            f"/api/v1/family/learning/children/{child_id}/weak-topics",
            headers=parent_children_family["auth_headers"],
        )
        assert resp.status_code == 200
        data = resp.json()["data"]

        # Should return 2 weak topics (A and C), sorted by accuracy ascending
        assert len(data) == 2
        assert data[0]["accuracy"] < data[1]["accuracy"]
        assert data[0]["accuracy"] == 0.25  # Topic A
        assert data[1]["accuracy"] == pytest.approx(0.333, rel=1e-2)  # Topic C

    def test_excludes_topics_with_high_accuracy(
        self, db: Session, parent_children_family, weak_topics_setup
    ):
        """Topics with accuracy >= 0.6 are not returned."""
        from packages.db.models.learning.practice import PracticeAttempt

        child_id = weak_topics_setup["child_id"]
        topics = weak_topics_setup["topics"]
        session = weak_topics_setup["session"]

        # Topic A: 3 attempts, all correct (accuracy 1.0) — NOT weak
        for i in range(3):
            db.add(PracticeAttempt(
                session_id=session.id,
                question_id=400 + i,
                child_id=child_id,
                topic_id=topics[0].id,
                user_answer_json="{}",
                is_correct=True,
                attempt_number=i + 1,
            ))
        db.flush()

        resp = parent_children_family["client"].get(
            f"/api/v1/family/learning/children/{child_id}/weak-topics",
            headers=parent_children_family["auth_headers"],
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 0

    def test_excludes_topics_with_few_attempts(
        self, db: Session, parent_children_family, weak_topics_setup
    ):
        """Topics with < 3 attempts are not returned."""
        from packages.db.models.learning.practice import PracticeAttempt

        child_id = weak_topics_setup["child_id"]
        topics = weak_topics_setup["topics"]
        session = weak_topics_setup["session"]

        # Topic A: 2 attempts, 0 correct (accuracy 0.0) — NOT weak (< 3 attempts)
        for i in range(2):
            db.add(PracticeAttempt(
                session_id=session.id,
                question_id=500 + i,
                child_id=child_id,
                topic_id=topics[0].id,
                user_answer_json="{}",
                is_correct=False,
                attempt_number=i + 1,
            ))
        db.flush()

        resp = parent_children_family["client"].get(
            f"/api/v1/family/learning/children/{child_id}/weak-topics",
            headers=parent_children_family["auth_headers"],
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 0

    def test_limits_to_10_topics(
        self, db: Session, parent_children_family
    ):
        """Returns at most 10 weak topics."""
        from datetime import UTC, datetime

        from packages.db.models.learning.practice import (
            PracticeAttempt,
            PracticeSession,
        )

        child_id = parent_children_family["child_ids"][0]

        # Create 12 topics with weak accuracy
        topics = []
        for i in range(12):
            t = LearningTopic(
                topic_key=f"u2_limit_{i}",
                topic_type="CONCEPTUAL",
                subject="mathematics",
                domain="Test",
                name=f"Limit Topic {i}",
                name_zh=f"限制知识点{i}",
                description="Test",
                age_group="mid",
                source_taxonomy="beijing",
                evidence_json="[]",
                standards_json="[]",
            )
            db.add(t)
            topics.append(t)
        db.flush()

        session = PracticeSession(
            child_id=child_id,
            topic_id=topics[0].id,
            session_mode="practice",
            question_ids_json="[]",
            source="adaptive",
            started_at=datetime.now(UTC),
            ended_at=datetime.now(UTC),
        )
        db.add(session)
        db.flush()

        # Create 3 weak attempts per topic
        for i, topic in enumerate(topics):
            for j in range(3):
                db.add(PracticeAttempt(
                    session_id=session.id,
                    question_id=6000 + i * 10 + j,
                    child_id=child_id,
                    topic_id=topic.id,
                    user_answer_json="{}",
                    is_correct=False,
                    attempt_number=j + 1,
                ))
        db.flush()

        resp = parent_children_family["client"].get(
            f"/api/v1/family/learning/children/{child_id}/weak-topics",
            headers=parent_children_family["auth_headers"],
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 10

    def test_returns_empty_when_no_weak_topics(
        self, db: Session, parent_children_family
    ):
        """Returns empty list when no weak topics exist."""
        child_id = parent_children_family["child_ids"][0]

        resp = parent_children_family["client"].get(
            f"/api/v1/family/learning/children/{child_id}/weak-topics",
            headers=parent_children_family["auth_headers"],
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 0

    def test_rejects_cross_family_access(
        self, db: Session, parent_children_family, child_of_another_family
    ):
        """Requesting weak topics for child from another family returns 404."""
        resp = parent_children_family["client"].get(
            f"/api/v1/family/learning/children/{child_of_another_family}/weak-topics",
            headers=parent_children_family["auth_headers"],
        )
        assert resp.status_code == 404

    def test_rejects_child_token(
        self, db: Session, parent_children_family, child_auth_headers
    ):
        """Child token cannot access weak topics endpoint."""
        child_id = parent_children_family["child_ids"][0]
        resp = parent_children_family["client"].get(
            f"/api/v1/family/learning/children/{child_id}/weak-topics",
            headers=child_auth_headers,
        )
        assert resp.status_code == 403

    def test_returns_ids_as_strings(
        self, db: Session, parent_children_family, weak_topics_setup
    ):
        """Response IDs are strings (SnowflakeBase serialization)."""
        from packages.db.models.learning.practice import PracticeAttempt

        child_id = weak_topics_setup["child_id"]
        topics = weak_topics_setup["topics"]
        session = weak_topics_setup["session"]

        # Create one weak topic
        for i in range(3):
            db.add(PracticeAttempt(
                session_id=session.id,
                question_id=700 + i,
                child_id=child_id,
                topic_id=topics[0].id,
                user_answer_json="{}",
                is_correct=False,
                attempt_number=i + 1,
            ))
        db.flush()

        resp = parent_children_family["client"].get(
            f"/api/v1/family/learning/children/{child_id}/weak-topics",
            headers=parent_children_family["auth_headers"],
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 1
        assert isinstance(data[0]["topic_id"], str)


# === U3: Practice Sessions Endpoint (TDD — proof-first) ===


@pytest.fixture
def practice_sessions_setup(db: Session, parent_children_family):
    """Create topics and practice sessions for sessions tests."""
    from datetime import UTC, datetime, timedelta

    from packages.db.models.learning.practice import PracticeSession

    child_id = parent_children_family["child_ids"][0]

    topic = LearningTopic(
        topic_key="u3_session_topic",
        topic_type="CONCEPTUAL",
        subject="mathematics",
        domain="Test",
        name="U3 Session Topic",
        name_zh="测试会话知识点",
        description="Test",
        age_group="mid",
        source_taxonomy="beijing",
        evidence_json="[]",
        standards_json="[]",
    )
    db.add(topic)
    db.flush()

    # Create 3 sessions with increasing start times
    now = datetime.now(UTC)
    sessions = []
    for i in range(3):
        s = PracticeSession(
            child_id=child_id,
            topic_id=topic.id,
            session_mode="practice",
            question_ids_json="[1,2,3,4,5]",
            source="adaptive",
            started_at=now - timedelta(hours=2 - i),
            ended_at=now - timedelta(hours=2 - i) + timedelta(minutes=10),
            total_score=0.6 + i * 0.1,
            completed_count=3 + i,
        )
        db.add(s)
        sessions.append(s)
    db.flush()

    return {"child_id": child_id, "topic": topic, "sessions": sessions}


class TestPracticeSessions:
    def test_returns_sessions_sorted_by_started_at_desc(
        self, db: Session, parent_children_family, practice_sessions_setup
    ):
        """Sessions are returned sorted by started_at descending."""
        child_id = practice_sessions_setup["child_id"]

        resp = parent_children_family["client"].get(
            f"/api/v1/family/learning/children/{child_id}/practice-sessions",
            headers=parent_children_family["auth_headers"],
        )
        assert resp.status_code == 200
        data = resp.json()["data"]

        assert len(data) == 3
        # Most recent first (started_at descending)
        assert data[0]["started_at"] > data[1]["started_at"]
        assert data[1]["started_at"] > data[2]["started_at"]

        # Verify field mappings
        assert data[0]["total_score"] == 0.8  # Most recent session (i=2)
        assert data[0]["completed_count"] == 5
        assert data[0]["total_count"] == 5  # From question_ids_json length

    def test_respects_limit_parameter(
        self, db: Session, parent_children_family, practice_sessions_setup
    ):
        """limit parameter restricts number of returned sessions."""
        child_id = practice_sessions_setup["child_id"]

        resp = parent_children_family["client"].get(
            f"/api/v1/family/learning/children/{child_id}/practice-sessions?limit=2",
            headers=parent_children_family["auth_headers"],
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 2

    def test_respects_offset_parameter(
        self, db: Session, parent_children_family, practice_sessions_setup
    ):
        """offset parameter skips the newest sessions."""
        child_id = practice_sessions_setup["child_id"]

        resp = parent_children_family["client"].get(
            f"/api/v1/family/learning/children/{child_id}/practice-sessions?offset=1&limit=2",
            headers=parent_children_family["auth_headers"],
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 2
        # Should skip the newest (i=2), return i=1 and i=0
        assert data[0]["completed_count"] == 4

    def test_returns_empty_when_no_sessions(
        self, db: Session, parent_children_family
    ):
        """Returns empty list when no sessions exist."""
        child_id = parent_children_family["child_ids"][0]

        resp = parent_children_family["client"].get(
            f"/api/v1/family/learning/children/{child_id}/practice-sessions",
            headers=parent_children_family["auth_headers"],
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 0

    def test_returns_empty_topic_name_when_topic_missing(
        self, db: Session, parent_children_family
    ):
        """When topic doesn't exist, topic_name is empty string."""
        from datetime import UTC, datetime

        from packages.db.models.learning.practice import PracticeSession

        child_id = parent_children_family["child_ids"][0]

        session = PracticeSession(
            child_id=child_id,
            topic_id=99999999,  # Non-existent topic
            session_mode="practice",
            question_ids_json="[1,2]",
            source="adaptive",
            started_at=datetime.now(UTC),
            ended_at=datetime.now(UTC),
        )
        db.add(session)
        db.flush()

        resp = parent_children_family["client"].get(
            f"/api/v1/family/learning/children/{child_id}/practice-sessions",
            headers=parent_children_family["auth_headers"],
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 1
        assert data[0]["topic_name"] == ""
        assert data[0]["topic_name_zh"] is None

    def test_does_not_include_other_child_sessions(
        self, db: Session, parent_children_family, practice_sessions_setup
    ):
        """Sessions for a different child are not returned."""
        other_child_id = parent_children_family["child_ids"][1]

        resp = parent_children_family["client"].get(
            f"/api/v1/family/learning/children/{other_child_id}/practice-sessions",
            headers=parent_children_family["auth_headers"],
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 0  # Other child has no sessions

    def test_returns_ids_as_strings(
        self, db: Session, parent_children_family, practice_sessions_setup
    ):
        """Response IDs are strings (SnowflakeBase serialization)."""
        child_id = practice_sessions_setup["child_id"]

        resp = parent_children_family["client"].get(
            f"/api/v1/family/learning/children/{child_id}/practice-sessions",
            headers=parent_children_family["auth_headers"],
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) > 0
        assert isinstance(data[0]["session_id"], str)
        assert isinstance(data[0]["topic_id"], str)

    def test_rejects_cross_family_access(
        self, db: Session, parent_children_family, child_of_another_family
    ):
        """Requesting sessions for child from another family returns 404."""
        resp = parent_children_family["client"].get(
            f"/api/v1/family/learning/children/{child_of_another_family}/practice-sessions",
            headers=parent_children_family["auth_headers"],
        )
        assert resp.status_code == 404

    def test_rejects_child_token(
        self, db: Session, parent_children_family, child_auth_headers
    ):
        """Child token cannot access practice sessions endpoint."""
        child_id = parent_children_family["child_ids"][0]
        resp = parent_children_family["client"].get(
            f"/api/v1/family/learning/children/{child_id}/practice-sessions",
            headers=child_auth_headers,
        )
        assert resp.status_code == 403


# === U6: ID serialization contract across all three endpoints ===


class TestIdSerializationContract:
    """Every ID field on the three new endpoints is a JSON string."""

    @pytest.mark.parametrize(
        ("path_suffix", "id_fields"),
        [
            ("learning-stats", ["child_id"]),
            ("weak-topics", ["topic_id"]),
            ("practice-sessions", ["session_id", "topic_id"]),
        ],
    )
    def test_ids_are_strings(
        self,
        db: Session,
        parent_children_family,
        weak_topics_setup,
        practice_sessions_setup,
        path_suffix,
        id_fields,
    ):
        # Both fixtures share the same first child, so each endpoint has rows
        # to serialize rather than returning an empty list.
        child_id = parent_children_family["child_ids"][0]

        # Give weak-topics at least one qualifying row.
        from packages.db.models.learning.practice import PracticeAttempt

        session_id = practice_sessions_setup["sessions"][0].id
        for i in range(3):
            db.add(
                PracticeAttempt(
                    session_id=session_id,
                    question_id=8000 + i,
                    child_id=child_id,
                    topic_id=weak_topics_setup["topics"][0].id,
                    user_answer_json="{}",
                    is_correct=False,
                    attempt_number=i + 1,
                )
            )
        db.flush()

        resp = parent_children_family["client"].get(
            f"/api/v1/family/learning/children/{child_id}/{path_suffix}",
            headers=parent_children_family["auth_headers"],
        )
        assert resp.status_code == 200

        body = resp.json()["data"]
        rows = body if isinstance(body, list) else [body]
        assert rows, f"{path_suffix} returned no rows to check"
        for row in rows:
            for field in id_fields:
                assert isinstance(row[field], str), f"{path_suffix}.{field} is not a str"
