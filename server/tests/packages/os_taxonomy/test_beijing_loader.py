"""Tests for the Beijing taxonomy loader.

Verifies that BeijingLoader correctly reads the 7 JSON files from the
Beijing data directory and produces NormalizedTopic/Dependency/Cluster
instances with source_taxonomy="beijing".
"""

from __future__ import annotations

import pytest

from packages.os_taxonomy.loaders import get_loader
from packages.os_taxonomy.loaders.beijing import BeijingLoader
from packages.os_taxonomy.types import NormalizedTopic


@pytest.fixture(scope="module")
def loader() -> BeijingLoader:
    """Create a BeijingLoader using the default data directory."""
    return BeijingLoader()


@pytest.fixture(scope="module")
def topics(loader: BeijingLoader) -> list[NormalizedTopic]:
    """Load all topics once for the test module."""
    return loader.load_topics()


@pytest.fixture(scope="module")
def mt_topics(topics: list[NormalizedTopic]) -> list[NormalizedTopic]:
    """Filter to mt_ prefix topics (from topics.zh.json)."""
    return [t for t in topics if t.topic_key.startswith("mt_")]


@pytest.fixture(scope="module")
def mtc_topics(topics: list[NormalizedTopic]) -> list[NormalizedTopic]:
    """Filter to mtc_ prefix topics (from cn-topics.json)."""
    return [t for t in topics if t.topic_key.startswith("mtc_")]


class TestLoadTopics:
    """Tests for load_topics()."""

    def test_total_mt_count(self, mt_topics: list[NormalizedTopic]) -> None:
        """topics.zh.json contains exactly 1590 mt_ topics."""
        assert len(mt_topics) == 1590

    def test_total_mtc_count(self, mtc_topics: list[NormalizedTopic]) -> None:
        """cn-topics.json contains exactly 2008 mtc_ topics."""
        assert len(mtc_topics) == 2008

    def test_all_source_taxonomy_beijing(self, topics: list[NormalizedTopic]) -> None:
        """All topics have source_taxonomy='beijing'."""
        assert all(t.source_taxonomy == "beijing" for t in topics)

    def test_mt_topics_have_name_zh(self, mt_topics: list[NormalizedTopic]) -> None:
        """mt_ topics have name_zh populated (Chinese name from topics.zh.json)."""
        assert all(t.name_zh is not None and t.name_zh for t in mt_topics)

    def test_mt_topics_have_curriculum_standards(
        self, mt_topics: list[NormalizedTopic]
    ) -> None:
        """mt_ topics have curriculum_standards populated (cnStandards field)."""
        # At least some topics should have non-empty curriculum_standards
        with_standards = [t for t in mt_topics if t.curriculum_standards]
        assert len(with_standards) > 0, "Expected some mt_ topics with curriculum_standards"

    def test_mtc_topics_subject_mapping(
        self, mtc_topics: list[NormalizedTopic]
    ) -> None:
        """mtc_ topics have correct subject slug mapping."""
        # Find a Chinese subject topic and verify mapping
        chinese_topics = [t for t in mtc_topics if t.subject == "chinese"]
        assert len(chinese_topics) > 0, "Expected topics with subject='chinese'"

        # Find an ethics_law topic (Moral & Rule of Law -> ethics_law)
        ethics_topics = [t for t in mtc_topics if t.subject == "ethics_law"]
        assert len(ethics_topics) > 0, "Expected topics with subject='ethics_law'"

    def test_mtc_topics_have_age_range(
        self, mtc_topics: list[NormalizedTopic]
    ) -> None:
        """mtc_ topics have age_range_start/end populated."""
        with_age = [t for t in mtc_topics if t.age_range_start is not None]
        assert len(with_age) > 0

    def test_mtc_topics_have_centrality(
        self, mtc_topics: list[NormalizedTopic]
    ) -> None:
        """mtc_ topics have centrality populated."""
        with_centrality = [t for t in mtc_topics if t.centrality is not None]
        assert len(with_centrality) > 0

    def test_mt_topics_enriched_from_upstream(
        self, mt_topics: list[NormalizedTopic]
    ) -> None:
        """mt_ topics are enriched with subject/age from upstream topics.json."""
        assert all(t.subject for t in mt_topics)
        assert all(
            t.age_group in ("low", "mid", "high") for t in mt_topics
        )
        with_age = [t for t in mt_topics if t.age_range_start is not None]
        assert len(with_age) > 0


