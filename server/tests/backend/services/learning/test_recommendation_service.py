"""Tests for recommendation engine: breakpoint, curriculum gap, review detection, and merged path."""

from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from apps.backend.app.services.learning.recommendation_service import (
    generate_recommendation_path,
)
from apps.backend.app.services.learning.zone_service import (
    find_breakpoint_topics,
    find_curriculum_gap_topics,
    find_review_due_topics,
)
from packages.db.models.learning.progress import LearningProgress
from packages.db.models.learning.topic import LearningDependency, LearningTopic
from packages.db.models.user import User

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def child_user(db: Session, client, auth_headers):
    """Create a child via API with a birthday that maps to age_group='mid' (9yo in 2026)."""
    resp = client.post(
        "/api/v1/family/children",
        headers=auth_headers,
        json={
            "username": "recchild",
            "password": "ChildPass1",
            "display_name": "Rec Kid",
            "avatar_color": "#FF5733",
            "pin": ["🐱", "🌟", "🎈", "🐶"],
        },
    )
    assert resp.status_code == 201
    child_id = int(resp.json()["data"]["id"])
    child = db.query(User).filter(User.id == child_id).first()
    child.birthday = date(2017, 1, 1)  # ~9yo → mid
    db.flush()
    return {"id": child_id}


def _make_topic(db, *, key, age_group="mid", centrality=50.0, curriculum="[]", **kw):
    t = LearningTopic(
        topic_key=key,
        topic_type=kw.get("topic_type", "CONCEPTUAL"),
        subject=kw.get("subject", "mathematics"),
        domain=kw.get("domain", "Test"),
        name=kw.get("name", f"Topic {key}"),
        name_zh=kw.get("name_zh"),
        description="Test topic",
        age_group=age_group,
        centrality=centrality,
        evidence_json="[]",
        standards_json="[]",
        curriculum_standards_json=curriculum,
    )
    db.add(t)
    db.flush()
    return t


def _make_progress(db, child_id, topic_id, mastery="mastered", **kw):
    p = LearningProgress(
        child_id=child_id,
        topic_id=topic_id,
        mastery_level=mastery,
        **kw,
    )
    db.add(p)
    db.flush()
    return p


# -- Breakpoint fixtures --

@pytest.fixture
def topic_graph(db: Session, child_user):
    """A --hard--> B. Child mastered A, B not mastered => B is breakpoint."""
    cid = child_user["id"]
    a = _make_topic(db, key="bp_a", name="Topic A", centrality=10.0)
    b = _make_topic(db, key="bp_b", name="Topic B", centrality=20.0)
    dep = LearningDependency(topic_id=b.id, prerequisite_id=a.id, strength="hard")
    db.add(dep)
    _make_progress(db, cid, a.id, "mastered")
    # B has a progress record but not mastered
    _make_progress(db, cid, b.id, "available")
    db.flush()
    return {"a_id": a.id, "b_id": b.id}


@pytest.fixture
def soft_dep_graph(db: Session, child_user):
    """A --soft--> B. Soft deps are NOT breakpoints."""
    cid = child_user["id"]
    a = _make_topic(db, key="soft_a", name="SoftA", centrality=10.0)
    b = _make_topic(db, key="soft_b", name="SoftB", centrality=20.0)
    dep = LearningDependency(topic_id=b.id, prerequisite_id=a.id, strength="soft")
    db.add(dep)
    _make_progress(db, cid, a.id, "mastered")
    _make_progress(db, cid, b.id, "available")
    db.flush()


@pytest.fixture
def mastered_graph(db: Session, child_user):
    """A --hard--> B. Child mastered BOTH => no breakpoint."""
    cid = child_user["id"]
    a = _make_topic(db, key="mast_a", name="MastA", centrality=10.0)
    b = _make_topic(db, key="mast_b", name="MastB", centrality=20.0)
    dep = LearningDependency(topic_id=b.id, prerequisite_id=a.id, strength="hard")
    db.add(dep)
    _make_progress(db, cid, a.id, "mastered")
    _make_progress(db, cid, b.id, "mastered")
    db.flush()


