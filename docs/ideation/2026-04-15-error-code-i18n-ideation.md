---
date: 2026-04-15
topic: error-code-i18n-architecture
focus: 统一错误码/结果码管理、架构简洁、错误提示国际化
---

# Ideation: Unified Error Code, Result Code & i18n Architecture

## Codebase Context

**Project:** Numina — FastAPI + Vue 3 family asset management app (self-hosted, privacy-first)

**Current error handling state:**
- Backend: 14 routers with `raise HTTPException(status_code=..., detail="Chinese string")` scattered throughout. No centralized exception handler. No error code enum. Mixed use of `status.HTTP_404_NOT_FOUND` vs raw integers.
- Custom exception hierarchy exists only in storage layer (`StorageError`, `StorageRateLimitError`, `StorageAuthError` in `backend/app/services/storage/base.py`) but never reaches the HTTP layer — routers re-raise as `HTTPException` with Chinese strings.
- Frontend: Vue-i18n v9.14.4 already installed and configured (`frontend/src/i18n/index.ts`) with zh-CN and en-US locale files. BUT error messages bypass i18n entirely — axios interceptor hardcodes Chinese strings (`'用户名或密码错误'`, `'登录已过期，请重新登录'`, etc.).
- No standardized API response envelope. No correlation IDs. No structured error logging.
- Past incident: silent exception swallowing in agent module caused partial failures to be invisible to callers.

**Key leverage points:**
- Vue-i18n is already installed — zero setup cost to start using it for errors
- `StorageError` hierarchy already exists — bridging it to HTTP is a natural extension
- Batch endpoints already exist — per-item failure tracking is a natural enhancement

---

## Ranked Ideas

### 1. Unified Error Code System + Centralized Handler + i18n Bridge
**Description:** Three tightly coupled pieces that form the core architecture:
1. Define an `ErrorCode` enum in `backend/app/errors/codes.py` with metadata per code: HTTP status, severity, i18n key. Example: `ASSET_NOT_FOUND = ("ASSET_NOT_FOUND", 404, "user", "errors.asset.notFound")`.
2. Add a FastAPI global exception handler in `main.py` that catches all `HTTPException` and domain exceptions, wraps them in a standardized envelope: `{ error_code: string, message: string, details?: any }`. Routers raise by code, not by raw status + string.
3. Backend returns only the error code (no Chinese strings). Frontend axios interceptor calls `i18n.global.t(errorCodeToKey(code))` to resolve the localized message. Populate `errors.*` namespace in both `zh-CN.ts` and `en-US.ts`.

**Rationale:** This is the foundational change. Everything else builds on it. It eliminates the dual problem of scattered error strings and bypassed i18n in one coordinated move. The i18n infrastructure is already in place — this just connects the wires.

**Downsides:** Requires touching all 14 routers to replace raw `HTTPException` calls with code-based raises. Migration is mechanical but non-trivial. Must be done in one coordinated PR to avoid a mixed state.

**Confidence:** 95%
**Complexity:** Medium
**Status:** Unexplored

---

### 2. Exception Hierarchy Bridge: Storage Errors → HTTP Layer
**Description:** Extend the existing `StorageError` hierarchy (already in `backend/app/services/storage/base.py`) to cover all service-layer domain errors. Register a FastAPI exception handler that maps each exception class to an `ErrorCode`. Services throw domain exceptions; routers never catch them. Example: `StorageRateLimitError` → `ErrorCode.STORAGE_RATE_LIMITED` → 429. This is a natural extension of Idea #1's centralized handler.

**Rationale:** The storage exception hierarchy already exists — it just doesn't reach the HTTP layer. Bridging it removes the manual catch-and-re-raise pattern in routers, keeps services clean of HTTP concerns, and ensures `StorageRateLimitError.reset_at` (currently unused) can propagate to the response.

**Downsides:** Requires defining domain exception classes for non-storage layers (auth, assets, liabilities). Adds a new abstraction layer that developers must learn.

**Confidence:** 88%
**Complexity:** Medium
**Status:** Unexplored

---

