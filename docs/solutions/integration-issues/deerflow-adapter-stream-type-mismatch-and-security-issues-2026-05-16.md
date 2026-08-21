---
title: "DeerFlow Adapter: stream_dispatch type mismatch and security issues (historical)"
date: "2026-05-16"
category: integration-issues
module: server/apps/agent
problem_type: integration_issue
component: assistant
severity: critical
root_cause: wrong_api
resolution_type: code_fix
tags:
  - stream-dispatch
  - family-id-validation
  - security
  - historical
---

# DeerFlow Adapter: Stream Type Mismatch and Security Issues (Historical)

> **Status: Mostly historical (2026-07).** This doc was written during the DeerFlow 2.0 alignment refactor. Four issues were identified; three have been superseded by later refactors. Only the `family_id` validation (Fix 2) remains current. The lessons about generator type contracts, HTTP header validation, and security hygiene are durable.

## Problem

The DeerFlow 2.0 adapter refactor changed `stream_dispatch()` to yield `StreamChunk` dataclass objects instead of plain strings, but did not update all callers. A concurrent security review found path traversal, timing oracle, and SSRF issues in the new Gateway proxy.

## Current Status of Fixes

| Fix | Status | Notes |
|-----|--------|-------|
| **Fix 1: StreamChunk→str contract** | Superseded | 6 raw-text streaming routers deleted in unified-dispatch refactor (U5/U7/U8). `StreamChunk` and `typed_stream_dispatch` survive on `DeerFlowAdapter`. |
| **Fix 2: `family_id` validation** | **CURRENT** | Centralized in `server/apps/agent/core/backend_client.py:_validate_family_id()` — regex `^[A-Za-z0-9_\-]{1,64}$`, called from `BackendClient.__init__` and every backend call. |
| **Fix 3: Constant-time token** | Superseded | `gateway.py` no longer has `_verify_token`; replaced by `Depends(verify_service_token)` with JWT-based auth from `packages/security/service_auth/agent_token_verify.py`. |
| **Fix 4: SSRF hostname allowlist** | **UNAPPLIED** | `DEERFLOW_GATEWAY_URL` in `server/apps/agent/app/config.py` still has no `model_post_init` hostname validation. Open TODO. |

## Durable Lessons

1. **Generator type contract:** Any refactor that changes a generator's yield type (`AsyncGenerator[X, None]`) must update all callers in the same commit. Search for all `async for chunk in <generator>` call sites before changing the yield type.

2. **HTTP header validation at router boundary:** Any value from an HTTP header used in a filesystem path must be validated with `re.compile(r"^[A-Za-z0-9_\-]{1,64}$")` at the router layer before entering any service. `pathlib` does NOT sanitize `..` components — `Path(base) / user_input` is not safe without validation.

3. **Constant-time comparison for secrets:** All secret/token/password comparisons must use `hmac.compare_digest`, never `==` or `!=`.

4. **URL hostname allowlists at startup:** All URLs configurable via env vars used for outbound HTTP must have hostname allowlists validated at startup (fail-fast). Path-segment validation on the suffix is not sufficient — the base URL must also be constrained.

## Related

- Current dispatch architecture: [`../architecture-patterns/two-ai-apps-unified-dispatch-stream-run.md`](../architecture-patterns/two-ai-apps-unified-dispatch-stream-run.md)
- Adapter decoupling: [`../architecture-patterns/deerflow-adapter-decoupling-stream-bridge-subclass.md`](../architecture-patterns/deerflow-adapter-decoupling-stream-bridge-subclass.md)
- Security patterns: [`../best-practices/security-protection.md`](../best-practices/security-protection.md)