# -- Curriculum gap fixtures --

@pytest.fixture
def age_topic(db: Session, child_user):
    """A mid-age topic with curriculum standards, not mastered."""
    cid = child_user["id"]
    t = _make_topic(
        db,
        key="curr_gap1",
        name="Curriculum Gap Topic",
        age_group="mid",
        centrality=80.0,
        curriculum='["CCSS.MATH.1"]',
    )
    _make_progress(db, cid, t.id, "available")
    db.flush()
    return {"id": t.id}


@pytest.fixture
def mastered_age_topic(db: Session, child_user):
    """A mid-age curriculum topic that IS mastered => excluded from gaps."""
    cid = child_user["id"]
    t = _make_topic(
        db,
        key="curr_mastered",
        name="Mastered Curriculum",
        age_group="mid",
        centrality=90.0,
        curriculum='["CCSS.MATH.2"]',
    )
    _make_progress(db, cid, t.id, "mastered")
    db.flush()
    return {"id": t.id}


@pytest.fixture
def multi_curriculum_topics(db: Session, child_user):
    """Multiple mid-age curriculum topics with different centralities."""
    cid = child_user["id"]
    topics = []
    for i, cent in enumerate([30.0, 70.0, 50.0]):
        t = _make_topic(
            db,
            key=f"multi_curr_{i}",
            name=f"Multi {i}",
            age_group="mid",
            centrality=cent,
            curriculum='["CCSS.MATH.X"]',
        )
        _make_progress(db, cid, t.id, "available")
        topics.append(t)
    db.flush()
    return topics


# -- Review due fixtures --

@pytest.fixture
def review_due_progress(db: Session, child_user):
    """Mastered topic with next_review_at in the past."""
    cid = child_user["id"]
    t = _make_topic(db, key="review_due", name="Review Due", centrality=60.0)
    past = datetime.now(UTC) - timedelta(days=5)
    _make_progress(db, cid, t.id, "mastered", next_review_at=past)
    db.flush()
    return {"topic_id": t.id, "next_review_at": past}


@pytest.fixture
def future_review_progress(db: Session, child_user):
    """Mastered topic with next_review_at in the future => not due."""
    cid = child_user["id"]
    t = _make_topic(db, key="review_future", name="Future Review", centrality=60.0)
    future = datetime.now(UTC) + timedelta(days=30)
    _make_progress(db, cid, t.id, "mastered", next_review_at=future)
    db.flush()


# -- Merged path fixtures --

@pytest.fixture
def mixed_graph(db: Session, child_user):
    """Breakpoint + curriculum gap + review due in one child."""
    cid = child_user["id"]
    # Topic A mastered
    a = _make_topic(db, key="mix_a", name="Mastered A", centrality=10.0)
    # Topic B: hard prereq of A (B is a dependent topic where A is hard prereq)
    # Actually: A is mastered, A --hard--> B (B depends on A), but B is not mastered
    # That makes B a breakpoint.
    b = _make_topic(
        db, key="mix_b", name="Breakpoint B", age_group="mid",
        centrality=80.0, curriculum='["CCSS.1"]',
    )
    dep = LearningDependency(topic_id=b.id, prerequisite_id=a.id, strength="hard")
    db.add(dep)
    _make_progress(db, cid, a.id, "mastered")
    _make_progress(db, cid, b.id, "available")
    # Topic C: curriculum gap only (no dependency)
    c = _make_topic(
        db, key="mix_c", name="Gap C", age_group="mid",
        centrality=40.0, curriculum='["CCSS.2"]',
    )
    _make_progress(db, cid, c.id, "available")
    # Topic D: review due
    d = _make_topic(db, key="mix_d", name="Review D", centrality=30.0)
    past = datetime.now(UTC) - timedelta(days=10)
    _make_progress(db, cid, d.id, "mastered", next_review_at=past)
    db.flush()


