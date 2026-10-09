"""Tests for Beijing taxonomy seed script behavior (U4/U5)."""

import importlib.util
import sys
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from packages.db.models.learning.topic import LearningCluster, LearningTopic
from packages.os_taxonomy.types import NormalizedCluster, NormalizedTopic

# Import the seed script as a module (it uses sys.path.insert at the top)
_spec = importlib.util.spec_from_file_location(
    "seed_learning_topics",
    Path(__file__).resolve().parent.parent.parent / "scripts" / "seed_learning_topics.py",
)
_seed_module = importlib.util.module_from_spec(_spec)
sys.modules["seed_learning_topics"] = _seed_module
_spec.loader.exec_module(_seed_module)

build_dedup_views = _seed_module.build_dedup_views
apply_dedup_to_topics = _seed_module.apply_dedup_to_topics
upsert_topic = _seed_module.upsert_topic
upsert_cluster = _seed_module.upsert_cluster
_union_list = _seed_module._union_list
SOURCE_BEIJING = _seed_module.SOURCE_BEIJING


# ---------------------------------------------------------------------------
# Pure function tests (no DB needed)
# ---------------------------------------------------------------------------


class TestBuildDedupViews:
    def test_build_dedup_views_merge_action(self):
        """action='merge' populates both mtc_actions and deprecated_to_merged."""
        mapping = [
            {
                "mtc_topic_key": "mtc_foo",
                "mt_topic_key": "mt_foo",
                "action": "merge",
            }
        ]
        mtc_actions, deprecated_to_merged = build_dedup_views(mapping)

        assert "mtc_foo" in mtc_actions
        assert mtc_actions["mtc_foo"]["action"] == "merge"
        assert deprecated_to_merged == {"mtc_foo": "mt_foo"}

    def test_build_dedup_views_hide_mtc(self):
        """action='hide_mtc' populates mtc_actions but not deprecated_to_merged."""
        mapping = [
            {
                "mtc_topic_key": "mtc_bar",
                "mt_topic_key": None,
                "action": "hide_mtc",
            }
        ]
        mtc_actions, deprecated_to_merged = build_dedup_views(mapping)

        assert "mtc_bar" in mtc_actions
        assert mtc_actions["mtc_bar"]["action"] == "hide_mtc"
        assert deprecated_to_merged == {}

    def test_build_dedup_views_keep_both(self):
        """action='keep_both' populates mtc_actions but not deprecated_to_merged."""
        mapping = [
            {
                "mtc_topic_key": "mtc_baz",
                "mt_topic_key": "mt_baz",
                "action": "keep_both",
            }
        ]
        mtc_actions, deprecated_to_merged = build_dedup_views(mapping)

        assert "mtc_baz" in mtc_actions
        assert mtc_actions["mtc_baz"]["action"] == "keep_both"
        assert deprecated_to_merged == {}

    def test_build_dedup_views_null_mt_key(self):
        """Entry with mt_topic_key=null is skipped entirely."""
        mapping = [
            {
                "mtc_topic_key": None,
                "mt_topic_key": "mt_something",
                "action": "merge",
            }
        ]
        mtc_actions, deprecated_to_merged = build_dedup_views(mapping)

        assert mtc_actions == {}
        assert deprecated_to_merged == {}


