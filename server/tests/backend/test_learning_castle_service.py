"""Tests for castle_service — scope, towers/floors, windows (U1)."""

from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from apps.backend.app.services.learning.castle_service import (
    MAX_REVIEW_DUE_WINDOWS,
    MAX_TOTAL_WINDOWS,
    get_castle_index,
)
from packages.db.models.learning.progress import LearningProgress
from packages.db.models.learning.topic import LearningTopic

PIN = ["🐱", "🌟", "🎈", "🐶"]
CHILD_PASSWORD = "ChildPass1"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_topic(
    db: Session,
    *,
    key: str,
    subject: str,
    domain: str,
    age_range_start: int = 6,
    age_range_end: int = 10,
    age_group: str = "mid",
    source_taxonomy: str = "os-taxonomy",
    centrality: float = 50.0,
) -> LearningTopic:
    t = LearningTopic(
        topic_key=key,
        topic_type="CONCEPTUAL",
        subject=subject,
        domain=domain,
        name=key,
        name_zh=f"中文{key}",
        description="",
        age_range_start=age_range_start,
        age_range_end=age_range_end,
        age_group=age_group,
        centrality=centrality,
        source_taxonomy=source_taxonomy,
        evidence_json="[]",
        standards_json="[]",
    )
    db.add(t)
    db.flush()
    return t


def _make_progress(
    db: Session,
    *,
    child_id: int,
    topic_id: int,
    mastery_level: str = "learning",
    first_mastered_at: datetime | None = None,
    next_review_at: datetime | None = None,
) -> LearningProgress:
    p = LearningProgress(
        child_id=child_id,
        topic_id=topic_id,
        mastery_level=mastery_level,
        first_mastered_at=first_mastered_at,
        next_review_at=next_review_at,
    )
    db.add(p)
    db.flush()
    return p


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def child_9(db: Session, client, auth_headers):
    """Create a 9-year-old child (age_group='mid')."""
    from packages.db.models.user import User

    resp = client.post(
        "/api/v1/family/children",
        headers=auth_headers,
        json={
            "username": "castlechild",
            "password": CHILD_PASSWORD,
            "display_name": "Castle Kid",
            "avatar_color": "#FF5733",
            "pin": PIN,
        },
    )
    assert resp.status_code == 201
    child_id = int(resp.json()["data"]["id"])
    child = db.query(User).filter(User.id == child_id).first()
    child.birthday = date(2017, 6, 1)  # ~9 years old
    db.flush()
    return child_id


@pytest.fixture
def child_no_birthday(db: Session, client, auth_headers):
    """Create a child without birthday set (NULL → D1 fallback)."""
    resp = client.post(
        "/api/v1/family/children",
        headers=auth_headers,
        json={
            "username": "nobirthdaychild",
            "password": CHILD_PASSWORD,
            "display_name": "No Birthday Kid",
            "avatar_color": "#11AA22",
            "pin": PIN,
        },
    )
    assert resp.status_code == 201
    return int(resp.json()["data"]["id"])


@pytest.fixture
def scope_topics(db: Session):
    """3 in-range topics + 1 out-of-range topic for scope testing."""
    t1 = _make_topic(
        db, key="castle_inrange_1", subject="mathematics", domain="Algebra"
    )
    t2 = _make_topic(
        db, key="castle_inrange_2", subject="mathematics", domain="Geometry"
    )
    t3 = _make_topic(db, key="castle_inrange_3", subject="science", domain="Physics")
    # Out-of-range: age_range_end=4, so 9-year-old doesn't cover it
    t4 = _make_topic(
        db,
        key="castle_outrange_1",
        subject="science",
        domain="Biology",
        age_range_start=3,
        age_range_end=4,
    )
    db.flush()
    return {"in_range": [t1, t2, t3], "out_of_range": [t4]}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCastleScope:
    def test_in_range_topics_in_scope(self, db: Session, child_9: int, scope_topics):
        """Age 9 child gets 3 in-range topics in scope."""
        data = get_castle_index(db, child_9, 0, "en-US")
        all_topic_subjects = {t.subject for t in data.towers}
        # Mathematics and Science towers exist (in-range topics)
        assert "mathematics" in all_topic_subjects
        assert "science" in all_topic_subjects

    def test_out_of_range_not_in_scope_without_mastery(
        self, db: Session, child_9: int, scope_topics
    ):
        """Out-of-range topic not mastered → not in scope."""
        data = get_castle_index(db, child_9, 0, "en-US")
        # Biology domain should not appear (out-of-range, not mastered)
        biology_floors = [
            f for t in data.towers for f in t.floors if f.domain == "Biology"
        ]
        assert len(biology_floors) == 0

    def test_out_of_range_in_scope_when_mastered(
        self, db: Session, child_9: int, scope_topics
    ):
        """Out-of-range topic with first_mastered_at → enters scope."""
        outrace = scope_topics["out_of_range"][0]
        _make_progress(
            db,
            child_id=child_9,
            topic_id=outrace.id,
            mastery_level="mastered",
            first_mastered_at=datetime.now(UTC),
        )
        db.flush()

        data = get_castle_index(db, child_9, 0, "en-US")
        biology_floors = [
            f for t in data.towers for f in t.floors if f.domain == "Biology"
        ]
        assert len(biology_floors) == 1
        assert biology_floors[0].mastered_count == 1

    def test_birthday_null_fallback_to_mid(
        self, db: Session, child_no_birthday: int, scope_topics
    ):
        """Birthday NULL → age_group='mid' fallback; topics with age_group='mid' included."""
        data = get_castle_index(db, child_no_birthday, 0, "en-US")
        # scope_topics all have age_group='mid', so they should be in scope
        assert len(data.towers) > 0

    def test_no_duplicate_tower_floor(self, db: Session, child_9: int, scope_topics):
        """No duplicate tower/floor ids in aggregated result."""
        data = get_castle_index(db, child_9, 0, "en-US")
        subjects = [t.subject for t in data.towers]
        assert len(subjects) == len(set(subjects))
        for tower in data.towers:
            domains = [f.domain for f in tower.floors]
            assert len(domains) == len(set(domains))