### 3. Correlation IDs + Structured Error Logging
**Description:** Add a middleware that generates or extracts a `X-Request-ID` header on every request and attaches it to the request state. The centralized error handler (from Idea #1) includes the correlation ID in every error response: `{ error_code: "...", correlation_id: "abc-123" }`. All error logs emit structured JSON with `correlation_id`, `user_id`, `endpoint`, and `error_code` fields. Frontend shows the correlation ID in error toasts so users can report it.

**Rationale:** When a user reports "I got an error," there's currently no way to find the corresponding server log. Correlation IDs make debugging instant. Structured logging makes logs queryable. This is especially valuable for AI service failures and batch operation errors where the failure path is non-obvious.

**Downsides:** Requires a logging infrastructure change (structured JSON vs current text logs). Correlation ID in UI may confuse non-technical users — consider showing it only in a "copy error details" button rather than the main toast.

**Confidence:** 82%
**Complexity:** Low–Medium
**Status:** Unexplored

---

### 4. Validation Error Standardization with Field-Level Codes
**Description:** Override FastAPI's default 422 response to return field-level error codes instead of raw Pydantic messages. Shape: `{ error_code: "VALIDATION_ERROR", details: [{ field: "password", code: "TOO_SHORT", message_key: "validation.password.tooShort" }] }`. Frontend axios interceptor parses `details` array and can highlight specific form fields with localized messages. Replace the current fragile `data.detail.map((e) => e.msg).join('; ')` pattern.

**Rationale:** The current 422 handling in the axios interceptor (`frontend/src/api/index.ts` lines 122–125) is fragile — it joins raw Pydantic message strings. Field-level codes let the frontend show per-field errors in the user's language and enable programmatic handling (e.g., "email already exists → focus email field").

**Downsides:** Requires a custom Pydantic validation error handler. Field-level i18n keys add maintenance overhead. May be overkill for a family app with simple forms — evaluate against actual form complexity.

**Confidence:** 75%
**Complexity:** Medium
**Status:** Unexplored

---

### 5. Partial Failure Tracking for Batch Operations
**Description:** Enhance `BatchOperationResponse` (used by batch archive, category, tags, status, export endpoints in `backend/app/routers/assets.py`) to include per-item results: `{ succeeded: [id, ...], failed: [{ id, error_code, message_key }], partial: bool }`. Frontend shows which items failed and why, with a retry option for failed items.

**Rationale:** Batch operations currently return aggregate counts. If 10 assets are archived and 2 fail, the user doesn't know which 2 or why. This is a direct application of the silent-failure lesson from the agent module incident. Per-item tracking makes partial failures visible and actionable.

**Downsides:** Increases response payload size. Requires frontend changes to display per-item errors. Adds complexity to batch endpoint logic.

**Confidence:** 78%
**Complexity:** Medium
**Status:** Unexplored

---

### 6. Error Code Validation in CI
**Description:** Add a pre-commit hook or CI lint step that validates: (a) all `raise HTTPException` calls in routers have been replaced with code-based raises (post-migration), (b) all error codes in the enum have corresponding i18n keys in both `zh-CN.ts` and `en-US.ts`, (c) no hardcoded Chinese strings remain in the axios interceptor. Implemented as a small Python/shell script.

**Rationale:** Prevents regression after the migration in Idea #1. Without enforcement, developers will add new `HTTPException(detail="Chinese string")` calls over time, undoing the architecture. CI validation makes the pattern self-enforcing.

**Downsides:** Adds CI complexity. False positives possible if the lint rules are too strict. Must be implemented after Idea #1 is complete.

**Confidence:** 85%
**Complexity:** Low
**Status:** Unexplored

---

### 7. Eliminate Empty Catch Blocks in Frontend (Hygiene)
**Description:** Audit all Vue components for empty `catch {}` blocks and `catch` blocks that only call `console.log`. Replace with either: (a) explicit delegation to the axios interceptor (remove the try-catch entirely), or (b) a `useErrorHandler` composable that logs context and re-throws. This is a hygiene pass, not a feature.

**Rationale:** Empty catch blocks are silent failure points. If an API call fails and the catch block does nothing, the user sees a frozen UI with no feedback. The axios interceptor already handles errors centrally — empty catches just suppress it. This is a low-effort, high-reliability improvement.

**Downsides:** Requires auditing all components. Some catch blocks may be intentionally silent (e.g., optional background refreshes) — these need case-by-case judgment.

**Confidence:** 90%
**Complexity:** Low
**Status:** Unexplored

---

## Rejection Summary

| # | Idea | Reason Rejected |
|---|------|-----------------|
| 1 | Error Message i18n Bridge (separate from error codes) | Duplicate of Idea #1 — absorbed into the combined approach |
| 2 | Error Severity Levels as separate infrastructure | Covered by `severity` field in the error code enum metadata |
| 3 | Error Budget / Rate Limit Transparency | Too niche; `StorageRateLimitError.reset_at` exists but no evidence users are hitting limits |
| 4 | Error Code Generation from Docstrings | Fragile — docstrings drift; manual registry is more reliable |
| 5 | Automated Error Code Documentation Generator | Duplicate of registry; do manually first, automate if it scales |
| 6 | Frontend Error Boundary | Vue 3 doesn't have React-style error boundaries; low ROI for this app's complexity |
| 7 | Error Retry Strategy + Exponential Backoff | Not grounded — no evidence of transient failures being a user problem |
| 8 | Error Context Propagation (Breadcrumb Trail) | Absorbed into Idea #3 (correlation IDs + structured logging) |
| 9 | Error Code → i18n Key Mapping Layer (standalone) | Duplicate of Idea #1's i18n bridge component |
| 10 | Global Exception Handler (standalone) | Duplicate of Idea #1's centralized handler component |
| 11 | Standardized API Response Envelope (standalone) | Duplicate of Idea #1's envelope component |

---

## Session Log
- 2026-04-15: Initial ideation — ~24 raw candidates generated across 4 frames, 7 survivors after adversarial filtering and cross-cutting synthesis
