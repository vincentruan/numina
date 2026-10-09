"""Tests for locale-based source_taxonomy filtering on learning APIs.

U6 — backend learning APIs filter topics by source_taxonomy based on the
requesting user's language:
  zh-CN  -> "beijing"
  en-US / unknown / None -> "os-taxonomy"
"""


import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from apps.backend.app.services.learning.topic_service import (
    locale_to_source_taxonomy,
)
from packages.db.models.learning.progress import LearningProgress
from packages.db.models.learning.topic import LearningTopic
from tests.backend.conftest import child_login_two_phase

# ── helpers ────────────────────────────────────────────────────────────────────

PIN = ["🐱", "🌟", "🎈", "🐶"]
CHILD_PASSWORD = "ChildPass1"


def _create_child(
    client: TestClient,
    headers: dict,
    username: str = "localechild",
    language: str | None = None,
) -> dict:  # type: ignore[no-any-return]
    """Create a child via the parent API.

    If ``language`` is set, the child's language is updated after creation
    via PUT /api/v1/auth/me/settings.
    """
    resp = client.post(
        "/api/v1/family/children",
        headers=headers,
        json={
            "username": username,
            "password": CHILD_PASSWORD,
            "display_name": "Locale Tester",
            "avatar_color": "#FF5733",
            "pin": PIN,
        },
    )
    assert resp.status_code == 201
    child = resp.json()["data"]

    if language:
        child_token = child_login_two_phase(
            client, username, CHILD_PASSWORD, PIN
        )
        child_headers = {"Authorization": f"Bearer {child_token}"}
        set_resp = client.put(
            "/api/v1/auth/me/settings",
            headers=child_headers,
            json={"language": language},
        )
        assert set_resp.status_code == 200
    return child


def _child_login(client: TestClient, username: str) -> dict:
    token = child_login_two_phase(client, username, CHILD_PASSWORD, PIN)
    return {"Authorization": f"Bearer {token}"}


def _create_topic(
    db: Session,
    topic_key: str,
    source_taxonomy: str = "os-taxonomy",
    name: str = "Topic",
    age_group: str = "mid",
) -> LearningTopic:
    t = LearningTopic(
        topic_key=topic_key,
        topic_type="CONCEPTUAL",
        subject="mathematics",
        domain="Test",
        name=name,
        description="Test topic",
        age_group=age_group,
        source_taxonomy=source_taxonomy,
        evidence_json="[]",
        standards_json="[]",
    )
    db.add(t)
    db.flush()
    return t


# ── locale_to_source_taxonomy unit tests ───────────────────────────────────────


def test_locale_zh_cn_maps_to_beijing():
    assert locale_to_source_taxonomy("zh-CN") == "beijing"


def test_locale_en_us_maps_to_os_taxonomy():
    assert locale_to_source_taxonomy("en-US") == "os-taxonomy"


def test_locale_none_maps_to_os_taxonomy():
    assert locale_to_source_taxonomy(None) == "os-taxonomy"


def test_locale_unknown_maps_to_os_taxonomy():
    assert locale_to_source_taxonomy("fr-FR") == "os-taxonomy"
    assert locale_to_source_taxonomy("") == "os-taxonomy"


# ── topic_service.list_topics locale filter ────────────────────────────────────


def test_list_topics_filter_beijing(db: Session):
    _create_topic(db, "beijing_topic", source_taxonomy="beijing")
    _create_topic(db, "os_topic", source_taxonomy="os-taxonomy")
    _create_topic(db, "beijing_topic2", source_taxonomy="beijing")

    from apps.backend.app.services.learning.topic_service import list_topics

    results = list_topics(db, source_taxonomy="beijing")
    assert len(results) == 2
    assert all(t.source_taxonomy == "beijing" for t in results)


