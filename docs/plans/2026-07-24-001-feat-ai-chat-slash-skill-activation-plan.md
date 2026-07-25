---
title: "feat: AI Chat Slash-Skill Activation"
date: 2026-07-24
type: feat
artifact_contract: ce-unified-plan/v1
artifact_readiness: implementation-ready
product_contract_source: ce-plan-bootstrap
execution: code
---

## Goal Capsule

Enable users to explicitly activate a skill in the `/ai/chat` path by typing `/skill-name` at the start of their message, so the agent runs that skill's SKILL.md prompt and tool policy for the turn instead of the default `chat`/`chat-search` auto-selection.

**Authority hierarchy:** DeerFlow-harness 2.1.0 already ships the complete mechanism (middleware, parser, skill storage, original-content key) and it is already mounted in numina's `DeerFlowClient` via `build_middlewares()`. This plan wires numina's integration layer to let it fire - it does not build a parallel system. Where numina's existing `set_active_skill` / `_apply_active_skill_tool_filter` conflicts with DeerFlow's `SkillToolPolicyMiddleware`, numina defers to DeerFlow for slash-activated runs.

**Stop conditions:**
- A user typing `/skill-name task` in `/ai/chat` activates the named skill (SKILL.md injected, tools restricted to its `allowed-tools`), when `skill-name` is an enabled skill for the user's tenant.
- A user typing a non-slash message gets the existing `chat`/`chat-search` behavior unchanged.
- A user typing `/unknown-skill` gets a graceful "skill not available" message, not a crash.
- Selectable skills are scoped to the tenant's enabled custom skills. Builtin skills are not slash-activatable (KTD6 + Q1 resolution): the 8 existing builtins are redundant (`chat`/`chat-search`), internal-only (`skill-creator`/`skill-installer`), or fixed-flow (`finance-coach`/`wish-advice`/`import-parse`/`asset-report`). The mechanism is forward-compatible - a future user-conversational builtin just needs its name added to the `available_skills` set.

## Product Contract

### Requirements

- R1. When a user sends a message starting with `/skill-name` in `/ai/chat`, the agent activates that skill for the turn - DeerFlow's `SkillActivationMiddleware` injects the full SKILL.md content as a hidden reminder, and `SkillToolPolicyMiddleware` restricts tools to the skill's declared `allowed-tools`.
- R2. Slash-activatable skills are limited to the user's tenant-enabled custom skills (`SkillRegistry.skill_type='custom'` AND `is_enabled=True`). Builtin skills are excluded from slash activation (KTD6: none of the 8 builtins are clean user-conversational slash targets; Q1 resolution: custom-only). The mechanism is forward-compatible - a future user-conversational builtin is added by including its name in the `available_skills` set. Slash-activating a disabled, unknown, or non-whitelisted skill produces a user-facing failure message from DeerFlow's `SkillActivationMiddleware` itself (it returns `AIMessage(content=failure_message)` directly at `skill_activation_middleware.py` `_prepare_model_request`): "Skill `/{name}` is not installed." / "Skill `/{name}` is installed but disabled. Enable it before using slash activation." / "Skill `/{name}` is not available for this agent." No numina-side error path is needed.
- R3. Non-slash messages retain the existing behavior: numina's `set_active_skill("chat" | "chat-search")` pre-selection and `_apply_active_skill_tool_filter` tool filtering remain active. DeerFlow's `SkillToolPolicyMiddleware` stays passive (allow-all) for these runs, as today.
- R4. The chat input box shows a slash-command autocomplete dropdown when the user types `/` at the start of the message, listing the tenant's enabled skills (name + description). Selecting a skill inserts `/skill-name ` into the input.
- R5. The feature reuses DeerFlow-harness's existing `SkillActivationMiddleware`, `SkillToolPolicyMiddleware`, `parse_slash_skill_reference`, `resolve_slash_skill`, `ORIGINAL_USER_CONTENT_KEY`, and `SkillStorage` / `UserScopedSkillStorage` - no reimplemented slash parser, no second tool-filter middleware, no parallel skill loader.

### Actors

- A. **Chat user** (adult family member) - types messages in `/ai/chat`, may prefix with `/skill-name` to activate a skill.
- A. **Backend** - serves the enabled-skills list to the agent and frontend via `SkillRegistry`.
- A. **Agent worker** - dispatches the chat run; detects slash, conditions `set_active_skill`, passes `available_skills` + `user_id` to the adapter.
- A. **DeerFlowClient** (reused, not modified at the source) - already mounts `SkillActivationMiddleware` + `SkillToolPolicyMiddleware` via `build_middlewares()`.

### Scope Boundaries

