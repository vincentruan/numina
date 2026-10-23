"""Tests for cross-subject bridge inference (issue #136)."""

import pytest
from sqlalchemy.orm import Session

from apps.backend.app.services.learning.bridge_inference import (
    InferredBridge,
    _extract_keywords,
    _tfidf_weighted_overlap,
    infer_cross_subject_bridges,
)
from packages.db.models.learning.topic import (
    LearningDependency,
    LearningTopic,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_topic(
    db: Session,
    *,
    key: str,
    subject: str,
    domain: str,
    name: str,
    source_taxonomy: str = "os-taxonomy",
    age_group: str = "mid",
) -> LearningTopic:
    t = LearningTopic(
        topic_key=key,
        topic_type="CONCEPTUAL",
        subject=subject,
        domain=domain,
        name=name,
        description="",
        age_group=age_group,
        source_taxonomy=source_taxonomy,
        evidence_json="[]",
        standards_json="[]",
    )
    db.add(t)
    return t


# ---------------------------------------------------------------------------
# Unit: keyword extraction
# ---------------------------------------------------------------------------


class TestKeywordExtraction:
    def test_basic_extraction(self):
        kws = _extract_keywords("Measurement and Units")
        assert "measurement" in kws
        assert "units" in kws
        # Stop words removed
        assert "and" not in kws

    def test_empty_name(self):
        assert _extract_keywords(None) == set()
        assert _extract_keywords("") == set()

    def test_single_char_words_excluded(self):
        kws = _extract_keywords("A B C measurement")
        assert "measurement" in kws
        assert "a" not in kws
        assert "b" not in kws


# ---------------------------------------------------------------------------
# Unit: weighted overlap
# ---------------------------------------------------------------------------


class TestWeightedOverlap:
    def test_identical_sets(self):
        kw = {"measurement", "units"}
        idf = {"measurement": 2.0, "units": 1.5}
        score = _tfidf_weighted_overlap(kw, kw, idf)
        assert score == pytest.approx(1.0)

    def test_disjoint_sets(self):
        idf = {"a": 1.0, "b": 1.0}
        score = _tfidf_weighted_overlap({"a"}, {"b"}, idf)
        assert score == 0.0

    def test_partial_overlap(self):
        idf = {"data": 2.0, "charts": 1.5, "analysis": 1.0}
        score = _tfidf_weighted_overlap(
            {"data", "charts"}, {"data", "analysis"}, idf
        )
        # shared: data (2.0), min_weight: min(3.5, 3.0) = 3.0
        assert 0.0 < score < 1.0

    def test_empty_input(self):
        assert _tfidf_weighted_overlap(set(), {"a"}, {"a": 1.0}) == 0.0


# ---------------------------------------------------------------------------
# Integration: full inference
# ---------------------------------------------------------------------------


class TestInferCrossSubjectBridges:
    def test_generates_bridges_for_keyword_overlap(self, db: Session):
        """Topics sharing keywords across subjects should produce bridges."""
        # Science topics about measurement
        _make_topic(
            db,
            key="sci-measure",
            subject="science",
            domain="Scientific Inquiry",
            name="Measurement and Data Collection",
        )
        _make_topic(
            db,
            key="sci-units",
            subject="science",
            domain="Scientific Inquiry",
            name="Units and Measurement",
        )
        # Math topics about measurement — same domain so edges aggregate
        _make_topic(
            db,
            key="math-measure",
            subject="mathematics",
            domain="Measurement",
            name="Measurement and Units",
        )
        _make_topic(
            db,
            key="math-units",
            subject="mathematics",
            domain="Measurement",
            name="Units and Conversion",
        )
        db.flush()

        bridges = infer_cross_subject_bridges(db, "os-taxonomy")

        # Should have generated bridges between science and math
        # (two topic-pairs sharing "measurement" and "units")
        assert len(bridges) > 0
        for b in bridges:
            assert isinstance(b, InferredBridge)
            assert b.confidence > 0
            assert b.strength == "soft"

    def test_no_bridges_for_unrelated_topics(self, db: Session):
        """Topics with no keyword overlap should not produce bridges."""
        _make_topic(
            db,
            key="sci-rock",
            subject="science",
            domain="Earth Science",
            name="Volcanoes and Eruptions",
        )
        _make_topic(
            db,
            key="eng-grammar",
            subject="english",
            domain="Grammar",
            name="Sentence Building",
        )
        db.flush()

        bridges = infer_cross_subject_bridges(
            db, "os-taxonomy", min_topic_links=2
        )
        # With only 1 topic per subject and min_topic_links=2, no domain
        # pair can reach the threshold
        assert len(bridges) == 0

    def test_respects_age_compatibility(self, db: Session):
        """Topics in incompatible age groups should not bridge."""
        # Low age group
        _make_topic(
            db,
            key="sci-low",
            subject="science",
            domain="Scientific Inquiry",
            name="Measurement and Data",
            age_group="low",
        )
        # High age group
        _make_topic(
            db,
            key="math-high",
            subject="mathematics",
            domain="Measurement",
            name="Measurement and Data",
            age_group="high",
        )
        db.flush()

        bridges = infer_cross_subject_bridges(db, "os-taxonomy")
        assert len(bridges) == 0

    def test_skips_existing_explicit_edges(self, db: Session):
        """If an explicit edge already exists, inference should not duplicate it."""
        t1 = _make_topic(
            db,
            key="sci-measure",
            subject="science",
            domain="Scientific Inquiry",
            name="Measurement and Data",
        )
        t2 = _make_topic(
            db,
            key="math-measure",
            subject="mathematics",
            domain="Measurement",
            name="Measurement and Units",
        )
        _make_topic(
            db,
            key="sci-units",
            subject="science",
            domain="Scientific Inquiry",
            name="Units and Measurement",
        )
        _make_topic(
            db,
            key="math-units",
            subject="mathematics",
            domain="Measurement",
            name="Units and Conversion",
        )
        db.flush()

        # Add an explicit edge t1 → t2
        db.add(
            LearningDependency(
                topic_id=t1.id,
                prerequisite_id=t2.id,
                strength="hard",
            )
        )
        db.flush()

        bridges = infer_cross_subject_bridges(db, "os-taxonomy")
        # The explicit edge (t1→t2) should not appear in inferred
        explicit_pairs = {(t1.id, t2.id)}
        for b in bridges:
            assert (b.topic_id, b.prerequisite_id) not in explicit_pairs
