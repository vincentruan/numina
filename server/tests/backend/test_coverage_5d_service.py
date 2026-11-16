"""Tests for Coverage 5D service — weighted quality model."""

import pytest

from apps.backend.app.services.learning.coverage_5d_service import (
    ALL_BLOOM_LEVELS,
    DimensionScores,
    _calc_bilingual,
    _calc_bloom,
    _calc_difficulty,
    _calc_existence,
    _calc_quality,
    _compute_weighted_score,
    compute_subject_coverage_5d,
    compute_topic_coverage_5d,
    get_coverage_report,
    get_worklist,
)
from packages.db.models.learning.question import Question
from packages.db.models.learning.topic import LearningDependency, LearningTopic

# ── Unit tests for dimension calculations ────────────────────────────


class TestDimensionCalculations:
    """Pure function tests for each dimension."""

    def test_existence_zero_when_no_questions(self):
        assert _calc_existence(0) == 0.0

    def test_existence_one_when_questions_exist(self):
        assert _calc_existence(5) == 1.0

    def test_difficulty_full_coverage(self):
        assert _calc_difficulty({1, 2, 3}) == 1.0

    def test_difficulty_partial_coverage(self):
        assert _calc_difficulty({1, 2}) == pytest.approx(2 / 3)

    def test_difficulty_no_coverage(self):
        assert _calc_difficulty(set()) == 0.0

    def test_bloom_full_coverage(self):
        assert _calc_bloom(set(ALL_BLOOM_LEVELS)) == 1.0

    def test_bloom_partial_coverage(self):
        assert _calc_bloom({"remember", "understand"}) == pytest.approx(2 / 6)

    def test_bloom_no_coverage(self):
        assert _calc_bloom(set()) == 0.0

    def test_bilingual_full_coverage(self):
        assert _calc_bilingual(10, 10) == 1.0

    def test_bilingual_partial_coverage(self):
        assert _calc_bilingual(10, 5) == 0.5

    def test_bilingual_zero_questions(self):
        assert _calc_bilingual(0, 0) == 0.0

    def test_quality_neutral_when_no_data(self):
        assert _calc_quality([]) == 0.5

    def test_quality_based_on_accuracy(self):
        assert _calc_quality([0.8, 0.6, 1.0]) == pytest.approx(0.8)


class TestWeightedScore:
    """Weighted score computation tests."""

    def test_zero_existence_means_zero_score(self):
        dims = DimensionScores(
            existence=0.0,
            difficulty=1.0,
            bloom=1.0,
            bilingual=1.0,
            quality=1.0,
        )
        assert _compute_weighted_score(dims) == 0.0

    def test_full_coverage_near_100(self):
        dims = DimensionScores(
            existence=1.0,
            difficulty=1.0,
            bloom=1.0,
            bilingual=1.0,
            quality=1.0,
        )
        score = _compute_weighted_score(dims)
        assert score == 100.0

    def test_partial_coverage(self):
        dims = DimensionScores(
            existence=1.0,
            difficulty=0.5,
            bloom=0.5,
            bilingual=0.5,
            quality=0.5,
        )
        score = _compute_weighted_score(dims)
        # 0.2*1 + 0.2*0.5 + 0.2*0.5 + 0.15*0.5 + 0.25*0.5 = 0.2 + 0.1 + 0.1 + 0.075 + 0.125 = 0.6
        assert score == pytest.approx(60.0, abs=0.5)

    def test_score_range_0_to_100(self):
        dims = DimensionScores(
            existence=1.0,
            difficulty=0.33,
            bloom=0.5,
            bilingual=0.0,
            quality=0.5,
        )
        score = _compute_weighted_score(dims)
        assert 0.0 <= score <= 100.0


# ── Integration tests with DB ────────────────────────────────────────


@pytest.fixture
def math_topics(db_session):
    """Create a small set of math topics with dependencies."""
    t1 = LearningTopic(
        topic_key="math.add", subject="mathematics", domain="number",
        name="Addition", age_group="lower", deprecated=False, topic_type="knowledge",
    )
    t2 = LearningTopic(
        topic_key="math.mul", subject="mathematics", domain="number",
        name="Multiplication", age_group="lower", deprecated=False, topic_type="knowledge",
    )
    t3 = LearningTopic(
        topic_key="math.div", subject="mathematics", domain="number",
        name="Division", age_group="lower", deprecated=False, topic_type="knowledge",
    )
    db_session.add_all([t1, t2, t3])
    db_session.flush()
    db_session.add_all([
        LearningDependency(topic_id=t2.id, prerequisite_id=t1.id, strength="required"),
        LearningDependency(topic_id=t3.id, prerequisite_id=t2.id, strength="required"),
    ])
    db_session.flush()
    return [t1, t2, t3]


