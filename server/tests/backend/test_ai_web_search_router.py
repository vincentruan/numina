# server/tests/backend/test_ai_web_search_router.py
import pytest



# NOTE: Do NOT define a local `client` fixture here.
# Use the `client` fixture from server/tests/backend/conftest.py which
# properly overrides get_db for test isolation.
# The `owner_headers` fixture below uses the conftest's client.

@pytest.fixture
def owner_headers(client):
    """Register + login as owner, return auth headers.
    Uses conftest's `client` fixture which has proper DB isolation.
    """
    client.post("/api/v1/auth/register", json={
        "username": "wsowner",
        "password": "Test1234!",
        "display_name": "WebSearch Owner",
        "family_name": "WebSearchFamily",
        "family_invitation_code": "AUTO-TEST",
    })
    resp = client.post("/api/v1/auth/login", json={
        "username": "wsowner",
        "password": "Test1234!",
    })
    data = resp.json().get("data", resp.json())
    token = data["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_list_templates(client, owner_headers):
    resp = client.get("/api/v1/ai/web-search/templates", headers=owner_headers)
    assert resp.status_code == 200
    data = resp.json().get("data", resp.json())
    assert len(data) == 5
    assert any(t["provider_name"] == "tavily" for t in data)


def test_create_provider(client, owner_headers):
    resp = client.post("/api/v1/ai/web-search", headers=owner_headers, json={
        "provider_name": "tavily",
        "api_key": "tvly-test-key-123",
        "max_results": 5,
    })
    assert resp.status_code == 201
    data = resp.json().get("data", resp.json())
    assert data["provider_name"] == "tavily"
    assert "id" in data
    assert "api_key" not in data  # encrypted, not returned


def test_create_ddg_without_api_key(client, owner_headers):
    resp = client.post("/api/v1/ai/web-search", headers=owner_headers, json={
        "provider_name": "ddg_search",
        "max_results": 5,
    })
    assert resp.status_code == 201
    data = resp.json().get("data", resp.json())
    assert data["provider_name"] == "ddg_search"


def test_create_unknown_provider_fails(client, owner_headers):
    resp = client.post("/api/v1/ai/web-search", headers=owner_headers, json={
        "provider_name": "unknown_engine",
        "api_key": "key",
    })
    assert resp.status_code == 422


def test_list_providers(client, owner_headers):
    client.post("/api/v1/ai/web-search", headers=owner_headers, json={
        "provider_name": "ddg_search",
        "max_results": 3,
    })
    resp = client.get("/api/v1/ai/web-search", headers=owner_headers)
    assert resp.status_code == 200
    data = resp.json().get("data", resp.json())
    assert len(data) >= 1


def test_enable_provider(client, owner_headers):
    create_resp = client.post("/api/v1/ai/web-search", headers=owner_headers, json={
        "provider_name": "ddg_search",
    })
    create_data = create_resp.json().get("data", create_resp.json())
    pid = create_data["id"]
    resp = client.post(f"/api/v1/ai/web-search/{pid}/enable", headers=owner_headers)
    assert resp.status_code == 200
    data = resp.json().get("data", resp.json())
    assert data["is_enabled"] is True


def test_disable_provider(client, owner_headers):
    create_resp = client.post("/api/v1/ai/web-search", headers=owner_headers, json={
        "provider_name": "ddg_search",
    })
    create_data = create_resp.json().get("data", create_resp.json())
    pid = create_data["id"]
    client.post(f"/api/v1/ai/web-search/{pid}/enable", headers=owner_headers)
    resp = client.post(f"/api/v1/ai/web-search/{pid}/disable", headers=owner_headers)
    assert resp.status_code == 200
    data = resp.json().get("data", resp.json())
    assert data["is_enabled"] is False


def test_delete_provider(client, owner_headers):
    create_resp = client.post("/api/v1/ai/web-search", headers=owner_headers, json={
        "provider_name": "ddg_search",
    })
    create_data = create_resp.json().get("data", create_resp.json())
    pid = create_data["id"]
    resp = client.delete(f"/api/v1/ai/web-search/{pid}", headers=owner_headers)
    assert resp.status_code == 204


def test_status_endpoint(client, owner_headers):
    resp = client.get("/api/v1/ai/web-search/status", headers=owner_headers)
    assert resp.status_code == 200
    data = resp.json().get("data", resp.json())
    assert "enabled_count" in data
    assert "has_web_search" in data