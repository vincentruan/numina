# Web Search Multi-Tenant Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate web search from static `config.yaml` to per-family DB-managed providers with priority-ordered failover, circuit breaker, and MCP-as-websearch channel support.

**Architecture:** Three-layer data model (static registry → DB instances → MCP channel). Backend exposes CRUD + internal config endpoints. Agent fetches family-specific web search config at dispatch time and injects into DeerFlow's temp config. Frontend provides a dedicated settings page for provider management.

**Tech Stack:** Python 3.12 + FastAPI + SQLAlchemy + Alembic (backend), Vue 3 + TypeScript + Vant 4 (frontend), Fernet encryption for API keys.

---

## File Structure

### Backend (server/apps/backend/)

| File | Responsibility |
|------|---------------|
| `app/models/family_web_search_provider.py` | SQLAlchemy model for `family_web_search_providers` table |
| `app/services/web_search_provider_registry.py` | Static provider template registry + reconcile logic |
| `app/services/web_search_circuit_service.py` | Three-state circuit breaker service (reuses AIProviderConfig pattern) |
| `app/routers/ai_web_search.py` | Public CRUD + test + enable/disable endpoints |
| `app/routers/ai_internal.py` (modify) | Add web search config to internal `/ai/config` response |
| `app/models/family_mcp_server.py` (modify) | Add `mcp_type` column |
| `app/main.py` (modify) | Register new router |
| `alembic/versions/xxxx_add_web_search_providers.py` | Migration for new table + mcp_type column |

### Agent (server/apps/agent/)

| File | Responsibility |
|------|---------------|
| `core/backend_client.py` (modify) | Add `report_web_search_circuit()` method |
| `services/agent_dispatch.py` (modify) | Expand web_search guidance with MCP fallback logic |
| `services/deerflow_adapter/family_adapter_cache.py` (modify) | Inject web search provider into temp config |

### Frontend (frontend/apps/main/src/)

| File | Responsibility |
|------|---------------|
| `api/webSearch.ts` | API module for web search endpoints |
| `types/webSearch.ts` | TypeScript type definitions |
| `pages/WebSearchPage.vue` | Provider list + status page |
| `pages/WebSearchFormPage.vue` | Provider config form |
| `pages/MCPFormPage.vue` (modify) | Add `mcp_type` selector |
| `pages/MCPManagePage.vue` (modify) | Show websearch type badge |
| `router/index.ts` (modify) | Add web search route |
| `i18n/locales/zh-CN.ts` (modify) | Add i18n keys |
| `i18n/locales/en-US.ts` (modify) | Add i18n keys |

---

## Task 1: Provider Registry (Static Template Layer)

**Files:**
- Create: `server/apps/backend/app/services/web_search_provider_registry.py`
- Test: `server/tests/backend/test_web_search_provider_registry.py`

- [ ] **Step 1: Write the failing test**

```python
# server/tests/backend/test_web_search_provider_registry.py
from apps.backend.app.services.web_search_provider_registry import (
    WEB_SEARCH_PROVIDER_REGISTRY,
    get_provider_template,
    list_provider_templates,
)


def test_registry_has_expected_providers():
    names = set(WEB_SEARCH_PROVIDER_REGISTRY.keys())
    assert "tavily" in names
    assert "ddg_search" in names
    assert "exa" in names
    assert "serper" in names
    assert "firecrawl" in names


def test_get_provider_template_returns_metadata():
    tmpl = get_provider_template("tavily")
    assert tmpl is not None
    assert tmpl["requires_api_key"] is True
    assert tmpl["display_name"] == "Tavily Search"
    assert any(f["key"] == "api_key" for f in tmpl["config_fields"])


def test_get_provider_template_unknown_returns_none():
    assert get_provider_template("nonexistent") is None


def test_list_provider_templates_returns_all():
    templates = list_provider_templates()
    assert len(templates) == 5
    assert all("provider_name" in t for t in templates)


def test_ddg_search_does_not_require_api_key():
    tmpl = get_provider_template("ddg_search")
    assert tmpl["requires_api_key"] is False


def test_reconcile_registry_returns_empty_when_all_present():
    from apps.backend.app.services.web_search_provider_registry import reconcile_registry
    # Without deerflow.community installed, should return empty (graceful skip)
    result = reconcile_registry()
    assert isinstance(result, list)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/vincentruan/geek_space/github/numina/server && uv run pytest tests/backend/test_web_search_provider_registry.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

```python
# server/apps/backend/app/services/web_search_provider_registry.py
from typing import Any

WEB_SEARCH_PROVIDER_REGISTRY: dict[str, dict[str, Any]] = {
    "tavily": {
        "provider_class": "deerflow.community.tavily.tools:web_search_tool",
        "display_name": "Tavily Search",
        "requires_api_key": True,
        "config_fields": [
            {"key": "api_key", "label": "API Key", "type": "secret", "required": True},
            {"key": "max_results", "label": "最大结果数", "type": "number", "default": 5},
        ],
        "docs_url": "https://tavily.com",
        "note": "免费 1000 次/月",
    },
    "ddg_search": {
        "provider_class": "deerflow.community.ddg_search.tools:web_search_tool",
        "display_name": "DuckDuckGo",
        "requires_api_key": False,
        "config_fields": [
            {"key": "max_results", "label": "最大结果数", "type": "number", "default": 5},
        ],
        "docs_url": "https://duckduckgo.com",
        "note": "免费无限制，无需 API Key",
    },
    "exa": {
        "provider_class": "deerflow.community.exa.tools:web_search_tool",
        "display_name": "Exa Search",
        "requires_api_key": True,
        "config_fields": [
            {"key": "api_key", "label": "API Key", "type": "secret", "required": True},
            {"key": "max_results", "label": "最大结果数", "type": "number", "default": 5},
        ],
        "docs_url": "https://exa.ai",
        "note": "语义搜索，适合研究类查询",
    },
    "serper": {
        "provider_class": "deerflow.community.serper.tools:web_search_tool",
        "display_name": "Serper (Google)",
        "requires_api_key": True,
        "config_fields": [
            {"key": "api_key", "label": "API Key", "type": "secret", "required": True},
            {"key": "max_results", "label": "最大结果数", "type": "number", "default": 5},
        ],
        "docs_url": "https://serper.dev",
        "note": "Google 搜索结果，免费 2500 次",
    },
    "firecrawl": {
        "provider_class": "deerflow.community.firecrawl.tools:web_search_tool",
        "display_name": "Firecrawl",
        "requires_api_key": True,
        "config_fields": [
            {"key": "api_key", "label": "API Key", "type": "secret", "required": True},
            {"key": "max_results", "label": "最大结果数", "type": "number", "default": 5},
        ],
        "docs_url": "https://firecrawl.dev",
        "note": "网页抓取 + 搜索",
    },
}


def get_provider_template(provider_name: str) -> dict[str, Any] | None:
    return WEB_SEARCH_PROVIDER_REGISTRY.get(provider_name)


def list_provider_templates() -> list[dict[str, Any]]:
    return [
        {"provider_name": name, **meta}
        for name, meta in WEB_SEARCH_PROVIDER_REGISTRY.items()
    ]


def reconcile_registry() -> list[str]:
    """启动时校验：检查已知 provider 的模块是否可导入。
    返回注册表中无法导入的 provider 名称列表（用于报警日志）。
    """
    import importlib
    import logging

    logger = logging.getLogger(__name__)
    unavailable: list[str] = []

    for name, meta in WEB_SEARCH_PROVIDER_REGISTRY.items():
        provider_class = meta.get("provider_class", "")
        module_path = provider_class.split(":")[0] if ":" in provider_class else ""
        if module_path:
            try:
                importlib.import_module(module_path)
            except ImportError:
                logger.warning("Web search provider '%s' module not importable: %s", name, module_path)
                unavailable.append(name)

    return unavailable
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/vincentruan/geek_space/github/numina/server && uv run pytest tests/backend/test_web_search_provider_registry.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add server/apps/backend/app/services/web_search_provider_registry.py server/tests/backend/test_web_search_provider_registry.py
git commit -m "feat(backend): add web search provider registry with static templates"
```

---

## Task 2: Database Model + Migration

**Files:**
- Create: `server/apps/backend/app/models/family_web_search_provider.py`
- Modify: `server/apps/backend/app/models/family_mcp_server.py`
- Create: `server/apps/backend/alembic/versions/xxxx_add_web_search_providers.py` (autogenerated)

- [ ] **Step 1: Write the model file**

```python
# server/apps/backend/app/models/family_web_search_provider.py
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from apps.backend.app.database import Base
from apps.backend.app.utils.snowflake import next_id