class TestApplyDedupToTopics:
    def test_apply_dedup_merge_concatenation(self):
        """Merge: mtc_ marked deprecated, mt_ gets concatenated description + unioned fields."""
        mt = NormalizedTopic(
            topic_key="mt_alpha",
            source_taxonomy=SOURCE_BEIJING,
            topic_type="CONCEPTUAL",
            subject="mathematics",
            description_zh="MT description",
            curriculum_standards=["std1", "std2"],
            evidence=["ev1"],
        )
        mtc = NormalizedTopic(
            topic_key="mtc_alpha",
            source_taxonomy=SOURCE_BEIJING,
            topic_type="CONCEPTUAL",
            subject="mathematics",
            description_zh="MTC extra detail",
            curriculum_standards=["std2", "std3"],
            evidence=["ev2"],
        )
        topics = [mt, mtc]
        mtc_actions = {
            "mtc_alpha": {
                "mtc_topic_key": "mtc_alpha",
                "mt_topic_key": "mt_alpha",
                "action": "merge",
            }
        }

        merges = apply_dedup_to_topics(topics, mtc_actions)

        assert merges == 1
        assert mtc.deprecated is True
        assert mt.deprecated is False
        # Description concatenated with \n\n
        assert mt.description_zh == "MT description\n\nMTC extra detail"
        # curriculum_standards unioned (order-preserving, deduped)
        assert mt.curriculum_standards == ["std1", "std2", "std3"]
        # evidence unioned
        assert mt.evidence == ["ev1", "ev2"]

    def test_apply_dedup_hide_mtc(self):
        """hide_mtc: mtc_ marked deprecated, mt_ unchanged."""
        mt = NormalizedTopic(
            topic_key="mt_beta",
            source_taxonomy=SOURCE_BEIJING,
            topic_type="CONCEPTUAL",
            subject="science",
            description_zh="Original",
        )
        mtc = NormalizedTopic(
            topic_key="mtc_beta",
            source_taxonomy=SOURCE_BEIJING,
            topic_type="CONCEPTUAL",
            subject="science",
            description_zh="MTC version",
        )
        topics = [mt, mtc]
        mtc_actions = {
            "mtc_beta": {
                "mtc_topic_key": "mtc_beta",
                "mt_topic_key": None,
                "action": "hide_mtc",
            }
        }

        merges = apply_dedup_to_topics(topics, mtc_actions)

        assert merges == 0
        assert mtc.deprecated is True
        assert mt.deprecated is False
        assert mt.description_zh == "Original"

    def test_apply_dedup_keep_both(self):
        """keep_both: neither topic is modified."""
        mt = NormalizedTopic(
            topic_key="mt_gamma",
            source_taxonomy=SOURCE_BEIJING,
            topic_type="CONCEPTUAL",
            subject="english",
            description_zh="MT",
        )
        mtc = NormalizedTopic(
            topic_key="mtc_gamma",
            source_taxonomy=SOURCE_BEIJING,
            topic_type="CONCEPTUAL",
            subject="english",
            description_zh="MTC",
        )
        topics = [mt, mtc]
        mtc_actions = {
            "mtc_gamma": {
                "mtc_topic_key": "mtc_gamma",
                "mt_topic_key": "mt_gamma",
                "action": "keep_both",
            }
        }

        merges = apply_dedup_to_topics(topics, mtc_actions)

        assert merges == 0
        assert mt.deprecated is False
        assert mtc.deprecated is False
        assert mt.description_zh == "MT"
        assert mtc.description_zh == "MTC"


class TestUnionList:
    def test_union_list(self):
        """Order-preserving union with deduplication."""
        result = _union_list(["a", "b", "c"], ["b", "c", "d"])
        assert result == ["a", "b", "c", "d"]

    def test_union_list_empty(self):
        assert _union_list([], ["x"]) == ["x"]
        assert _union_list(["x"], []) == ["x"]
        assert _union_list([], []) == []

    def test_union_list_no_overlap(self):
        assert _union_list(["a"], ["b"]) == ["a", "b"]

    def test_union_list_full_overlap(self):
        assert _union_list(["a", "b"], ["a", "b"]) == ["a", "b"]


# ---------------------------------------------------------------------------
# DB-dependent tests (use `db` fixture)
# ---------------------------------------------------------------------------


