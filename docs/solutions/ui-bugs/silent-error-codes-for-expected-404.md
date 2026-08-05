---
date: 2026-08-05
module: frontend
problem_type: ui_bug
component: frontend_stimulus
severity: low
root_cause: logic_error
resolution_type: code_fix
symptoms:
  - "Spurious MANIFESTO_NOT_FOUND fail-toast on feedback list page load"
  - "Opening the feedback list page shows a red fail toast '家庭宣言尚未创建' even though the page correctly renders an empty state"
  - "The toast is confusing — the page works fine, but the error message suggests something broke"
tags:
  - axios-interceptor
  - silent-error-codes
  - expected-404
applies_when:
  - "Endpoint returns a known error code as part of normal operation (not a real failure)"
  - "Global axios interceptor shows toast for expected 404 responses"
---

# Spurious MANIFESTO_NOT_FOUND Toast on Feedback List

## Problem
The global axios interceptor shows a `showFailToast()` for any non-2xx response. `getFeedbackList()` returns a 404 `MANIFESTO_NOT_FOUND` when no manifesto exists yet, triggering an ugly error toast on a page that should handle this gracefully.

## Symptoms
- Opening the feedback list page shows a red fail toast "家庭宣言尚未创建" even though the page correctly renders an empty state
- The toast is confusing — the page works fine, but the error message suggests something broke

## Solution
Add `_silentErrorCodes` to the request config so the global interceptor skips the toast for expected error codes.

**Before** (`frontend/apps/main/src/api/manifesto.ts`):
```typescript
export function getFeedbackList() {
  return http.get<ManifestoFeedback[]>('/family/manifesto/feedback')
}
```

**After**:
```typescript
export function getFeedbackList() {
  return http.get<ManifestoFeedback[]>('/family/manifesto/feedback', {
    _silentErrorCodes: ['MANIFESTO_NOT_FOUND'],
  })
}
```

## Why This Works
The axios interceptor in `frontend/apps/main/src/api/index.ts` checks `config._silentErrorCodes` before showing the toast. When the error code is in the silent list, the interceptor passes the error through to the caller without showing a toast. The caller already handles the 404 gracefully by showing an empty state.

## Prevention
- **Use `_silentErrorCodes` for all expected error responses** — any endpoint that returns a known error code as part of normal operation (not a real failure) should declare it as silent.
- **Audit 404 responses** — "not found" responses for resources that may legitimately not exist yet (manifesto, feedback, settings) are common candidates for silent error codes.