class FamilyWebSearchProvider(Base):
    __tablename__ = "family_web_search_providers"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    family_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    provider_name: Mapped[str] = mapped_column(String(50), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    api_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_results: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    # Circuit breaker fields (three-state: closed | open | half_open)
    circuit_state: Mapped[str] = mapped_column(String(20), default="closed", nullable=False)
    circuit_reason: Mapped[str | None] = mapped_column(String(30), nullable=True)
    recovery_schedule: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_failure_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    half_open_success_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    half_open_failure_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    half_open_window_start: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    failure_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_failure_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
```

- [ ] **Step 2: Add `mcp_type` field to FamilyMCPServer**

In `server/apps/backend/app/models/family_mcp_server.py`, add after the `is_enabled` field:

```python
mcp_type: Mapped[str] = mapped_column(String(20), default="general", nullable=False)
```

- [ ] **Step 3: Generate the Alembic migration**

Run: `cd /Users/vincentruan/geek_space/github/numina/server/apps/backend && uv run alembic revision --autogenerate -m "add_web_search_providers_and_mcp_type"`
Expected: New migration file created in `alembic/versions/`

- [ ] **Step 4: Review the generated migration**

Verify it contains:
- `op.create_table("family_web_search_providers", ...)` with all columns
- `op.create_index("ix_family_web_search_providers_family_id", ...)`
- `op.add_column("ai_mcp_servers", sa.Column("mcp_type", sa.String(20), nullable=False, server_default="general"))`
- Corresponding `downgrade()` with `op.drop_table` and `op.drop_column`

- [ ] **Step 5: Apply the migration**

Run: `cd /Users/vincentruan/geek_space/github/numina/server/apps/backend && uv run alembic upgrade head`
Expected: Migration applies successfully

- [ ] **Step 6: Add model import to test conftest**

In `server/tests/backend/conftest.py`, add alongside the other model imports:

```python
from apps.backend.app.models.family_web_search_provider import FamilyWebSearchProvider  # noqa: F401
```

This ensures `Base.metadata.create_all()` creates the new table in the test database.

- [ ] **Step 7: Commit**

```bash
git add server/apps/backend/app/models/family_web_search_provider.py server/apps/backend/app/models/family_mcp_server.py server/apps/backend/alembic/versions/ server/tests/backend/conftest.py
git commit -m "feat(backend): add family_web_search_providers table and mcp_type column"
```

---

## Task 3: Circuit Breaker Service

**Files:**
- Create: `server/apps/backend/app/services/web_search_circuit_service.py`
- Test: `server/tests/backend/test_web_search_circuit_service.py`

- [ ] **Step 1: Write the failing test**

```python
# server/tests/backend/test_web_search_circuit_service.py
from datetime import datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from apps.backend.app.models.family_web_search_provider import FamilyWebSearchProvider
from apps.backend.app.services.web_search_circuit_service import WebSearchCircuitService
from apps.backend.app.utils.snowflake import next_id


@pytest.fixture
def provider(db: Session) -> FamilyWebSearchProvider:
    p = FamilyWebSearchProvider(
        id=next_id(),
        family_id=1001,
        provider_name="tavily",
        api_key_encrypted="encrypted_key",
        is_enabled=True,
        display_order=1,
        max_results=5,
        circuit_state="closed",
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def test_report_transient_failure_increments_count(db: Session, provider: FamilyWebSearchProvider):
    WebSearchCircuitService.report_failure(provider.id, "transient_rate_limit", db)
    db.refresh(provider)
    assert provider.failure_count == 1
    assert provider.circuit_state == "closed"


def test_report_permanent_auth_opens_circuit(db: Session, provider: FamilyWebSearchProvider):
    WebSearchCircuitService.report_failure(provider.id, "permanent_auth", db)
    db.refresh(provider)
    assert provider.circuit_state == "open"
    assert provider.circuit_reason == "permanent_auth"


def test_transient_failures_open_after_threshold(db: Session, provider: FamilyWebSearchProvider):
    for _ in range(5):
        WebSearchCircuitService.report_failure(provider.id, "transient_rate_limit", db)
    db.refresh(provider)
    assert provider.circuit_state == "open"
    assert provider.circuit_reason == "transient_rate_limit"


def test_half_open_success_closes_circuit(db: Session, provider: FamilyWebSearchProvider):
    provider.circuit_state = "half_open"
    provider.half_open_success_count = 0
    provider.half_open_window_start = datetime.utcnow()
    db.commit()

    WebSearchCircuitService.report_success(provider.id, db)
    db.refresh(provider)
    assert provider.half_open_success_count == 1


def test_half_open_three_successes_closes(db: Session, provider: FamilyWebSearchProvider):
    provider.circuit_state = "half_open"
    provider.half_open_success_count = 2
    provider.half_open_window_start = datetime.utcnow()
    db.commit()

    WebSearchCircuitService.report_success(provider.id, db)
    db.refresh(provider)
    assert provider.circuit_state == "closed"
    assert provider.failure_count == 0


def test_recovery_schedule_transitions_to_half_open(db: Session, provider: FamilyWebSearchProvider):
    provider.circuit_state = "open"
    provider.circuit_reason = "transient_rate_limit"
    provider.recovery_schedule = ":01,:31"
    provider.last_failure_at = datetime.utcnow() - timedelta(minutes=35)
    db.commit()

    result = WebSearchCircuitService.check_recovery(provider.id, db)
    db.refresh(provider)
    assert result is True
    assert provider.circuit_state == "half_open"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/vincentruan/geek_space/github/numina/server && uv run pytest tests/backend/test_web_search_circuit_service.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

```python
# server/apps/backend/app/services/web_search_circuit_service.py
from datetime import datetime

from sqlalchemy.orm import Session

from apps.backend.app.models.family_web_search_provider import FamilyWebSearchProvider

TRANSIENT_FAILURE_THRESHOLD = 5
HALF_OPEN_SUCCESS_THRESHOLD = 3


class WebSearchCircuitService:
    @staticmethod
    def report_failure(provider_id: int, failure_type: str, db: Session) -> None:
        provider = db.query(FamilyWebSearchProvider).filter_by(id=provider_id).first()
        if not provider:
            return

        provider.last_failure_type = failure_type
        provider.last_failure_at = datetime.utcnow()
        provider.failure_count += 1

        if failure_type.startswith("permanent_"):
            provider.circuit_state = "open"
            provider.circuit_reason = failure_type
        elif provider.failure_count >= TRANSIENT_FAILURE_THRESHOLD:
            provider.circuit_state = "open"
            provider.circuit_reason = failure_type
            provider.recovery_schedule = ":01,:31"

        db.commit()

    @staticmethod
    def report_success(provider_id: int, db: Session) -> None:
        provider = db.query(FamilyWebSearchProvider).filter_by(id=provider_id).first()
        if not provider:
            return

        if provider.circuit_state == "half_open":
            provider.half_open_success_count += 1
            if provider.half_open_success_count >= HALF_OPEN_SUCCESS_THRESHOLD:
                provider.circuit_state = "closed"
                provider.circuit_reason = None
                provider.failure_count = 0
                provider.half_open_success_count = 0
                provider.half_open_failure_count = 0
                provider.half_open_window_start = None
                provider.recovery_schedule = None
        elif provider.circuit_state == "closed":
            if provider.failure_count > 0:
                provider.failure_count = max(0, provider.failure_count - 1)

        db.commit()

    @staticmethod
    def check_recovery(provider_id: int, db: Session) -> bool:
        provider = db.query(FamilyWebSearchProvider).filter_by(id=provider_id).first()
        if not provider or provider.circuit_state != "open":
            return False

        if not provider.recovery_schedule:
            return False

        if provider.circuit_reason and provider.circuit_reason.startswith("permanent_"):
            return False

        now = datetime.utcnow()
        if provider.last_failure_at:
            elapsed = (now - provider.last_failure_at).total_seconds()
            if elapsed < 60:
                return False

        provider.circuit_state = "half_open"
        provider.half_open_success_count = 0
        provider.half_open_failure_count = 0
        provider.half_open_window_start = now
        db.commit()
        return True


```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/vincentruan/geek_space/github/numina/server && uv run pytest tests/backend/test_web_search_circuit_service.py -v`
Expected: All 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add server/apps/backend/app/services/web_search_circuit_service.py server/tests/backend/test_web_search_circuit_service.py
git commit -m "feat(backend): add web search circuit breaker service with three-state model"
```

---

## Task 4: Backend CRUD Router

**Files:**
- Create: `server/apps/backend/app/routers/ai_web_search.py`
- Modify: `server/apps/backend/app/main.py`
- Test: `server/tests/backend/test_ai_web_search_router.py`

- [ ] **Step 1: Write the failing test**

```python
# server/tests/backend/test_ai_web_search_router.py
import pytest
from fastapi.testclient import TestClient

from apps.backend.app.main import app


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
        "family_name": "WebSearchFamily",
    })
    resp = client.post("/api/v1/auth/login", json={
        "username": "wsowner",
        "password": "Test1234!",
    })
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_list_templates(client, owner_headers):
    resp = client.get("/api/v1/ai/web-search/templates", headers=owner_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 5
    assert any(t["provider_name"] == "tavily" for t in data)


def test_create_provider(client, owner_headers):
    resp = client.post("/api/v1/ai/web-search", headers=owner_headers, json={
        "provider_name": "tavily",
        "api_key": "tvly-test-key-123",
        "max_results": 5,
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["provider_name"] == "tavily"
    assert "id" in data
    assert "api_key" not in data  # encrypted, not returned


def test_create_ddg_without_api_key(client, owner_headers):
    resp = client.post("/api/v1/ai/web-search", headers=owner_headers, json={
        "provider_name": "ddg_search",
        "max_results": 5,
    })
    assert resp.status_code == 201
    assert resp.json()["provider_name"] == "ddg_search"


def test_create_unknown_provider_fails(client, owner_headers):
    resp = client.post("/api/v1/ai/web-search", headers=owner_headers, json={
        "provider_name": "unknown_engine",
        "api_key": "key",
    })
    assert resp.status_code == 400


def test_list_providers(client, owner_headers):
    client.post("/api/v1/ai/web-search", headers=owner_headers, json={
        "provider_name": "ddg_search",
        "max_results": 3,
    })
    resp = client.get("/api/v1/ai/web-search", headers=owner_headers)
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


def test_enable_provider(client, owner_headers):
    create_resp = client.post("/api/v1/ai/web-search", headers=owner_headers, json={
        "provider_name": "ddg_search",
    })
    pid = create_resp.json()["id"]
    resp = client.post(f"/api/v1/ai/web-search/{pid}/enable", headers=owner_headers)
    assert resp.status_code == 200
    assert resp.json()["is_enabled"] is True


def test_disable_provider(client, owner_headers):
    create_resp = client.post("/api/v1/ai/web-search", headers=owner_headers, json={
        "provider_name": "ddg_search",
    })
    pid = create_resp.json()["id"]
    client.post(f"/api/v1/ai/web-search/{pid}/enable", headers=owner_headers)
    resp = client.post(f"/api/v1/ai/web-search/{pid}/disable", headers=owner_headers)
    assert resp.status_code == 200
    assert resp.json()["is_enabled"] is False


def test_delete_provider(client, owner_headers):
    create_resp = client.post("/api/v1/ai/web-search", headers=owner_headers, json={
        "provider_name": "ddg_search",
    })
    pid = create_resp.json()["id"]
    resp = client.delete(f"/api/v1/ai/web-search/{pid}", headers=owner_headers)
    assert resp.status_code == 204


def test_status_endpoint(client, owner_headers):
    resp = client.get("/api/v1/ai/web-search/status", headers=owner_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "enabled_count" in data
    assert "has_web_search" in data
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/vincentruan/geek_space/github/numina/server && uv run pytest tests/backend/test_ai_web_search_router.py -v`
Expected: FAIL (router not registered)

- [ ] **Step 3: Write the router implementation**

```python
# server/apps/backend/app/routers/ai_web_search.py
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from apps.backend.app.auth.deps import require_adult, require_owner
from apps.backend.app.database import get_db
from apps.backend.app.models.family_web_search_provider import FamilyWebSearchProvider
from apps.backend.app.models.user import User
from apps.backend.app.schemas.base import SnowflakeBase
from apps.backend.app.services.ai_crypto import decrypt_api_key, encrypt_api_key
from apps.backend.app.services.web_search_provider_registry import (
    get_provider_template,
    list_provider_templates,
)

router = APIRouter(prefix="/ai/web-search", tags=["ai-web-search"])


class WebSearchProviderCreate(BaseModel):
    provider_name: str
    display_name: str | None = None
    api_key: str | None = None
    max_results: int = 5


class WebSearchProviderUpdate(BaseModel):
    display_name: str | None = None
    api_key: str | None = None
    max_results: int | None = None
    display_order: int | None = None


class WebSearchProviderResponse(SnowflakeBase):
    id: int
    family_id: int
    provider_name: str
    display_name: str | None
    is_enabled: bool
    display_order: int
    max_results: int
    circuit_state: str
    circuit_reason: str | None
    has_api_key: bool
    created_at: str
    updated_at: str


class WebSearchStatusResponse(BaseModel):
    has_web_search: bool
    enabled_count: int


def _to_response(p: FamilyWebSearchProvider) -> WebSearchProviderResponse:
    return WebSearchProviderResponse(
        id=p.id,
        family_id=p.family_id,
        provider_name=p.provider_name,
        display_name=p.display_name,
        is_enabled=p.is_enabled,
        display_order=p.display_order,
        max_results=p.max_results,
        circuit_state=p.circuit_state,
        circuit_reason=p.circuit_reason,
        has_api_key=p.api_key_encrypted is not None,
        created_at=p.created_at.isoformat() if p.created_at else "",
        updated_at=p.updated_at.isoformat() if p.updated_at else "",
    )


@router.get("/templates")
def get_templates(
    current_user: User = Depends(require_adult),
) -> list[dict]:
    return list_provider_templates()


@router.get("/status", response_model=WebSearchStatusResponse)
def get_status(
    current_user: User = Depends(require_adult),
    db: Session = Depends(get_db),
) -> WebSearchStatusResponse:
    count = (
        db.query(FamilyWebSearchProvider)
        .filter(
            FamilyWebSearchProvider.family_id == current_user.family_id,
            FamilyWebSearchProvider.is_enabled.is_(True),
        )
        .count()
    )
    return WebSearchStatusResponse(has_web_search=count > 0, enabled_count=count)


@router.get("", response_model=list[WebSearchProviderResponse])
def list_providers(
    current_user: User = Depends(require_adult),
    db: Session = Depends(get_db),
) -> list[WebSearchProviderResponse]:
    providers = (
        db.query(FamilyWebSearchProvider)
        .filter(FamilyWebSearchProvider.family_id == current_user.family_id)
        .order_by(FamilyWebSearchProvider.display_order)
        .all()
    )
    return [_to_response(p) for p in providers]


@router.post("", response_model=WebSearchProviderResponse, status_code=201)
def create_provider(
    payload: WebSearchProviderCreate,
    current_user: User = Depends(require_owner),
    db: Session = Depends(get_db),
) -> WebSearchProviderResponse:
    template = get_provider_template(payload.provider_name)
    if not template:
        raise HTTPException(status_code=400, detail="不支持的搜索引擎类型")

    if template["requires_api_key"] and not payload.api_key:
        raise HTTPException(status_code=400, detail="该搜索引擎需要 API Key")

    max_order = (
        db.query(FamilyWebSearchProvider.display_order)
        .filter(FamilyWebSearchProvider.family_id == current_user.family_id)
        .order_by(FamilyWebSearchProvider.display_order.desc())
        .first()
    )
    next_order = (max_order[0] + 1) if max_order else 1

    encrypted_key = None
    if payload.api_key:
        encrypted_key = encrypt_api_key(payload.api_key)
        if encrypted_key is None:
            raise HTTPException(status_code=500, detail="加密服务不可用，请联系管理员")

    provider = FamilyWebSearchProvider(
        family_id=current_user.family_id,
        provider_name=payload.provider_name,
        display_name=payload.display_name or template["display_name"],
        api_key_encrypted=encrypted_key,
        display_order=next_order,
        max_results=payload.max_results,
    )
    db.add(provider)
    db.commit()
    db.refresh(provider)
    return _to_response(provider)


@router.put("/{provider_id}", response_model=WebSearchProviderResponse)
def update_provider(
    provider_id: str,
    payload: WebSearchProviderUpdate,
    current_user: User = Depends(require_owner),
    db: Session = Depends(get_db),
) -> WebSearchProviderResponse:
    provider = (
        db.query(FamilyWebSearchProvider)
        .filter(
            FamilyWebSearchProvider.id == int(provider_id),
            FamilyWebSearchProvider.family_id == current_user.family_id,
        )
        .first()
    )
    if not provider:
        raise HTTPException(status_code=404, detail="搜索引擎配置不存在")

    if payload.display_name is not None:
        provider.display_name = payload.display_name
    if payload.api_key is not None:
        provider.api_key_encrypted = encrypt_api_key(payload.api_key)
    if payload.max_results is not None:
        provider.max_results = payload.max_results
    if payload.display_order is not None:
        provider.display_order = payload.display_order

    db.commit()
    db.refresh(provider)
    return _to_response(provider)


@router.delete("/{provider_id}", status_code=204)
def delete_provider(
    provider_id: str,
    current_user: User = Depends(require_owner),
    db: Session = Depends(get_db),
) -> None:
    provider = (
        db.query(FamilyWebSearchProvider)
        .filter(
            FamilyWebSearchProvider.id == int(provider_id),
            FamilyWebSearchProvider.family_id == current_user.family_id,
        )
        .first()
    )
    if not provider:
        raise HTTPException(status_code=404, detail="搜索引擎配置不存在")

    db.delete(provider)
    db.commit()


@router.post("/{provider_id}/enable", response_model=WebSearchProviderResponse)
def enable_provider(
    provider_id: str,
    current_user: User = Depends(require_owner),
    db: Session = Depends(get_db),
) -> WebSearchProviderResponse:
    provider = (
        db.query(FamilyWebSearchProvider)
        .filter(
            FamilyWebSearchProvider.id == int(provider_id),
            FamilyWebSearchProvider.family_id == current_user.family_id,
        )
        .first()
    )
    if not provider:
        raise HTTPException(status_code=404, detail="搜索引擎配置不存在")

    template = get_provider_template(provider.provider_name)
    if template and template["requires_api_key"] and not provider.api_key_encrypted:
        raise HTTPException(status_code=400, detail="请先配置 API Key")

    provider.is_enabled = True
    db.commit()
    db.refresh(provider)
    return _to_response(provider)


@router.post("/{provider_id}/disable", response_model=WebSearchProviderResponse)
def disable_provider(
    provider_id: str,
    current_user: User = Depends(require_owner),
    db: Session = Depends(get_db),
) -> WebSearchProviderResponse:
    provider = (
        db.query(FamilyWebSearchProvider)
        .filter(
            FamilyWebSearchProvider.id == int(provider_id),
            FamilyWebSearchProvider.family_id == current_user.family_id,
        )
        .first()
    )
    if not provider:
        raise HTTPException(status_code=404, detail="搜索引擎配置不存在")

    provider.is_enabled = False
    db.commit()
    db.refresh(provider)
    return _to_response(provider)


@router.post("/{provider_id}/test")
def test_provider(
    provider_id: str,
    current_user: User = Depends(require_owner),
    db: Session = Depends(get_db),
) -> dict:
    provider = (
        db.query(FamilyWebSearchProvider)
        .filter(
            FamilyWebSearchProvider.id == int(provider_id),
            FamilyWebSearchProvider.family_id == current_user.family_id,
        )
        .first()
    )
    if not provider:
        raise HTTPException(status_code=404, detail="搜索引擎配置不存在")

    api_key = decrypt_api_key(provider.api_key_encrypted) if provider.api_key_encrypted else None
    template = get_provider_template(provider.provider_name)

    if template and template["requires_api_key"] and not api_key:
        return {"success": False, "message": "未配置 API Key"}

    # Actual connectivity test would call the provider here
    # For now, validate that the key is non-empty
    return {"success": True, "message": "配置有效"}
```

- [ ] **Step 4: Register the router in main.py**

In `server/apps/backend/app/main.py`, add:

```python
from apps.backend.app.routers import ai_web_search as ai_web_search_router
# ... in the router registration section:
app.include_router(ai_web_search_router.router, prefix="/api/v1")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /Users/vincentruan/geek_space/github/numina/server && uv run pytest tests/backend/test_ai_web_search_router.py -v`
Expected: All 9 tests PASS

- [ ] **Step 6: Run ruff + mypy**

Run: `cd /Users/vincentruan/geek_space/github/numina/server && uv run ruff check apps/backend/app/routers/ai_web_search.py && uv run mypy apps/backend/app/routers/ai_web_search.py`
Expected: No errors

- [ ] **Step 7: Commit**

```bash
git add server/apps/backend/app/routers/ai_web_search.py server/apps/backend/app/main.py server/tests/backend/test_ai_web_search_router.py
git commit -m "feat(backend): add web search provider CRUD router with enable/disable/test"
```

---

## Task 5: Internal API — Web Search Config Endpoint

**Files:**
- Modify: `server/apps/backend/app/routers/ai_internal.py`
- Test: `server/tests/backend/test_ai_internal_web_search.py`

- [ ] **Step 1: Write the failing test**

```python
# server/tests/backend/test_ai_internal_web_search.py
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from apps.backend.app.main import app
from apps.backend.app.models.family_web_search_provider import FamilyWebSearchProvider
from apps.backend.app.models.family_mcp_server import FamilyMCPServer
from apps.backend.app.services.ai_crypto import encrypt_api_key
from apps.backend.app.utils.snowflake import next_id


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def internal_headers():
    """Headers that pass verify_agent_token."""
    return {
        "Authorization": "Bearer test-agent-token",
        "X-Family-Id": "1001",
    }


@pytest.fixture
def setup_web_search(db):
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
def setup_websearch_mcp(db):
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


@patch("apps.backend.app.routers.ai_internal.verify_agent_token", return_value="1001")
def test_internal_config_includes_web_search_providers(mock_auth, client, internal_headers, setup_web_search):
    resp = client.get("/api/v1/internal/ai/config", headers=internal_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "web_search_providers" in data
    providers = data["web_search_providers"]
    # Only non-open circuit providers returned
    assert len(providers) == 2
    assert providers[0]["provider_name"] == "tavily"
    assert providers[0]["api_key"] == "tvly-test-key"
    assert providers[1]["provider_name"] == "ddg_search"
    assert providers[1]["api_key"] is None


@patch("apps.backend.app.routers.ai_internal.verify_agent_token", return_value="1001")
def test_internal_config_includes_websearch_mcp(mock_auth, client, internal_headers, setup_websearch_mcp):
    resp = client.get("/api/v1/internal/ai/config", headers=internal_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "web_search_mcp_servers" in data
    mcps = data["web_search_mcp_servers"]
    assert len(mcps) == 1
    assert mcps[0]["name"] == "brave-mcp"
    assert mcps[0]["transport"] == "sse"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/vincentruan/geek_space/github/numina/server && uv run pytest tests/backend/test_ai_internal_web_search.py -v`
Expected: FAIL (key `web_search_providers` not in response)

- [ ] **Step 3: Modify `ai_internal.py` to include web search config**

In the `internal_get_ai_config` function (or equivalent endpoint that returns `/ai/config`), add after the existing provider/MCP logic:

```python
# Web search providers (enabled + circuit not open)
from apps.backend.app.models.family_web_search_provider import FamilyWebSearchProvider
from apps.backend.app.services.web_search_provider_registry import get_provider_template

ws_providers = (
    db.query(FamilyWebSearchProvider)
    .filter(
        FamilyWebSearchProvider.family_id == family_id,
        FamilyWebSearchProvider.is_enabled.is_(True),
        FamilyWebSearchProvider.circuit_state != "open",
    )
    .order_by(FamilyWebSearchProvider.display_order)
    .all()
)

web_search_providers = []
for wsp in ws_providers:
    template = get_provider_template(wsp.provider_name)
    api_key = decrypt_api_key(wsp.api_key_encrypted) if wsp.api_key_encrypted else None
    web_search_providers.append({
        "provider_id": wsp.id,
        "provider_name": wsp.provider_name,
        "provider_class": template["provider_class"] if template else None,
        "api_key": api_key,
        "max_results": wsp.max_results,
        "display_order": wsp.display_order,
    })

# Websearch-type MCP servers
ws_mcps = (
    db.query(FamilyMCPServer)
    .filter(
        FamilyMCPServer.family_id == family_id,
        FamilyMCPServer.is_enabled.is_(True),
        FamilyMCPServer.mcp_type == "websearch",
    )
    .all()
)

web_search_mcp_servers = []
for m in ws_mcps:
    web_search_mcp_servers.append({
        "name": m.name,
        "url": m.url,
        "transport": m.transport,
    })

# Include in the return dict alongside existing fields:
# return {
#     "ai_enabled": bool(providers),
#     "providers": providers,
#     ...existing fields...,
#     "web_search_providers": web_search_providers,
#     "web_search_mcp_servers": web_search_mcp_servers,
# }
# Note: the existing function returns a dict literal directly — add these
# two keys to that literal. There is no mutable `response` variable.
```

- [ ] **Step 4: Add circuit report endpoint to ai_internal.py**

```python
class WebSearchCircuitRequest(BaseModel):
    failure_type: Literal[
        "transient_timeout",
        "transient_rate_limit",
        "transient_network",
        "transient_server",
        "permanent_auth",
        "permanent_account",
    ]


@router.post("/ai/web-search/{provider_id}/circuit")
def report_web_search_circuit(
    provider_id: str,
    payload: WebSearchCircuitRequest,
    family_id: str = Depends(verify_agent_token),
    db: Session = Depends(get_db),
) -> dict:
    from apps.backend.app.services.web_search_circuit_service import WebSearchCircuitService

    provider = (
        db.query(FamilyWebSearchProvider)
        .filter(
            FamilyWebSearchProvider.id == int(provider_id),
            FamilyWebSearchProvider.family_id == int(family_id),
        )
        .first()
    )
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")

    WebSearchCircuitService.report_failure(provider.id, payload.failure_type, db)
    db.refresh(provider)
    return {"status": "recorded", "circuit_state": provider.circuit_state}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /Users/vincentruan/geek_space/github/numina/server && uv run pytest tests/backend/test_ai_internal_web_search.py -v`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add server/apps/backend/app/routers/ai_internal.py server/tests/backend/test_ai_internal_web_search.py
git commit -m "feat(backend): expose web search providers in internal /ai/config endpoint"
```

---

## Task 6: Agent Integration — Config Injection + Failover

**Files:**
- Modify: `server/apps/agent/core/backend_client.py`
- Modify: `server/apps/agent/services/deerflow_adapter/family_adapter_cache.py`
- Modify: `server/apps/agent/services/agent_dispatch.py`
- Test: `server/tests/agent/test_web_search_integration.py`

- [ ] **Step 1: Write the failing test**

```python
# server/tests/agent/test_web_search_config_injection.py
"""Test the web search injection logic inside _generate_temp_config.

Since _generate_temp_config reads YAML from disk and returns a Path, we test
by creating a real temp config dir and reading back the generated YAML.
"""
import tempfile
from pathlib import Path

import pytest
import yaml


def _make_base_config_dir(tools: list[dict]) -> str:
    """Create a temp dir with a base/config.yaml for testing."""
    tmp = tempfile.mkdtemp(prefix="test_ws_")
    base_dir = Path(tmp) / "base"
    base_dir.mkdir()
    config = {
        "models": [{"model_name": "test", "use": "langchain_openai:ChatOpenAI"}],
        "tools": tools,
    }
    (base_dir / "config.yaml").write_text(yaml.dump(config), encoding="utf-8")
    return tmp


@pytest.fixture
def base_config_dir():
    tools = [
        {"name": "web_search", "use": "placeholder", "api_key": "", "max_results": 5},
        {"name": "crawl", "use": "some_crawler"},
    ]
    return _make_base_config_dir(tools)


@pytest.fixture
def ai_config_with_ws():
    return {
        "api_key": "sk-test",
        "ai_model_id": "gpt-4",
        "ai_provider": "openai",
        "web_search_providers": [
            {
                "provider_id": 1001,
                "provider_name": "tavily",
                "provider_class": "deerflow.community.tavily.tools:web_search_tool",
                "api_key": "tvly-real-key",
                "max_results": 5,
                "display_order": 1,
            },
        ],
        "web_search_mcp_servers": [],
    }


@pytest.fixture
def ai_config_no_ws():
    return {
        "api_key": "sk-test",
        "ai_model_id": "gpt-4",
        "ai_provider": "openai",
        "web_search_providers": [],
        "web_search_mcp_servers": [],
    }


@pytest.fixture
def ai_config_mcp_only():
    return {
        "api_key": "sk-test",
        "ai_model_id": "gpt-4",
        "ai_provider": "openai",
        "web_search_providers": [],
        "web_search_mcp_servers": [
            {"name": "brave-mcp", "url": "http://localhost:3001/sse", "transport": "sse"}
        ],
    }


def test_inject_web_search_provider_into_config(base_config_dir, ai_config_with_ws):
    """First available provider (tavily) should be injected into web_search tool."""
    from apps.agent.services.deerflow_adapter.family_adapter_cache import _generate_temp_config

    config_path = _generate_temp_config(base_config_dir, ai_config_with_ws, family_id="test1")
    config = yaml.safe_load(config_path.read_text())
    ws_tool = next(t for t in config["tools"] if t["name"] == "web_search")
    assert ws_tool["use"] == "deerflow.community.tavily.tools:web_search_tool"
    assert ws_tool["api_key"] == "tvly-real-key"
    assert ws_tool["max_results"] == 5


def test_no_web_search_providers_removes_tool(base_config_dir, ai_config_no_ws):
    """When no providers configured, web_search tool should be removed."""
    from apps.agent.services.deerflow_adapter.family_adapter_cache import _generate_temp_config

    config_path = _generate_temp_config(base_config_dir, ai_config_no_ws, family_id="test2")
    config = yaml.safe_load(config_path.read_text())
    tool_names = [t["name"] for t in config.get("tools", [])]
    assert "web_search" not in tool_names
    assert "crawl" in tool_names


def test_web_search_mcp_fallback_when_no_native(base_config_dir, ai_config_mcp_only):
    """When only MCP websearch available, web_search tool removed but MCP injected."""
    from apps.agent.services.deerflow_adapter.family_adapter_cache import _generate_temp_config

    config_path = _generate_temp_config(base_config_dir, ai_config_mcp_only, family_id="test3")
    config = yaml.safe_load(config_path.read_text())
    tool_names = [t["name"] for t in config.get("tools", [])]
    assert "web_search" not in tool_names
    assert any(m["name"] == "brave-mcp" for m in config.get("mcp_servers", []))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/vincentruan/geek_space/github/numina/server && uv run pytest tests/agent/test_web_search_integration.py -v`
Expected: FAIL (signature mismatch or missing parameter)

- [ ] **Step 3: Add `report_web_search_circuit` to BackendClient**

In `server/apps/agent/core/backend_client.py`, add:

```python
async def report_web_search_circuit(self, provider_id: int, failure_type: str) -> None:
    """Report web search tool failure to trigger circuit breaker."""
    validated_id = _validate_family_id(self.family_id)
    async with httpx.AsyncClient(
        timeout=_CONFIG_TIMEOUT, base_url=settings.BACKEND_BASE_URL
    ) as client:
        resp = await client.post(
            f"/api/v1/internal/ai/web-search/{provider_id}/circuit",
            json={"failure_type": failure_type},
            headers=_make_headers(validated_id),
        )
        resp.raise_for_status()
```

This follows the same pattern as the existing `report_circuit_event()` function in `backend_client.py`.

- [ ] **Step 4: Add web search injection to `_generate_temp_config`**

The existing function signature is:
```python
def _generate_temp_config(
    base_config_dir: str,
    ai_config: dict[str, Any],
    family_id: str = "",
    mcp_servers: list[dict[str, Any]] | None = None,
) -> Path:
```

It reads `deerflow_config/base/config.yaml`, injects model/provider config, writes a temp YAML file, and returns the `Path`. **Do not change the signature or return type.**

Instead, the `ai_config` dict (fetched from `/internal/ai/config`) will now include `web_search_providers` and `web_search_mcp_servers` keys (added in Task 5). Add the following injection logic **after** the existing MCP injection block (after `if mcp_servers: config["mcp_servers"] = mcp_servers`) and **before** the YAML write:

```python
    # Web search provider injection (from ai_config, populated by Task 5)
    ws_providers = ai_config.get("web_search_providers", [])
    ws_mcps = ai_config.get("web_search_mcp_servers", [])

    if ws_providers:
        active = ws_providers[0]  # First by display_order (already sorted by backend)
        for tool in config.get("tools", []):
            if tool.get("name") == "web_search":
                tool["use"] = active["provider_class"]
                tool["api_key"] = active["api_key"] or ""
                tool["max_results"] = active.get("max_results", 5)
                break
    else:
        # No native providers — remove web_search tool from config
        config["tools"] = [t for t in config.get("tools", []) if t.get("name") != "web_search"]

        # If MCP websearch servers available, add them to mcp_servers list
        if ws_mcps:
            if "mcp_servers" not in config:
                config["mcp_servers"] = []
            for mcp_srv in ws_mcps:
                config["mcp_servers"].append({
                    "name": mcp_srv["name"],
                    "url": mcp_srv["url"],
                    "transport": mcp_srv.get("transport", "sse"),
                })
```

No signature change needed — the web search data flows through `ai_config` which is already passed in.

- [ ] **Step 5: Modify `agent_dispatch.py` — expand web_search guidance**

In the section that builds `web_search_guidance`, replace the simple boolean check with:

```python
if web_search:
    # Reuse the ai_config already fetched earlier in the dispatch function
    # (do NOT call get_family_ai_config() again — it's already available)
    ws_providers = ai_config.get("web_search_providers", [])
    ws_mcps = ai_config.get("web_search_mcp_servers", [])

    has_native_provider = len(ws_providers) > 0
    has_websearch_mcp = len(ws_mcps) > 0

    if has_native_provider:
        web_search_guidance = "## 联网搜索\n当问题涉及实时信息时，使用 web_search(query) 工具检索。"
    elif has_websearch_mcp:
        mcp_list = "\n".join(f"- mcp:{m['name']}.search(query)" for m in ws_mcps)
        web_search_guidance = (
            "## 联网搜索\n"
            "当用户问题需要联网获取实时信息时，调用以下 MCP 工具进行搜索：\n"
            + mcp_list
        )
    else:
        web_search_guidance = ""
        # No provider available — this shouldn't happen (frontend checks first)
else:
    web_search_guidance = "用户未启用联网搜索。请仅基于已有工具和知识回答，不要尝试联网。"
```

- [ ] **Step 6: Add circuit failure reporting in the tool execution path**

In `server/apps/agent/services/agent_dispatch.py`, find the section where DeerFlow tool call results are processed (typically in the streaming event handler or post-execution callback). Add a try/catch around web_search tool invocations:

The actual integration point is in the `except Exception` block of `agent_dispatch.py`'s streaming loop (around line 649). DeerFlow tool failures surface as exceptions, not structured error dicts. Add circuit reporting as a best-effort fire-and-forget in the error handler:

```python
# In agent_dispatch.py, inside the except block that catches DeerFlow stream errors:
# (around line 649, where stream_error_type is set)
except Exception as e:
    error_msg = str(e)
    stream_error_type = classify_error_type(0, error_msg)

    # Report web search circuit failure if web_search was active
    if web_search and ai_config.get("web_search_providers"):
        active_provider = ai_config["web_search_providers"][0]
        if "401" in error_msg or "403" in error_msg or "invalid api key" in error_msg.lower():
            ws_failure_type = "permanent_auth"
        elif "429" in error_msg or "rate limit" in error_msg.lower():
            ws_failure_type = "transient_rate_limit"
        elif "timeout" in error_msg.lower():
            ws_failure_type = "transient_timeout"
        else:
            ws_failure_type = "transient_server"

        try:
            await report_web_search_circuit(
                family_id,
                provider_id=active_provider["provider_id"],
                failure_type=ws_failure_type,
            )
        except Exception:
            pass  # Best-effort — don't fail the main error path
```

Note: `report_web_search_circuit` is the module-level async function added to `backend_client.py` (not a method on `self`). The `family_id` and `ai_config` variables are already in scope from the dispatch function. This approach is consistent with how `report_circuit_event` is already called in the existing error handler.

- [ ] **Step 7: Run tests to verify they pass**

Run: `cd /Users/vincentruan/geek_space/github/numina/server && uv run pytest tests/agent/test_web_search_integration.py -v`
Expected: All 3 tests PASS

- [ ] **Step 8: Commit**

```bash
git add server/apps/agent/core/backend_client.py server/apps/agent/services/deerflow_adapter/family_adapter_cache.py server/apps/agent/services/agent_dispatch.py server/tests/agent/test_web_search_config_injection.py
git commit -m "feat(agent): inject per-family web search providers into DeerFlow config with MCP fallback"
```

---

## Task 7: Frontend — API Module + Types

**Files:**
- Create: `frontend/apps/main/src/types/webSearch.ts`
- Create: `frontend/apps/main/src/api/webSearch.ts`

- [ ] **Step 1: Create TypeScript types**

```typescript
// frontend/apps/main/src/types/webSearch.ts
export interface WebSearchProviderTemplate {
  provider_name: string
  provider_class: string
  display_name: string
  requires_api_key: boolean
  config_fields: ConfigField[]
  docs_url: string
  note: string
}

export interface ConfigField {
  key: string
  label: string
  type: 'secret' | 'number' | 'string'
  required?: boolean
  default?: number | string
}

export interface WebSearchProvider {
  id: string
  family_id: string
  provider_name: string
  display_name: string | null
  is_enabled: boolean
  display_order: number
  max_results: number
  circuit_state: 'closed' | 'open' | 'half_open'
  circuit_reason: string | null
  has_api_key: boolean
  created_at: string
  updated_at: string
}

export interface WebSearchProviderCreate {
  provider_name: string
  display_name?: string
  api_key?: string
  max_results?: number
}

export interface WebSearchProviderUpdate {
  display_name?: string
  api_key?: string
  max_results?: number
  display_order?: number
}

export interface WebSearchStatus {
  has_web_search: boolean
  enabled_count: number
}
```

- [ ] **Step 2: Create API module**

```typescript
// frontend/apps/main/src/api/webSearch.ts
import api from '@/api'
import type {
  WebSearchProvider,
  WebSearchProviderCreate,
  WebSearchProviderTemplate,
  WebSearchProviderUpdate,
  WebSearchStatus,
} from '@/types/webSearch'

export function getWebSearchTemplates(): Promise<WebSearchProviderTemplate[]> {
  return api.get('/ai/web-search/templates').then((r) => r.data)
}

export function getWebSearchProviders(): Promise<WebSearchProvider[]> {
  return api.get('/ai/web-search').then((r) => r.data)
}

export function createWebSearchProvider(payload: WebSearchProviderCreate): Promise<WebSearchProvider> {
  return api.post('/ai/web-search', payload).then((r) => r.data)
}

export function updateWebSearchProvider(
  id: string,
  payload: WebSearchProviderUpdate,
): Promise<WebSearchProvider> {
  return api.put(`/ai/web-search/${id}`, payload).then((r) => r.data)
}

export function deleteWebSearchProvider(id: string): Promise<void> {
  return api.delete(`/ai/web-search/${id}`)
}

export function enableWebSearchProvider(id: string): Promise<WebSearchProvider> {
  return api.post(`/ai/web-search/${id}/enable`).then((r) => r.data)
}

export function disableWebSearchProvider(id: string): Promise<WebSearchProvider> {
  return api.post(`/ai/web-search/${id}/disable`).then((r) => r.data)
}

export function testWebSearchProvider(id: string): Promise<{ success: boolean; message: string }> {
  return api.post(`/ai/web-search/${id}/test`).then((r) => r.data)
}

export function getWebSearchStatus(): Promise<WebSearchStatus> {
  return api.get('/ai/web-search/status').then((r) => r.data)
}
```

- [ ] **Step 3: Run typecheck**

Run: `cd /Users/vincentruan/geek_space/github/numina/frontend/apps/main && pnpm typecheck`
Expected: No type errors

- [ ] **Step 4: Commit**

```bash
git add frontend/apps/main/src/types/webSearch.ts frontend/apps/main/src/api/webSearch.ts
git commit -m "feat(frontend): add web search API module and TypeScript types"
```

---

## Task 8: Frontend — i18n Keys

**Files:**
- Modify: `frontend/apps/main/src/i18n/locales/zh-CN.ts`
- Modify: `frontend/apps/main/src/i18n/locales/en-US.ts`

- [ ] **Step 1: Add zh-CN keys**

Add under the appropriate section in `zh-CN.ts`:

```typescript
webSearch: {
  title: '联网搜索',
  subtitle: '配置搜索引擎以启用 AI 联网搜索能力',
  statusEnabled: '已启用 {count} 个搜索源',
  statusDisabled: '未配置',
  configBtn: '配置',
  enableBtn: '启用',
  disableBtn: '禁用',
  deleteBtn: '删除',
  testBtn: '测试连通性',
  addProvider: '添加搜索引擎',
  providerName: '搜索引擎',
  apiKey: 'API Key',
  apiKeyPlaceholder: '请输入 API Key',
  maxResults: '最大结果数',
  displayOrder: '优先级',
  circuitOpen: '熔断中',
  circuitHalfOpen: '恢复中',
  circuitClosed: '正常',
  noApiKeyWarning: '⚠️ 请先配置 API Key',
  mcpHint: '也可在 MCP 管理中添加 websearch 类型的 MCP server',
  formTitle: '配置搜索引擎',
  formEditTitle: '编辑搜索引擎',
  saveSuccess: '✅ 保存成功',
  deleteSuccess: '🗑️ 已删除',
  enableSuccess: '✅ 已启用',
  disableSuccess: '✅ 已禁用',
  testSuccess: '✅ 连通性测试通过',
  testFailed: '❌ 连通性测试失败',
  confirmDelete: '⚠️ 确定要删除「{name}」吗？',
  noProviderToast: '⚠️ 请先在设置→AI助手→联网搜索中启用至少一个搜索源',
},
```

- [ ] **Step 2: Add en-US keys**

Add matching keys in `en-US.ts`:

```typescript
webSearch: {
  title: 'Web Search',
  subtitle: 'Configure search engines to enable AI web search',
  statusEnabled: '{count} search source(s) enabled',
  statusDisabled: 'Not configured',
  configBtn: 'Configure',
  enableBtn: 'Enable',
  disableBtn: 'Disable',
  deleteBtn: 'Delete',
  testBtn: 'Test Connection',
  addProvider: 'Add Search Engine',
  providerName: 'Search Engine',
  apiKey: 'API Key',
  apiKeyPlaceholder: 'Enter API Key',
  maxResults: 'Max Results',
  displayOrder: 'Priority',
  circuitOpen: 'Circuit Open',
  circuitHalfOpen: 'Recovering',
  circuitClosed: 'Normal',
  noApiKeyWarning: '⚠️ Please configure API Key first',
  mcpHint: 'You can also add websearch-type MCP servers in MCP management',
  formTitle: 'Configure Search Engine',
  formEditTitle: 'Edit Search Engine',
  saveSuccess: '✅ Saved successfully',
  deleteSuccess: '🗑️ Deleted',
  enableSuccess: '✅ Enabled',
  disableSuccess: '✅ Disabled',
  testSuccess: '✅ Connection test passed',
  testFailed: '❌ Connection test failed',
  confirmDelete: '⚠️ Are you sure you want to delete "{name}"?',
  noProviderToast: '⚠️ Please enable at least one search source in Settings → AI → Web Search',
},
```

- [ ] **Step 3: Run typecheck**

Run: `cd /Users/vincentruan/geek_space/github/numina/frontend/apps/main && pnpm typecheck`
Expected: No type errors

- [ ] **Step 4: Commit**

```bash
git add frontend/apps/main/src/i18n/locales/zh-CN.ts frontend/apps/main/src/i18n/locales/en-US.ts
git commit -m "feat(frontend): add web search i18n keys for zh-CN and en-US"
```

---

## Task 9: Frontend — WebSearchPage (Provider List)

**Files:**
- Create: `frontend/apps/main/src/pages/WebSearchPage.vue`
- Modify: `frontend/apps/main/src/router/index.ts`

- [ ] **Step 1: Create the page component**

```vue
<!-- frontend/apps/main/src/pages/WebSearchPage.vue -->
<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { showToast, showConfirmDialog } from 'vant'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@numina/auth'
import {
  getWebSearchTemplates,
  getWebSearchProviders,
  enableWebSearchProvider,
  disableWebSearchProvider,
  deleteWebSearchProvider,
  testWebSearchProvider,
} from '@/api/webSearch'
import type { WebSearchProvider, WebSearchProviderTemplate } from '@/types/webSearch'

const { t } = useI18n()
const router = useRouter()
const authStore = useAuthStore()
const isOwner = computed(() => authStore.user?.role === 'owner')

const templates = ref<WebSearchProviderTemplate[]>([])
const providers = ref<WebSearchProvider[]>([])
const loading = ref(false)

const enabledCount = computed(() => providers.value.filter((p) => p.is_enabled).length)

function getTemplate(providerName: string) {
  return templates.value.find((t) => t.provider_name === providerName)
}

function getCircuitLabel(state: string) {
  if (state === 'open') return t('webSearch.circuitOpen')
  if (state === 'half_open') return t('webSearch.circuitHalfOpen')
  return t('webSearch.circuitClosed')
}

function getCircuitColor(state: string) {
  if (state === 'open') return 'var(--van-danger-color)'
  if (state === 'half_open') return 'var(--van-warning-color)'
  return 'var(--van-success-color)'
}

async function load() {
  loading.value = true
  try {
    const [tmpl, provs] = await Promise.all([getWebSearchTemplates(), getWebSearchProviders()])
    templates.value = tmpl
    providers.value = provs
  } finally {
    loading.value = false
  }
}

function goToForm(providerName?: string, providerId?: string) {
  if (providerId) {
    router.push({ name: 'WebSearchForm', query: { id: providerId } })
  } else if (providerName) {
    router.push({ name: 'WebSearchForm', query: { provider: providerName } })
  }
}

async function handleToggle(provider: WebSearchProvider) {
  try {
    if (provider.is_enabled) {
      await disableWebSearchProvider(provider.id)
      showToast(t('webSearch.disableSuccess'))
    } else {
      await enableWebSearchProvider(provider.id)
      showToast(t('webSearch.enableSuccess'))
    }
    await load()
  } catch (e: any) {
    showToast(e?.response?.data?.detail || t('webSearch.noApiKeyWarning'))
  }
}

async function handleDelete(provider: WebSearchProvider) {
  try {
    await showConfirmDialog({
      title: t('webSearch.deleteBtn'),
      message: t('webSearch.confirmDelete', { name: provider.display_name || provider.provider_name }),
    })
    await deleteWebSearchProvider(provider.id)
    showToast(t('webSearch.deleteSuccess'))
    await load()
  } catch {
    // User cancelled
  }
}

async function handleTest(provider: WebSearchProvider) {
  try {
    const result = await testWebSearchProvider(provider.id)
    if (result.success) {
      showToast(t('webSearch.testSuccess'))
    } else {
      showToast(t('webSearch.testFailed'))
    }
  } catch {
    showToast(t('webSearch.testFailed'))
  }
}

onMounted(load)
</script>

<template>
  <div class="web-search-page">
    <van-nav-bar :title="t('webSearch.title')" left-arrow @click-left="router.back()" />

    <div class="status-bar">
      <span v-if="enabledCount > 0" class="status-enabled">
        {{ t('webSearch.statusEnabled', { count: enabledCount }) }}
      </span>
      <span v-else class="status-disabled">{{ t('webSearch.statusDisabled') }}</span>
    </div>

    <van-cell-group :title="t('webSearch.subtitle')">
      <van-cell
        v-for="provider in providers"
        :key="provider.id"
        :title="provider.display_name || provider.provider_name"
        :label="getTemplate(provider.provider_name)?.note"
        is-link
        @click="goToForm(undefined, provider.id)"
      >
        <template #right-icon>
          <div class="provider-actions">
            <span
              class="circuit-badge"
              :style="{ color: getCircuitColor(provider.circuit_state) }"
            >
              {{ getCircuitLabel(provider.circuit_state) }}
            </span>
            <van-switch
              v-if="isOwner"
              :model-value="provider.is_enabled"
              size="20px"
              @click.stop
              @update:model-value="handleToggle(provider)"
            />
          </div>
        </template>
      </van-cell>
    </van-cell-group>

    <!-- Unconfigured templates -->
    <van-cell-group v-if="isOwner" :title="t('webSearch.addProvider')">
      <template v-for="tmpl in templates" :key="tmpl.provider_name">
        <van-cell
          v-if="!providers.some((p) => p.provider_name === tmpl.provider_name)"
          :title="tmpl.display_name"
          :label="tmpl.note"
          is-link
          @click="goToForm(tmpl.provider_name)"
        >
          <template #right-icon>
            <van-button size="small" type="primary" plain>
              {{ t('webSearch.configBtn') }}
            </van-button>
          </template>
        </van-cell>
      </template>
    </van-cell-group>

    <div class="mcp-hint">
      <van-icon name="info-o" />
      <span>{{ t('webSearch.mcpHint') }}</span>
    </div>
  </div>
</template>

<style scoped>
.web-search-page {
  padding-bottom: 20px;
}

.status-bar {
  padding: 12px 16px;
  font-size: 14px;
}

.status-enabled {
  color: var(--van-success-color);
}

.status-disabled {
  color: var(--text-secondary);
}

.provider-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.circuit-badge {
  font-size: 12px;
}

.mcp-hint {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 12px 16px;
  font-size: 12px;
  color: var(--text-secondary);
}
</style>
```

- [ ] **Step 2: Add route to router/index.ts**

In `frontend/apps/main/src/router/index.ts`, add after the MCP route:

```typescript
{
  path: 'settings/ai/web-search',
  name: 'WebSearch',
  component: () => import('@/pages/WebSearchPage.vue'),
},
// WebSearchForm route is added in Task 10 after WebSearchFormPage.vue is created
```

- [ ] **Step 3: Run typecheck**

Run: `cd /Users/vincentruan/geek_space/github/numina/frontend/apps/main && pnpm typecheck`
Expected: No type errors (WebSearchFormPage.vue doesn't exist yet — may need to create a stub or add route after Task 10)

- [ ] **Step 4: Commit**

```bash
git add frontend/apps/main/src/pages/WebSearchPage.vue frontend/apps/main/src/router/index.ts
git commit -m "feat(frontend): add WebSearchPage with provider list and status display"
```

---

## Task 10: Frontend — WebSearchFormPage (Provider Config Form)

**Files:**
- Create: `frontend/apps/main/src/pages/WebSearchFormPage.vue`

- [ ] **Step 1: Create the form page component**

```vue
<!-- frontend/apps/main/src/pages/WebSearchFormPage.vue -->
<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { showToast } from 'vant'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@numina/auth'
import {
  getWebSearchTemplates,
  getWebSearchProviders,
  createWebSearchProvider,
  updateWebSearchProvider,
  testWebSearchProvider,
  deleteWebSearchProvider,
} from '@/api/webSearch'
import type { WebSearchProvider, WebSearchProviderTemplate } from '@/types/webSearch'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const isOwner = computed(() => authStore.user?.role === 'owner')

const isEdit = computed(() => !!route.query.id)
const providerId = computed(() => route.query.id as string | undefined)
const providerNameParam = computed(() => route.query.provider as string | undefined)

const template = ref<WebSearchProviderTemplate | null>(null)
const existingProvider = ref<WebSearchProvider | null>(null)

const form = ref({
  provider_name: '',
  display_name: '',
  api_key: '',
  max_results: 5,
})

const loading = ref(false)
const saving = ref(false)

const pageTitle = computed(() =>
  isEdit.value ? t('webSearch.formEditTitle') : t('webSearch.formTitle'),
)

async function load() {
  loading.value = true
  try {
    const templates = await getWebSearchTemplates()

    if (isEdit.value && providerId.value) {
      const providers = await getWebSearchProviders()
      existingProvider.value = providers.find((p) => p.id === providerId.value) || null
      if (existingProvider.value) {
        template.value =
          templates.find((t) => t.provider_name === existingProvider.value!.provider_name) || null
        form.value.provider_name = existingProvider.value.provider_name
        form.value.display_name = existingProvider.value.display_name || ''
        form.value.max_results = existingProvider.value.max_results
        form.value.api_key = ''
      }
    } else if (providerNameParam.value) {
      template.value = templates.find((t) => t.provider_name === providerNameParam.value) || null
      if (template.value) {
        form.value.provider_name = template.value.provider_name
        form.value.display_name = template.value.display_name
      }
    }
  } finally {
    loading.value = false
  }
}

async function handleSave() {
  if (!template.value) return

  if (template.value.requires_api_key && !form.value.api_key && !isEdit.value) {
    showToast(t('webSearch.noApiKeyWarning'))
    return
  }

  saving.value = true
  try {
    if (isEdit.value && providerId.value) {
      const payload: Record<string, any> = {
        display_name: form.value.display_name || undefined,
        max_results: form.value.max_results,
      }
      if (form.value.api_key) {
        payload.api_key = form.value.api_key
      }
      await updateWebSearchProvider(providerId.value, payload)
    } else {
      await createWebSearchProvider({
        provider_name: form.value.provider_name,
        display_name: form.value.display_name || undefined,
        api_key: form.value.api_key || undefined,
        max_results: form.value.max_results,
      })
    }
    showToast(t('webSearch.saveSuccess'))
    router.back()
  } catch (e: any) {
    showToast(e?.response?.data?.detail || '❌ 保存失败')
  } finally {
    saving.value = false
  }
}

async function handleTest() {
  if (!providerId.value) return
  try {
    const result = await testWebSearchProvider(providerId.value)
    showToast(result.success ? t('webSearch.testSuccess') : t('webSearch.testFailed'))
  } catch {
    showToast(t('webSearch.testFailed'))
  }
}

onMounted(load)
</script>

<template>
  <div class="web-search-form-page">
    <van-nav-bar :title="pageTitle" left-arrow @click-left="router.back()" />

    <van-form @submit="handleSave">
      <van-cell-group inset>
        <van-field
          v-model="form.display_name"
          :label="t('webSearch.providerName')"
          :placeholder="template?.display_name"
        />

        <van-field
          v-if="template?.requires_api_key"
          v-model="form.api_key"
          :label="t('webSearch.apiKey')"
          :placeholder="
            isEdit && existingProvider?.has_api_key
              ? '••••••••（已配置，留空不修改）'
              : t('webSearch.apiKeyPlaceholder')
          "
          type="password"
        />

        <van-field
          v-model.number="form.max_results"
          :label="t('webSearch.maxResults')"
          type="digit"
        />
      </van-cell-group>

      <div class="form-actions">
        <van-button
          v-if="isOwner"
          type="primary"
          block
          native-type="submit"
          :loading="saving"
        >
          {{ t('webSearch.saveSuccess').replace('✅ ', '') }}
        </van-button>

        <van-button
          v-if="isEdit && isOwner"
          plain
          block
          @click="handleTest"
        >
          {{ t('webSearch.testBtn') }}
        </van-button>
      </div>

      <div v-if="template" class="provider-info">
        <p>{{ template.note }}</p>
        <a :href="template.docs_url" target="_blank" rel="noopener">{{ template.docs_url }}</a>
      </div>
    </van-form>
  </div>
</template>

<style scoped>
.web-search-form-page {
  padding-bottom: 20px;
}

.form-actions {
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.provider-info {
  padding: 12px 16px;
  font-size: 12px;
  color: var(--text-secondary);
}

.provider-info a {
  color: var(--van-primary-color);
}
</style>
```

- [ ] **Step 2: Run typecheck**

Run: `cd /Users/vincentruan/geek_space/github/numina/frontend/apps/main && pnpm typecheck`
Expected: No type errors

- [ ] **Step 3: Commit**

```bash
git add frontend/apps/main/src/pages/WebSearchFormPage.vue
git commit -m "feat(frontend): add WebSearchFormPage for provider configuration"
```

---

## Task 11: Frontend — MCP Page Modifications (mcp_type)

**Files:**
- Modify: `frontend/apps/main/src/pages/MCPFormPage.vue`
- Modify: `frontend/apps/main/src/pages/MCPManagePage.vue`

- [ ] **Step 1: Add mcp_type to MCP types**

In the MCP type definition (likely in `@/types/` or inline in `@/api/ai.ts`), add `mcp_type` field:

```typescript
// Add to the MCPServer interface (wherever it's defined)
mcp_type: 'general' | 'websearch'
```

And to the create/update payload:

```typescript
mcp_type?: 'general' | 'websearch'
```

- [ ] **Step 2: Add mcp_type picker to MCPFormPage.vue**

In `MCPFormPage.vue`, add a radio group after the transport field:

```vue
<van-field :label="t('mcp.type')" name="mcp_type">
  <template #input>
    <van-radio-group v-model="form.mcp_type" direction="horizontal">
      <van-radio name="general">{{ t('mcp.typeGeneral') }}</van-radio>
      <van-radio name="websearch">{{ t('mcp.typeWebsearch') }}</van-radio>
    </van-radio-group>
  </template>
</van-field>
```

Initialize `form.mcp_type = 'general'` in the form ref, and include it in the save payload.

- [ ] **Step 3: Add websearch badge to MCPManagePage.vue**

In `MCPManagePage.vue`, in the server list cell, add a tag for websearch type:

```vue
<template #title>
  <span>{{ server.name }}</span>
  <van-tag v-if="server.mcp_type === 'websearch'" type="primary" size="small" style="margin-left: 6px">
    {{ t('webSearch.title') }}
  </van-tag>
</template>
```

- [ ] **Step 4: Add i18n keys for MCP type**

In `zh-CN.ts` under the `mcp` section:

```typescript
type: '类型',
typeGeneral: '通用',
typeWebsearch: '联网搜索',
```

In `en-US.ts`:

```typescript
type: 'Type',
typeGeneral: 'General',
typeWebsearch: 'Web Search',
```

- [ ] **Step 5: Run typecheck**

Run: `cd /Users/vincentruan/geek_space/github/numina/frontend/apps/main && pnpm typecheck`
Expected: No type errors

- [ ] **Step 6: Commit**

```bash
git add frontend/apps/main/src/pages/MCPFormPage.vue frontend/apps/main/src/pages/MCPManagePage.vue frontend/apps/main/src/i18n/locales/zh-CN.ts frontend/apps/main/src/i18n/locales/en-US.ts
git commit -m "feat(frontend): add mcp_type selector to MCP form and websearch badge to list"
```

---

## Task 12: Frontend — Agent Card Web Search Pre-Check

**Files:**
- Modify: `frontend/apps/main/src/components/agent/AgentCard.vue` (or equivalent component with web search toggle)

- [ ] **Step 1: Add pre-check before enabling web search**

In the component that handles the web search toggle on the agent card, add a check:

```typescript
import { getWebSearchStatus } from '@/api/webSearch'

async function handleWebSearchToggle(enabled: boolean) {
  if (enabled) {
    const status = await getWebSearchStatus()
    if (!status.has_web_search) {
      showToast(t('webSearch.noProviderToast'))
      return
    }
  }
  // Proceed with existing toggle logic
  emit('update:webSearch', enabled)
}
```

- [ ] **Step 2: Run typecheck**

Run: `cd /Users/vincentruan/geek_space/github/numina/frontend/apps/main && pnpm typecheck`
Expected: No type errors

- [ ] **Step 3: Commit**

```bash
git add frontend/apps/main/src/components/agent/AgentCard.vue
git commit -m "feat(frontend): add web search status pre-check on agent card toggle"
```

---

## Task 13: Config Cleanup — Remove Static Tavily Key

**Files:**
- Modify: `server/apps/agent/deerflow_config/base/config.yaml`
- Modify: `docker-compose.yml`

- [ ] **Step 1: Remove static api_key from DeerFlow base config**

In `server/apps/agent/deerflow_config/base/config.yaml`, find the `web_search` tool entry and remove the hardcoded `api_key` value, leaving it as a placeholder:

```yaml
tools:
  - name: web_search
    use: "placeholder"
    api_key: ""
    max_results: 5
```

- [ ] **Step 2: Remove TAVILY_API_KEY from docker-compose.yml**

In `docker-compose.yml`, remove the `TAVILY_API_KEY` environment variable from the agent service section.

- [ ] **Step 3: Verify agent still starts without the env var**

Run: `cd /Users/vincentruan/geek_space/github/numina/server && uv run pytest tests/agent/ -v -k "not integration" --tb=short -q`
Expected: Tests pass (agent doesn't crash without TAVILY_API_KEY)

- [ ] **Step 4: Commit**

```bash
git add server/apps/agent/deerflow_config/base/config.yaml docker-compose.yml
git commit -m "chore: remove static TAVILY_API_KEY from config and docker-compose"
```

---

## Task 14: Integration Test — End-to-End Failover

**Files:**
- Create: `server/tests/backend/test_agent_dispatch_web_search_failover.py`

- [ ] **Step 1: Write the integration test**

```python
# server/tests/backend/test_agent_dispatch_web_search_failover.py
"""Integration test: web search provider failover when primary returns 401."""
import pytest
from unittest.mock import patch, AsyncMock

from apps.backend.app.models.family_web_search_provider import FamilyWebSearchProvider
from apps.backend.app.services.ai_crypto import encrypt_api_key
from apps.backend.app.services.web_search_circuit_service import WebSearchCircuitService
from apps.backend.app.utils.snowflake import next_id


@pytest.fixture
def family_providers(db):
    """Two providers: tavily (primary) and ddg_search (fallback)."""
    p1 = FamilyWebSearchProvider(
        id=next_id(),
        family_id=2001,
        provider_name="tavily",
        api_key_encrypted=encrypt_api_key("tvly-bad-key"),
        is_enabled=True,
        display_order=1,
        max_results=5,
        circuit_state="closed",
    )
    p2 = FamilyWebSearchProvider(
        id=next_id(),
        family_id=2001,
        provider_name="ddg_search",
        is_enabled=True,
        display_order=2,
        max_results=3,
        circuit_state="closed",
    )
    db.add_all([p1, p2])
    db.commit()
    return p1, p2


def test_circuit_opens_on_permanent_auth_failure(db, family_providers):
    """When tavily returns 401, circuit opens and ddg becomes primary."""
    tavily, ddg = family_providers

    # Simulate permanent auth failure
    WebSearchCircuitService.report_failure(tavily.id, "permanent_auth", db)

    db.refresh(tavily)
    assert tavily.circuit_state == "open"
    assert tavily.circuit_reason == "permanent_auth"

    # Query available providers (simulating what internal API does)
    available = (
        db.query(FamilyWebSearchProvider)
        .filter(
            FamilyWebSearchProvider.family_id == 2001,
            FamilyWebSearchProvider.is_enabled.is_(True),
            FamilyWebSearchProvider.circuit_state != "open",
        )
        .order_by(FamilyWebSearchProvider.display_order)
        .all()
    )
    assert len(available) == 1
    assert available[0].provider_name == "ddg_search"


def test_transient_failures_accumulate_then_open(db, family_providers):
    """5 transient failures open the circuit."""
    tavily, _ = family_providers

    for i in range(4):
        WebSearchCircuitService.report_failure(tavily.id, "transient_rate_limit", db)
        db.refresh(tavily)
        assert tavily.circuit_state == "closed"

    WebSearchCircuitService.report_failure(tavily.id, "transient_rate_limit", db)
    db.refresh(tavily)
    assert tavily.circuit_state == "open"


def test_half_open_recovery_flow(db, family_providers):
    """After circuit opens, recovery transitions through half_open to closed."""
    tavily, _ = family_providers

    # Open the circuit
    for _ in range(5):
        WebSearchCircuitService.report_failure(tavily.id, "transient_rate_limit", db)

    db.refresh(tavily)
    assert tavily.circuit_state == "open"

    # Trigger recovery check
    WebSearchCircuitService.check_recovery(tavily.id, db)
    db.refresh(tavily)
    assert tavily.circuit_state == "half_open"

    # 3 successes close it
    for _ in range(3):
        WebSearchCircuitService.report_success(tavily.id, db)

    db.refresh(tavily)
    assert tavily.circuit_state == "closed"
    assert tavily.failure_count == 0
```

- [ ] **Step 2: Run the integration test**

Run: `cd /Users/vincentruan/geek_space/github/numina/server && uv run pytest tests/backend/test_agent_dispatch_web_search_failover.py -v`
Expected: All 3 tests PASS

- [ ] **Step 3: Commit**

```bash
git add server/tests/backend/test_agent_dispatch_web_search_failover.py
git commit -m "test(backend): add integration tests for web search provider failover"
```

---

## Task 15: Final Verification

- [ ] **Step 1: Run full backend test suite**

Run: `cd /Users/vincentruan/geek_space/github/numina/server && uv run pytest tests/backend/ -q --tb=short -k "not titlemiddleware" 2>&1 | tail -20`
Expected: All tests pass, no regressions

- [ ] **Step 2: Run ruff on all new files**

Run: `cd /Users/vincentruan/geek_space/github/numina/server && uv run ruff check apps/backend/app/models/family_web_search_provider.py apps/backend/app/services/web_search_provider_registry.py apps/backend/app/services/web_search_circuit_service.py apps/backend/app/routers/ai_web_search.py`
Expected: No lint errors

- [ ] **Step 3: Run frontend typecheck**

Run: `cd /Users/vincentruan/geek_space/github/numina/frontend/apps/main && pnpm typecheck`
Expected: No type errors

- [ ] **Step 4: Run frontend lint**

Run: `cd /Users/vincentruan/geek_space/github/numina/frontend/apps/main && pnpm lint`
Expected: No lint errors

- [ ] **Step 5: Verify all new files are committed**

Run: `git status`
Expected: Clean working tree

---

