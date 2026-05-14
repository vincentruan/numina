---
date: 2026-05-13
topic: backend-architecture
focus: Backend architecture refactoring to server/apps/{backend_api,agent_api,worker,scheduler} + packages/{core,security,tenancy,db,domain,llm,contracts,clients,observability}
mode: repo-grounded
---

# Ideation: Backend Architecture Refactoring

## Grounding Context

**Codebase Context:**
- Numina is a privacy-first family asset visualization system with Backend (monolithic FastAPI, ~40 routers/services flat under app/), Agent (separate DeerFlow/LangChain microservice), Frontend (Vue 3 pnpm monorepo), and Docker/Nginx infrastructure
- Backend has no apps+packages separation; all routers/services live flat making navigation difficult and merge conflicts likely
- Agent-Backend boundary is clean (HTTP-only, no Python imports) but lacks shared contract package risking silent API drift
- APScheduler in backend has 5 active jobs (exchange rates, file sync, audit purge, token cleanup, device sessions, reminders, snapshots); agent scheduler is dormant (Phase 1 unfinished)
- Domain boundaries visible in router naming (assets, auth, family, children, AI, storage, activities, blind_box, chores) making extraction straightforward
- Pain points: temp file leak in family_adapter_cache, session journal divergence (fire-and-forget), hardcoded empty assets/members context in orchestrator, duplicate scheduler pattern

**Past learnings:**
- Module autonomy: each module owns tooling/docs (CLAUDE.md pattern) — root is thin with cross-cutting rules only
- Tenant isolation: family-level filtering on all queries (`User.family_id == current_user.family_id`)
- Schema organization: one file per domain in `schemas/`, routers import never define
- Service abstraction: ABC + factory caching pattern for pluggable backends
- Singleton management: explicit exports, verify import names (avoid broad exception swallowing)
- Concurrency safety: asyncio.Lock acquired in async context before run_in_executor
- Module boundaries: never import private names across modules, add public API wrappers

**External context:**
- Hexagonal Architecture: Domain (pure business logic), Application (orchestration), Infrastructure (FastAPI routers, DB adapters) — FastAPI DI wires adapters to services
- Multi-tenant strategies: (1) Shared Tables + PostgreSQL RLS, (2) Schema-Per-Tenant, (3) Database-Per-Tenant, (4) Hybrid Sharding, (5) Container Isolation — TenantContext via contextvars middleware
- LLM provider abstraction: Strategy pattern with BaseLLMProvider ABC, normalized ChatMessage/LLMResponse models, registry for runtime selection
- Strangler Fig migration: introduce gateway, extract peripheral bounded contexts first, route traffic gradually — modular monolith as intermediate step
- Python monorepo: uv workspaces with `[tool.uv.workspace] members = ["packages/*"]`, unified lockfile
- Migration warning: start with 3-5 services, don't over-fragment (47 microservices made everything worse)

---

## Ranked Ideas

### 1. Contract-Driven Domain Network
**Description:** Each domain package (assets, auth, family, children, AI, storage) is self-contained with its own published contracts (`packages/domain/assets/contracts.py`). Backend_api and agent_api import domain contracts, never domain internals. Domains communicate via contract-defined events. Infrastructure packages (core, security, db, observability) serve all domains without domain-to-domain direct imports.

**Rationale:** Synthesizes contract-first API boundaries (eliminating API drift) with domain-network architecture (preventing domain coupling). Addresses the top two architectural risks: API drift between backend-agent and flat router sprawl hiding domain boundaries. Once established, domains can be extracted to microservices without breaking contracts, and backend-agent integration becomes type-safe.

**Downsides:** Requires upfront contract design discipline. Domain packages must publish stable interfaces before apps consume them. Migration path: define contracts for each domain, move domain logic, refactor apps to import contracts.

**Confidence:** 95%

**Complexity:** High

**Status:** Unexplored

---

### 2. Strangler Fig In-Place Migration
**Description:** Create target architecture (apps+packages) as empty skeleton in `server/`. Migrate routers one-by-one: move assets routers to `apps/backend_api/routes/assets.py`, extract services to `packages/domain/assets/`, redirect old routes to new implementation. Old monolith gradually hollows out. No feature freeze, no branch divergence, continuous deployment. Completion: delete old backend/app/ structure.

