"""Tests for the Beijing taxonomy loader.

Verifies that BeijingLoader correctly reads the JSON files from the
Beijing data directory and produces NormalizedTopic/Dependency/Cluster
instances with source_taxonomy="beijing".
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from packages.os_taxonomy.loaders import get_loader
from packages.os_taxonomy.loaders.beijing import BeijingLoader
from packages.os_taxonomy.types import CurriculumStandard, NormalizedTopic

# scripts/ is importable from the server workspace root
from scripts.seed_learning_topics import _union_list


@pytest.fixture(scope="module")
def loader() -> BeijingLoader:
    """Create a BeijingLoader using the default data directory."""
    return BeijingLoader()


def _beijing_data_dir() -> Path:
    """Resolve the default Beijing data directory the loader would use."""
    return BeijingLoader()._data_dir


requires_beijing_data = pytest.mark.skipif(
    not _beijing_data_dir().is_dir(),
    reason=(
        "Beijing taxonomy data directory is absent "
        f"({_beijing_data_dir()}); server/data/ is gitignored"
    ),
)


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
        # Resolved entries carry the curriculum document title and code
        assert all(
            isinstance(s, CurriculumStandard) and s.name and s.code
            for t in with_standards
            for s in t.curriculum_standards
        )

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


class TestCurriculumStandardResolution:
    """Curriculum standards are resolved from cnStandards at load time."""

    @pytest.fixture()
    def fixture_loader(self, tmp_path: Path) -> BeijingLoader:
        """Loader over a minimal data dir with two metadata standards."""
        (tmp_path / "topics.zh.json").write_text(
            json.dumps({"topics": []}), encoding="utf-8"
        )
        (tmp_path / "cn-topics.json").write_text(
            json.dumps(
                {
                    "topics": [
                        {
                            "id": "mtc_demo",
                            "name": "示例主题",
                            "cnStandards": ["demo:X.1"],
                        },
                        {
                            "id": "mtc_unknown",
                            "name": "未知标准主题",
                            "cnStandards": ["demo:X.1", "demo:NOT-IN-METADATA"],
                        },
                        {"id": "mtc_none", "name": "无标准主题"},
                    ]
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        (tmp_path / "cn-curriculum-standards.json").write_text(
            json.dumps(
                {
                    "curricula": [
                        {
                            "slug": "demo",
                            "name": "示例课程标准（2022年版）",
                            "topics": [
                                {"key": "demo:X.1", "code": "X.1", "strand": "", "note": ""}
                            ],
                        }
                    ]
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return BeijingLoader(data_dir=tmp_path)

    def test_identifier_resolves_to_document_title_and_code(
        self, fixture_loader: BeijingLoader
    ) -> None:
        """A cnStandards identifier resolves to title + code."""
        by_key = {t.topic_key: t for t in fixture_loader.load_topics()}

        assert by_key["mtc_demo"].curriculum_standards == [
            CurriculumStandard(key="demo:X.1", name="示例课程标准（2022年版）", code="X.1")
        ]

    def test_unresolvable_identifier_is_dropped(
        self, fixture_loader: BeijingLoader
    ) -> None:
        """Identifiers absent from the metadata are dropped, not raised."""
        by_key = {t.topic_key: t for t in fixture_loader.load_topics()}

        assert by_key["mtc_unknown"].curriculum_standards == [
            CurriculumStandard(key="demo:X.1", name="示例课程标准（2022年版）", code="X.1")
        ]

    def test_no_standards_yields_empty_list(
        self, fixture_loader: BeijingLoader
    ) -> None:
        """A topic with no cnStandards yields an empty list."""
        by_key = {t.topic_key: t for t in fixture_loader.load_topics()}

        assert by_key["mtc_none"].curriculum_standards == []

    @requires_beijing_data
    def test_mtc_001_resolves(self, topics: list[NormalizedTopic]) -> None:
        """mtc_001 (moe-2022-chinese:S1.RW.01) resolves to title + code."""
        topic = next(t for t in topics if t.topic_key == "mtc_001")

        assert topic.curriculum_standards == [
            CurriculumStandard(
                key="moe-2022-chinese:S1.RW.01",
                name="义务教育语文课程标准（2022年版）",
                code="S1.RW.01",
            )
        ]

    @requires_beijing_data
    def test_every_reference_resolves(
        self, loader: BeijingLoader, topics: list[NormalizedTopic]
    ) -> None:
        """Every mt_/mtc_ cnStandards identifier resolves — zero unresolved."""
        raw_total = 0
        for filename in ("topics.zh.json", "cn-topics.json"):
            data = loader._read_json(filename)
            raw_total += sum(len(t.get("cnStandards", [])) for t in data["topics"])

        resolved_total = sum(len(t.curriculum_standards) for t in topics)
        assert raw_total == resolved_total == 2345

    def test_os_taxonomy_loader_returns_empty(self) -> None:
        """OsTaxonomyLoader still returns an empty curriculum_standards list."""
        from packages.os_taxonomy.loaders.os_taxonomy import OsTaxonomyLoader

        topics = OsTaxonomyLoader().load_topics()

        assert topics
        assert all(t.curriculum_standards == [] for t in topics)


class TestCurriculumStandardHashability:
    """CurriculumStandard is hashable so set-based unions work."""

    def test_standard_is_hashable(self) -> None:
        """A CurriculumStandard can be inserted into a set."""
        standard = CurriculumStandard(key="demo:X.1", name="示例", code="X.1")

        assert {standard} == {standard}

    def test_union_list_over_resolved_standards(self) -> None:
        """_union_list dedupes resolved standards instead of raising TypeError."""
        a = [CurriculumStandard(key="k1", name="N", code="C1")]
        b = [
            CurriculumStandard(key="k1", name="N", code="C1"),
            CurriculumStandard(key="k2", name="N", code="C2"),
        ]

        result = _union_list(a, b)

        assert [s.key for s in result] == ["k1", "k2"]


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