**In scope:**
- `/skill-name` slash activation in the `/ai/chat` (numina) path.
- Tenant-enabled custom-skill scoping (builtin skills excluded from slash - see KTD6/Q1).
- Frontend slash autocomplete in the chat InputBox.
- Reconciling numina's `set_active_skill` with DeerFlow's `SkillToolPolicyMiddleware`.

**Out of scope (this product's identity):**
- `@`-mention agent selection - DeerFlow has no `@` mechanism; agent selection is a construction-time `agent_name` parameter already used for fixed-flow apps. Not replicating because there is no DeerFlow original to reuse.
- TUI-style control commands (`/new`, `/goal`, `/model`, `/skills`, etc.) - these are DeerFlow TUI-specific and not applicable to numina's web chat.
- Changing the existing fixed-flow pipelines (asset-report, import-parse, finance-coach, wish-advice) - they already use `agent_name` correctly and are not user-slash-activatable.
- Removing or altering the R1 `app` metadata gate in `sse_gateway.py` - it stays as the top-level dispatch router.

### Deferred to Follow-Up Work

- Per-family skill enable/disable management UI (the `SkillRegistry.is_enabled` column exists; a management surface is separate work).
- Slash activation in the child app (`frontend/apps/child`) - adult-facing chat only for now.

## Planning Contract

### Key Technical Decisions

- KTD1. **Reuse DeerFlow's `ORIGINAL_USER_CONTENT_KEY` to bridge JSON wrapping.** Numina's `_build_prompt` wraps user text as JSON (`json.dumps({"family_id":..., "free_text": "..."})`), and `DeerFlowClient.stream()` wraps that string into `HumanMessage(content=json, additional_kwargs={"run_id": ...})`. DeerFlow's `SkillActivationMiddleware` reads `get_original_user_content_text()`, which checks `additional_kwargs["original_user_content"]` first, then falls back to the (JSON) content. Without the key, `parse_slash_skill_reference` (`^/`) fails on the JSON's leading `{`. The fix sets `ORIGINAL_USER_CONTENT_KEY` to the raw user text in the HumanMessage's `additional_kwargs`, so DeerFlow's middleware parses the slash natively. **Why:** this is DeerFlow's designed escape hatch for context-wrapping consumers; inventing a numina-side parser would duplicate `parse_slash_skill_reference`.

- KTD2. **Conditionally skip `set_active_skill` for slash runs.** Numina's `_apply_active_skill_tool_filter` (in `sync_tool_patch.py`) restricts tools to the `set_active_skill()`-selected skill's `allowed-tools`. It always fires because the worker always calls `set_active_skill("chat" | "chat-search")`. If it fired on a slash run, it would override DeerFlow's `SkillToolPolicyMiddleware` and restrict tools to `chat`'s allowed-tools, blocking the slash skill. The worker detects slash via DeerFlow's `parse_slash_skill_reference` and omits `set_active_skill` when present, so DeerFlow's `SkillToolPolicyMiddleware` owns tool filtering for that run. **Why:** reuses DeerFlow's parser for detection; keeps the existing pre-selection for the non-slash default; avoids removing the numina filter (which would make non-slash runs allow-all).

- KTD3. **Thread `available_skills` + `user_id` to the adapter.** `DeerFlowClient.__init__` already accepts `available_skills: set[str] | None` and `build_middlewares()` already accepts `user_id` for `UserScopedSkillStorage` custom-skill resolution. Numina's `create_family_adapter` / `get_family_adapter` do not currently pass these. The worker builds `available_skills` from the tenant's enabled skill names and passes it (plus `user_id`) through `create_family_adapter` -> `DeerFlowClient` -> `build_middlewares`. **Why:** DeerFlow's `SkillActivationMiddleware._resolve_activation` checks `reference.name not in self._available_skills` and rejects non-whitelisted skills; without passing the set, `None` means all scanned skills are available (too permissive for tenant scoping). `user_id` is required for `UserScopedSkillStorage` to find per-family custom skills.

- KTD4. **Agent fetches enabled skills via `BackendClient`.** The `SkillRegistry` table lives in the backend DB. The agent already calls `BackendClient.get_family_ai_config()` per run. Extend that response (or add a sibling method) to include the family's enabled `skill_id` list (`is_enabled=True`, all types). **Why:** avoids a new auth-scoped HTTP endpoint; reuses the existing tenant-isolated `BackendClient` fetch the worker already performs.

- KTD5. **Frontend reuses DeerFlow's slash regex, not a DeerFlow frontend package.** DeerFlow's slash parser (`frontend/src/core/skills/slash.ts`) is not shipped in the `deerflow-harness` pip package. The frontend replicates the regex `^/([a-z0-9]+(?:-[a-z0-9]+)*)` and the reserved-name set (`bootstrap`, `goal`, `help`, `memory`, `models`, `new`, `status`) for the autocomplete trigger, matching the Python `parse_slash_skill_reference` exactly. **Why:** the pip package is the reused harness boundary; the frontend parser is not in it, so replication at the regex contract level is the reuse path.

- KTD6. **Builtin skill categorization (verified against SKILL.md source).** The 8 builtin skills at `server/apps/agent/skills/builtin/public/` fall into three categories, determined by reading each SKILL.md's `description` and trigger design:
  - **User-conversational (2):** `chat`, `chat-search` - designed for interactive Q&A. BUT these are the DEFAULT auto-selected skills (`set_active_skill("chat" | "chat-search")`), so slash-activating them is redundant with the non-slash default.
  - **Internal-only (2):** `skill-creator`, `skill-installer` - SKILL.md explicitly says *"Internal-only skill - not exposed to user-facing agents."* Already gated by the `/skill-dispatch` internal whitelist (`gateway.py:39`).
  - **Fixed-flow only (4):** `finance-coach`, `wish-advice`, `import-parse`, `asset-report` - each SKILL.md says *"非用户直聊触发"* (not user direct-chat trigger); they expect a backend-synthesized trigger message with a JSON snapshot injected into message content, and output structured JSON (not conversational replies). User slash-activation would send free text where a JSON snapshot is expected.
  **Consequence:** the plan's original R2 ("builtin skills with `is_enabled=True`") would expose fixed-flow and internal-only skills as slash-activatable, producing broken output. **Q1 resolution (user decision, 2026-07-24): option 1 - custom-skills-only.** Slash activation is limited to tenant-enabled custom skills; all 8 builtin skills are excluded. The mechanism is forward-compatible (a future user-conversational builtin just needs its name in `available_skills`). All slash-activation examples in this plan use `/my-budget` (a custom-skill illustration). **Why:** this categorization is provable from the SKILL.md source files (deterministic); the custom-only scope is the user's product decision (Q1, resolved).

### High-Level Technical Design

Slash-activation flow (happy path):

```
User types "/my-budget 帮我分析负债" in InputBox
  ↓
Frontend: slash autocomplete shows enabled custom skills; on send, message goes to
POST /api/threads/{id}/runs/stream (unchanged wire path)
  ↓
Worker._run_numina_agent:
  1. Extract free_text from graph_input messages
  2. parse_slash_skill_reference(free_text) -> SlashSkillReference(name="my-budget", ...)
     - detected: skip set_active_skill (KTD2)
     - not detected: set_active_skill("chat"|"chat-search") as today
  3. Fetch enabled custom skills via BackendClient -> available_skills set (KTD4)
  4. create_family_adapter(..., available_skills=available_skills, user_id=user_id) (KTD3)
  ↓
Adapter._build_prompt: JSON-wraps context as today, BUT also preserves raw
free_text via ORIGINAL_USER_CONTENT_KEY on the HumanMessage (KTD1)
  ↓
DeerFlowClient.stream(message, ...) -> HumanMessage(content=json,
  additional_kwargs={"run_id":..., "original_user_content": "/my-budget 帮我分析负债"})
  ↓
SkillActivationMiddleware (already mounted):
  - get_original_user_content_text -> "/my-budget 帮我分析负债"
  - parse_slash_skill_reference -> name="my-budget"
  - resolve_slash_skill against SkillStorage (available_skills whitelist)
  - inject SKILL.md as <slash_skill_activation> hidden reminder
  ↓
SkillToolPolicyMiddleware (already mounted):
  - reads slash_source_owner_token -> slash-activated
  - restricts tools to my-budget's allowed-tools
  ↓
Agent runs with my-budget skill prompt + restricted tools
```

Non-slash flow (unchanged): worker sets `set_active_skill("chat"|"chat-search")`, `_apply_active_skill_tool_filter` restricts tools, DeerFlow's `SkillToolPolicyMiddleware` stays passive (no slash source).

### Assumptions

- DeerFlow's `InputSanitizationMiddleware` (first in the chain via `build_lead_runtime_middlewares`) does not strip or re-wrap `ORIGINAL_USER_CONTENT_KEY` when it sets it - it preserves an existing valid string value (verified in source: `input_sanitization_middleware.py:317-322`). Numina setting the key before `stream()` is safe.
- `get_effective_user_id()` resolves to `family_id` via `set_family_sandbox_context` -> `set_current_user(SimpleNamespace(id=family_id))` (sandbox_provider.py:96-99), already called in `run_agent` (worker.py:295). `_run_in_executor_with_context` (adapter.py:72-100) propagates it to the executor thread. Verified against source - no threading needed (see KTD6).
- Custom skills are already managed in `SkillRegistry` with `skill_type='custom'` per family (existing functionality). U4 does NOT seed builtin skills for slash activation (Q1 resolution: custom-only). The existing `list_skills_grouped` already returns only custom skills, which is the desired autocomplete source - no frontend endpoint change is needed.

### Resolved Questions (from 2026-07-24 doc review)

All three findings from the doc review are now resolved. Two required user product decisions (Q1, Q3); one was deterministic against DeerFlow source (Q2).

- **Q1. ✅ RESOLVED (user decision, 2026-07-24): option 1 - custom-skills-only.** Slash activation is limited to tenant-enabled custom skills; all 8 builtin skills are excluded (redundant, internal-only, or fixed-flow per KTD6). The user's original "包括启用的内置技能" was based on the assumption that builtin skills are user-conversational, which the review disproved. The mechanism is forward-compatible for future user-conversational builtins (just add the name to `available_skills`). R2, U4, U5, and all slash-activation examples updated to custom-only scope.

- **Q2. ✅ RESOLVED (deterministic, 2026-07-24): no extra invalidation needed - U3+U4 design + existing LRU cache handles it.** The concern ("a disabled skill remains slash-activatable until the old entry expires") is disproven by the design itself: U4 fetches `available_skills` fresh every run (`get_enabled_skills` in `_run_numina_agent`), and U3 includes `available_skills` in the cache key (`_adapter_cache` is an LRU `OrderedDict`, max 100, `family_adapter_cache.py:156-161`). When a skill is toggled, the next run constructs a new cache key (new `available_skills` set) -> a new `DeerFlowClient` with the correct whitelist -> the disabled skill is immediately rejected by `SkillActivationMiddleware`. The old cache entry (stale whitelist) is never reused (key mismatch) and is evicted by LRU when the cache fills. No TTL, version counter, or eviction endpoint is required for correctness. Optional future enhancement: the backend could call the agent's existing `invalidate_family_adapter_cache(family_id)` (`family_adapter_cache.py:859`) on skill toggle for immediate memory reclamation - not required for correctness.

- **Q3. ✅ RESOLVED (user decision, 2026-07-24): option 1 - standard slash-menu model.** Keyboard navigation: Arrow Up/Down cycles highlight (wraps at list ends), **Enter selects** the highlighted skill (inserts `/{skill_id} ` + closes dropdown, does NOT send the message), Escape closes the dropdown, Tab also selects, click-outside closes. When the dropdown is closed, Enter sends as today. Implementation: a `keydown` handler on the textarea that checks `dropdownOpen` before deciding select-vs-send. Matches the universal Discord/Slack/GitHub/VS Code slash-menu convention; preserves keyboard accessibility (consistent with N2 a11y work).

## Implementation Units

### U1. Set `ORIGINAL_USER_CONTENT_KEY` so DeerFlow parses slash through JSON wrapping

**Goal:** Make DeerFlow's `SkillActivationMiddleware` see the raw user text (e.g. `/my-budget task`) instead of the JSON-wrapped context, by setting `ORIGINAL_USER_CONTENT_KEY` in the HumanMessage's `additional_kwargs`.

**Requirements:** R1, R5.

**Dependencies:** None (foundational for U2's detection to matter).

**Files:**
- `server/apps/agent/services/deerflow_adapter/adapter.py` - `_build_prompt` or the `raw_stream_dispatch` / `typed_stream_dispatch` call site that passes the message to `self._client.stream()`.
- `server/apps/agent/services/deerflow_adapter/sync_tool_patch.py` - if a patch on `DeerFlowClient.stream()` (or the internal `HumanMessage` construction at `client.py:766`) is needed to merge the key into `additional_kwargs`.
- `server/apps/agent/tests/unit/test_adapter_original_content_key.py` - new test file.

**Approach:**
`DeerFlowClient.stream()` constructs `HumanMessage(content=message, additional_kwargs={"run_id": run_id})` (harness `client.py:766`). It does not accept caller-supplied `additional_kwargs`. Two viable paths, decide during implementation based on harness mutability:
- **Path A (preferred):** Patch `DeerFlowClient.stream()` in `sync_tool_patch.py` (consistent with existing patches) to accept an optional `original_user_content: str | None` kwarg and merge it into the HumanMessage's `additional_kwargs` under `ORIGINAL_USER_CONTENT_KEY`. Numina's adapter passes `context.free_text` (the raw user text) as this kwarg.
- **Path B (fallback):** Use a coroutine-scoped ContextVar (mirroring `active_skill_context.py`) set by the adapter before `stream()`, and a patch on the HumanMessage construction site that reads it.

Either path imports `ORIGINAL_USER_CONTENT_KEY` from `deerflow.utils.messages` (reuse, do not hardcode the string).

**Patterns to follow:** `server/apps/agent/services/deerflow_adapter/active_skill_context.py` (coroutine-scoped ContextVar + reset pattern); `sync_tool_patch.py`'s existing patch style (`_patched_*` wrappers with logging).

**Test scenarios:**
- Happy path: adapter calls `stream()` with `original_user_content="/my-budget task"`; the resulting HumanMessage's `additional_kwargs["original_user_content"]` equals `"/my-budget task"`.
- No original content: when `original_user_content` is None (e.g. continuation runs), `additional_kwargs` does not contain the key (or contains None) - DeerFlow falls back to content text, as today.
- Round-trip with `SkillActivationMiddleware`: a HumanMessage built with `original_user_content="/my-budget task"` and JSON content; `get_original_user_content_text(content, additional_kwargs)` returns `"/my-budget task"` (DeerFlow's own contract - verify with an import-level assertion, not a reimplementation).
- Edge: `original_user_content` containing multi-line text with leading whitespace is preserved verbatim (no trim).

**Verification:** `uv run pytest apps/agent/tests/unit/test_adapter_original_content_key.py -v` passes; `uv run ruff check apps/agent/services/deerflow_adapter/` clean.

### U2. Conditionally skip `set_active_skill` when user text starts with a slash

**Goal:** When the user's message starts with `/skill-name`, the worker does NOT call `set_active_skill`, so DeerFlow's `SkillToolPolicyMiddleware` (not numina's `_apply_active_skill_tool_filter`) owns tool filtering for that run. Non-slash messages keep the existing `chat`/`chat-search` pre-selection.

**Requirements:** R1, R3, R5.

**Dependencies:** U1 (the key must be set for DeerFlow to parse the slash; without U1, skipping `set_active_skill` alone does not activate the skill).

**Files:**
- `server/apps/agent/services/runtime/worker.py` - `_run_numina_agent`, around the `skill_id = "chat-search" if ... else "chat"` / `set_active_skill(skill_id)` site (approx line 2053-2059).
- `server/apps/agent/tests/unit/test_worker_slash_detection.py` - new test file.

**Approach:**
Before the `set_active_skill` call, parse `free_text` with DeerFlow's `parse_slash_skill_reference` (import from `deerflow.skills.slash`). If it returns a non-None reference, skip `set_active_skill` entirely (leave `active_skill_context` empty). If it returns None, proceed with the existing `set_active_skill("chat" | "chat-search")` logic.

The `free_text` is already extracted from `graph_input["messages"]` (worker builds `FamilyContext(family_id=..., free_text=user_message)` at approx line 1988/2053 region). Reuse the existing extraction helper; do not add a second parser.

Do NOT parse or resolve the skill name in the worker - that is DeerFlow's `SkillActivationMiddleware` job. The worker only decides "is this a slash message?" to gate `set_active_skill`.

**Patterns to follow:** DeerFlow's `parse_slash_skill_reference` / `RESERVED_SLASH_SKILL_NAMES` (import, do not replicate the regex).

**Test scenarios:**
- Slash detected: `free_text="/my-budget 帮我分析"` -> `parse_slash_skill_reference` returns `SlashSkillReference(name="my-budget", ...)` -> `set_active_skill` is NOT called -> `get_active_skill()` returns None.
- No slash: `free_text="你好"` -> `parse_slash_skill_reference` returns None -> `set_active_skill("chat")` called as today -> `get_active_skill()` returns `"chat"`.
- Reserved command: `free_text="/goal do something"` -> `parse_slash_skill_reference` returns None (reserved) -> existing `set_active_skill("chat")` fires (reserved commands are not skill activations).
- Slash with no text: `free_text="/my-budget"` (no trailing text) -> slash detected -> `set_active_skill` skipped; DeerFlow's middleware handles the empty `remaining_text` (its own behavior).
- Continuation run (goal continuation path): the hidden continuation message is not a slash message -> `set_active_skill` behaves per the existing continuation logic, unchanged.

**Verification:** `uv run pytest apps/agent/tests/unit/test_worker_slash_detection.py -v` passes; existing `test_sync_tool_patch.py` still passes (the filter logic itself is unchanged - only the caller's gating changes).

### U3. Thread `available_skills` through `create_family_adapter` (`user_id` already resolved)

**Goal:** Pass the tenant's enabled skill-name set from the worker through `create_family_adapter` -> `get_family_adapter` -> `DeerFlowClient` -> `build_middlewares`, so DeerFlow's `SkillActivationMiddleware` enforces the whitelist. `user_id` requires no threading - see KTD6.

**Requirements:** R2, R5.

**Dependencies:** U4 (backend must expose enabled skills for the worker to build the set).

**Files:**
- `server/apps/agent/services/deerflow_adapter/family_adapter_cache.py` - `get_family_adapter` and `create_family_adapter` signatures (add `available_skills: set[str] | None = None` param; already has `agent_name`).
- `server/apps/agent/services/runtime/worker.py` - `_run_numina_agent` call to `create_family_adapter` (approx line 2006).
- `server/apps/agent/tests/unit/test_family_adapter_cache.py` - new or existing test file.

**Approach:**
`get_family_adapter` already accepts `agent_name` and `middlewares` and includes them in the cache key (family_adapter_cache.py:735). Add `available_skills` to the same signature and cache key (as a frozenset or sorted tuple for hashability). Thread it to `DeerFlowClient.__init__(available_skills=...)`. `user_id` requires no threading: `run_agent` (worker.py:295) calls `set_family_sandbox_context(family_id, ...)` which calls `set_current_user(SimpleNamespace(id=family_id))` (sandbox_provider.py:96-99), so `get_effective_user_id()` returns `family_id` inside `DeerFlowClient.build_middlewares()`. `_run_in_executor_with_context` (adapter.py:72-100) propagates the ContextVar to the executor thread. `UserScopedSkillStorage` is thus family-scoped, matching `SkillRegistry`'s per-family design.

The cache key must include `available_skills` so a run with a different enabled-skill set does not reuse a cached client with a stale whitelist. Cache invalidation on skill toggle is handled by design (Q2 resolution): the worker fetches `available_skills` fresh every run (U4), so a toggled skill produces a new cache key -> a new client with the correct whitelist on the very next run. The stale entry is never reused (key mismatch) and is evicted by the existing LRU (`_adapter_cache` max 100, `family_adapter_cache.py:156`). No TTL or explicit eviction is needed for correctness. Optional future enhancement: call the existing `invalidate_family_adapter_cache(family_id)` (`family_adapter_cache.py:859`) on toggle for immediate memory reclamation.

**Patterns to follow:** existing `agent_name` / `middlewares_key` cache-key pattern in `family_adapter_cache.py:729-735`.

**Test scenarios:**
- Happy path: `create_family_adapter(family_id, ai_config, available_skills={"my-budget","savings-tip"})` -> the cached `DeerFlowClient._available_skills` equals `{"my-budget","savings-tip"}`.
- Cache separation: two calls with different `available_skills` sets produce distinct cached clients (cache key includes the set).
- None available_skills (backward compat): `available_skills=None` -> `DeerFlowClient._available_skills` is None (all skills available) - existing behavior preserved for fixed-flow apps that do not pass it.
- user_id resolution (verified, no threading): `run_agent` calls `set_family_sandbox_context` -> `set_current_user(SimpleNamespace(id=family_id))`; assert `get_effective_user_id()` returns `family_id` inside the executor thread (propagated via `_run_in_executor_with_context`).

**Verification:** `uv run pytest apps/agent/tests/unit/test_family_adapter_cache.py -v` passes; `uv run ruff check apps/agent/services/deerflow_adapter/family_adapter_cache.py` clean.

### U4. Backend: expose tenant-enabled custom skills to agent

**Goal:** The agent can fetch the family's enabled custom `skill_id` list via `BackendClient`, for building the `available_skills` whitelist. The existing `/ai/skills/grouped` endpoint already returns enabled custom skills - no frontend-facing change is needed (Q1 resolution: custom-only; builtin skills are excluded from slash activation per KTD6).

**Requirements:** R2.

**Dependencies:** None (backend change is independently testable).

**Files:**
- `server/apps/agent/services/backend_client.py` - add `get_enabled_skills(family_id) -> list[str]` (or extend `get_family_ai_config` response).
- `server/apps/backend/app/routers/ai_skills.py` - add an agent-facing endpoint (or extend the existing internal endpoint) returning enabled custom skill_ids. The existing `list_skills_grouped` (frontend-facing) is unchanged.
- `server/tests/backend/test_ai_skills_enabled.py` - new test file.

**Approach:**
Add a `BackendClient` method that queries the backend for the family's enabled custom skill_ids. The backend endpoint returns `SkillRegistry.skill_id` where `family_id=current` AND `skill_type='custom'` AND `is_enabled=True`. Reuse the existing `X-Agent-Token` auth pattern used by other internal endpoints. The agent worker calls this in `_run_numina_agent` alongside `get_family_ai_config`.

No builtin seeding is needed: builtin skills are excluded from slash activation (KTD6 + Q1). The fixed-flow builtin apps (finance-coach, wish-advice, import-parse, asset-report) continue to use the existing `agent_name` + `set_active_skill` path, unaffected by `available_skills` (they pass `available_skills=None`, and `SkillActivationMiddleware` is slash-only).

**Patterns to follow:** existing `list_skills_grouped` query pattern (filter by `family_id`, `skill_type`, `is_enabled`); `BackendClient` existing method style (`get_family_ai_config`).

**Test scenarios:**
- Happy path: a family with 2 enabled custom + 1 disabled custom -> `BackendClient.get_enabled_skills(family_id)` returns the 2 enabled custom skill_ids (disabled excluded).
- Empty family: a family with no custom `SkillRegistry` rows -> returns `[]` (no slash-activatable skills; slash autocomplete shows empty state).
- Builtin excluded: a family with builtin `SkillRegistry` rows (if any exist) -> `get_enabled_skills` returns only custom skill_ids (builtin filtered out by `skill_type='custom'`).
- Agent fetch reuse: the worker calls `get_enabled_skills` once per run alongside `get_family_ai_config` (no extra round-trip pattern change).

**Verification:** `uv run pytest server/tests/backend/test_ai_skills_enabled.py -v` passes; `uv run ruff check apps/agent/services/backend_client.py apps/backend/app/routers/ai_skills.py` clean.

### U5. Frontend: slash-command autocomplete in chat InputBox

**Goal:** When the user types `/` at the start of the chat input, show a dropdown of the tenant's enabled skills; selecting one inserts `/skill-name ` into the input. The message is sent as-is (no frontend-side skill resolution).

**Requirements:** R4, R5.

**Dependencies:** None hard - `/ai/skills/grouped` already returns enabled custom skills (existing behavior). U4 adds the agent-facing endpoint only and does not change the frontend endpoint.

**Files:**
- `frontend/apps/main/src/components/ai-chat/InputBox.vue` - add slash detection + dropdown rendering.
- `frontend/apps/main/src/composables/ai-chat/useSlashSkills.ts` - new composable: fetches enabled skills, exposes filtered list by typed prefix.
- `frontend/apps/main/src/utils/slashSkill.ts` - new util: the slash regex + reserved-name set, mirroring DeerFlow's `parse_slash_skill_reference`.
- `frontend/apps/main/src/i18n/locales/zh-CN.ts` and `en-US.ts` - i18n strings for the dropdown (skill list label, empty state, etc.).
- `frontend/apps/main/src/components/ai-chat/__tests__/useSlashSkills.spec.ts` - new test file.

**Approach:**
The InputBox watches its textarea value. When the value matches `^/([a-z0-9-]*)$` (partial typing, no space yet), it shows a dropdown filtered by the typed prefix. The dropdown lists skills from `GET /ai/v1/ai/skills/grouped` (reuse existing `ai.ts` API), using the `custom` list (the `builtin` list is empty and excluded from slash - KTD6/Q1). Selecting a skill sets the textarea to `/{skill_id} ` (with trailing space) and focuses it. When the user types a space after `/skill-name`, the dropdown closes - the message is sent verbatim and the backend handles activation.

The slash regex and reserved names (`bootstrap`, `goal`, `help`, `memory`, `models`, `new`, `status`) live in `slashSkill.ts` and mirror DeerFlow's `deerflow/skills/slash.py` `_SLASH_SKILL_RE` and `RESERVED_SLASH_SKILL_NAMES`. If a reserved command is typed, the dropdown does not show skill suggestions (it is a control command, not a skill).

**Keyboard navigation (standard slash-menu model, Q3 resolution):** Arrow Up/Down cycles the highlighted item (wraps around at list ends), **Enter selects** the highlighted skill (inserts `/{skill_id} ` + closes dropdown, does NOT send the message), Escape closes the dropdown, Tab also selects (consistent with autocomplete conventions), click-outside closes. When the dropdown is closed, Enter sends the message as today - the Enter-intercept only fires while the dropdown is open. This matches the universal Discord/Slack/GitHub/VS Code slash-menu convention and preserves keyboard accessibility (consistent with the N2 a11y work already in the repo). Implementation: a `keydown` handler on the textarea that checks `dropdownOpen` before deciding select-vs-send.

All user-visible strings (dropdown title, empty state, aria labels) go through `t('key')` in both locale files. No emoji in i18n text. Vant components for the dropdown (consistent with the rest of the app).

**Patterns to follow:** existing InputBox Vue structure; `useCurrency` / `useAiContext` composable pattern; Vant dropdown/popover patterns used elsewhere in the app.

**Test scenarios:**
- Happy path: user types `/m` -> dropdown shows enabled custom skills starting with `m` (e.g. `my-budget`).
- Select: user clicks `my-budget` -> textarea becomes `/my-budget ` (trailing space), dropdown closes, focus stays in textarea.
- No match: user types `/xyz` -> dropdown shows empty state ("无匹配技能").
- Reserved: user types `/goal` -> dropdown does not show skill suggestions (reserved command).
- Non-slash: user types `你好` -> no dropdown.
- Mid-message slash: user types `hello /f` -> no dropdown (slash not at start).
- Empty skill list: family has no enabled skills -> typing `/` shows empty state, not a crash.
- Loading state: while `/ai/skills/grouped` is in flight, dropdown shows a loading indicator (not the empty state).
- Error state: if `/ai/skills/grouped` fetch fails, dropdown shows an error message with a retry option (not a silent empty state).
- i18n: switching locale updates the dropdown labels.
- Keyboard - Arrow Down: user types `/` -> dropdown opens with all enabled skills; presses Arrow Down -> highlight moves to the second item (wraps to last if only one).
- Keyboard - Arrow Up: user types `/` -> presses Arrow Up -> highlight moves to the last item (wraps to first if only one).
- Keyboard - Enter selects (does NOT send): user types `/my` -> dropdown shows `my-budget` highlighted -> presses Enter -> textarea becomes `/my-budget ` (trailing space), dropdown closes, message is NOT sent (Enter intercepted while dropdown open).
- Keyboard - Escape closes: user types `/` -> dropdown opens -> presses Escape -> dropdown closes -> textarea retains `/` (or clears to empty, depending on UX preference - decide during implementation) -> next Enter sends normally.
- Keyboard - Tab selects: user types `/` -> presses Tab -> highlighted skill selected, same as Enter.
- Keyboard - wrap-around: user types `/` with 3 skills -> presses Arrow Down 3 times -> highlight returns to the first item.

**Verification:** `cd frontend/apps/main && pnpm typecheck` passes; `pnpm test:run -- useSlashSkills` passes; `pnpm lint` clean on touched files.

## Verification Contract

**Backend:**
- `cd server && uv run pytest apps/agent/tests/unit/ server/tests/backend/test_ai_skills_enabled.py -v` - all green.
- `cd server && uv run ruff check apps/agent/services/deerflow_adapter/ apps/agent/services/runtime/worker.py apps/backend/app/routers/ai_skills.py` - clean.
- `cd server && uv run mypy apps/agent/services/deerflow_adapter/` - no new errors.

**Frontend:**
- `cd frontend/apps/main && pnpm typecheck` - 0 errors.
- `cd frontend/apps/main && pnpm test:run` - no new failures.
- `cd frontend/apps/main && pnpm lint` - clean on touched files.

**Integration (manual, via bsk against dev server):**
- Login as demouser, open `/ai/chat`. Prerequisite: create or enable a custom skill (e.g. `my-budget`) for the family first (families with no custom skills see an empty autocomplete). Type `/my-budget ` -> autocomplete shows my-budget; send message -> agent activates my-budget skill (SKILL.md prompt visible in behavior, tool set restricted).
- Type a non-slash message -> existing chat behavior unchanged (MCP tools load, family data queries work).
- Type `/nonexistent-skill` -> graceful "skill not available" response, no crash.
- Type `/goal ...` -> no skill dropdown, no skill activation (reserved command).

## Definition of Done

- All five Implementation Units implemented, each with its test scenarios passing.
- `ORIGINAL_USER_CONTENT_KEY` is set on the HumanMessage for chat runs, verified by unit test.
- `set_active_skill` is skipped for slash messages, verified by unit test.
- `available_skills` + `user_id` reach `DeerFlowClient` and `build_middlewares`, verified by unit test.
- Backend exposes enabled custom skills to the agent; the existing `/ai/skills/grouped` serves the frontend (no frontend endpoint change), verified by backend tests.
- Frontend slash autocomplete renders and filters enabled skills, verified by vitest.
- No regressions: existing `test_sync_tool_patch.py`, `test_adapter_contextvar.py`, `test_finance_coach_skill.py` still pass.
- Manual bsk verification confirms slash activation works end-to-end for at least one custom skill and one non-slash message.
- No new dependencies added (DeerFlow-harness already provides all reused classes).
- i18n strings added to both `zh-CN.ts` and `en-US.ts`; no hard-coded Chinese in `.vue` files.
