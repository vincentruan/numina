---
date: 2026-05-31
module: backend/services/mcp
problem_type: architecture_pattern
tags: [mcp, security, tenant-isolation, confused-deputy, caller-binding]
---

# MCP Caller-Bound Principal

## Problem

`_get_owner_user(family_id, db)` in `mcp_session.py` silently selected the family owner as the service-layer principal for all MCP tool calls. Any family member (child, parent, member) initiating a chat would have their tools executed under the owner's identity — a confused-deputy vulnerability.

## Solution

Bind the real caller identity at SSE handshake time and freeze it in `MCPSession.__slots__`.

## Hard Invariants

1. `MCPSession.__slots__ = ("_family_id", "_caller_user_id", "_caller_role", "_server")` — all frozen at construction
2. `_get_owner_user` is deleted. `_get_caller_user(family_id, caller_user_id, db)` is the only entry point
3. Caller validation failure at SSE handshake → 403, never silent fallback to owner
4. `list_tools()` filters by `caller_role ∈ allowed_roles` from `mcp_tool_registry`
5. `call_tool()` re-checks role before execution (defense in depth)
6. `permission_denied` response has `retryable: false` — classified as permanent_auth error
7. Child role is rejected at handshake (fail-fast), never enters MCP
8. `mcp_session.py` and `mcp_tool_registry.py` must never import HTTP libraries (zero outbound)

## Recommended Patterns

- Tool metadata centralized in `mcp_tool_registry.py` with `@dataclass(frozen=True)`
- `validate_registry()` called at startup — missing `allowed_roles` = fail-fast
- Audit log: success=INFO, permission_denied=WARNING, service_error=ERROR; all include `caller_user_id` + `caller_role`
- SSE connection lifetime > request scope → use `with SessionLocal() as db:` per-call, not `Depends(get_db)`

## Anti-Patterns

- Silent fallback: caller not found → use owner (confused-deputy reborn)
- Reading `family_id` / `caller_user_id` / `role` from tool arguments (prompt injection vector)
- Caching DeerFlowClient with caller_user_id in cache key (cache thrashing, no benefit — caller only matters at backend MCPSession level)
- `permission_denied` as transient error (causes LLM retry loops)

## Test Guard

- `tests/backend/test_mcp_no_outbound_http.py` — static AST + dynamic httpx patch
- `tests/backend/unit/test_mcp_session_caller_binding.py` — 10 scenarios covering slots, cross-family, inactive, args-emit
- `tests/backend/unit/test_mcp_sse_caller_handshake.py` — 8 scenarios covering all rejection vectors + success paths
- `tests/backend/unit/test_mcp_audit_log.py` — log level and field completeness
- `tests/backend/test_mcp_tenant_isolation.py` — family isolation regression
