# backend/CLAUDE.md

Module-specific guidance for the Python FastAPI backend.
See root [`CLAUDE.md`](../CLAUDE.md) for behavioral guidelines and cross-cutting conventions.

## Cache Backend

Controlled by `CACHE_BACKEND` env var (default: `"memory"`). Set to `"redis"` to enable Redis. When using Redis, also set `REDIS_URL` (e.g. `redis://localhost:6379/0`). The in-memory backend is suitable for single-instance dev; Redis is required for multi-worker or multi-instance deployments.

## Key Invariants

- **Always run `alembic upgrade head` before starting the app on an existing database.** `Base.metadata.create_all()` only creates tables for fresh installs — it does not apply migrations. Skipping causes `OperationalError: no such column` on endpoints that read newly added columns.
- **Import direction** — see [server/CLAUDE.md](../../CLAUDE.md) §Import Direction.
- **Error detail convention** — backend uses `AppError` (`app/errors/exceptions.py`) with `ErrorCode` enum (`app/errors/codes.py`). Each error code maps to a status code via `ERROR_META` and to i18n messages via `app/errors/locales/{zh-CN,en-US}.json`. The global `error_handlers.py` catches `AppError`, `RequestValidationError`, `StarletteHTTPException`, and `StorageError`, returning a unified JSON envelope: `{"code": "ERROR_CODE", "message": "localized message", "data": null, "request_id": "..."}`. Language is selected via `Accept-Language` header. Frontend catches via axios interceptor and maps `code` to i18n key `t('errors.ERROR_CODE')`.
- **Agent Communication** — Never use raw `httpx.AsyncClient` to call Agent microservices. Always use `apps.backend.app.services.agent_client.AgentClient`. It guarantees tenant isolation by automatically injecting `X-Family-Id`, `X-User-Id`, and `X-Agent-Token` headers.

## Snowflake ID Serialization

All response schemas containing IDs inherit from `SnowflakeBase` (app/schemas/base.py).

### Pattern

```python
from apps.backend.app.schemas.base import SnowflakeBase

class MyResponse(SnowflakeBase):
    id: int  # Define as int (matches DB)
    family_id: int
    other_id: int
    name: str
```

JSON output automatically converts IDs to strings:
```json
{"id": "123456789012345", "family_id": "987654321098765"}
```

### Key Points

- Schemas define IDs as `int` (internal representation matches SQLAlchemy)
- SnowflakeBase.model_serializer converts to `str` during JSON serialization
- No manual `str()` calls in routers — return int values directly
- Request schemas (Create/Update) don't need SnowflakeBase — input comes as string

### Common Pitfalls

1. **Don't use plain BaseModel for schemas with IDs** → Use SnowflakeBase
2. **Don't manually define `id: str`** → Define `id: int`, let serializer convert
3. **Don't add field_validator for ID coercion** → SnowflakeBase handles it
4. **Don't call str() in routers** → Return int, schema serializes
5. **Request schemas don't need SnowflakeBase** → Input validation handles string→int

### Why

JavaScript loses precision for integers > 2^53. Snowflake IDs are 18-19 digits.
Serializing as strings preserves exact values across the API boundary.

## Backend 问题排查指南

遇到以下问题时，参考对应的 solution 文档：

