"""Tests for the prerequisite backtrace diagnosis (issue #213)."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from apps.backend.app.services.learning.adaptive_service import (
    DIAGNOSIS_CONFIG_VERSION,
    DIAGNOSIS_MASTERY_THRESHOLD,
    diagnose_weak_prerequisites,
)
from packages.db.models.family import Family
from packages.db.models.learning.diagnosis_impression import DiagnosisImpression
from packages.db.models.learning.practice import PracticeAttempt, PracticeSession
from packages.db.models.learning.progress import LearningProgress
from packages.db.models.learning.question import Question
from packages.db.models.learning.topic import LearningDependency, LearningTopic
from packages.db.models.user import User

# ────────────────────────────────────────────────────────────────────────────
# Fixtures
# ────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def family(db: Session):
    f = Family(name="T Family", invite_code="T101", created_by=1)
    db.add(f)
    db.flush()
    return f


@pytest.fixture
def child(db: Session, family: Family):
    c = User(display_name="Child", password_hash="x", role="child", family_id=family.id)
    db.add(c)
    db.flush()
    return c


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


def _dep(db: Session, topic_id: int, prerequisite_id: int, strength: str = "hard") -> LearningDependency:
    d = LearningDependency(topic_id=topic_id, prerequisite_id=prerequisite_id, strength=strength)
    db.add(d)
    db.flush()
    return d


def _progress(db: Session, child_id: int, topic_id: int, mastery_level: str) -> LearningProgress:
    p = LearningProgress(child_id=child_id, topic_id=topic_id, mastery_level=mastery_level)
    db.add(p)
    db.flush()
    return p


def _session_and_attempts(
    db: Session,
    child: User,
    topic: LearningTopic,
    n_attempts: int,
    correct: int,
    session_source: str = "adaptive",
):
    """Create a practice session with n_attempts; correct-many are marked correct."""
    from packages.core.snowflake import next_id

    session = PracticeSession(
        id=next_id(),
        child_id=child.id,
        topic_id=topic.id,
        session_mode="practice",
        question_ids_json="[]",
        started_at=datetime.now(UTC),
        completed_count=n_attempts,
        source=session_source,
    )
    db.add(session)
    db.flush()

    for i in range(n_attempts):
        a = PracticeAttempt(
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
        db.add(a)
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


# ────────────────────────────────────────────────────────────────────────────
# AE1: depth-2 candidate returned when direct mastered and direct unmet filter out
# ────────────────────────────────────────────────────────────────────────────


def test_ae1_depth2_candidate_is_top(db: Session, child: User):
    target = _topic(db, 200_001, "fractions_add")
    # Direct prerequisite the child is weak on: shown on the page already, so
    # the router passes it in as a lookback and the backtrace looks past it.
    direct_unmet = _topic(db, 200_002, "common_denom")
    # Depth-2 qualified
    depth2 = _topic(db, 200_003, "lcm")
    _dep(db, target.id, direct_unmet.id)
    _dep(db, direct_unmet.id, depth2.id)  # lcm is depth-2 from target via direct_unmet

    # Target: 8 attempts, below threshold
    _session_and_attempts(db, child, target, n_attempts=8, correct=3)
    _progress(db, child.id, target.id, "learning")

    # Direct unmet: not mastered → excluded by R10
    _progress(db, child.id, direct_unmet.id, "learning")

    # Depth-2: 4 attempts, below threshold (rule-based class since <5)
    _session_and_attempts(db, child, depth2, n_attempts=4, correct=1)
    _progress(db, child.id, depth2.id, "learning")
    _question(db, depth2)

    results = diagnose_weak_prerequisites(
        db, target.id, child.id, lookback_topic_ids=[direct_unmet.id]
    )
    assert len(results) == 1, f"expected 1 candidate, got {[r['topic_name'] for r in results]}"
    assert results[0]["topic_id"] == depth2.id
    # One layer back from the direct prerequisites the page already shows.
    assert results[0]["depth"] == 1
    assert results[0]["sample_size"] == 4


# ────────────────────────────────────────────────────────────────────────────
# AE2: zero-attempt prerequisite silently absent (R3)
# ────────────────────────────────────────────────────────────────────────────


def test_ae2_zero_attempt_prereq_excluded(db: Session, child: User):
    target = _topic(db, 300_001, "target")
    direct = _topic(db, 300_002, "direct")  # zero attempts
    _dep(db, target.id, direct.id)

    _session_and_attempts(db, child, target, n_attempts=8, correct=3)
    _progress(db, child.id, target.id, "learning")
    # No progress row for `direct` (no attempts)

    results = diagnose_weak_prerequisites(db, target.id, child.id)
    assert results == []


# ────────────────────────────────────────────────────────────────────────────
# AE5 / AE6: target with < 3 attempts or above threshold → empty
# ────────────────────────────────────────────────────────────────────────────


def test_ae5_target_below_min_attempts_returns_empty(db: Session, child: User):
    target = _topic(db, 400_001, "target")
    candidate = _topic(db, 400_002, "candidate")
    _dep(db, target.id, candidate.id)

    _session_and_attempts(db, child, target, n_attempts=2, correct=0)
    _progress(db, child.id, target.id, "learning")
    _session_and_attempts(db, child, candidate, n_attempts=5, correct=1)
    _progress(db, child.id, candidate.id, "learning")
    _question(db, candidate)

    assert diagnose_weak_prerequisites(db, target.id, child.id) == []
    # No impression written either.
    assert db.query(DiagnosisImpression).filter_by(child_id=child.id).count() == 0


def test_ae6_target_above_threshold_returns_empty(db: Session, child: User):
    target = _topic(db, 500_001, "target")
    candidate = _topic(db, 500_002, "candidate")
    _dep(db, target.id, candidate.id)

    # 8 attempts, all correct → mastery ≈ 1.0 (well above 0.60)
    _session_and_attempts(db, child, target, n_attempts=8, correct=8)
    _progress(db, child.id, target.id, "mastered")
    _session_and_attempts(db, child, candidate, n_attempts=5, correct=1)
    _progress(db, child.id, candidate.id, "learning")
    _question(db, candidate)

    assert diagnose_weak_prerequisites(db, target.id, child.id) == []


# ────────────────────────────────────────────────────────────────────────────
# AE7: cyclic graph terminates; B returned at depth 1; no duplicates
# ────────────────────────────────────────────────────────────────────────────


def test_ae7_cycle_terminates(db: Session, child: User):
    """A→B (hard), B→A (hard cycle), B→C (hard). Target A.

    B is a direct prerequisite but mastered → not a gap, so it is not on the
    page and the backtrace starts at it. C, one layer back from B, is
    qualified. The cycle A↔B terminates via the visited set without raising
    or producing duplicate entries.
    """
    a = _topic(db, 600_001, "A")
    b = _topic(db, 600_002, "B")
    c = _topic(db, 600_003, "C")
    _dep(db, a.id, b.id)
    _dep(db, b.id, a.id)  # cycle back to A
    _dep(db, b.id, c.id)

    _session_and_attempts(db, child, a, n_attempts=8, correct=3)
    _progress(db, child.id, a.id, "learning")
    # B is mastered (A's only direct prereq satisfied) → fails R1(c)
    _session_and_attempts(db, child, b, n_attempts=8, correct=7)
    _progress(db, child.id, b.id, "mastered")
    _question(db, b)
    # C is weak one layer back from B — qualified candidate
    _session_and_attempts(db, child, c, n_attempts=5, correct=1)
    _progress(db, child.id, c.id, "learning")
    _question(db, c)

    results = diagnose_weak_prerequisites(db, a.id, child.id)
    assert len(results) == 1
    assert results[0]["topic_id"] == c.id
    assert results[0]["depth"] == 1


# ────────────────────────────────────────────────────────────────────────────
# AE8: BKT-class candidate ranks above rule-based candidate with lower score
# ────────────────────────────────────────────────────────────────────────────


def test_ae8_bkt_class_ranks_before_rule_based(db: Session, child: User):
    """Two weak prereqs: BKT-class (5+ attempts) before rule-based (3-4 attempts).

    Both are placed at depth 2 (via a mastered direct prereq so R10 does not
    exclude them) and satisfy all weak-candidate filters.
    """
    target = _topic(db, 700_001, "target")
    buffer = _topic(db, 700_004, "buffer")  # depth-1 mastered; unlocks R10 exclusion for depth-2
    bkt_cand = _topic(db, 700_002, "bkt_cand")
    rule_cand = _topic(db, 700_003, "rule_cand")
    _dep(db, target.id, buffer.id)
    _dep(db, buffer.id, bkt_cand.id)
    _dep(db, buffer.id, rule_cand.id)

    _session_and_attempts(db, child, target, n_attempts=8, correct=3)
    _progress(db, child.id, target.id, "learning")
    _session_and_attempts(db, child, buffer, n_attempts=8, correct=7)
    _progress(db, child.id, buffer.id, "mastered")
    _question(db, buffer)

    # BKT-class candidate: 6 attempts, mostly correct
    _session_and_attempts(db, child, bkt_cand, n_attempts=6, correct=2)
    _progress(db, child.id, bkt_cand.id, "learning")
    _question(db, bkt_cand)

    # Rule-based candidate: 4 attempts, low accuracy
    _session_and_attempts(db, child, rule_cand, n_attempts=4, correct=1)
    _progress(db, child.id, rule_cand.id, "learning")
    _question(db, rule_cand)

    results = diagnose_weak_prerequisites(db, target.id, child.id)
    assert len(results) == 2
    # BKT-eligible candidate (6 attempts) sorts before rule-based (4 attempts)
    # regardless of their respective mastery scores.
    assert results[0]["topic_id"] == bkt_cand.id
    assert results[1]["topic_id"] == rule_cand.id


# ────────────────────────────────────────────────────────────────────────────
# Diamond: same prerequisite reachable at depth 1 and 2 → appears once, at depth 1
# ────────────────────────────────────────────────────────────────────────────


def test_diamond_dedupe_by_topic_id_at_min_depth(db: Session, child: User):
    """A diamond: target → middle (mastered), target → diamond_mastered (mastered),
    both pointing at diamond_weak.

    diamond_weak is reachable through two distinct paths at the same depth, so
    it must be reported once.
    """
    target = _topic(db, 800_001, "target")
    middle = _topic(db, 800_002, "middle")
    diamond_mastered = _topic(db, 800_003, "diamond_mastered")
    diamond_weak = _topic(db, 800_004, "diamond_weak")
    # Two mastered direct prereqs; diamond_weak is reached via two distinct
    # paths: middle → diamond_weak and diamond_mastered → diamond_weak.
    _dep(db, target.id, middle.id)
    _dep(db, target.id, diamond_mastered.id)
    _dep(db, middle.id, diamond_weak.id)
    _dep(db, diamond_mastered.id, diamond_weak.id)

    _session_and_attempts(db, child, target, n_attempts=8, correct=3)
    _progress(db, child.id, target.id, "learning")
    for topic, mastery, correct, total in [
        (middle, "mastered", 7, 8),
        (diamond_mastered, "mastered", 7, 8),
        (diamond_weak, "learning", 1, 5),
    ]:
        _session_and_attempts(db, child, topic, n_attempts=total, correct=correct)
        _progress(db, child.id, topic.id, mastery)
        _question(db, topic)

    results = diagnose_weak_prerequisites(db, target.id, child.id)
    diamond_entries = [r for r in results if r["topic_id"] == diamond_weak.id]
    assert len(diamond_entries) == 1
    assert diamond_entries[0]["depth"] == 1


# ────────────────────────────────────────────────────────────────────────────
# SC5: mastered candidate excluded
# ────────────────────────────────────────────────────────────────────────────


def test_mastered_candidate_excluded(db: Session, child: User):
    target = _topic(db, 900_001, "target")
    buffer = _topic(db, 900_003, "buffer")
    cand = _topic(db, 900_002, "cand")
    _dep(db, target.id, buffer.id)
    _dep(db, buffer.id, cand.id)

    _session_and_attempts(db, child, target, n_attempts=8, correct=3)
    _progress(db, child.id, target.id, "learning")
    _session_and_attempts(db, child, buffer, n_attempts=8, correct=7)
    _progress(db, child.id, buffer.id, "mastered")
    _question(db, buffer)
    # Candidate: 5 attempts below threshold, BUT mastered via learning flow
    _session_and_attempts(db, child, cand, n_attempts=5, correct=2)
    _progress(db, child.id, cand.id, "mastered")
    _question(db, cand)

    assert diagnose_weak_prerequisites(db, target.id, child.id) == []


# ────────────────────────────────────────────────────────────────────────────
# Deprecated topic excluded
# ────────────────────────────────────────────────────────────────────────────


def test_deprecated_candidate_excluded(db: Session, child: User):
    target = _topic(db, 1_000_001, "target")
    buffer = _topic(db, 1_000_003, "buffer")
    cand = _topic(db, 1_000_002, "cand", deprecated=True)
    _dep(db, target.id, buffer.id)
    _dep(db, buffer.id, cand.id)

    _session_and_attempts(db, child, target, n_attempts=8, correct=3)
    _progress(db, child.id, target.id, "learning")
    _session_and_attempts(db, child, buffer, n_attempts=8, correct=7)
    _progress(db, child.id, buffer.id, "mastered")
    _question(db, buffer)
    _session_and_attempts(db, child, cand, n_attempts=5, correct=1)
    _progress(db, child.id, cand.id, "learning")
    _question(db, cand)

    assert diagnose_weak_prerequisites(db, target.id, child.id) == []


# ────────────────────────────────────────────────────────────────────────────
# Locked candidate excluded (doc review P1 fix)
# ────────────────────────────────────────────────────────────────────────────


def test_locked_candidate_excluded(db: Session, child: User):
    target = _topic(db, 1_100_001, "target")
    buffer = _topic(db, 1_100_003, "buffer")
    cand = _topic(db, 1_100_002, "cand")
    _dep(db, target.id, buffer.id)
    _dep(db, buffer.id, cand.id)

    _session_and_attempts(db, child, target, n_attempts=8, correct=3)
    _progress(db, child.id, target.id, "learning")
    _session_and_attempts(db, child, buffer, n_attempts=8, correct=7)
    _progress(db, child.id, buffer.id, "mastered")
    _question(db, buffer)
    # Candidate has ≥3 attempts but its own progress level is 'locked'
    # (e.g. learned through learning flow bypassing the lock, then practice session
    # bypasses the lock on self-selection — but stored level stays 'locked').
    _session_and_attempts(db, child, cand, n_attempts=5, correct=1)
    _progress(db, child.id, cand.id, "locked")
    _question(db, cand)

    assert diagnose_weak_prerequisites(db, target.id, child.id) == []


# ────────────────────────────────────────────────────────────────────────────
# Impression row written per qualified candidate
# ────────────────────────────────────────────────────────────────────────────


def test_impression_written_for_each_qualified_candidate(db: Session, child: User):
    target = _topic(db, 1_200_001, "target")
    buffer = _topic(db, 1_200_004, "buffer")
    cand1 = _topic(db, 1_200_002, "cand1")
    cand2 = _topic(db, 1_200_003, "cand2")
    _dep(db, target.id, buffer.id)
    _dep(db, buffer.id, cand1.id)
    _dep(db, buffer.id, cand2.id)

    _session_and_attempts(db, child, target, n_attempts=8, correct=3)
    _progress(db, child.id, target.id, "learning")
    _session_and_attempts(db, child, buffer, n_attempts=8, correct=7)
    _progress(db, child.id, buffer.id, "mastered")
    _question(db, buffer)
    _session_and_attempts(db, child, cand1, n_attempts=6, correct=2)
    _progress(db, child.id, cand1.id, "learning")
    _question(db, cand1)
    _session_and_attempts(db, child, cand2, n_attempts=5, correct=1)
    _progress(db, child.id, cand2.id, "learning")
    _question(db, cand2)

    results = diagnose_weak_prerequisites(db, target.id, child.id)
    assert len(results) == 2

    impressions = (
        db.query(DiagnosisImpression)
        .filter_by(child_id=child.id, target_topic_id=target.id)
        .all()
    )
    assert len(impressions) == 2
    recommended_ids = {i.recommended_topic_id for i in impressions}
    assert recommended_ids == {cand1.id, cand2.id}
    assert all(i.config_version == DIAGNOSIS_CONFIG_VERSION for i in impressions)
    assert all(i.sample_size >= 5 for i in impressions)


# ────────────────────────────────────────────────────────────────────────────
# Threshold is a module constant (plan's KTD10)
# ────────────────────────────────────────────────────────────────────────────


def test_threshold_constant_value():
    assert DIAGNOSIS_MASTERY_THRESHOLD == 0.60
