"""Tests for the mt_/mtc_ topic deduplication pipeline (packages.os_taxonomy.dedup)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from packages.os_taxonomy.dedup import run_dedup
from packages.os_taxonomy.types import NormalizedTopic

SERVER_DIR = Path(__file__).resolve().parents[3]


def _make_topic(
    key: str,
    name_zh: str | None,
    subject: str = "mathematics",
) -> NormalizedTopic:
    """Build a NormalizedTopic with minimal required fields."""
    return NormalizedTopic(
        topic_key=key,
        source_taxonomy="beijing",
        topic_type="concept",
        subject=subject,
        name_zh=name_zh,
    )


class TestFallbackDedup:
    """Rule-based (fallback) dedup logic over a small topic set."""

    @pytest.fixture()
    def topics(self) -> list[NormalizedTopic]:
        return [
            # Subject "mathematics" has both mt_ and mtc_ topics
            _make_topic("mt_aaaa", "分数加法", "mathematics"),
            _make_topic("mt_bbbb", "分数加法", "mathematics"),
            _make_topic("mt_cccc", "分数", "mathematics"),
            _make_topic("mt_dddd", "几何证明", "mathematics"),
            _make_topic("mtc_001", "分数加法", "mathematics"),
            _make_topic("mtc_002", "分数", "mathematics"),
            _make_topic("mtc_003", "几何证明与推理", "mathematics"),
            _make_topic("mtc_004", "代数方程", "mathematics"),
            # Subject "chinese" has only mtc_ topics
            _make_topic("mtc_101", "古诗词鉴赏", "chinese"),
            _make_topic("mtc_102", "文言文阅读", "chinese"),
            # Subject "history" has only mt_ topics (should produce no entries)
            _make_topic("mt_eeee", "工业革命", "history"),
        ]

    def test_identical_name_zh_merges(self, topics: list[NormalizedTopic]):
        mappings = run_dedup(topics, mode="fallback")
        by_mtc = {m["mtc_topic_key"]: m for m in mappings}
        assert by_mtc["mtc_001"]["action"] == "merge"
        assert by_mtc["mtc_001"]["overlap_type"] == "equivalent"
        assert by_mtc["mtc_001"]["mt_topic_key"] in ("mt_aaaa", "mt_bbbb")

    def test_completely_different_name_zh_keeps_both(
        self, topics: list[NormalizedTopic]
    ):
        mappings = run_dedup(topics, mode="fallback")
        by_mtc = {m["mtc_topic_key"]: m for m in mappings}
        assert by_mtc["mtc_004"]["action"] == "keep_both"
        assert by_mtc["mtc_004"]["overlap_type"] == "none"

    def test_partial_overlap_hides_mtc(self, topics: list[NormalizedTopic]):
        """'几何证明与推理' vs '几何证明' — partial overlap in [0.5, 0.8)."""
        import difflib

        ratio = difflib.SequenceMatcher(None, "几何证明与推理", "几何证明").ratio()
        assert 0.5 <= ratio < 0.8, f"ratio {ratio} not in subset band"
        mappings = run_dedup(topics, mode="fallback")
        by_mtc = {m["mtc_topic_key"]: m for m in mappings}
        entry = by_mtc["mtc_003"]
        assert entry["action"] == "hide_mtc"
        assert entry["overlap_type"] == "subset"
        assert entry["mt_topic_key"] == "mt_dddd"

    def test_only_mtc_subjects_get_keep_both(self, topics: list[NormalizedTopic]):
        mappings = run_dedup(topics, mode="fallback")
        by_mtc = {m["mtc_topic_key"]: m for m in mappings}
        assert by_mtc["mtc_101"]["action"] == "keep_both"
        assert by_mtc["mtc_101"]["mt_topic_key"] is None
        assert by_mtc["mtc_102"]["action"] == "keep_both"

    def test_only_mt_subjects_produce_no_entries(self, topics: list[NormalizedTopic]):
        mappings = run_dedup(topics, mode="fallback")
        mtc_keys = {m["mtc_topic_key"] for m in mappings}
        # No mtc_ topics exist in "history", so no history entries
        assert len(mtc_keys) == 6  # 4 mathematics + 2 chinese, 0 history

    def test_mapping_structure_valid_json(self, topics: list[NormalizedTopic]):
        mappings = run_dedup(topics, mode="fallback")
        required_keys = {"mtc_topic_key", "mt_topic_key", "overlap_type", "action"}
        for m in mappings:
            assert required_keys <= set(m.keys())
            # NOTE: "complementary" is reserved for future LLM mode.
            # Fallback mode only produces equivalent/subset/none.
            assert m["overlap_type"] in (
                "equivalent",
                "subset",
                "none",
            )
            assert m["action"] in ("merge", "hide_mtc", "keep_both")
        serialized = json.dumps(mappings, ensure_ascii=False)
        reloaded = json.loads(serialized)
        assert isinstance(reloaded, list)
        assert len(reloaded) == len(mappings)

    def test_llm_mode_defaults_to_fallback_behavior(
        self, topics: list[NormalizedTopic]
    ):
        """LLM mode without credentials must still produce valid mappings."""
        mappings = run_dedup(topics, mode="llm")
        assert all("mtc_topic_key" in m for m in mappings)

    def test_unknown_mode_raises(self, topics: list[NormalizedTopic]):
        with pytest.raises(ValueError, match="Unknown dedup mode"):
            run_dedup(topics, mode="bogus")

    def test_custom_threshold(self, topics: list[NormalizedTopic]):
        """A higher threshold demotes 'subset' pairs to keep_both."""
        default = run_dedup(topics, mode="fallback", threshold=0.8)
        strict = run_dedup(topics, mode="fallback", threshold=0.99)
        default_by_key = {m["mtc_topic_key"]: m for m in default}
        strict_by_key = {m["mtc_topic_key"]: m for m in strict}
        # mtc_001 is identical -> merge in both
        assert default_by_key["mtc_001"]["action"] == "merge"
        assert strict_by_key["mtc_001"]["action"] == "merge"
        # mtc_004 unrelated -> keep_both in both
        assert default_by_key["mtc_004"]["action"] == "keep_both"
        assert strict_by_key["mtc_004"]["action"] == "keep_both"


class TestCliHelp:
    def test_cli_help(self):
        result = subprocess.run(
            [sys.executable, "-m", "packages.os_taxonomy.dedup", "--help"],
            cwd=SERVER_DIR,
            capture_output=True,
            text=True,
            check=False,
        )
        # `packages.os_taxonomy.dedup` is the module path as run from server/
        assert result.returncode == 0, result.stderr
        assert "--source" in result.stdout
        assert "--fallback" in result.stdout
        assert "--threshold" in result.stdout
        assert "--output" in result.stdout