class TestCastleCounts:
    def test_mastered_count_correct(self, db: Session, child_9: int, scope_topics):
        """Mastered topic counted in mastered_count."""
        t = scope_topics["in_range"][0]
        _make_progress(
            db,
            child_id=child_9,
            topic_id=t.id,
            mastery_level="mastered",
            first_mastered_at=datetime.now(UTC),
        )
        db.flush()

        data = get_castle_index(db, child_9, 0, "en-US")
        math_tower = next(t for t in data.towers if t.subject == "mathematics")
        assert math_tower.mastered_count >= 1

    def test_review_due_count_separate(self, db: Session, child_9: int, scope_topics):
        """Decayed mastered topic counts in both mastered_count and review_due_count."""
        t = scope_topics["in_range"][0]
        _make_progress(
            db,
            child_id=child_9,
            topic_id=t.id,
            mastery_level="mastered",
            first_mastered_at=datetime.now(UTC) - timedelta(days=60),
            next_review_at=datetime.now(UTC) - timedelta(days=1),
        )
        db.flush()

        data = get_castle_index(db, child_9, 0, "en-US")
        math_tower = next(t for t in data.towers if t.subject == "mathematics")
        assert math_tower.review_due_count == 1
        # The brick stays: decay is an overlay, not a removal (R3).
        assert math_tower.mastered_count == 1

    def test_learning_count(self, db: Session, child_9: int, scope_topics):
        """'learning' mastery counted in learning_count."""
        t = scope_topics["in_range"][0]
        _make_progress(db, child_id=child_9, topic_id=t.id, mastery_level="learning")
        db.flush()

        data = get_castle_index(db, child_9, 0, "en-US")
        math_tower = next(t for t in data.towers if t.subject == "mathematics")
        assert math_tower.learning_count >= 1