| 问题场景 | 参考文档 |
|---------|---------|
| Snowflake ID 序列化 / JS 精度丢失 | [`snowflake-id-serialization`](../../../docs/solutions/best-practices/snowflake-id-json-string-serialization-2026-04-27.md) |
| 金额计算精度 / Decimal vs Float / money-as-str | [`money-decimal-compute`](../../../docs/solutions/best-practices/money-decimal-compute-str-wire-serialization.md) |
| 缓存键粒度 / 多用户数据隔离 | [`cache-key-granularity`](../../../docs/solutions/best-practices/cache-key-granularity-matches-data-scope-2026-04-27.md) |
| JWT JTI 撤销 / token 安全 | [`jti-revocation`](../../../docs/solutions/best-practices/jti-revocation-requires-db-persistence-2026-04-27.md) |
| Pydantic 验证错误本地化 | [`fastapi-pydantic-validation`](../../../docs/solutions/best-practices/fastapi-pydantic-validation-error-localization-2026-04-16.md) |
| Redis fail-fast / 集群部署 | [`redis-fail-fast`](../../../docs/solutions/best-practices/redis-fail-fast-strategy.md) |
| 日志配置 / rotation / archival | [`logging-config`](../../../docs/solutions/best-practices/logging-config.md) |
| 安全审计 / 文件上传 magic bytes | [`security-audit`](../../../docs/solutions/best-practices/security-audit.md) |
| 安全防护 / rate-limiting / brute-force | [`security-protection`](../../../docs/solutions/best-practices/security-protection.md) |
| Altcha CAPTCHA 集成 | [`altcha-captcha`](../../../docs/solutions/best-practices/altcha-captcha-best-practices-2026-04-03.md) |
| 文件存储抽象 / GitHub API / WebDAV | [`file-storage-abstraction`](../../../docs/solutions/best-practices/file-storage-abstraction-2026-04-10.md) |
| Nginx DNS 上游缓存 / stale DNS | [`nginx-stale-dns`](../../../docs/solutions/integration-issues/nginx-stale-dns-upstream-cache.md) |
| 统一数据根路径管理 / Docker volume | [`unified-data-root-path`](../../../docs/solutions/architecture-patterns/unified-data-root-path-management-2026-05-17.md) |
| MCP caller-bound principal / tenant isolation | [`mcp-caller-bound-principal`](../../../docs/solutions/architecture-patterns/mcp-caller-bound-principal-2026-05-31.md) |
| DB check constraint 与 Pydantic regex 不一致 | [`db-check-constraint-pydantic-regex-sync`](../../../docs/solutions/best-practices/db-check-constraint-pydantic-regex-sync.md) |
| ASR WER/CER 100% 错误率 / 文本归一化 | [`asr-wer-whitespace-stripping-tokenization`](../../../docs/solutions/integration-issues/asr-wer-whitespace-stripping-tokenization.md) |

## App Layout

```
app/
├── main.py            # FastAPI entry point + router registration (54 routers)
├── config.py          # AppSettings (pydantic-settings)
├── database.py        # SessionLocal binding + dependency
├── errors/            # AppError, ErrorCode enum, i18n locales (zh-CN.json, en-US.json)
├── error_handlers.py  # Global exception handlers (AppError → i18n JSON envelope)
├── responses.py       # Shared response helpers
├── auth/              # JWT helpers, password hashing, dependency-injection guards
├── routers/           # All HTTP route definitions (one file per resource)
├── schemas/           # Pydantic request/response models (all extend SnowflakeBase when returning IDs)
├── models/            # SQLAlchemy ORM models (joined to packages.db.session.Base)
├── services/          # Business logic above ORM, below routers
├── middleware/        # request_id, rate_limit, family_context
├── seed/              # System-category and seed-data loaders (run on startup)
├── constants/         # Static lookups (categories, currencies, etc.)
└── utils/             # Shared helpers
```

Models referenced from `packages/db` (Base inheritance) and from `packages/db/models/` for cross-app entities (currencies, exchange rates, devices, notifications, reminders, audit logs).

## Router Inventory

All routers live in `app/routers/` and are mounted with `prefix="/api/v1"` in `app/main.py`. Final paths combine that prefix with the router's own prefix (shown below).

### Core (assets, identity, dashboard)

| Router | Final prefix | Purpose |
|--------|--------------|---------|
| `auth` | `/api/v1/auth` | Login, register, refresh, `/me`, family-join |
| `device` | `/api/v1/auth` | Trusted device + WebAuthn (shares `/auth` prefix) |
| `family` | `/api/v1/family` | Invite code, member list, transfer ownership |
| `assets` | `/api/v1/assets` | CRUD + batch + `/{id}/archive` (soft-delete) |
| `assets_analysis` | `/api/v1` | Asset projection + purchasing-power endpoints |
| `liabilities` | `/api/v1/liabilities` | CRUD + repayment |
| `dashboard` | `/api/v1/dashboard` | Overview, trend, allocation |
| `categories` | `/api/v1/categories` | System category list (read-only) |
| `tags` | `/api/v1/tags` | CRUD |
| `wishes` | `/api/v1/wishes` | Adult wish list |
| `currencies` | `/api/v1/currencies` | Currency master + exchange rates |

### Children & gamification