def _make_question(
    topic_id: int,
    difficulty: int = 1,
    bloom_level: str = "apply",
    stem_zh: str | None = None,
    empirical_difficulty: float | None = None,
    correct_count: int = 0,
    times_used: int = 0,
) -> Question:
    """Helper to create a question with specific attributes."""
    return Question(
        topic_id=topic_id,
        question_type="calculation",
        stem="test question",
        stem_zh=stem_zh,
        answer_json='{"answer": 2}',
        difficulty=difficulty,
        bloom_level=bloom_level,
        source="template",
        review_status="approved",
        age_group="lower",
        empirical_difficulty=empirical_difficulty,
        correct_count=correct_count,
        times_used=times_used,
    )


class TestTopicCoverage5D:
    """Integration tests for compute_topic_coverage_5d."""

    def test_no_questions_returns_zero_score(self, db_session, math_topics):
        result = compute_topic_coverage_5d(db_session, math_topics[0].id)
        assert result.coverage_score == 0.0
        assert result.dimensions.existence == 0.0
        assert result.approved_question_count == 0

    def test_single_question_partial_coverage(self, db_session, math_topics):
        t1 = math_topics[0]
        db_session.add(_make_question(t1.id, difficulty=1, bloom_level="apply"))
        db_session.flush()

        result = compute_topic_coverage_5d(db_session, t1.id)
        assert result.coverage_score > 0.0
        assert result.dimensions.existence == 1.0
        assert result.dimensions.difficulty == pytest.approx(1 / 3)  # only level 1
        assert 1 in result.difficulty_levels_present
        assert result.approved_question_count == 1

    def test_full_difficulty_coverage(self, db_session, math_topics):
        t1 = math_topics[0]
        for d in [1, 2, 3]:
            db_session.add(_make_question(t1.id, difficulty=d, bloom_level="apply"))
        db_session.flush()

        result = compute_topic_coverage_5d(db_session, t1.id)
        assert result.dimensions.difficulty == 1.0
        assert result.difficulty_levels_present == [1, 2, 3]

    def test_full_bloom_coverage(self, db_session, math_topics):
        t1 = math_topics[0]
        for b in ALL_BLOOM_LEVELS:
            db_session.add(_make_question(t1.id, difficulty=1, bloom_level=b))
        db_session.flush()

        result = compute_topic_coverage_5d(db_session, t1.id)
        assert result.dimensions.bloom == 1.0
        assert set(result.bloom_levels_present) == set(ALL_BLOOM_LEVELS)

    def test_bilingual_completeness(self, db_session, math_topics):
        t1 = math_topics[0]
        # 2 questions: 1 with stem_zh, 1 without
        db_session.add(_make_question(t1.id, difficulty=1, stem_zh=None))
        db_session.add(_make_question(t1.id, difficulty=2, stem_zh="测试题目"))
        db_session.flush()

        result = compute_topic_coverage_5d(db_session, t1.id)
        assert result.dimensions.bilingual == pytest.approx(0.5)
        assert result.bilingual_ratio == pytest.approx(0.5)

    def test_quality_uses_accuracy(self, db_session, math_topics):
        t1 = math_topics[0]
        db_session.add(_make_question(
            t1.id, difficulty=1, correct_count=8, times_used=10,
        ))
        db_session.add(_make_question(
            t1.id, difficulty=2, correct_count=6, times_used=10,
        ))
        db_session.flush()

        result = compute_topic_coverage_5d(db_session, t1.id)
        assert result.avg_accuracy == pytest.approx(0.7)  # (0.8 + 0.6) / 2
        assert result.dimensions.quality == pytest.approx(0.7)

    def test_rejected_questions_dont_count(self, db_session, math_topics):
        t1 = math_topics[0]
        q = _make_question(t1.id, difficulty=1)
        q.review_status = "rejected"
        db_session.add(q)
        db_session.flush()

        result = compute_topic_coverage_5d(db_session, t1.id)
        assert result.coverage_score == 0.0
        assert result.approved_question_count == 0

    def test_comprehensive_topic_high_score(self, db_session, math_topics):
        """A topic with questions across all dimensions should score high."""
        t1 = math_topics[0]
        # Add questions covering all difficulties, blooms, bilingual, good accuracy
        for d in [1, 2, 3]:
            for b in ["remember", "understand", "apply"]:
                db_session.add(_make_question(
                    t1.id, difficulty=d, bloom_level=b,
                    stem_zh="中文题目", correct_count=7, times_used=10,
                ))
        db_session.flush()

        result = compute_topic_coverage_5d(db_session, t1.id)
        assert result.coverage_score >= 80.0  # High score expected
        assert result.dimensions.existence == 1.0
        assert result.dimensions.difficulty == 1.0
        assert result.dimensions.bilingual == 1.0