def test_list_topics_filter_os_taxonomy(db: Session):
    _create_topic(db, "beijing_topic", source_taxonomy="beijing")
    _create_topic(db, "os_topic", source_taxonomy="os-taxonomy")

    from apps.backend.app.services.learning.topic_service import list_topics

    results = list_topics(db, source_taxonomy="os-taxonomy")
    assert len(results) == 1
    assert results[0].source_taxonomy == "os-taxonomy"


def test_list_topics_deprecated_excluded_regardless_of_locale(db: Session):
    t1 = _create_topic(db, "bj_active", source_taxonomy="beijing")
    t2 = _create_topic(db, "bj_deprecated", source_taxonomy="beijing")
    t2.deprecated = True
    db.flush()

    from apps.backend.app.services.learning.topic_service import list_topics

    results = list_topics(db, source_taxonomy="beijing", deprecated=False)
    assert len(results) == 1
    assert results[0].id == t1.id


def test_list_subjects_locale_filter(db: Session):
    _create_topic(db, "bj_subj", source_taxonomy="beijing")
    _create_topic(db, "os_subj", source_taxonomy="os-taxonomy")
    _create_topic(db, "bj_subj2", source_taxonomy="beijing")

    from apps.backend.app.services.learning.topic_service import list_subjects

    bj_subjects = list_subjects(db, source_taxonomy="beijing")
    assert sum(s["topic_count"] for s in bj_subjects) == 2

    os_subjects = list_subjects(db, source_taxonomy="os-taxonomy")
    assert sum(s["topic_count"] for s in os_subjects) == 1


# ── API-level tests: child endpoints ───────────────────────────────────────────


@pytest.fixture
def zh_child_setup(client, db, auth_headers):
    """zh-CN child with a beijing topic and an os-taxonomy topic."""
    child = _create_child(client, auth_headers, username="zhchild")
    child_headers = _child_login(client, child["username"])
    child_id = int(child["id"])

    bj_topic = _create_topic(db, "zh_bj_topic", source_taxonomy="beijing", name="BJ Topic")
    os_topic = _create_topic(db, "zh_os_topic", source_taxonomy="os-taxonomy", name="OS Topic")

    # Create progress so the child has visible topics
    db.add(LearningProgress(
        child_id=child_id, topic_id=bj_topic.id, mastery_level="learning"
    ))
    db.add(LearningProgress(
        child_id=child_id, topic_id=os_topic.id, mastery_level="learning"
    ))
    db.flush()

    return {
        "child": child,
        "child_headers": child_headers,
        "child_id": child_id,
        "bj_topic": bj_topic,
        "os_topic": os_topic,
    }


