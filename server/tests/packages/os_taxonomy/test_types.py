"""Tests for normalized taxonomy types and loader registry."""

from __future__ import annotations

import pytest

from packages.os_taxonomy.loaders import get_loader
from packages.os_taxonomy.types import (
    NormalizedCluster,
    NormalizedDependency,
    NormalizedTopic,
)


class TestNormalizedTopic:
    """NormalizedTopic dataclass tests."""

    def test_required_fields_only(self):
        """Topic can be instantiated with only required fields."""
        topic = NormalizedTopic(
            topic_key="mt_abc123",
            source_taxonomy="os-taxonomy",
            topic_type="CONCEPTUAL",
            subject="Computing",
        )
        assert topic.topic_key == "mt_abc123"
        assert topic.source_taxonomy == "os-taxonomy"
        assert topic.topic_type == "CONCEPTUAL"
        assert topic.subject == "Computing"
        assert topic.domain is None
        assert topic.name is None
        assert topic.description == ""
        assert topic.evidence == []
        assert topic.standards == []
        assert topic.deprecated is False
        assert topic.age_group == "mid"

    def test_all_fields(self):
        """Topic can be instantiated with all fields populated."""
        topic = NormalizedTopic(
            topic_key="mt_xyz789",
            source_taxonomy="os-taxonomy-beijing",
            topic_type="PROCEDURAL",
            subject="Mathematics",
            domain="Algebra",
            name="Linear Equations",
            name_zh="线性方程",
            description="Solving linear equations in one variable",
            description_zh="求解一元一次方程",
            age_range_start=10,
            age_range_end=12,
            centrality=0.045,
            evidence=["Solve 2x + 3 = 11", "Graph the solution"],
            evidence_zh=["求解 2x + 3 = 11", "绘制解的图形"],
            assessment_prompt="Can {{name}} solve 2x + 3 = 11?",
            assessment_prompt_zh="{{name}} 能解 2x + 3 = 11 吗？",
            standards=["CCSS.MATH.CONTENT.6.EE.A.2"],
            curriculum_standards=["Beijing.Math.6.2"],
            translation_status="reviewed",
            deprecated=False,
            age_group="upper",
        )
        assert topic.topic_key == "mt_xyz789"
        assert topic.source_taxonomy == "os-taxonomy-beijing"
        assert topic.domain == "Algebra"
        assert topic.name == "Linear Equations"
        assert topic.name_zh == "线性方程"
        assert topic.age_range_start == 10
        assert topic.age_range_end == 12
        assert topic.centrality == 0.045
        assert len(topic.evidence) == 2
        assert len(topic.evidence_zh) == 2  # type: ignore[arg-type]
        assert topic.translation_status == "reviewed"
        assert topic.age_group == "upper"

    def test_defaults_are_independent(self):
        """Mutable defaults (lists) are independent between instances."""
        topic1 = NormalizedTopic(
            topic_key="mt_1",
            source_taxonomy="os-taxonomy",
            topic_type="CONCEPTUAL",
            subject="Computing",
        )
        topic2 = NormalizedTopic(
            topic_key="mt_2",
            source_taxonomy="os-taxonomy",
            topic_type="CONCEPTUAL",
            subject="Computing",
        )
        topic1.evidence.append("test evidence")
        assert topic1.evidence == ["test evidence"]
        assert topic2.evidence == []


class TestNormalizedDependency:
    """NormalizedDependency dataclass tests."""

    def test_os_taxonomy_dependency_no_review(self):
        """Dependency from os-taxonomy has review_status=None."""
        dep = NormalizedDependency(
            topic_key="mt_abc",
            prerequisite_key="mt_xyz",
            strength="strong",
        )
        assert dep.topic_key == "mt_abc"
        assert dep.prerequisite_key == "mt_xyz"
        assert dep.strength == "strong"
        assert dep.reason is None
        assert dep.review_status is None

    def test_beijing_dependency_with_review(self):
        """Dependency from os-taxonomy-beijing can have review_status."""
        dep = NormalizedDependency(
            topic_key="mt_abc",
            prerequisite_key="mt_xyz",
            strength="medium",
            reason="Foundational concept",
            review_status="reviewed",
        )
        assert dep.review_status == "reviewed"
        assert dep.reason == "Foundational concept"


class TestNormalizedCluster:
    """NormalizedCluster dataclass tests."""

    def test_minimal_cluster(self):
        """Cluster can be instantiated with only required fields."""
        cluster = NormalizedCluster(
            subject="Computing",
            domain="Artificial Intelligence",
        )
        assert cluster.subject == "Computing"
        assert cluster.domain == "Artificial Intelligence"
        assert cluster.age_range_start is None
        assert cluster.age_group == "mid"
        assert cluster.summary == ""
        assert cluster.summary_zh is None
        assert cluster.source_taxonomy == "os-taxonomy"

    def test_full_cluster(self):
        """Cluster can be instantiated with all fields."""
        cluster = NormalizedCluster(
            subject="Mathematics",
            domain="Algebra",
            age_range_start=10,
            age_group="upper",
            summary="Linear equations and inequalities",
            summary_zh="线性方程与不等式",
            source_taxonomy="os-taxonomy-beijing",
        )
        assert cluster.age_range_start == 10
        assert cluster.age_group == "upper"
        assert cluster.summary == "Linear equations and inequalities"
        assert cluster.summary_zh == "线性方程与不等式"
        assert cluster.source_taxonomy == "os-taxonomy-beijing"


class TestLoaderRegistry:
    """Loader registry and factory tests."""

    def test_unknown_source_raises_value_error(self):
        """get_loader raises ValueError for unknown sources."""
        with pytest.raises(ValueError, match="Unknown taxonomy source"):
            get_loader("nonexistent-source")

    def test_empty_registry_message(self, monkeypatch):
        """Error message indicates no sources are available when registry is empty."""
        from packages.os_taxonomy.loaders import _LOADER_REGISTRY

        saved = dict(_LOADER_REGISTRY)
        _LOADER_REGISTRY.clear()
        try:
            with pytest.raises(ValueError, match="Available sources: none"):
                get_loader("any-source")
        finally:
            _LOADER_REGISTRY.update(saved)
