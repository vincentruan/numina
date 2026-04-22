"""Tests for tag CRUD and asset-tag association."""

import pytest


@pytest.fixture
def sample_tag(client, auth_headers):
    """Create a sample tag and return its data."""
    response = client.post("/api/v1/tags", headers=auth_headers, json={
        "name": "重要",
        "color": "#FF5733",
    })
    assert response.status_code == 201
    return response.json()["data"]


def test_create_tag(client, auth_headers):
    """POST /tags creates a tag and returns 201."""
    response = client.post("/api/v1/tags", headers=auth_headers, json={
        "name": "家庭",
        "color": "#3498DB",
    })
    assert response.status_code == 201
    data = response.json()["data"]
    assert data["name"] == "家庭"
    assert data["color"] == "#3498DB"
    assert "id" in data


def test_list_tags_empty(client, auth_headers):
    """GET /tags returns empty list when no tags exist."""
    response = client.get("/api/v1/tags", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["data"] == []


def test_list_tags(client, auth_headers, sample_tag):
    """GET /tags returns all tags for the family."""
    response = client.get("/api/v1/tags", headers=auth_headers)
    assert response.status_code == 200
    tags = response.json()["data"]
    assert len(tags) == 1
    assert tags[0]["id"] == str(sample_tag["id"])
    assert tags[0]["name"] == sample_tag["name"]


def test_update_tag(client, auth_headers, sample_tag):
    """PUT /tags/{id} updates name and color."""
    response = client.put(f"/api/v1/tags/{sample_tag['id']}", headers=auth_headers, json={
        "name": "非常重要",
        "color": "#E74C3C",
    })
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["name"] == "非常重要"
    assert data["color"] == "#E74C3C"


def test_update_tag_not_found(client, auth_headers):
    """PUT /tags/{id} with unknown id returns 404."""
    response = client.put("/api/v1/tags/nonexistent-id", headers=auth_headers, json={
        "name": "不存在",
    })
    assert response.status_code == 404


def test_delete_tag(client, auth_headers, sample_tag):
    """DELETE /tags/{id} removes the tag."""
    response = client.delete(f"/api/v1/tags/{sample_tag['id']}", headers=auth_headers)
    assert response.status_code == 200

    # Verify it's gone
    tags = client.get("/api/v1/tags", headers=auth_headers).json()["data"]
    assert all(t["id"] != sample_tag["id"] for t in tags)


def test_delete_tag_not_found(client, auth_headers):
    """DELETE /tags/{id} with unknown id returns 404."""
    response = client.delete("/api/v1/tags/nonexistent-id", headers=auth_headers)
    assert response.status_code == 404


def test_create_asset_with_tags(client, auth_headers, sample_tag):
    """Creating an asset with tag_ids associates the tags."""
    cats = client.get("/api/v1/categories", headers=auth_headers).json()["data"]
    cat_id = next(c["id"] for c in cats if c["asset_type"] == "physical")

    response = client.post("/api/v1/assets", headers=auth_headers, json={
        "name": "带标签资产",
        "category_id": cat_id,
        "asset_type": "physical",
        "purchase_price": 100000,
        "current_value": 100000,
        "tag_ids": [sample_tag["id"]],
    })
    assert response.status_code == 201
    data = response.json()["data"]
    tag_ids = [t["id"] for t in data.get("tags", [])]
    assert sample_tag["id"] in tag_ids


def test_tags_unauthorized(client):
    """Tag endpoints require authentication."""
    assert client.get("/api/v1/tags").status_code == 401
    assert client.post("/api/v1/tags", json={"name": "x"}).status_code == 401


def test_cross_family_tag_isolation(client, auth_headers, second_user_headers):
    """Family A tags are not visible to Family B."""
    # Create tag in family A
    client.post("/api/v1/tags", headers=auth_headers, json={"name": "家庭A标签", "color": "#AAA"})

    # Family B should see no tags
    tags_b = client.get("/api/v1/tags", headers=second_user_headers).json()["data"]
    assert all(t["name"] != "家庭A标签" for t in tags_b)


def test_cross_family_tag_update_forbidden(client, auth_headers, second_user_headers, sample_tag):
    """Family B cannot update Family A's tag."""
    response = client.put(f"/api/v1/tags/{sample_tag['id']}", headers=second_user_headers, json={
        "name": "篡改标签",
    })
    assert response.status_code == 404


def test_cross_family_tag_delete_forbidden(client, auth_headers, second_user_headers, sample_tag):
    """Family B cannot delete Family A's tag."""
    response = client.delete(f"/api/v1/tags/{sample_tag['id']}", headers=second_user_headers)
    assert response.status_code == 404