class TestLoadDependencies:
    """Tests for load_dependencies()."""

    def test_includes_zh_dependencies(self, loader: BeijingLoader) -> None:
        """Dependencies include mt_→mt_ edges from dependencies.zh.json."""
        deps = loader.load_dependencies()
        mt_to_mt = [
            d for d in deps
            if d.topic_key.startswith("mt_") and d.prerequisite_key.startswith("mt_")
        ]
        assert len(mt_to_mt) == 3221

    def test_includes_cn_dependencies(self, loader: BeijingLoader) -> None:
        """Dependencies include mtc_→mtc_ edges from cn-dependencies.json."""
        deps = loader.load_dependencies()
        mtc_to_mtc = [
            d for d in deps
            if d.topic_key.startswith("mtc_") and d.prerequisite_key.startswith("mtc_")
        ]
        # 2619 total minus 420 rejected = 2199
        assert len(mtc_to_mtc) == 2619 - 420

    def test_includes_bridge_dependencies(self, loader: BeijingLoader) -> None:
        """Dependencies include bridge edges from cn-bridge-dependencies.json."""
        deps = loader.load_dependencies()
        bridge = [
            d for d in deps
            if d.topic_key.startswith("mtc_") and d.prerequisite_key.startswith("mt_")
        ]
        # 47 total minus 1 rejected = 46
        assert len(bridge) == 47 - 1

    def test_rejected_excluded(self, loader: BeijingLoader) -> None:
        """Edges with reviewStatus='rejected' are excluded."""
        deps = loader.load_dependencies()
        assert all(d.review_status != "rejected" for d in deps)

    def test_total_count(self, loader: BeijingLoader) -> None:
        """Total dependency count after filtering."""
        deps = loader.load_dependencies()
        # 3221 + (2619-420) + (47-1) = 3221 + 2199 + 46 = 5466
        assert len(deps) == 5466


class TestLoadClusters:
    """Tests for load_clusters()."""

    def test_cluster_count(self, loader: BeijingLoader) -> None:
        """clusters.zh.json contains exactly 183 clusters."""
        clusters = loader.load_clusters()
        assert len(clusters) == 183

    def test_all_source_taxonomy_beijing(self, loader: BeijingLoader) -> None:
        """All clusters have source_taxonomy='beijing'."""
        clusters = loader.load_clusters()
        assert all(c.source_taxonomy == "beijing" for c in clusters)

    def test_subject_slug_mapping(self, loader: BeijingLoader) -> None:
        """Cluster subjects are mapped to slugs."""
        clusters = loader.load_clusters()
        subjects = {c.subject for c in clusters}
        # Should contain mapped slugs, not raw English names
        assert "english" in subjects
        assert "mathematics" in subjects
        # Should not contain raw display names
        assert "English" not in subjects
        assert "Mathematics" not in subjects

    def test_summary_zh_populated(self, loader: BeijingLoader) -> None:
        """Clusters have summary_zh populated from summary field."""
        clusters = loader.load_clusters()
        with_summary = [c for c in clusters if c.summary_zh]
        assert len(with_summary) > 0


class TestRegistry:
    """Tests for loader registration."""

    def test_get_loader_beijing(self) -> None:
        """get_loader('beijing') returns a BeijingLoader instance."""
        loader = get_loader("beijing")
        assert isinstance(loader, BeijingLoader)

    def test_get_loader_unknown_raises(self) -> None:
        """get_loader() raises ValueError for unknown sources."""
        with pytest.raises(ValueError, match="Unknown taxonomy source"):
            get_loader("nonexistent-source")