| Router | Final prefix | Purpose |
|--------|--------------|---------|
| `children` | `/api/v1/family` | Child profile management (under family) |
| `chores` | `/api/v1` | Chore tracking + approval flow |
| `coins` | `/api/v1` | Coin ledger + balance |
| `child_wishes` | `/api/v1` | Wish list visible to children |
| `milestones` | `/api/v1` | Milestone unlocks |
| `treasures` | `/api/v1` | Treasure rewards |
| `calendar` | `/api/v1` | Family calendar (lunar + Gregorian) |
| `blind_box` | `/api/v1/blind-box` | Adult-side blind-box config |
| `child_blind_box` | `/api/v1/child/blind-box` | Child-side blind-box draw |
| `challenge_grants` | `/api/v1/challenges` + `/api/v1/child/challenges` | Two routers from one file: parent-issue + child-claim |

### Files, import, export, utilities

| Router | Final prefix | Purpose |
|--------|--------------|---------|
| `upload` | `/api/v1/upload` | File upload entry |
| `files` | `/api/v1/files` | File listing + download |
| `export` | `/api/v1/export` | Family data export |
| `import_` | `/api/v1/import` | CSV/JSON import |
| `import_report` | `/api/v1/import` | Import status reports (shares `/import` prefix) |
| `captcha` | `/api/v1/captcha` | ALTCHA challenge issuance |
| `activities` | `/api/v1/activities` | Activity feed |

### Notifications & reminders

| Router | Final prefix | Purpose |
|--------|--------------|---------|
| `notifications` | `/api/v1/notifications` | User-facing notification inbox |
| `notification_channels` | `/api/v1/notification-channels` | Channel CRUD (email, webhook, etc.) |
| `notification_config` | `/api/v1/notification-config` | Per-user channel binding |
| `reminders` | `/api/v1/reminders` | Smart reminder rules |

### AI (frontend → backend → agent dispatch)

Backend AI routers are the frontend's entry point. Multi-step capabilities proxy to the agent via `AgentClient.stream` (SSE, `X-Agent-Token`); the agent runs them as `stream_run` apps (`numina`/`asset-report`/`import-parse`/`finance-coach`/`wish-advice`) — see `server/apps/agent/CLAUDE.md` §Runtime & Dispatch. Lightweight single-call capabilities (suggest) call the agent's lightweight LLM endpoint directly.

| Router | Final prefix | Purpose | Dispatch |
|--------|--------------|---------|----------|
| `ai_config` | `/api/v1/ai` | Per-family AI provider config (encrypted at rest) | — |
| `ai_chat` | `/api/v1/ai/chat` | Chat (live conversation) | `AgentClient.stream` → `numina` app |
| `ai_chat.sessions_router` | `/api/v1/ai` | Session events, artifacts, system-default | — |
| `ai_threads` | `/api/threads` | Thread CRUD + state + history + token-usage (proxy to agent `threads` router) | `AgentClient` |
| `ai_context` | `/api/v1/ai/context` | GET family AI context (4-source bundle) | direct |
| `ai_report` | `/api/v1/ai/report` | Family report generation (SSE 3-step) | `AgentClient.stream` → `asset-report` app |
| `ai_finance_coach` | `/api/v1/ai/finance-coach` | Finance coach advice (cached) | `AgentClient.stream` → `finance-coach` app |
| `ai_wish_advice` | `/api/v1/ai/wish-advice` | Wish savings advice (cached) | `AgentClient.stream` → `wish-advice` app |
| `ai_suggest` | `/api/v1/ai/suggest` | Asset field suggestions | lightweight LLM |
| `ai_input_polish` | `/api` | D3 DeerFlow-synced draft polish (cookie auth) | lightweight LLM |
| `ai_skills` | `/api/v1/ai/skills` | Per-family skill overrides (`RESERVED_NAMES = ["chat","asset-report","import-parse","finance-coach"]`) | — |
| `ai_mcp` | `/api/v1/ai/mcp` | MCP tool catalogue | — |
| `ai_agents` | `/api/v1/ai/agents` | Agent catalogue (frontend) | — |
| `ai_tasks` | `/api/v1/ai/tasks` | Long-running AI task tracking | — |
| `ai_web_search` | `/api/v1/ai/web-search` | Web search proxy | — |
| `ai_time_machine` | `/api/v1/ai` | Time-machine projections (legacy) | — |

### Internal (agent ↔ backend, admin)