def test_child_knowledge_map_locale_filter(client, zh_child_setup):
    """zh-CN child's knowledge map only shows beijing topics."""
    resp = client.get(
        "/api/v1/child/learning/map", headers=zh_child_setup["child_headers"]
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    topic_ids = {int(p["topic_id"]) for p in data}
    assert zh_child_setup["bj_topic"].id in topic_ids
    assert zh_child_setup["os_topic"].id not in topic_ids


def test_child_topic_detail_locale_filter(client, zh_child_setup):
    """zh-CN child cannot fetch os-taxonomy topic detail (404)."""
    bj_id = zh_child_setup["bj_topic"].id
    os_id = zh_child_setup["os_topic"].id

    resp_bj = client.get(
        f"/api/v1/child/learning/topics/{bj_id}",
        headers=zh_child_setup["child_headers"],
    )
    assert resp_bj.status_code == 200

    resp_os = client.get(
        f"/api/v1/child/learning/topics/{os_id}",
        headers=zh_child_setup["child_headers"],
    )
    assert resp_os.status_code == 404


def test_child_today_locale_filter(client, zh_child_setup):
    """zh-CN child's today endpoint only shows beijing topics as current."""
    resp = client.get(
        "/api/v1/child/learning/today",
        headers=zh_child_setup["child_headers"],
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    if data["current_topic"]:
        assert int(data["current_topic"]["id"]) == zh_child_setup["bj_topic"].id


# ── en-US child: sees os-taxonomy topics ──────────────────────────────────────


@pytest.fixture
def en_child_setup(client, db, auth_headers):
    """en-US child with a beijing topic and an os-taxonomy topic."""
    child = _create_child(
        client, auth_headers, username="enchild", language="en-US"
    )
    child_headers = _child_login(client, child["username"])
    child_id = int(child["id"])

    bj_topic = _create_topic(db, "en_bj_topic", source_taxonomy="beijing", name="BJ Topic EN")
    os_topic = _create_topic(db, "en_os_topic", source_taxonomy="os-taxonomy", name="OS Topic EN")

    db.add(LearningProgress(
        child_id=child_id, topic_id=bj_topic.id, mastery_level="learning"
    ))
    db.add(LearningProgress(
        child_id=child_id, topic_id=os_topic.id, mastery_level="learning"
    ))
    db.flush()

    return {
        "child_headers": child_headers,
        "child_id": child_id,
        "bj_topic": bj_topic,
        "os_topic": os_topic,
    }


def test_en_child_knowledge_map_shows_os_taxonomy(client, en_child_setup):
    """en-US child's knowledge map shows os-taxonomy topics, not beijing."""
    resp = client.get(
        "/api/v1/child/learning/map",
        headers=en_child_setup["child_headers"],
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    topic_ids = {int(p["topic_id"]) for p in data}
    assert en_child_setup["os_topic"].id in topic_ids
    assert en_child_setup["bj_topic"].id not in topic_ids


def test_en_child_topic_detail_rejects_beijing(client, en_child_setup):
    """en-US child cannot fetch beijing topic detail (404)."""
    bj_id = en_child_setup["bj_topic"].id
    os_id = en_child_setup["os_topic"].id

    resp_os = client.get(
        f"/api/v1/child/learning/topics/{os_id}",
        headers=en_child_setup["child_headers"],
    )
    assert resp_os.status_code == 200

    resp_bj = client.get(
        f"/api/v1/child/learning/topics/{bj_id}",
        headers=en_child_setup["child_headers"],
    )
    assert resp_bj.status_code == 404


# ── family (parent) endpoints ──────────────────────────────────────────────────


def test_parent_child_map_locale_filter(client, db, auth_headers):
    """Parent's view of child's knowledge map applies parent's locale filter."""
    # Create child + zh-CN parent (default language)
    child = _create_child(client, auth_headers, username="famchild")
    child_id = int(child["id"])

    bj_topic = _create_topic(db, "fam_bj", source_taxonomy="beijing")
    os_topic = _create_topic(db, "fam_os", source_taxonomy="os-taxonomy")

    db.add(LearningProgress(
        child_id=child_id, topic_id=bj_topic.id, mastery_level="learning"
    ))
    db.add(LearningProgress(
        child_id=child_id, topic_id=os_topic.id, mastery_level="learning"
    ))
    db.flush()

    # Parent (auth_headers) defaults to zh-CN -> sees beijing only
    resp = client.get(
        f"/api/v1/family/learning/children/{child_id}/map",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    topic_ids = {int(p["topic_id"]) for p in data}
    assert bj_topic.id in topic_ids
    assert os_topic.id not in topic_ids


def test_parent_child_progress_locale_filter(client, db, auth_headers):
    """Parent's view of child's progress applies parent's locale filter."""
    child = _create_child(client, auth_headers, username="progchild")
    child_id = int(child["id"])

    bj_topic = _create_topic(db, "prog_bj", source_taxonomy="beijing")
    os_topic = _create_topic(db, "prog_os", source_taxonomy="os-taxonomy")

    db.add(LearningProgress(
        child_id=child_id, topic_id=bj_topic.id, mastery_level="learning"
    ))
    db.add(LearningProgress(
        child_id=child_id, topic_id=os_topic.id, mastery_level="learning"
    ))
    db.flush()

    resp = client.get(
        f"/api/v1/family/learning/children/{child_id}/progress",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    topic_ids = {int(p["topic_id"]) for p in data}
    assert bj_topic.id in topic_ids
    assert os_topic.id not in topic_ids


def test_parent_topic_detail_locale_filter(client, db, auth_headers):
    """Parent cannot fetch topic from the other taxonomy (404)."""
    bj_topic = _create_topic(db, "pd_bj", source_taxonomy="beijing")
    os_topic = _create_topic(db, "pd_os", source_taxonomy="os-taxonomy")

    # zh-CN parent -> sees beijing only
    resp_bj = client.get(
        f"/api/v1/family/learning/topics/{bj_topic.id}",
        headers=auth_headers,
    )
    assert resp_bj.status_code == 200

    resp_os = client.get(
        f"/api/v1/family/learning/topics/{os_topic.id}",
        headers=auth_headers,
    )
    assert resp_os.status_code == 404


# ── Global (public) learning endpoints ─────────────────────────────────────────


def test_global_topic_index_locale_filter(client, db, auth_headers):
    """Topic index applies locale filter based on authenticated user's language."""
    _create_topic(db, "idx_bj", source_taxonomy="beijing")
    _create_topic(db, "idx_os", source_taxonomy="os-taxonomy")

    # zh-CN user -> only beijing topics
    resp = client.get(
        "/api/v1/learning/topics/index", headers=auth_headers
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    bj_topic = db.query(LearningTopic).filter(LearningTopic.topic_key == "idx_bj").first()
    os_topic = db.query(LearningTopic).filter(LearningTopic.topic_key == "idx_os").first()
    topic_ids = {int(t["id"]) for t in data}
    assert bj_topic.id in topic_ids
    assert os_topic.id not in topic_ids


def test_global_list_topics_locale_filter(client, db, auth_headers):
    """GET /learning/topics applies locale filter."""
    _create_topic(db, "lst_bj", source_taxonomy="beijing")
    _create_topic(db, "lst_os", source_taxonomy="os-taxonomy")

    resp = client.get("/api/v1/learning/topics", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    topic_keys = {t["topic_key"] for t in data}
    assert "lst_bj" in topic_keys
    assert "lst_os" not in topic_keys


def test_global_subjects_locale_filter(client, db, auth_headers):
    """GET /learning/subjects counts only topics from user's taxonomy."""
    _create_topic(db, "subj_bj", source_taxonomy="beijing")
    _create_topic(db, "subj_bj2", source_taxonomy="beijing")
    _create_topic(db, "subj_os", source_taxonomy="os-taxonomy")

    resp = client.get("/api/v1/learning/subjects", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    total = sum(s["topic_count"] for s in data)
    assert total == 2  # only beijing topics counted


def test_global_topic_batch_locale_filter(client, db, auth_headers):
    """GET /learning/topics/batch applies locale filter."""
    bj = _create_topic(db, "batch_bj", source_taxonomy="beijing")
    os_ = _create_topic(db, "batch_os", source_taxonomy="os-taxonomy")

    resp = client.get(
        f"/api/v1/learning/topics/batch?ids={bj.id},{os_.id}",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    ids = {int(t["id"]) for t in data}
    assert bj.id in ids
    assert os_.id not in ids


# ── Explicit source_taxonomy override ──────────────────────────────────────────


def test_explicit_source_taxonomy_overrides_locale(client, db, auth_headers):
    """Query param source_taxonomy overrides user's language-derived taxonomy."""
    _create_topic(db, "over_bj", source_taxonomy="beijing")
    _create_topic(db, "over_os", source_taxonomy="os-taxonomy")

    # User is zh-CN (beijing) but override to os-taxonomy via query param
    resp = client.get(
        "/api/v1/learning/topics?source_taxonomy=os-taxonomy",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    topic_keys = {t["topic_key"] for t in data}
    assert "over_os" in topic_keys
    assert "over_bj" not in topic_keys
