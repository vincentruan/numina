"""Tests for self-directed learning: difficulty warning, age-appropriate topic, unmet prerequisites."""

from datetime import date

import pytest
from sqlalchemy.orm import Session

from apps.backend.app.schemas.learning import SessionCreate
from apps.backend.app.services.learning.progress_service import (
    AGE_GROUP_ORDER,
    _age_to_group,
    _compute_age,
    find_age_appropriate_topic,
    get_unmet_prerequisites,
)
from apps.backend.app.services.learning.session_service import (
    _build_difficulty_warning,
    create_session,
)
from packages.db.models.learning.assignment import LearningAssignment
from packages.db.models.learning.progress import LearningProgress
from packages.db.models.learning.topic import LearningDependency, LearningTopic

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def math_topic_mid(db: Session):
    """A mid-level mathematics topic."""
    t = LearningTopic(
        topic_key="mt_math_mid",
        topic_type="CONCEPTUAL",
        subject="mathematics",
        domain="Arithmetic",
        name="Mid Math",
        name_zh="中级数学",
        description="Mid-level math topic",
        age_group="mid",
        evidence_json="[]",
        standards_json="[]",
    )
    db.add(t)
    db.flush()
    return t


@pytest.fixture
def math_topic_high(db: Session):
    """A high-level mathematics topic (harder)."""
    t = LearningTopic(
        topic_key="mt_math_high",
        topic_type="CONCEPTUAL",
        subject="mathematics",
        domain="Algebra",
        name="High Math",
        name_zh="高级数学",
        description="High-level math topic",
        age_group="high",
        evidence_json="[]",
        standards_json="[]",
    )
    db.add(t)
    db.flush()
    return t


@pytest.fixture
def math_topic_low(db: Session):
    """A low-level mathematics topic (easier)."""
    t = LearningTopic(
        topic_key="mt_math_low",
        topic_type="CONCEPTUAL",
        subject="mathematics",
        domain="Counting",
        name="Low Math",
        name_zh="初级数学",
        description="Low-level math topic",
        age_group="low",
        evidence_json="[]",
        standards_json="[]",
    )
    db.add(t)
    db.flush()
    return t


@pytest.fixture
def prereq_topic(db: Session, math_topic_mid):
    """A topic that has math_topic_mid as a hard prerequisite."""
    t = LearningTopic(
        topic_key="mt_prereq_target",
        topic_type="CONCEPTUAL",
        subject="mathematics",
        domain="Advanced",
        name="Prereq Target",
        name_zh="前置目标",
        description="Requires mid math",
        age_group="mid",
        evidence_json="[]",
        standards_json="[]",
    )
    db.add(t)
    db.flush()
    dep = LearningDependency(
        topic_id=t.id,
        prerequisite_id=math_topic_mid.id,
        strength="hard",
    )
    db.add(dep)
    db.flush()
    return t


@pytest.fixture
def child_with_birthday(client, auth_headers, db: Session):
    """Create a child user with a known birthday (age ~9 -> mid group)."""
    resp = client.post(
        "/api/v1/family/children",
        headers=auth_headers,
        json={
            "username": "diffchild",
            "password": "ChildPass1",
            "display_name": "Diff Learner",
            "avatar_color": "#FF5733",
            "pin": ["🐱", "🌟", "🎈", "🐶"],
        },
    )
    assert resp.status_code == 201
    child_data = resp.json()["data"]
    child_id = int(child_data["id"])

    # Set birthday to make child ~9 years old (mid group)
    from packages.db.models.user import User

    child_user = db.query(User).filter(User.id == child_id).first()
    today = date.today()
    child_user.birthday = date(today.year - 9, today.month, today.day)
    db.flush()
    return {"id": child_id}


