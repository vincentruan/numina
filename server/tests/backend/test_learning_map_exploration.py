"""Tests for map exploration instrumentation (R11, R12, AE4).

Records how long a child spent on the knowledge map before their first topic
selection, and how deep they zoomed — so exploration depth is separable from
dwell time.
"""

import pytest

from packages.db.models.learning.map_exploration import LearningMapExploration
from tests.backend.conftest import child_login_two_phase

PIN = ["🐱", "🌟", "🎈", "🐶"]
CHILD_PASSWORD = "ChildPass1"


def _make_topic(db, *, key: str, subject: str = "mathematics", domain: str = "Addition"):
    from packages.db.models.learning.topic import LearningTopic

    topic = LearningTopic(
        topic_key=key,
        topic_type="CONCEPTUAL",
        subject=subject,
        domain=domain,
        name=key,
        description="",
        age_group="mid",
        source_taxonomy="beijing",
        evidence_json="[]",
        standards_json="[]",
    )
    db.add(topic)
    return topic


@pytest.fixture
def child_headers(client, auth_headers):
    resp = client.post(
        "/api/v1/family/children",
        headers=auth_headers,
        json={
            "username": "mapchild",
            "password": CHILD_PASSWORD,
            "display_name": "Map Explorer",
            "avatar_color": "#FF5733",
            "pin": PIN,
        },
    )
    assert resp.status_code == 201
    token = child_login_two_phase(client, "mapchild", CHILD_PASSWORD, PIN)
    return {"Authorization": f"Bearer {token}"}


class TestRecordExploration:
    def test_records_a_completed_exploration(self, client, child_headers, db):
        resp = client.post(
            "/api/v1/child/learning/map/explorations",
            headers=child_headers,
            json={
                "duration_ms": 125_000,
                "max_zoom_level": 2,
                "topic_selected": True,
                "interaction_count": 14,
            },
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()["data"]
        assert body["duration_ms"] == 125_000
        assert body["max_zoom_level"] == 2
        assert body["topic_selected"] is True
        assert body["interaction_count"] == 14

        row = db.query(LearningMapExploration).one()
        assert row.duration_ms == 125_000
        assert row.max_zoom_level == 2
        assert row.topic_selected is True

    def test_records_session_with_no_topic_selection(self, client, child_headers, db):
        """AE4 — exploration that ends without a selection is still retained."""
        resp = client.post(
            "/api/v1/child/learning/map/explorations",
            headers=child_headers,
            json={
                "duration_ms": 48_000,
                "max_zoom_level": 1,
                "topic_selected": False,
                "interaction_count": 6,
            },
        )
        assert resp.status_code == 201, resp.text
        row = db.query(LearningMapExploration).one()
        assert row.duration_ms == 48_000
        assert row.max_zoom_level == 1
        assert row.topic_selected is False

    def test_stores_selected_topic_id(self, client, child_headers, db):
        """R12 — the selected topic is recorded, so a selection is attributable."""
        topic = _make_topic(db, key="map-selected-topic")
        db.flush()

        resp = client.post(
            "/api/v1/child/learning/map/explorations",
            headers=child_headers,
            json={
                "duration_ms": 1000,
                "max_zoom_level": 2,
                "topic_selected": True,
                "interaction_count": 1,
                "selected_topic_id": str(topic.id),
            },
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["data"]["selected_topic_id"] == str(topic.id)

    def test_clears_topic_id_when_no_selection(self, client, child_headers, db):
        """A stray topic id with topic_selected=false is not recorded."""
        topic = _make_topic(db, key="map-unselected-topic")
        db.flush()

        resp = client.post(
            "/api/v1/child/learning/map/explorations",
            headers=child_headers,
            json={
                "duration_ms": 1000,
                "max_zoom_level": 1,
                "topic_selected": False,
                "interaction_count": 3,
                "selected_topic_id": str(topic.id),
            },
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["data"]["selected_topic_id"] is None

    def test_rejects_unknown_zoom_level(self, client, child_headers):
        resp = client.post(
            "/api/v1/child/learning/map/explorations",
            headers=child_headers,
            json={
                "duration_ms": 1000,
                "max_zoom_level": 7,
                "topic_selected": False,
                "interaction_count": 0,
            },
        )
        assert resp.status_code == 422

    def test_rejects_negative_duration(self, client, child_headers):
        resp = client.post(
            "/api/v1/child/learning/map/explorations",
            headers=child_headers,
            json={
                "duration_ms": -5,
                "max_zoom_level": 0,
                "topic_selected": False,
                "interaction_count": 0,
            },
        )
        assert resp.status_code == 422

    def test_requires_child_auth(self, client):
        resp = client.post(
            "/api/v1/child/learning/map/explorations",
            json={
                "duration_ms": 1000,
                "max_zoom_level": 0,
                "topic_selected": False,
                "interaction_count": 0,
            },
        )
        assert resp.status_code in (401, 403)

    def test_adult_cannot_post_as_child(self, client, auth_headers):
        resp = client.post(
            "/api/v1/child/learning/map/explorations",
            headers=auth_headers,
            json={
                "duration_ms": 1000,
                "max_zoom_level": 0,
                "topic_selected": False,
                "interaction_count": 0,
            },
        )
        assert resp.status_code in (401, 403)