| Router | Final prefix | Purpose |
|--------|--------------|---------|
| `ai_internal` | `/api/v1/internal` | Agent → backend data access (`X-Agent-Token`) |
| `ai_agents_internal` | `/api/v1/internal/ai/agents` | Agent → backend (agent-side) |
| `mcp_internal` | `/api/v1/internal/mcp` | MCP runtime → backend |
| `admin_ai_extraction` | `/api/v1/admin` | Admin tooling for AI extraction review |
| `admin_audit_logs` | `/api/v1/admin` | Admin audit log viewing |

When adding a new router: register it in `app/main.py`, set `prefix=""` for root-path decorators (see §URL Style in root [CLAUDE.md](../../../CLAUDE.md)), and inherit response schemas from `SnowflakeBase`.

## Patterns

### Common Pitfalls

- 6-character alphanumeric code stored on the `Family` model
- `POST /api/v1/family/invite-code` regenerates it (owner only)
- `POST /api/v1/auth/family/join` accepts it — joins the caller to that family
- Codes are single-use per join attempt but not invalidated after use (any member can share the same code)

### Data Model Key Relationships

- `User` → `Family` (many-to-one via `family_id`)
- `Asset` → `User` (many-to-one via `owner_id`); family aggregate queries join through `User.family_id`
- `Asset` → `Category` (many-to-one); `Asset` ↔ `Tag` (many-to-many via `asset_tags`)
- `Liability` → `Asset` (optional many-to-one via `linked_asset_id`)
- `AssetSnapshot` → `Family` (many-to-one); one snapshot per family per day

### Asset Enhanced Fields

Physical assets carry daily-cost fields:
- `purchase_price`, `current_value`, `purchase_date`, `expected_lifespan_years`, `annual_maintenance_cost`
- `daily_cost` = `(purchase_price + total_maintenance) / total_days_owned` (computed, not stored)
- `usage_frequency`: `daily` / `weekly` / `monthly` / `rarely` / `never`

Financial assets carry return fields:
- `principal_amount`, `current_value`, `annual_return_rate`
- `return_rate` = `(current_value - principal_amount) / principal_amount` (computed)

### Predefined Categories

21 system categories seeded on startup (read-only, `is_system=True`). See `app/seed/categories.py` and `app/constants/categories.py` for the full list.

### Common Pitfalls

- `DELETE /assets/{id}` archives (sets `is_archived=True`), does not hard-delete
- Dashboard queries filter `is_archived=False` — archived assets are excluded from all aggregates
- **Error handling pattern:** raise `AppError(ErrorCode.XXX, details=...)` from `app/errors/exceptions.py`. The global handler in `error_handlers.py` maps it to the i18n JSON envelope via `errors/codes.py` + `errors/locales/{zh-CN,en-US}.json`. Never raise raw `HTTPException` with English strings for new code — use `AppError` + `ErrorCode`.

## MCP Caller Binding Invariants

These must hold for all MCP tool execution paths:

1. **Caller identity frozen at SSE handshake** — `MCPSession.__slots__` contains `_family_id`, `_caller_user_id`, `_caller_role`, `_server`. All frozen at construction. Tool handlers NEVER read identity from tool args.
2. **No silent fallback** — If caller validation fails (unknown, inactive, cross-family, child role), the SSE handshake returns 403. Never fall back to owner.
3. **Protocol-layer filtering** — `list_tools()` returns only tools where `caller_role ∈ allowed_roles`. `call_tool()` re-checks (defense in depth).
4. **permission_denied = permanent** — Role check failure returns `{"error": "permission_denied", "retryable": false}`. LLM must not retry.
5. **Zero outbound HTTP** — `mcp_session.py` and `mcp_tool_registry.py` must never import `httpx`, `aiohttp`, or `apps.agent`. Enforced by static AST test + dynamic httpx patch test.
6. **Audit fields** — All log paths include `caller_user_id` and `caller_role`. Success = INFO, permission_denied = WARNING, service error = ERROR.
7. **Tool registry SSOT** — All tool metadata lives in `mcp_tool_registry.py`. `validate_registry()` runs at startup; missing `allowed_roles` = fail-fast.
8. **POST /messages isolation** — Relies on MCP SDK's UUID4 session_id for session routing. No additional caller check needed on POST path.

## Links

- Root [`CLAUDE.md`](../CLAUDE.md) — behavioral guidelines, cross-cutting conventions
- Module [`README.md`](./README.md) — quick start, architecture, API endpoints
- [`docs/solutions/`](../docs/solutions/) — documented solutions to past problems
