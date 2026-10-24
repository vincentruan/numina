"""Tests for the OsTaxonomyLoader and backward-compatible get_* functions."""

from __future__ import annotations

from packages.os_taxonomy.loaders.os_taxonomy import OsTaxonomyLoader
from packages.os_taxonomy.types import (
    NormalizedCluster,
    NormalizedDependency,
    NormalizedTopic,
)


class TestOsTaxonomyLoaderTopics:
    """Tests for OsTaxonomyLoader.load_topics()."""

    def test_returns_normalized_topics(self) -> None:
        loader = OsTaxonomyLoader()
        topics = loader.load_topics()
        assert len(topics) == 1590
        assert all(isinstance(t, NormalizedTopic) for t in topics)

    def test_field_mapping_first_topic(self) -> None:
        loader = OsTaxonomyLoader()
        topics = loader.load_topics()
        t = topics[0]
        # Spot-check field mapping
        assert t.topic_key == "mt_AzTrT5ySCx"
        assert t.source_taxonomy == "os-taxonomy"
        assert t.topic_type == "CONCEPTUAL"
        assert t.subject == "Computing"
        assert t.domain == "Artificial Intelligence"
        assert t.name == "AI in Daily Life"
        assert t.name_zh == "日常生活中的AI"
        assert t.age_range_start == 5
        assert t.age_range_end == 7
        assert t.age_group == "low"  # 5 <= 7
        assert t.centrality == 0.02735978112175103
        assert len(t.evidence) == 3
        assert t.evidence_zh is not None
        assert len(t.evidence_zh) == 3
        assert t.assessment_prompt is not None
        assert t.assessment_prompt_zh is not None
        assert t.standards == []
        assert t.curriculum_standards == []
        assert t.translation_status is None
        assert t.deprecated is False

    def test_source_taxonomy_is_os_taxonomy(self) -> None:
        loader = OsTaxonomyLoader()
        topics = loader.load_topics()
        assert all(t.source_taxonomy == "os-taxonomy" for t in topics)

    def test_age_group_computation(self) -> None:
        loader = OsTaxonomyLoader()
        topics = loader.load_topics()
        # Verify age_group is set for all topics
        for t in topics:
            assert t.age_group in {"low", "mid", "high"}
            if t.age_range_start is None:
                assert t.age_group == "mid"
            elif t.age_range_start <= 7:
                assert t.age_group == "low"
            elif t.age_range_start <= 10:
                assert t.age_group == "mid"
            else:
                assert t.age_group == "high"


class TestOsTaxonomyLoaderDependencies:
    """Tests for OsTaxonomyLoader.load_dependencies()."""

    def test_returns_normalized_dependencies(self) -> None:
        loader = OsTaxonomyLoader()
        deps = loader.load_dependencies()
        assert len(deps) == 3221
        assert all(isinstance(d, NormalizedDependency) for d in deps)

    def test_field_mapping_first_dependency(self) -> None:
        loader = OsTaxonomyLoader()
        deps = loader.load_dependencies()
        d = deps[0]
        assert d.topic_key == "mt__00ZSLnB7p"
        assert d.prerequisite_key == "mt_VBl1T1sFCM"
        assert d.strength == "hard"
        assert d.reason is not None
        assert d.review_status is None

    def test_all_review_status_none(self) -> None:
        loader = OsTaxonomyLoader()
        deps = loader.load_dependencies()
        assert all(d.review_status is None for d in deps)


class TestOsTaxonomyLoaderClusters:
    """Tests for OsTaxonomyLoader.load_clusters()."""

    def test_returns_normalized_clusters(self) -> None:
        loader = OsTaxonomyLoader()
        clusters = loader.load_clusters()
        assert len(clusters) == 183
        assert all(isinstance(c, NormalizedCluster) for c in clusters)

    def test_field_mapping_first_cluster(self) -> None:
        loader = OsTaxonomyLoader()
        clusters = loader.load_clusters()
        c = clusters[0]
        assert c.subject == "English"
        assert c.domain == "Grammar & Punctuation"
        assert c.age_range_start == 5
        assert c.age_group == "low"  # 5 <= 7
        assert c.summary.startswith("Your child is learning")
        assert c.summary_zh is not None
        assert c.source_taxonomy == "os-taxonomy"

    def test_all_source_taxonomy_is_os_taxonomy(self) -> None:
        loader = OsTaxonomyLoader()
        clusters = loader.load_clusters()
        assert all(c.source_taxonomy == "os-taxonomy" for c in clusters)


class TestBackwardCompatibility:
    """Tests for backward-compatible get_* functions."""

    def test_get_topics_returns_list_of_dicts(self) -> None:
        from packages.os_taxonomy import get_topics

        topics = get_topics()
        assert len(topics) == 1590
        assert isinstance(topics, list)
        assert isinstance(topics[0], dict)

    def test_get_dependencies_returns_list_of_dicts(self) -> None:
        from packages.os_taxonomy import get_dependencies

        deps = get_dependencies()
        assert len(deps) == 3221
        assert isinstance(deps, list)
        assert isinstance(deps[0], dict)

    def test_get_clusters_returns_list_of_dicts(self) -> None:
        from packages.os_taxonomy import get_clusters

        clusters = get_clusters()
        assert len(clusters) == 183
        assert isinstance(clusters, list)
        assert isinstance(clusters[0], dict)


class TestLoaderRegistry:
    """Test that OsTaxonomyLoader is registered in the loader registry."""

    def test_get_loader_os_taxonomy(self) -> None:
        from packages.os_taxonomy.loaders import get_loader

        # Importing the loader module registers it
        from packages.os_taxonomy.loaders.os_taxonomy import (
            OsTaxonomyLoader,  # noqa: F401
        )

        loader = get_loader("os-taxonomy")
        assert isinstance(loader, OsTaxonomyLoader)