@pytest.fixture
def overlap_graph(db: Session, child_user):
    """Topic that is both a breakpoint AND a curriculum gap."""
    cid = child_user["id"]
    a = _make_topic(db, key="ov_a", name="Mastered A", centrality=10.0)
    # B is both a breakpoint (hard prereq gap from A) AND a curriculum gap
    b = _make_topic(
        db, key="ov_b", name="Overlap B", age_group="mid",
        centrality=70.0, curriculum='["CCSS.X"]',
    )
    dep = LearningDependency(topic_id=b.id, prerequisite_id=a.id, strength="hard")
    db.add(dep)
    _make_progress(db, cid, a.id, "mastered")
    _make_progress(db, cid, b.id, "available")
    db.flush()


@pytest.fixture
def prereq_graph(db: Session, child_user):
    """Topics with varying prereq-met status."""
    cid = child_user["id"]
    # A mastered
    a = _make_topic(db, key="pr_a", name="Prereq A", centrality=10.0)
    _make_progress(db, cid, a.id, "mastered")
    # B: curriculum gap, hard prereq A (mastered) => prerequisites_met=True
    b = _make_topic(
        db, key="pr_b", name="Prereq B", age_group="mid",
        centrality=50.0, curriculum='["CCSS.1"]',
    )
    dep_b = LearningDependency(topic_id=b.id, prerequisite_id=a.id, strength="hard")
    db.add(dep_b)
    _make_progress(db, cid, b.id, "available")
    # C: curriculum gap, hard prereq X (NOT mastered) => prerequisites_met=False
    x = _make_topic(db, key="pr_x", name="Unmet X", centrality=5.0)
    c = _make_topic(
        db, key="pr_c", name="Prereq C", age_group="mid",
        centrality=60.0, curriculum='["CCSS.2"]',
    )
    dep_c = LearningDependency(topic_id=c.id, prerequisite_id=x.id, strength="hard")
    db.add(dep_c)
    _make_progress(db, cid, c.id, "available")
    db.flush()


# ---------------------------------------------------------------------------
# Tests: find_breakpoint_topics
# ---------------------------------------------------------------------------

class TestFindBreakpointTopics:
    def test_returns_hard_prereqs_not_mastered(self, db: Session, child_user, topic_graph):
        """Child mastered A, A --hard--> B (not mastered) => B is breakpoint."""
        result = find_breakpoint_topics(db, child_user["id"])
        assert len(result) == 1
        assert result[0].topic_id == topic_graph["b_id"]
        assert "知识断点" in result[0].reasons

    def test_excludes_soft_dependency_gaps(self, db: Session, child_user, soft_dep_graph):
        """Soft dependency gaps are NOT breakpoints."""
        result = find_breakpoint_topics(db, child_user["id"])
        assert len(result) == 0

    def test_excludes_already_mastered_prereqs(self, db: Session, child_user, mastered_graph):
        """If child already mastered the dependent topic, no breakpoint."""
        result = find_breakpoint_topics(db, child_user["id"])
        assert len(result) == 0

    def test_empty_when_no_progress(self, db: Session, child_user, topic_graph):
        """No mastered topics => no breakpoints to find."""
        # Query with a non-existent child_id — no progress records at all
        result = find_breakpoint_topics(db, child_user["id"] + 88888)
        assert result == []


# ---------------------------------------------------------------------------
# Tests: find_curriculum_gap_topics
# ---------------------------------------------------------------------------

