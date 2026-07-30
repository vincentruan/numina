# server/tests/backend/test_ai_internal_web_search.py
from unittest.mock import patch

import pytest

from apps.backend.app.models.family import Family
from apps.backend.app.models.family_mcp_server import FamilyMCPServer
from apps.backend.app.models.family_web_search_provider import FamilyWebSearchProvider
from apps.backend.app.services.ai_crypto import encrypt_api_key
from apps.backend.app.utils.snowflake import next_id
from packages.security.service_auth.agent_jwt import create_agent_token

# Set SECRET_KEY before create_agent_token calls (singleton settings)
from packages.core.settings import settings as _core_settings

_core_settings.SECRET_KEY = "test-secret-key-for-jwt-tests"
_FAMILY_ID = "1001"


def _make_jwt(family_id: str = _FAMILY_ID) -> str:
    return create_agent_token(family_id)


@pytest.fixture
def internal_headers():
    """Headers that pass verify_agent_token."""
    return {
        "Authorization": f"Bearer {_make_jwt()}",
        "X-Family-Id": _FAMILY_ID,
    }


@pytest.fixture
def seed_family_1001(db):
    """Seed family 1001 so verify_agent_token validation passes."""
    family = Family(
        id=1001,
        name="Test Family 1001",
        invite_code="INV1001",
        created_by=1001,
    )
    db.add(family)
    db.commit()
    return family


@pytest.fixture
def setup_web_search(db, seed_family_1001):
    """Create enabled web search providers for family 1001."""
    p1 = FamilyWebSearchProvider(
        id=next_id(),
        family_id=1001,
        provider_name="tavily",
        api_key_encrypted=encrypt_api_key("tvly-test-key"),
        is_enabled=True,
        display_order=1,
        max_results=5,
        circuit_state="closed",
    )
    p2 = FamilyWebSearchProvider(
        id=next_id(),
        family_id=1001,
        provider_name="ddg_search",
        is_enabled=True,
        display_order=2,
        max_results=3,
        circuit_state="closed",
    )
    p3 = FamilyWebSearchProvider(
        id=next_id(),
        family_id=1001,
        provider_name="exa",
        api_key_encrypted=encrypt_api_key("exa-key"),
        is_enabled=True,
        display_order=3,
        max_results=5,
        circuit_state="open",
    )
    db.add_all([p1, p2, p3])
    db.commit()
    return [p1, p2, p3]


@pytest.fixture
def setup_websearch_mcp(db, seed_family_1001):
    """Create a websearch-type MCP server for family 1001."""
    mcp = FamilyMCPServer(
        id=next_id(),
        family_id=1001,
        name="brave-mcp",
        url="http://localhost:3001/sse",
        transport="sse",
        is_enabled=True,
        mcp_type="websearch",
    )
    db.add(mcp)
    db.commit()
    return mcp


def test_internal_config_includes_web_search_providers(client, internal_headers, setup_web_search):
    resp = client.get("/api/v1/internal/ai/config", headers=internal_headers)
    assert resp.status_code == 200
    envelope = resp.json()
    assert envelope["code"] == "OK"
    data = envelope["data"]
    assert "web_search_providers" in data
    providers = data["web_search_providers"]
    # Only non-open circuit providers returned
    assert len(providers) == 2
    assert providers[0]["provider_name"] == "tavily"
    assert providers[0]["api_key"] == "tvly-test-key"
    assert providers[1]["provider_name"] == "ddg_search"
    assert providers[1]["api_key"] is None


def test_internal_config_includes_websearch_mcp(client, internal_headers, setup_websearch_mcp):
    resp = client.get("/api/v1/internal/ai/config", headers=internal_headers)
    assert resp.status_code == 200
    envelope = resp.json()
    assert envelope["code"] == "OK"
    data = envelope["data"]
    assert "web_search_mcp_servers" in data
    mcps = data["web_search_mcp_servers"]
    assert len(mcps) == 1
    assert mcps[0]["name"] == "brave-mcp"
    assert mcps[0]["transport"] == "sse"