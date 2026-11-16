---
title: "Tool Promotion Middleware - Plan"
date: 2026-11-03
type: feat
topic: tool-promotion-middleware
artifact_contract: ce-unified-plan/v1
product_contract_source: ce-brainstorm
execution: code
---

# Tool Promotion Middleware — Plan

## Goal Capsule

- **Objective:** Reduce the LLM prompt size for families with many MCP servers by enabling DeerFlow's upstream deferred MCP tool pipeline, so only tool names (not full schemas) are bound to the model until the LLM discovers the tools it needs via `tool_search`.
- **Means:** Conditional activation — defer MCP tools only when the family's MCP server count meets or exceeds a configurable threshold (default: 3). Families below the threshold bind all tools normally, paying no discovery latency.
- **Execution profile:** Single PR. Pure config injection + threshold logic + unit tests. No custom Python middleware class — the upstream `DeferredToolFilterMiddleware` + `McpRoutingMiddleware` + `DeferredToolPromotionAuditMiddleware` chain is already in the default middleware assembly.
- **Stop conditions:** Threshold-based activation passes unit tests; no regression in existing agent dispatch tests when disabled.

## Product Contract

### Summary

Enable DeerFlow's upstream `tool_search` deferred tool pipeline for Numina families with ≥ N MCP servers (default 3). The LLM sees only compact tool names in `<available-deferred-tools>` and discovers full schemas on demand via the `tool_search` builtin tool. Families with fewer MCP servers bind all tools directly, avoiding the extra `tool_search` call latency.

### Problem Frame

Numina families can have 0–10+ MCP servers configured. Each MCP tool contributes its full JSON schema (name, description, parameters) to the LLM's `bind_tools` call. With 5+ MCP servers providing 15+ tools, the prompt grows significantly — consuming context window, increasing token cost, and potentially confusing the model with irrelevant tool schemas for simple queries that only need 1–2 tools.

DeerFlow harness v2.2.0 ships a complete deferred tool pipeline (`DeferredToolFilterMiddleware`, `McpRoutingMiddleware`, `tool_search` builtin) controlled by a single `tool_search.enabled` config flag. Numina needs to integrate this into its per-family config injection system with conditional activation.

### Key Decisions