@pytest.fixture
def young_child(client, auth_headers, db: Session):
    """Create a child user with a young birthday (age ~6 -> low group)."""
    resp = client.post(
        "/api/v1/family/children",
        headers=auth_headers,
        json={
            "username": "youngchild",
            "password": "ChildPass1",
            "display_name": "Young Learner",
            "avatar_color": "#33FF57",
            "pin": ["🐱", "🌟", "🎈", "🐶"],
        },
    )
    assert resp.status_code == 201
    child_data = resp.json()["data"]
    child_id = int(child_data["id"])

    from packages.db.models.user import User

    child_user = db.query(User).filter(User.id == child_id).first()
    today = date.today()
    child_user.birthday = date(today.year - 6, today.month, today.day)
    db.flush()
    return {"id": child_id}


# ---------------------------------------------------------------------------
# Tests: _compute_age / _age_to_group / AGE_GROUP_ORDER
# ---------------------------------------------------------------------------


class TestAgeHelpers:
    def test_compute_age(self):
        today = date.today()
        birthday = date(today.year - 10, today.month, today.day)
        assert _compute_age(birthday) == 10

    def test_compute_age_before_birthday_this_year(self):
        today = date.today()
        # Birthday later this year -> age is one less
        birthday = date(today.year - 10, 12, 31)
        if (today.month, today.day) < (12, 31):
            assert _compute_age(birthday) == 9
        else:
            assert _compute_age(birthday) == 10

    def test_age_to_group(self):
        assert _age_to_group(5) == "low"
        assert _age_to_group(7) == "low"
        assert _age_to_group(8) == "mid"
        assert _age_to_group(10) == "mid"
        assert _age_to_group(11) == "high"
        assert _age_to_group(15) == "high"

    def test_age_group_order(self):
        assert AGE_GROUP_ORDER["low"] < AGE_GROUP_ORDER["mid"]
        assert AGE_GROUP_ORDER["mid"] < AGE_GROUP_ORDER["high"]


# ---------------------------------------------------------------------------
# Tests: find_age_appropriate_topic
# ---------------------------------------------------------------------------


class TestFindAgeAppropriateTopic:
    def test_returns_topic_same_subject_and_age_group(
        self, db, child_with_birthday, math_topic_mid
    ):
        """Child is mid (age 9), topic is mid -> should find it."""
        # Create progress so the topic shows up as available
        p = LearningProgress(
            child_id=child_with_birthday["id"],
            topic_id=math_topic_mid.id,
            mastery_level="available",
        )
        db.add(p)
        db.flush()

        result = find_age_appropriate_topic(db, child_with_birthday["id"], "mathematics")
        assert result is not None
        assert result.subject == "mathematics"
        assert result.age_group == "mid"

    def test_returns_none_for_unknown_subject(self, db, child_with_birthday):
        result = find_age_appropriate_topic(db, child_with_birthday["id"], "nonexistent")
        assert result is None

    def test_fallback_to_any_topic_at_age_group(
        self, db, young_child, math_topic_low
    ):
        """Young child (low) with no progress -> fallback to any non-deprecated low topic."""
        result = find_age_appropriate_topic(db, young_child["id"], "mathematics")
        assert result is not None
        assert result.age_group == "low"


# ---------------------------------------------------------------------------
# Tests: get_unmet_prerequisites
# ---------------------------------------------------------------------------


class TestGetUnmetPrerequisites:
    def test_no_prereqs(self, db, child_with_birthday, math_topic_mid):
        """Topic with no dependencies -> no unmet prereqs."""
        result = get_unmet_prerequisites(db, math_topic_mid.id, child_with_birthday["id"])
        assert result == []

    def test_unmet_prereqs(self, db, child_with_birthday, prereq_topic, math_topic_mid):
        """Child hasn't mastered the prereq -> it shows as unmet."""
        result = get_unmet_prerequisites(db, prereq_topic.id, child_with_birthday["id"])
        assert len(result) == 1
        assert result[0].id == math_topic_mid.id

    def test_met_prereqs(self, db, child_with_birthday, prereq_topic, math_topic_mid):
        """Child has mastered the prereq -> no unmet prereqs."""
        p = LearningProgress(
            child_id=child_with_birthday["id"],
            topic_id=math_topic_mid.id,
            mastery_level="mastered",
        )
        db.add(p)
        db.flush()

        result = get_unmet_prerequisites(db, prereq_topic.id, child_with_birthday["id"])
        assert result == []


