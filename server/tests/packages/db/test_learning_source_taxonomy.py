"""Tests for dual-source taxonomy columns and review_status additions.

Verifies:
- LearningTopic.source_taxonomy + curriculum_standards_json columns
- curriculum_standards json_text accessor
- Composite unique constraint (topic_key, source_taxonomy)
- LearningDependency.review_status column
- LearningCluster.source_taxonomy column
- Default values
"""

from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError

from packages.db.models.learning.topic import (
    LearningCluster,
    LearningDependency,
    LearningTopic,
)


def _make_topic(
    topic_key: str = "math.counting",
    source_taxonomy: str = "os-taxonomy",
    curriculum_standards_json: str = "[]",
) -> LearningTopic:
    return LearningTopic(
        topic_key=topic_key,
        topic_type="concept",
        subject="math",
        source_taxonomy=source_taxonomy,
        curriculum_standards_json=curriculum_standards_json,
    )


class TestLearningTopicSourceTaxonomy:
    """source_taxonomy column and default value."""

    def test_default_source_taxonomy(self, packages_db):
        topic = LearningTopic(
            topic_key="math.default",
            topic_type="concept",
            subject="math",
        )
        packages_db.add(topic)
        packages_db.flush()
        assert topic.source_taxonomy == "os-taxonomy"

    def test_beijing_source_taxonomy(self, packages_db):
        topic = _make_topic(
            topic_key="math.beijing-01",
            source_taxonomy="beijing",
            curriculum_standards_json='[{"code":"BJ-M-001"}]',
        )
        packages_db.add(topic)
        packages_db.flush()
        assert topic.source_taxonomy == "beijing"
        assert topic.curriculum_standards_json == '[{"code":"BJ-M-001"}]'


class TestCurriculumStandardsAccessor:
    """curriculum_standards json_text accessor."""

    def test_accessor_returns_parsed_list(self, packages_db):
        topic = _make_topic(
            topic_key="math.acc-01",
            curriculum_standards_json='["CCSS.MATH.CONTENT.1.OA.A.1"]',
        )
        packages_db.add(topic)
        packages_db.flush()
        assert topic.curriculum_standards == ["CCSS.MATH.CONTENT.1.OA.A.1"]

    def test_accessor_empty_json(self, packages_db):
        topic = _make_topic(topic_key="math.acc-02", curriculum_standards_json="[]")
        packages_db.add(topic)
        packages_db.flush()
        assert topic.curriculum_standards == []


class TestCompositeUniqueConstraint:
    """uq_topic_key_source: (topic_key, source_taxonomy)."""

    def test_same_key_different_source_coexist(self, packages_db):
        packages_db.add(_make_topic(topic_key="math.shared", source_taxonomy="os-taxonomy"))
        packages_db.add(_make_topic(topic_key="math.shared", source_taxonomy="beijing"))
        packages_db.flush()  # no error

    def test_same_key_same_source_raises(self, packages_db):
        packages_db.add(_make_topic(topic_key="math.dup", source_taxonomy="os-taxonomy"))
        packages_db.flush()
        packages_db.add(_make_topic(topic_key="math.dup", source_taxonomy="os-taxonomy"))
        with pytest.raises(IntegrityError):
            packages_db.flush()


class TestLearningDependencyReviewStatus:
    """review_status column on LearningDependency."""

    def test_review_status_null(self, packages_db):
        topic_a = _make_topic(topic_key="dep-a")
        topic_b = _make_topic(topic_key="dep-b")
        packages_db.add_all([topic_a, topic_b])
        packages_db.flush()
        dep = LearningDependency(
            topic_id=topic_a.id,
            prerequisite_id=topic_b.id,
            strength="strong",
        )
        packages_db.add(dep)
        packages_db.flush()
        assert dep.review_status is None

    def test_review_status_reviewed(self, packages_db):
        topic_a = _make_topic(topic_key="dep-c")
        topic_b = _make_topic(topic_key="dep-d")
        packages_db.add_all([topic_a, topic_b])
        packages_db.flush()
        dep = LearningDependency(
            topic_id=topic_a.id,
            prerequisite_id=topic_b.id,
            strength="weak",
            review_status="reviewed",
        )
        packages_db.add(dep)
        packages_db.flush()
        assert dep.review_status == "reviewed"


class TestLearningClusterSourceTaxonomy:
    """source_taxonomy column on LearningCluster."""

    def test_beijing_cluster(self, packages_db):
        cluster = LearningCluster(
            subject="math",
            domain="counting",
            source_taxonomy="beijing",
        )
        packages_db.add(cluster)
        packages_db.flush()
        assert cluster.source_taxonomy == "beijing"

    def test_default_cluster_source(self, packages_db):
        cluster = LearningCluster(subject="math", domain="algebra")
        packages_db.add(cluster)
        packages_db.flush()
        assert cluster.source_taxonomy == "os-taxonomy"