**Rationale:** Matches domain boundaries visible in grounding (assets, auth, family, children, AI, storage). Prevents stalled migration by enabling continuous deployment. Works with existing architecture rather than requiring big-bang rewrite. Modular monolith as valid endpoint — migration can stop mid-way if apps+packages proves sufficient without full microservices decomposition.

**Downsides:** Requires maintaining old and new structures simultaneously during transition. Router redirection adds runtime overhead until old structure deleted. Careful dependency management to avoid circular imports during migration.

**Confidence:** 90%

**Complexity:** Medium

**Status:** Unexplored

---

### 3. Tenant-Aware Hexagonal Domains
**Description:** Each domain package structured hexagonally: `packages/domain/assets/port/in/` (API use cases), `port/out/` (repository interfaces), `adapter/in/http/` (FastAPI route handlers), `adapter/out/db/` (SQLAlchemy repositories). Domain core never imports FastAPI or SQLAlchemy. Tenant middleware auto-injects TenantContext at adapter layer. Domain logic receives TenantContext as explicit parameter, enabling pure testing without framework dependencies.

**Rationale:** Synthesizes tenant-aware infrastructure (centralizing family_id filtering) with hexagonal domains (enabling testing purity). Addresses scattered tenant logic across routers and framework coupling in domain services. TenantContext injection at adapter layer ensures isolation enforcement without polluting domain logic. Domain testing becomes trivial: call domain use case with TenantContext and test repositories.

**Downsides:** Domain packages become more verbose (ports/adapters structure). Requires clear separation between domain logic and HTTP/database adapters. Team must understand hexagonal architecture pattern.

**Confidence:** 85%

**Complexity:** High

**Status:** Unexplored

---

### 4. Runtime Decomposition with Worker Backbone
**Description:** server/apps/ splits by runtime characteristics: `backend_api/` (stateless FastAPI for HTTP endpoints), `worker/` (stateful background job processor), `scheduler/` (APScheduler orchestrator), `agent_api/` (DeerFlow process manager). Extract backend's 5 APScheduler jobs and agent's dormant scheduler into unified `apps/scheduler/` service. Worker imports domain packages and contracts, uses abstract TaskQueue ABC (implementations: APScheduler for dev, Celery/RQ for prod). Scheduler coordinates all async work, preventing duplicate scheduler infrastructure.