# ---------------------------------------------------------------------------
# Tests: _build_difficulty_warning
# ---------------------------------------------------------------------------


class TestBuildDifficultyWarning:
    def test_no_warning_when_age_matches(
        self, db, child_with_birthday, math_topic_mid
    ):
        """Child is mid, topic is mid, no prereqs -> no warning."""
        result = _build_difficulty_warning(db, child_with_birthday["id"], math_topic_mid)
        assert result is None

    def test_age_warning_when_topic_harder(
        self, db, young_child, math_topic_high
    ):
        """Young child (low) trying high topic -> age warning."""
        result = _build_difficulty_warning(db, young_child["id"], math_topic_high)
        assert result is not None
        assert result["type"] == "age"
        assert result["level"] == "high"
        assert result["child_level"] == "low"

    def test_prereq_warning_when_prereqs_unmet(
        self, db, child_with_birthday, prereq_topic, math_topic_mid
    ):
        """Child hasn't mastered prereq -> prerequisite warning."""
        result = _build_difficulty_warning(
            db, child_with_birthday["id"], prereq_topic
        )
        assert result is not None
        assert result["type"] == "prerequisite"
        assert result["unmet_count"] == 1


# ---------------------------------------------------------------------------
# Tests: Self-selected bypass in create_session
# ---------------------------------------------------------------------------


class TestSelfSelectedBypass:
    def test_locked_topic_unlocked_for_self_selected(
        self, db, child_with_birthday, math_topic_mid
    ):
        """Child can start a locked topic via self-selected bypass."""
        # Create locked progress
        p = LearningProgress(
            child_id=child_with_birthday["id"],
            topic_id=math_topic_mid.id,
            mastery_level="locked",
        )
        db.add(p)
        db.flush()

        req = SessionCreate(topic_id=math_topic_mid.id, session_type="tutorial")
        result = create_session(db, child_with_birthday["id"], req)

        assert result["id"] is not None
        assert result["child_id"] == child_with_birthday["id"]
        assert result["topic_id"] == math_topic_mid.id

        # Verify progress was transitioned to learning
        progress = (
            db.query(LearningProgress)
            .filter_by(
                child_id=child_with_birthday["id"],
                topic_id=math_topic_mid.id,
            )
            .first()
        )
        assert progress.mastery_level == "learning"

    def test_auto_creates_self_selected_assignment(
        self, db, child_with_birthday, math_topic_mid
    ):
        """When no assignment exists, a self_selected one is auto-created."""
        req = SessionCreate(topic_id=math_topic_mid.id)
        result = create_session(db, child_with_birthday["id"], req)

        assignment = (
            db.query(LearningAssignment)
            .filter(
                LearningAssignment.child_id == child_with_birthday["id"],
                LearningAssignment.topic_id == math_topic_mid.id,
                LearningAssignment.assignment_type == "self_selected",
            )
            .first()
        )
        assert assignment is not None
        assert result["assignment_id"] == assignment.id

    def test_reuses_existing_assignment(
        self, db, child_with_birthday, math_topic_mid
    ):
        """When an assignment already exists, it is reused."""
        from packages.db.models.user import User

        child = db.query(User).filter(User.id == child_with_birthday["id"]).first()
        existing = LearningAssignment(
            family_id=child.family_id,
            child_id=child_with_birthday["id"],
            topic_id=math_topic_mid.id,
            created_by=child_with_birthday["id"],
            assignment_type="parent_assigned",
            status="pending",
        )
        db.add(existing)
        db.flush()

        req = SessionCreate(topic_id=math_topic_mid.id)
        result = create_session(db, child_with_birthday["id"], req)
        assert result["assignment_id"] == existing.id

    def test_difficulty_warning_returned_in_response(
        self, db, young_child, math_topic_high
    ):
        """Young child starting high topic gets difficulty_warning in response."""
        req = SessionCreate(topic_id=math_topic_high.id)
        result = create_session(db, young_child["id"], req)
        assert result["difficulty_warning"] is not None
        assert result["difficulty_warning"]["type"] == "age"