- **KTD1. Use upstream `tool_search.enabled` config key directly.** No custom Numina middleware class needed. The upstream three-middleware chain (`DeferredToolFilterMiddleware` #28, `McpRoutingMiddleware` #26, `DeferredToolPromotionAuditMiddleware` #27) is already assembled in `build_middlewares`. Governs R1, R2.
- **KTD2. Threshold is on MCP server count, not tool count.** Server count is known at config generation time (`_generate_temp_config`); tool count requires loading MCP connections first. Default threshold: 3 servers. Governs R3.
- **KTD3. Per-family `ai_config` override takes precedence over threshold.** When a family explicitly sets `tool_search.enabled: true/false` in their AI config, that overrides the threshold-based decision. Governs R4.
- **KTD4. No change to skill `allowed-tools` filtering.** The `_apply_active_skill_tool_filter` in `sync_tool_patch.py` runs on the full tool list before deferral takes effect. Deferred MCP tools that pass the filter are hidden from the LLM until promoted. GuardrailMiddleware provides defense-in-depth at call time. Governs R5.

### Requirements

- R1. When `tool_search.enabled` is `true` in the generated per-family config, the DeerFlow harness defers all MCP tools (identified by `deerflow_mcp` metadata tag) and adds `tool_search` to the agent's tool list.
- R2. When `tool_search.enabled` is `false` (default), all tools bind normally — zero behavior change from current state.
- R3. The threshold logic counts `len(mcp_servers)` during `_generate_temp_config()`. When `mcp_server_count >= tool_search.mcp_server_threshold` (default: 3), `tool_search.enabled` is set to `true`. When below, `false`.
- R4. Per-family `ai_config` can explicitly set `tool_search.enabled: true` or `tool_search.enabled: false` to override the threshold-based decision. Explicit override always wins.
- R5. The existing `_apply_active_skill_tool_filter` in `sync_tool_patch.py` continues to filter tools by skill `allowed-tools` before the upstream deferred pipeline takes effect. No interaction between skill filtering and deferral causes tool access errors.
- R6. The `tool_search` config block in `base/config.yaml` defaults to `enabled: false` with `mcp_server_threshold: 3`.

### How This Work Fits Together

This plan covers T24 (Tool Promotion Middleware) from issue #176. It is one of six P3 future enhancement tasks (T22–T27).

- T24 (this plan): Deferred MCP tool pipeline — config injection + threshold
- T25 (Task Continuity): Depends on nothing in T24; can proceed independently
- T26 (Thread Branching): Can proceed independently
- T27 (Evidence Seal): Can proceed independently
- T22 (Container Sandbox): Can proceed independently
- T23 (Scheduled Tasks): Can proceed independently

T15 (SubagentLimitMiddleware) and T17 (ToolProgressMiddleware) were completed in prior commits on this branch and follow the same `_inject_*` pattern in `family_adapter_cache.py`.

### Scope Boundaries

**In scope:**
- Base config YAML entry (`tool_search` block)
- `_inject_tool_search()` in `family_adapter_cache.py`
- Threshold logic in `_generate_temp_config()`
- Unit tests

**Deferred for later:**
- MCP routing metadata for Numina tools (`deerflow_mcp_routing` with keywords/priority) — the upstream `McpRoutingMiddleware` supports auto-promotion from routing hints, but Numina's MCP tools don't declare routing metadata yet. Can be added per-tool without code changes.
- Frontend rendering of `tool_search` events — already handled by existing ChainOfThought.vue tool call display.
- Changes to DeerFlow upstream harness.

### Acceptance Examples

- AE1. Family with 1 MCP server
  - **Given:** A family has `mcp_servers: [{name: "backend", ...}]` (1 server)
  - **When:** `_generate_temp_config()` runs
  - **Then:** `tool_search.enabled` is `false`; all MCP tools bind normally; no `tool_search` tool added
  - **Covers R3, R6**

- AE2. Family with 3 MCP servers (threshold boundary)
  - **Given:** A family has 3 MCP servers configured
  - **When:** `_generate_temp_config()` runs with default threshold (3)
  - **Then:** `tool_search.enabled` is `true`; MCP tools are deferred; `tool_search` tool is added; system prompt includes `<available-deferred-tools>`
  - **Covers R1, R3**

- AE3. Per-family override disables deferred despite threshold
  - **Given:** A family has 5 MCP servers but `ai_config.tool_search.enabled: false`
  - **When:** `_generate_temp_config()` runs
  - **Then:** `tool_search.enabled` is `false`; override wins over threshold
  - **Covers R4**

- AE4. Skill allowed-tools with deferred tools
  - **Given:** `tool_search.enabled: true`, active skill declares `allowed-tools: [get_assets, get_liabilities]`
  - **When:** `get_available_tools` runs
  - **Then:** `_apply_active_skill_tool_filter` narrows to the 2 allowed MCP tools; upstream deferral hides their schemas; LLM sees names in `<available-deferred-tools>`; LLM calls `tool_search("select:get_assets")` to promote
  - **Covers R5**

---

## Planning Contract

### Key Technical Decisions

KTD1. **`_inject_tool_search` reads `mcp_servers` from the config dict, not from a separate parameter.** `_inject_mcp` runs before `_inject_tool_search` in `_generate_temp_config()` (line 737 → new line ~744), so `config["mcp_servers"]` is already populated when the threshold check runs. This avoids adding a new parameter to the function signature.

KTD2. **Threshold comparison uses `>=` (not `>`).** When `mcp_server_threshold: 3` and a family has exactly 3 servers, deferred is activated. This matches the Acceptance Example AE2 (3 servers → enabled).

KTD3. **Override precedence: explicit `ai_config` > threshold > base config default.** The function first checks `ai_config["tool_search"]["enabled"]` for an explicit boolean. If present, that wins unconditionally. If absent, the threshold logic decides. The base config's `tool_search.enabled: false` serves as the fallback when both are absent (which it always is, since `_inject_tool_search` always writes the resolved value).

KTD4. **No new `AgentSettings` env var for the threshold.** The threshold lives in the YAML config (`tool_search.mcp_server_threshold`), not in env vars. It's an operational tuning parameter, not a deployment constant. Changing it requires editing `base/config.yaml` or overriding per-family via `ai_config`.

### Assumptions

- The DeerFlow harness reads `tool_search.enabled` from the per-family config.yaml. The upstream `build_deferred_tool_setup(candidate_tools, enabled=...)` is called during agent assembly with this value. Verified in upstream `tool_search.py:278-299`.
- The upstream `assemble_deferred_tools()` handles the case where `enabled=True` but no MCP tools exist (returns empty setup, no `tool_search` tool added). No Numina-side guard needed.
- `_apply_active_skill_tool_filter` in `sync_tool_patch.py` runs inside `get_available_tools`, which is called BEFORE the upstream deferred tool assembly. The filter narrows the candidate list; deferral then hides the filtered MCP tools from the model. This ordering is correct (KTD4 in Product Contract).

---

## Implementation Units

### U1. Base config YAML entry

- **Goal:** Add the `tool_search` config block to `base/config.yaml` with safe defaults.
- **Requirements:** R6
- **Files:**
  - `server/apps/agent/deerflow_config/base/config.yaml` (modify)
- **Approach:**
  1. Add after the `tool_progress` block (line ~120):
     ```yaml
     # 延迟 MCP 工具 schema 提升（T24 — 条件启用 tool_search）
     # 当 MCP server 数量 >= mcp_server_threshold 时自动启用，
     # 或按家庭 ai_config.tool_search.enabled 显式覆盖。
     tool_search:
       enabled: false
       mcp_server_threshold: 3
     ```
  2. Default `enabled: false` ensures zero behavior change until threshold or override activates it.
- **Verification:** `cat server/apps/agent/deerflow_config/base/config.yaml | grep -A3 tool_search`

### U2. `_inject_tool_search()` function

- **Goal:** Implement the conditional injection function following the `_inject_*` pattern from T15/T17.
- **Requirements:** R3, R4
- **Dependencies:** U1
- **Files:**
  - `server/apps/agent/services/deerflow_adapter/family_adapter_cache.py` (modify)
- **Approach:**
  1. Add `_inject_tool_search(config, ai_config)` function after `_inject_tool_progress` (after line 308).
  2. Logic:
     ```python
     def _inject_tool_search(config, ai_config):
         # 1. Read base config defaults (already loaded from config.yaml)
         ts_config = config.get("tool_search", {})
         threshold = ts_config.get("mcp_server_threshold", 3)

         # 2. Check per-family explicit override
         ai_ts = ai_config.get("tool_search", {})
         explicit_enabled = ai_ts.get("enabled")  # None | True | False

         if explicit_enabled is not None:
             # Explicit override wins
             enabled = bool(explicit_enabled)
         else:
             # Threshold-based decision
             mcp_count = len(config.get("mcp_servers") or [])
             enabled = mcp_count >= threshold

         # 3. Write resolved value
         config.setdefault("tool_search", {})
         config["tool_search"]["enabled"] = enabled
         config["tool_search"]["mcp_server_threshold"] = threshold
     ```
  3. Called from `_generate_temp_config()` after `_inject_tool_progress` (line 743).
- **Patterns to follow:** `_inject_subagent_limit()` and `_inject_tool_progress()` — same function signature `(config, ai_config)`, same logging pattern.
- **Key difference from T15/T17:** Those functions read `ai_config` only and return early if disabled. This function always writes the resolved value (threshold or override) because the decision depends on runtime state (MCP server count).
- **Verification:** Unit tests in U3.

### U3. Unit tests

- **Goal:** Verify threshold logic, override precedence, and edge cases.
- **Requirements:** R1–R6
- **Dependencies:** U1, U2
- **Files:**
  - `server/tests/agent/unit/test_tool_search_injection.py` (create)
- **Test scenarios:**
  1. **Below threshold (1 server):** `mcp_servers=[{1}]`, no ai_config override → `tool_search.enabled` is `false` (AE1)
  2. **At threshold (3 servers):** `mcp_servers=[{3}]`, no ai_config override → `tool_search.enabled` is `true` (AE2)
  3. **Above threshold (5 servers):** `mcp_servers=[{5}]`, no ai_config override → `tool_search.enabled` is `true`
  4. **Zero servers:** `mcp_servers=None` or `[]` → `tool_search.enabled` is `false`
  5. **Explicit override True (below threshold):** 1 server + `ai_config.tool_search.enabled: true` → `true` (override wins)
  6. **Explicit override False (above threshold):** 5 servers + `ai_config.tool_search.enabled: false` → `false` (AE3)
  7. **Custom threshold:** base config has `mcp_server_threshold: 5`, 3 servers → `false`; 5 servers → `true`
  8. **Per-family threshold override:** `ai_config.tool_search.mcp_server_threshold: 2`, 2 servers → `true`
- **Verification:** `cd server && uv run pytest tests/agent/unit/test_tool_search_injection.py -v`

---

## Verification Contract

| Check | Command | Scope |
|-------|---------|-------|
| Unit tests | `cd server && uv run pytest tests/agent/unit/test_tool_search_injection.py -v` | U3 |
| Regression | `cd server && uv run pytest tests/agent/unit/ -v --timeout=60` | Full agent unit suite |
| Lint | `cd server && uv run ruff check apps/agent/services/deerflow_adapter/family_adapter_cache.py` | Changed files |

## Definition of Done

- All three implementation units pass their verification commands
- `tool_search` defaults to `enabled: false` — zero behavior change for existing deployments
- Threshold logic is correct at boundary (3 servers with threshold 3 → enabled)
- Per-family `ai_config` override takes precedence over threshold
- `_inject_tool_search` follows the established `_inject_*` pattern in `family_adapter_cache.py`
- No code added to `custom_middlewares` config key (Product Contract KTD1)

---

## Sources

- Upstream `DeferredToolFilterMiddleware`: `server/.venv/lib/python3.13/site-packages/deerflow/agents/middlewares/deferred_tool_filter_middleware.py`
- Upstream `DeferredToolSetup` + `build_deferred_tool_setup`: `server/.venv/lib/python3.13/site-packages/deerflow/tools/builtins/tool_search.py`
- Upstream `tool_search` builtin: same file, `build_tool_search_tool()`
- Upstream middleware chain order: `server/.venv/lib/python3.13/site-packages/deerflow/agents/middlewares/AGENTS.md` (positions #26–#28)
- Existing Numina config injection pattern: `server/apps/agent/services/deerflow_adapter/family_adapter_cache.py` (`_inject_token_budget`, `_inject_pii_redaction`, `_inject_guardrail`)
- Existing tool filter: `server/apps/agent/services/deerflow_adapter/sync_tool_patch.py` (`_apply_active_skill_tool_filter`)
- Issue: [vincentruan/numina#176](https://github.com/vincentruan/numina/issues/176) — T24