class TestCastleWindows:
    def test_window_dedup_review_wins(self, db: Session, child_9: int, scope_topics):
        """Topic both review_due and recommended → appears once as '复习到期'."""
        t = scope_topics["in_range"][0]
        _make_progress(
            db,
            child_id=child_9,
            topic_id=t.id,
            mastery_level="mastered",
            first_mastered_at=datetime.now(UTC) - timedelta(days=60),
            next_review_at=datetime.now(UTC) - timedelta(days=1),
        )
        db.flush()

        data = get_castle_index(db, child_9, 0, "en-US")
        topic_windows = [w for w in data.windows if w.topic_id == t.id]
        assert len(topic_windows) <= 1
        if topic_windows:
            assert topic_windows[0].reason == "复习到期"

    def test_window_cap_total(self, db: Session, child_9: int):
        """Total windows capped at MAX_TOTAL_WINDOWS."""
        # Create 15 topics, all review due
        topics = []
        for i in range(15):
            t = _make_topic(
                db,
                key=f"window_cap_{i}",
                subject="mathematics",
                domain=f"Domain{i}",
                centrality=float(i),
            )
            topics.append(t)
            _make_progress(
                db,
                child_id=child_9,
                topic_id=t.id,
                mastery_level="mastered",
                first_mastered_at=datetime.now(UTC) - timedelta(days=60),
                next_review_at=datetime.now(UTC) - timedelta(days=i + 1),
            )
        db.flush()

        data = get_castle_index(db, child_9, 0, "en-US")
        assert len(data.windows) <= MAX_TOTAL_WINDOWS

    def test_window_cap_review(self, db: Session, child_9: int):
        """Review-due windows capped at MAX_REVIEW_DUE_WINDOWS."""
        for i in range(10):
            t = _make_topic(
                db,
                key=f"review_cap_{i}",
                subject="mathematics",
                domain=f"Domain{i}",
            )
            _make_progress(
                db,
                child_id=child_9,
                topic_id=t.id,
                mastery_level="mastered",
                first_mastered_at=datetime.now(UTC) - timedelta(days=60),
                next_review_at=datetime.now(UTC) - timedelta(days=i + 1),
            )
        db.flush()

        data = get_castle_index(db, child_9, 0, "en-US")
        review_windows = [w for w in data.windows if w.reason == "复习到期"]
        assert len(review_windows) <= MAX_REVIEW_DUE_WINDOWS

    def test_review_and_recommended_fill_to_total_cap(
        self, db: Session, child_9: int
    ):
        """Exactly 6 review-due windows still leaves room for 4 recommended."""
        # 6 overdue mastered topics → MAX_REVIEW_DUE_WINDOWS.
        for i in range(MAX_REVIEW_DUE_WINDOWS):
            t = _make_topic(
                db,
                key=f"cap_review_{i}",
                subject="mathematics",
                domain=f"Review{i}",
                centrality=100.0 - i,
            )
            _make_progress(
                db,
                child_id=child_9,
                topic_id=t.id,
                mastery_level="mastered",
                first_mastered_at=datetime.now(UTC) - timedelta(days=60),
                next_review_at=datetime.now(UTC) - timedelta(days=i + 1),
            )
        # 6 unmastered in-scope candidates for the recommended/fallback path.
        for i in range(6):
            t = _make_topic(
                db,
                key=f"cap_available_{i}",
                subject="mathematics",
                domain=f"Avail{i}",
                centrality=50.0 - i,
            )
            _make_progress(
                db, child_id=child_9, topic_id=t.id, mastery_level="available"
            )
        db.flush()

        data = get_castle_index(db, child_9, 0, "en-US")
        review = [w for w in data.windows if w.reason == "复习到期"]
        assert len(review) == MAX_REVIEW_DUE_WINDOWS
        assert len(data.windows) <= MAX_TOTAL_WINDOWS
        # The recommended loop must be able to add past the review cap.
        assert len(data.windows) > MAX_REVIEW_DUE_WINDOWS

    def test_windows_unique_by_topic(self, db: Session, child_9: int):
        """No topic appears twice in the window list."""
        for i in range(8):
            t = _make_topic(
                db,
                key=f"uniq_{i}",
                subject="mathematics",
                domain=f"D{i}",
                centrality=float(i),
            )
            _make_progress(
                db,
                child_id=child_9,
                topic_id=t.id,
                mastery_level="mastered",
                first_mastered_at=datetime.now(UTC) - timedelta(days=60),
                next_review_at=datetime.now(UTC) - timedelta(days=i + 1),
            )
        db.flush()

        data = get_castle_index(db, child_9, 0, "en-US")
        ids = [w.topic_id for w in data.windows]
        assert len(ids) == len(set(ids))

    def test_window_has_subject_and_domain(
        self, db: Session, child_9: int, scope_topics
    ):
        """Every window has subject and domain in scope."""
        t = scope_topics["in_range"][0]
        _make_progress(
            db,
            child_id=child_9,
            topic_id=t.id,
            mastery_level="mastered",
            first_mastered_at=datetime.now(UTC) - timedelta(days=60),
            next_review_at=datetime.now(UTC) - timedelta(days=1),
        )
        db.flush()

        data = get_castle_index(db, child_9, 0, "en-US")
        for w in data.windows:
            assert w.subject
            assert w.domain

    def test_source_taxonomy_filter(self, db: Session, child_9: int):
        """Other-taxonomy topics excluded from towers and windows."""
        # Create a beijing-taxonomy topic in scope
        _make_topic(
            db,
            key="beijing_castle_topic",
            subject="mathematics",
            domain="BeijingDomain",
            source_taxonomy="beijing",
        )
        db.flush()

        # For en-US child, effective taxonomy is os-taxonomy
        data = get_castle_index(db, child_9, 0, "en-US")
        beijing_floors = [
            f for t in data.towers for f in t.floors if f.domain == "BeijingDomain"
        ]
        assert len(beijing_floors) == 0

    def test_zero_progress_returns_empty_towers(
        self, db: Session, child_9: int, scope_topics
    ):
        """Zero-progress child gets tower skeletons, not 404."""
        data = get_castle_index(db, child_9, 0, "en-US")
        assert len(data.towers) > 0
        # All counts zero (no progress)
        for tower in data.towers:
            assert tower.mastered_count == 0
            assert tower.review_due_count == 0

    def test_streak_days_in_response(self, db: Session, child_9: int, scope_topics):
        """streak_days is included and non-negative."""
        data = get_castle_index(db, child_9, 0, "en-US")
        assert data.streak_days >= 0
