"""Tests for preset learning paths: generation, assignment, and listing."""

import json

import pytest
from sqlalchemy.orm import Session

from apps.backend.app.services.learning.preset_path_service import (
    assign_preset_path,
    generate_preset_paths,
    list_preset_paths,
)
from packages.db.models.learning.path import LearningPath, LearningPathItem
from packages.db.models.learning.preset_path import PresetLearningPath
from packages.db.models.learning.topic import LearningDependency, LearningTopic
from packages.db.models.user import User

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def child_user(db: Session, client, auth_headers):
    """Create a child via API."""
    resp = client.post(
        "/api/v1/family/children",
        headers=auth_headers,
        json={
            "username": "presetchild",
            "password": "ChildPass1",
            "display_name": "Preset Kid",
            "avatar_color": "#FF5733",
            "pin": ["🐱", "🌟", "🎈", "🐶"],
        },
    )
    assert resp.status_code == 201
    child_id = int(resp.json()["data"]["id"])
    child = db.query(User).filter(User.id == child_id).first()
    db.flush()
    return {"id": child_id, "parent_id": int(auth_headers.get("X-User-Id", "0"))}


def _make_topic(db, *, key, subject="mathematics", age_group="mid", curriculum="[]", **kw):
    """Create a learning topic with curriculum standards."""
    t = LearningTopic(
        topic_key=key,
        topic_type=kw.get("topic_type", "CONCEPTUAL"),
        subject=subject,
        domain=kw.get("domain", "Test"),
        name=kw.get("name", f"Topic {key}"),
        name_zh=kw.get("name_zh"),
        description="Test topic",
        age_group=age_group,
        centrality=kw.get("centrality", 50.0),
        evidence_json="[]",
        standards_json="[]",
        curriculum_standards_json=curriculum,
        source_taxonomy=kw.get("source_taxonomy", "os-taxonomy"),
    )
    db.add(t)
    db.flush()
    return t


@pytest.fixture
def topic_with_curriculum(db: Session):
    """A topic with curriculum standards."""
    curriculum = json.dumps([{"key": "moe-2022-math:S1.N.01", "name": "Math Std 1", "code": "S1.N.01"}])
    return _make_topic(db, key="curr_1", curriculum=curriculum, age_group="mid")


@pytest.fixture
def topic_chain(db: Session):
    """Three topics with hard dependencies: A -> B -> C."""
    a = _make_topic(db, key="chain_a", name="Chain A", age_group="mid")
    b = _make_topic(db, key="chain_b", name="Chain B", age_group="mid")
    c = _make_topic(db, key="chain_c", name="Chain C", age_group="mid")

    # Add curriculum standards to all
    curriculum = json.dumps([{"key": "moe-2022-math:S1.N.01", "name": "Math Std 1", "code": "S1.N.01"}])
    a.curriculum_standards_json = curriculum
    b.curriculum_standards_json = curriculum
    c.curriculum_standards_json = curriculum

    # Hard dependencies: B requires A, C requires B
    db.add(LearningDependency(topic_id=b.id, prerequisite_id=a.id, strength="hard"))
    db.add(LearningDependency(topic_id=c.id, prerequisite_id=b.id, strength="hard"))
    db.flush()
    return {"a": a, "b": b, "c": c}


@pytest.fixture
def preset_path(db: Session, topic_with_curriculum):
    """A preset learning path."""
    preset = PresetLearningPath(
        grade=3,
        semester="fall",
        subject="mathematics",
        name="Grade 3 Fall · Math · Unit 1",
        name_zh="三年级上 · 数学 · 第一单元",
        description="Test preset path",
        topic_ids_json=json.dumps([topic_with_curriculum.id]),
        topic_count=1,
        age_group="mid",
        source_taxonomy="os-taxonomy",
        is_active=True,
    )
    db.add(preset)
    db.commit()
    db.refresh(preset)
    return preset


# ---------------------------------------------------------------------------
# TestGeneratePresetPaths
# ---------------------------------------------------------------------------


class TestGeneratePresetPaths:
    def test_generates_paths_from_curriculum_standards(self, db: Session, topic_with_curriculum):
        """Generate preset paths from topics with curriculum_standards_json."""
        paths = generate_preset_paths(db)
        assert len(paths) > 0
        for p in paths:
            assert p.topic_count > 0
            assert p.grade in range(1, 7)
            assert p.semester in ("fall", "spring")

    def test_topics_ordered_by_prerequisites(self, db: Session, topic_chain):
        """Within a preset path, topics are topologically sorted by hard dependencies."""
        paths = generate_preset_paths(db)
        for p in paths:
            topic_ids = json.loads(p.topic_ids_json)
            # Verify no topic appears before its hard prereqs
            for i, tid in enumerate(topic_ids):
                prior = set(topic_ids[:i])
                # Get hard prerequisites for this topic
                hard_prereqs = {
                    dep.prerequisite_id
                    for dep in db.query(LearningDependency)
                    .filter(
                        LearningDependency.topic_id == tid,
                        LearningDependency.strength == "hard",
                    )
                    .all()
                }
                # All hard prereqs in the path should appear before this topic
                prereqs_in_path = hard_prereqs.intersection(set(topic_ids))
                assert prereqs_in_path.issubset(prior)


# ---------------------------------------------------------------------------
# TestAssignPresetPath
# ---------------------------------------------------------------------------


class TestAssignPresetPath:
    def test_creates_learning_path_for_child(self, db: Session, child_user, preset_path):
        """Assigning a preset creates a LearningPath for the child."""
        path = assign_preset_path(db, preset_path.id, child_user["id"], child_user["parent_id"])
        assert path.child_id == child_user["id"]
        assert path.status == "active"

    def test_creates_path_items_for_each_topic(self, db: Session, child_user, preset_path):
        """Assigning a preset creates LearningPathItems for each topic."""
        path = assign_preset_path(db, preset_path.id, child_user["id"], child_user["parent_id"])
        items = db.query(LearningPathItem).filter_by(path_id=path.id).all()
        assert len(items) == preset_path.topic_count

    def test_assigning_same_preset_twice_creates_new_path(self, db: Session, child_user, preset_path):
        """Assigning the same preset twice creates two separate paths."""
        path1 = assign_preset_path(db, preset_path.id, child_user["id"], child_user["parent_id"])
        path2 = assign_preset_path(db, preset_path.id, child_user["id"], child_user["parent_id"])
        assert path1.id != path2.id


# ---------------------------------------------------------------------------
# TestListPresetPaths
# ---------------------------------------------------------------------------


class TestListPresetPaths:
    def test_list_all_preset_paths(self, db: Session, preset_path):
        """List all preset paths without filters."""
        paths = list_preset_paths(db, grade=None, semester=None, subject=None)
        assert len(paths) >= 1
        assert any(p.id == preset_path.id for p in paths)

    def test_filter_by_grade(self, db: Session, preset_path):
        """Filter preset paths by grade."""
        paths = list_preset_paths(db, grade=3, semester=None, subject=None)
        assert len(paths) >= 1
        assert all(p.grade == 3 for p in paths)

    def test_filter_by_semester(self, db: Session, preset_path):
        """Filter preset paths by semester."""
        paths = list_preset_paths(db, grade=None, semester="fall", subject=None)
        assert len(paths) >= 1
        assert all(p.semester == "fall" for p in paths)

    def test_filter_by_subject(self, db: Session, preset_path):
        """Filter preset paths by subject."""
        paths = list_preset_paths(db, grade=None, semester=None, subject="mathematics")
        assert len(paths) >= 1
        assert all(p.subject == "mathematics" for p in paths)