class TestUpsertTopic:
    def test_upsert_topic_creates_new(self, db: Session):
        """First call creates a new row, returns True."""
        topic = NormalizedTopic(
            topic_key="mt_new1",
            source_taxonomy=SOURCE_BEIJING,
            topic_type="CONCEPTUAL",
            subject="mathematics",
            name="New Topic",
            description="A new topic",
        )
        created = upsert_topic(db, topic)
        db.flush()

        assert created is True
        row = db.query(LearningTopic).filter_by(
            topic_key="mt_new1", source_taxonomy=SOURCE_BEIJING
        ).first()
        assert row is not None
        assert row.name == "New Topic"
        assert row.subject == "mathematics"

    def test_upsert_topic_updates_existing(self, db: Session):
        """Second call with same composite key updates the row, returns False."""
        topic_v1 = NormalizedTopic(
            topic_key="mt_upd1",
            source_taxonomy=SOURCE_BEIJING,
            topic_type="CONCEPTUAL",
            subject="mathematics",
            name="Version 1",
            description="Desc v1",
        )
        created1 = upsert_topic(db, topic_v1)
        db.flush()
        assert created1 is True

        topic_v2 = NormalizedTopic(
            topic_key="mt_upd1",
            source_taxonomy=SOURCE_BEIJING,
            topic_type="CONCEPTUAL",
            subject="mathematics",
            name="Version 2",
            description="Desc v2",
        )
        created2 = upsert_topic(db, topic_v2)
        db.flush()

        assert created2 is False
        row = db.query(LearningTopic).filter_by(
            topic_key="mt_upd1", source_taxonomy=SOURCE_BEIJING
        ).first()
        assert row.name == "Version 2"
        assert row.description == "Desc v2"

    def test_upsert_topic_composite_key(self, db: Session):
        """Same topic_key with different source_taxonomy creates TWO separate rows."""
        topic_beijing = NormalizedTopic(
            topic_key="mt_shared",
            source_taxonomy=SOURCE_BEIJING,
            topic_type="CONCEPTUAL",
            subject="mathematics",
            name="Beijing Version",
        )
        topic_ostax = NormalizedTopic(
            topic_key="mt_shared",
            source_taxonomy="os-taxonomy",
            topic_type="CONCEPTUAL",
            subject="mathematics",
            name="OS-Taxonomy Version",
        )
        created1 = upsert_topic(db, topic_beijing)
        created2 = upsert_topic(db, topic_ostax)
        db.flush()

        assert created1 is True
        assert created2 is True
        rows = db.query(LearningTopic).filter_by(topic_key="mt_shared").all()
        assert len(rows) == 2
        names = {r.name for r in rows}
        assert names == {"Beijing Version", "OS-Taxonomy Version"}


class TestUpsertCluster:
    def test_upsert_cluster_creates_new(self, db: Session):
        """First call creates a new cluster, returns True."""
        cluster = NormalizedCluster(
            subject="mathematics",
            domain="Algebra",
            age_range_start=8,
            summary="Algebra basics",
            source_taxonomy=SOURCE_BEIJING,
        )
        created = upsert_cluster(db, cluster)
        db.flush()

        assert created is True
        row = db.query(LearningCluster).filter_by(
            subject="mathematics",
            domain="Algebra",
            age_range_start=8,
            source_taxonomy=SOURCE_BEIJING,
        ).first()
        assert row is not None
        assert row.summary == "Algebra basics"

    def test_upsert_cluster_skips_existing(self, db: Session):
        """Second call with same composite key skips, returns False (updates summary)."""
        cluster_v1 = NormalizedCluster(
            subject="science",
            domain="Physics",
            age_range_start=10,
            summary="Physics v1",
            source_taxonomy=SOURCE_BEIJING,
        )
        created1 = upsert_cluster(db, cluster_v1)
        db.flush()
        assert created1 is True

        cluster_v2 = NormalizedCluster(
            subject="science",
            domain="Physics",
            age_range_start=10,
            summary="Physics v2 updated",
            source_taxonomy=SOURCE_BEIJING,
        )
        created2 = upsert_cluster(db, cluster_v2)
        db.flush()

        assert created2 is False
        row = db.query(LearningCluster).filter_by(
            subject="science",
            domain="Physics",
            age_range_start=10,
            source_taxonomy=SOURCE_BEIJING,
        ).first()
        assert row.summary == "Physics v2 updated"