class TestSubjectCoverage5D:
    """Integration tests for compute_subject_coverage_5d."""

    def test_empty_subject(self, db_session):
        result = compute_subject_coverage_5d(db_session, "nonexistent")
        assert result["total_topics"] == 0
        assert result["avg_coverage_score"] == 0.0

    def test_subject_aggregation(self, db_session, math_topics):
        t1 = math_topics[0]
        db_session.add(_make_question(t1.id, difficulty=1))
        db_session.flush()

        result = compute_subject_coverage_5d(db_session, "mathematics")
        assert result["total_topics"] == 3
        assert result["avg_coverage_score"] > 0.0
        assert "avg_dimensions" in result
        assert "existence" in result["avg_dimensions"]

    def test_subject_bucket_counts(self, db_session, math_topics):
        t1 = math_topics[0]
        # Add comprehensive questions to push score above 70
        for d in [1, 2, 3]:
            for b in ALL_BLOOM_LEVELS:
                db_session.add(_make_question(
                    t1.id, difficulty=d, bloom_level=b,
                    stem_zh="中文", correct_count=8, times_used=10,
                ))
        db_session.flush()

        result = compute_subject_coverage_5d(db_session, "mathematics")
        assert result["topics_above_70"] >= 1
        assert result["topics_below_40"] >= 2  # t2, t3 still uncovered


class TestWorklist:
    """Integration tests for get_worklist."""

    def test_worklist_identifies_low_coverage_topics(self, db_session, math_topics):
        # Only t1 has questions
        t1 = math_topics[0]
        db_session.add(_make_question(t1.id, difficulty=1))
        db_session.flush()

        worklist = get_worklist(db_session, subject="mathematics", threshold=50.0)
        # t2 and t3 should be in worklist (score=0), t1 may or may not be depending on score
        topic_ids_in_worklist = {w["topic_id"] for w in worklist}
        assert math_topics[1].id in topic_ids_in_worklist
        assert math_topics[2].id in topic_ids_in_worklist

    def test_worklist_sorted_by_priority(self, db_session, math_topics):
        worklist = get_worklist(db_session, subject="mathematics", threshold=100.0)
        priorities = [w["priority"] for w in worklist]
        assert priorities == sorted(priorities, reverse=True)

    def test_worklist_includes_dimension_breakdown(self, db_session, math_topics):
        worklist = get_worklist(db_session, subject="mathematics", threshold=100.0)
        assert len(worklist) > 0
        item = worklist[0]
        assert "dimensions" in item
        assert "missing_difficulties" in item
        assert "missing_blooms" in item

    def test_worklist_missing_difficulties(self, db_session, math_topics):
        t1 = math_topics[0]
        # Only difficulty 1
        db_session.add(_make_question(t1.id, difficulty=1))
        db_session.flush()

        worklist = get_worklist(db_session, subject="mathematics", threshold=100.0)
        t1_item = next(w for w in worklist if w["topic_id"] == t1.id)
        assert 2 in t1_item["missing_difficulties"]
        assert 3 in t1_item["missing_difficulties"]
        assert 1 not in t1_item["missing_difficulties"]


class TestCoverageReport:
    """Integration tests for get_coverage_report."""

    def test_report_structure(self, db_session, math_topics):
        report = get_coverage_report(db_session)
        assert "overall_score" in report
        assert "subjects" in report
        assert "worklist" in report
        assert "total_topics" in report

    def test_report_filters_by_subject(self, db_session, math_topics):
        report = get_coverage_report(db_session, subject="mathematics")
        subjects = [s["subject"] for s in report["subjects"]]
        assert "mathematics" in subjects

    def test_report_worklist_ids_are_strings(self, db_session, math_topics):
        """Snowflake IDs must be serialized as strings for JS precision."""
        report = get_coverage_report(db_session, subject="mathematics")
        for w in report["worklist"]:
            assert isinstance(w["topic_id"], str)