class TestFindCurriculumGapTopics:
    def test_returns_age_appropriate_unmastered(self, db: Session, child_user, age_topic):
        """Topic matching child's age_group with curriculum_standards, not mastered => gap."""
        result = find_curriculum_gap_topics(db, child_user["id"])
        assert len(result) >= 1
        assert any(t.topic_id == age_topic["id"] for t in result)
        assert "课标必会" in result[0].reasons

    def test_excludes_mastered_topics(self, db: Session, child_user, mastered_age_topic):
        """Already-mastered topics are excluded even if curriculum-matching."""
        result = find_curriculum_gap_topics(db, child_user["id"])
        assert all(t.topic_id != mastered_age_topic["id"] for t in result)

    def test_sorted_by_centrality(self, db: Session, child_user, multi_curriculum_topics):
        """Higher centrality topics come first."""
        result = find_curriculum_gap_topics(db, child_user["id"])
        centrality_values = [t.centrality for t in result]
        assert centrality_values == sorted(centrality_values, reverse=True)


# ---------------------------------------------------------------------------
# Tests: find_review_due_topics
# ---------------------------------------------------------------------------

class TestFindReviewDueTopics:
    def test_returns_mastered_past_review_date(self, db: Session, child_user, review_due_progress):
        """Mastered topic with next_review_at <= now => review due."""
        result = find_review_due_topics(db, child_user["id"])
        assert len(result) == 1
        assert result[0].topic_id == review_due_progress["topic_id"]
        assert "需要复习" in result[0].reasons

    def test_excludes_future_review(self, db: Session, child_user, future_review_progress):
        """Mastered topic with next_review_at > now => not due."""
        result = find_review_due_topics(db, child_user["id"])
        assert len(result) == 0


# ---------------------------------------------------------------------------
# Tests: generate_recommendation_path
# ---------------------------------------------------------------------------

class TestGenerateRecommendationPath:
    def test_breakpoint_sorted_first(self, db: Session, child_user, mixed_graph):
        """Breakpoints appear before curriculum-only gaps in the merged path."""
        path = generate_recommendation_path(db, child_user["id"])
        reasons_list = [t.reasons for t in path.topics]
        # Find first breakpoint position and first curriculum-only position
        first_bp = next(
            (i for i, r in enumerate(reasons_list) if "知识断点" in r),
            len(reasons_list),
        )
        first_gap_only = next(
            (i for i, r in enumerate(reasons_list) if r == ["课标必会"]),
            len(reasons_list),
        )
        assert first_bp < first_gap_only

    def test_merges_labels_for_same_topic(self, db: Session, child_user, overlap_graph):
        """Topic that is both breakpoint AND curriculum gap gets both labels."""
        path = generate_recommendation_path(db, child_user["id"])
        overlap = [t for t in path.topics if len(t.reasons) > 1]
        assert len(overlap) >= 1
        assert "知识断点" in overlap[0].reasons
        assert "课标必会" in overlap[0].reasons

    def test_empty_for_child_with_no_data(self, db: Session, child_user):
        """Child with no progress and no topics => empty path."""
        path = generate_recommendation_path(db, child_user["id"])
        assert path.topics == []
        assert path.total_count == 0

    def test_prerequisites_met_flag(self, db: Session, child_user, prereq_graph):
        """Topics whose all hard prereqs are mastered have prerequisites_met=True."""
        path = generate_recommendation_path(db, child_user["id"])
        # Build lookup
        by_name = {t.topic_name: t for t in path.topics}
        # B's hard prereq A is mastered => prerequisites_met=True
        assert by_name["Prereq B"].prerequisites_met is True
        # C's hard prereq X is NOT mastered => prerequisites_met=False
        assert by_name["Prereq C"].prerequisites_met is False

    def test_suggested_position_is_sequential(self, db: Session, child_user, mixed_graph):
        """suggested_position is 1-based sequential index."""
        path = generate_recommendation_path(db, child_user["id"])
        positions = [t.suggested_position for t in path.topics]
        assert positions == list(range(1, len(path.topics) + 1))

    def test_path_name(self, db: Session, child_user, mixed_graph):
        """Path has the expected name."""
        path = generate_recommendation_path(db, child_user["id"])
        assert path.name == "建议学习路径"