**Rationale:** Addresses conflated runtime (backend mixes API serving + scheduled jobs + worker logic) and dormant agent scheduler (wasted code). Worker abstraction enables horizontal scaling (run 3 workers for file sync backlog), independent deployment (worker restarts don't impact API), and queue strategy swaps. Scheduler becomes transit hub coordinating all apps, solving jurisdiction confusion.

**Downsides:** Four separate processes increase deployment complexity. Requires shared state management (Redis for queues, job coordination). Monitoring must track four process health instead of one backend health.

**Confidence:** 80%

**Complexity:** High

**Status:** Explored

---

### 5. LLM Integration Gateway with Strategy Registry
**Description:** Extract all AI service logic (`ai_chat.py`, `ai_suggest.py`, `ai_report.py`, `ai_mcp.py`, `ai_time_machine.py`, `ai_internal.py`, `ai_spending_leaks.py` from backend + DeerFlow from agent) into `packages/llm/`. Provide: `LLMClient` ABC (chat, embed, analyze), provider registry (DeerFlow, OpenAI, Anthropic, local models), prompt templates (versioned, testable), response parsers. Backend `apps/backend_api/` and agent `apps/agent_api/` both import from llm package.

**Rationale:** Addresses split AI logic (7 backend AI routers + DeerFlow agent integration). Unified llm package enables provider swapping (DeerFlow → OpenAI without backend changes), prompt versioning (test prompts before deploy), and response validation. Centralizes fail-fast logic for provider failures. Makes LLM choice a config toggle, enabling cost optimization, fallback resilience, and compliance (EU families use EU-hosted models).

**Downsides:** Requires standardizing prompt/response formats across providers. DeerFlow integration may have unique features not captured in generic ABC. Backend team must learn LLM provider nuances previously handled by agent team.

**Confidence:** 75%

**Complexity:** Medium

**Status:** Unexplored

---

### 6. Storage Backend Abstraction with Health Registry
**Description:** Extract `services/storage/` (already has base.py, factory.py, config_crypto.py) into `packages/storage/`. Add: storage backend registry (dynamic registration for GitHub, WebDAV, local filesystem, future backends), health check protocol (ping backends periodically, detect dead WebDAV before sync attempts), storage metrics (bytes stored, sync success rates), and storage policy engine (auto-select backend by file size/type: large → S3, small → GitHub). Backend and worker both import from storage package.

**Rationale:** Addresses partial abstraction (backend-internal storage). Package-level storage enables multi-app usage (worker syncs files, backend handles uploads, agent stores artifacts), backend health monitoring (prevent sync failures from dead backends), and policy-driven routing. Once storage package exists, adding new backends (Backblaze B2, Azure Blob, IPFS) follows registration pattern.

**Downsides:** Health checks add latency to storage operations. Policy engine requires tuning (file size thresholds, type routing rules). Metrics collection must not slow storage ops. Storage package must handle offline scenarios gracefully.

**Confidence:** 70%

**Complexity:** Medium

**Status:** Unexplored

---

### 7. Agent as DeerFlow Runtime with Active Scheduler
**Description:** Rename `apps/agent_api/` to `apps/deerflow_runtime/`. Package structure: `packages/llm/` (model abstractions), `packages/deerflow/` (agent orchestration, tool calling, MCP protocol), `packages/contracts/` (backend integration). Backend becomes DeerFlow client via contracts. Agent scheduler wakes up as DeerFlow job scheduler for AI-specific async work (insight generation, model batch calls). Clarifies asymmetry: agent is DeerFlow framework instance, backend is API gateway that uses it.

**Rationale:** Addresses dormant agent scheduler (runtime identity unclear) and backend-agent asymmetry confusion. Elevates DeerFlow from "integration detail" to architectural participant. Agent scheduler activates meaningfully for DeerFlow-specific async work rather than duplicating backend's general scheduler. Backend-team understanding of agent improves: agent is DeerFlow runtime, not generic AI service.

**Downsides:** Rename may break existing documentation and deployment scripts. DeerFlow scheduler scope unclear (what AI-specific async work exists?). Backend-team must learn DeerFlow framework lifecycle. May over-specialize agent if DeerFlow is not long-term LLM orchestration choice.

**Confidence:** 65%

**Complexity:** Medium

**Status:** Unexplored

---

## Rejection Summary

| # | Idea | Reason Rejected |
|---|------|-----------------|
| 1 | Domain Event Pipeline | Not grounded in current architecture — speculative, no evidence backend emits events or agent subscribes |
| 2 | Temp File Lifecycle Package | Too narrow — solves temp leak but doesn't address architectural sprawl or integration risks |
| 3 | Cross-Service Observability Package | Useful but not architectural leverage — supports debugging but doesn't prevent core risks (API drift, domain sprawl) |
| 4 | API Gateway App Pattern | Not grounded in current frontend-backend flow — frontend calls backend directly, no gateway requirement evident |
| 5 | Domain-Network Architecture | Not actionable — abstract reframe without concrete migration path or implementation steps |
| 6 | API Dispatcher Pattern | Not grounded in current architecture — speculative dispatcher design, no evidence routing is core problem vs domain sprawl |
| 7 | Database-as-Integration-Service | Over-engineered for current scope — implicit database sharing works, explicit service contract adds complexity without clear benefit |
| 8 | Zero Router Backend | Not pragmatic — forces domain purity through unrealistic unified dispatch, ignores legitimate domain-specific routing needs |
| 9 | 400 Router Explosion | Diagnostic tool, not refactoring proposal — reveals hidden complexity but doesn't reduce it |
| 10 | Zero Tenant Families | Diagnostic, not proposal — forces evaluation but removing multi-tenancy contradicts project identity (family coordination) |
| 11 | Zero LLM Providers | Diagnostic, not proposal — evaluates LLM value but removing contradicts project scope (AI insights) |
| 12 | Organ System Isolation | Metaphor for domain packages — interesting reframing but not actionable implementation guidance |
| 13 | Metropolitan Zoning | Metaphor for apps separation — interesting reframing but not actionable implementation guidance |
| 14 | JIT Assembly Pipeline | Metaphor for worker/scheduler — interesting reframing but not actionable implementation guidance |
| 15 | Game Engine Plugin | Metaphor for apps/packages — interesting reframing but not actionable implementation guidance |
| 16 | Compiler Pass Pipeline | Metaphor for request flow — interesting reframing but not actionable implementation guidance |
| 17 | Container Terminal | Metaphor for coordination — interesting reframing but not actionable implementation guidance |
| 18 | File System Inode | Metaphor for layering — interesting reframing but not actionable implementation guidance |
| 19 | Immune System | Metaphor for layering — interesting reframing but not actionable implementation guidance |
| 20 | Observability Mesh + Contract Tests | Minor combination — observability supports contracts but doesn't synthesize architectural leverage |
| 21 | Storage + Worker Coordination | Minor combination — storage-worker sync is detail, not architectural synthesis |
| 22 | API Versioning Router | Premature optimization — current API stable at /api/v1/, no versioning pressure evident |
| 23 | Tenancy Enforcement Package | Subsumed by Tenant-Aware Hexagonal Domains — standalone tenancy package weaker than synthesis with hexagonal domains |
| 24 | Contracts Package | Subsumed by Contract-Driven Domain Network — standalone contracts weaker than synthesis with domain autonomy |
| 25 | Worker App Extraction | Subsumed by Runtime Decomposition with Worker Backbone — standalone worker weaker than synthesis with runtime clarity |
| 26 | Domain Package Extraction | Subsumed by domain isolation combos — standalone domain extraction weaker than synthesis with tenant injection or hexagonal structure |
| 27 | Tenant Context Automation | Subsumed by Tenant-Aware Hexagonal Domains — standalone tenant automation weaker than synthesis with hexagonal domains |
| 28 | Security Package Automation | Lower leverage than top 7 — addresses scattered auth checks but doesn't synthesize architectural layers |
| 29 | DB Session Automation Package | Lower leverage than top 7 — addresses session management but doesn't synthesize architectural layers |
| 30 | Runtime Decomposition | Subsumed by Runtime Decomposition with Worker Backbone — standalone runtime split weaker than synthesis with async backbone |
| 31 | 1000 Tenant Families | Forcing function, not proposal — reveals shared-nothing isolation need but not actionable refactoring step |
| 32 | 20 LLM Providers | Forcing function, not proposal — reveals abstraction layer need but not actionable refactoring step (LLM Integration Gateway already addresses) |
| 33 | Contract-First API Development | Duplicate of Contracts Package — subsumed by Contract-Driven Domain Network |
| 34 | Scheduler App Separation | Duplicate of Worker App Extraction — subsumed by Runtime Decomposition with Worker Backbone |
| 35 | Background Worker App Extraction | Duplicate of Worker App Extraction — subsumed by Runtime Decomposition with Worker Backbone |
| 36 | Observability Package Centralization | Duplicate of Cross-Service Observability Package — useful but not architectural leverage |
| 37 | Shared Contracts Package | Duplicate of Contracts Package — subsumed by Contract-Driven Domain Network |
| 38 | Unified Worker Process | Duplicate of Worker App Extraction — subsumed by Runtime Decomposition with Worker Backbone |
| 39 | Tenant-Aware Infrastructure | Duplicate of Tenant Context Automation — subsumed by Tenant-Aware Hexagonal Domains |
| 40 | Domain Bounded Contexts | Duplicate of Domain Package Extraction — subsumed by domain isolation combos |
| 41 | Contract-First API Boundaries | Duplicate of Contracts Package — subsumed by Contract-Driven Domain Network |

---

**Next step:** Brainstorming Runtime Decomposition with Worker Backbone (80% confidence, High complexity)