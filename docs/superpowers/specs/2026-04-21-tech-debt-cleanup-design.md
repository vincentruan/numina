# Tech Debt Cleanup Design

**Date:** 2026-04-21
**Status:** Approved
**Approach:** Layered cleanup (3 independent PRs)

## Overview

Numina has accumulated tech debt across security, testing, and code quality layers. This design proposes a layered cleanup approach with 3 independent PRs, allowing incremental review and merge without blocking other development work.

---

## PR1: Security Layer

### 1.1 JTI Revocation Persistence

**Problem:**
- `backend/app/auth/deps.py` uses in-memory dicts (`_revoked_jtis`, `_user_revocation_times`)
- Server restart invalidates revocation state — revoked tokens become usable again

**Solution: SQLite table persistence**

New model `backend/app/models/revoked_token.py`:

```python
class RevokedToken(Base):
    __tablename__ = "revoked_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    jti: Mapped[str] = mapped_column(unique=True, index=True)  # Single token revocation
    user_id: Mapped[str] = mapped_column(index=True)  # User-level revocation
    revoked_at: Mapped[float] = mapped_column()  # Unix timestamp
    expires_at: Mapped[float] = mapped_column(index=True)  # Auto-expiry for cleanup

    __table_args__ = (
        Index("ix_revoked_tokens_user_expires", "user_id", "expires_at"),
    )
```

**Changes to `auth/deps.py`:**

| Function | Current | New |
|---|---|---|
| `revoke_jti()` | `_revoked_jtis[jti] = expiry` | Insert to `RevokedToken` table |
| `revoke_all_user_tokens()` | `_user_revocation_times[user_id] = now` | Insert to `RevokedToken` table |
| `is_token_revoked()` | Check in-memory dicts | Query database (user_id first, then jti) |

**Cleanup mechanism:**
- APScheduler task in lifespan: hourly cleanup of `expires_at < now()`
- Alternative: lazy cleanup on each query (preserve current behavior)

---

### 1.2 Type Guard Injection

**Problem:**
- `AssetForm.vue`: 10+ `as any` casts for dynamic field access
- `LiabilityForm.vue`: 5+ `as any` casts
- Type safety bypassed, potential runtime errors

**Solution: Partial + Runtime Guards**

Add to `frontend/src/types/index.ts`:

```typescript
// Guard functions
function isPhysicalAsset(data: Partial<Asset>): boolean {
  return data.asset_type === 'physical'
}

function isFinancialAsset(data: Partial<Asset>): boolean {
  return data.asset_type === 'financial'
}

// Safe field access
function getAssetField<T>(data: Partial<Asset>, field: string): T | undefined {
  return field in data ? (data as Record<string, unknown>)[field] as T : undefined
}
```

**Changes to forms:**
- Replace `(data as any)[key]` with `getAssetField(data, key)`
- Add runtime guards: `if (isPhysicalAsset(data)) { ... }`

**Not changing:**
- Complex discriminated union types (deferred)
- LiabilityForm handled similarly

---

## PR2: Testing Layer

### 2.1 Test Priority Order

| Batch | Modules | Risk Level |
|---|---|---|
| Batch 1 | Authentication (WebAuthn, child auth, JTI) | Highest - security boundary |
| Batch 2 | File storage (upload, WebDAV, validation) | High - data integrity |
| Batch 3 | AI functions (report, allocation, chat) | Medium - correctness |

---

### 2.2 Batch 1: Authentication Tests

| Test File | Coverage | Estimated Tests |
|---|---|---|
| `test_webauthn.py` | Passkey registration/login, credential exclusion | 8-10 |
| `test_child_auth.py` | PIN login, child token refresh, permission isolation | 6-8 |
| `test_jti_revocation.py` | JTI revocation, user-level revocation, persistence after restart | 5-6 |

**Key test scenarios:**

```python
# test_jti_revocation.py
def test_jti_revocation_persists_after_restart(db):
    """Revocation state persists across server restart"""
    # 1. Revoke JTI
    # 2. Simulate restart (clear memory, refresh db session)
    # 3. Verify JTI still revoked
```

---

### 2.3 Batch 2: File Storage Tests

| Test File | Coverage | Estimated Tests |
|---|---|---|
| `test_file_upload.py` | Upload, download, delete, size limits | 6-8 |
| `test_webdav_sync.py` | WebDAV connection, sync conflict handling | 4-6 |
| `test_file_validation.py` | MIME type validation, malicious file blocking | 4-5 |

---

### 2.4 Batch 3: AI Function Tests

| Test File | Coverage | Estimated Tests |
|---|---|---|
| `test_ai_report.py` | Report generation, scoring logic | 4-5 |
| `test_ai_allocation.py` | Asset allocation suggestions, target setting | 3-4 |
| `test_ai_chat.py` | Chat sessions, history records | 3-4 |

**Test strategy:**
- Mock external AI calls (avoid dependency on external services)
- Focus on logic correctness, not AI output quality

---

## PR3: Code Quality Layer

### 3.1 Selective File Splitting

| File | Current Lines | Split Strategy | Target Lines |
|---|---|---|---|
| `DashboardPage.vue` | 951 | Extract asset list + pagination to composables | ~400 |
| `auth.py` (router) | 530 | Extract child auth + WebAuthn to separate routers | ~250 |
| `AIHubPage.vue` | 768 | Extract AI feature cards + chat input components | ~300 |

---

### 3.2 DashboardPage.vue Split

**Extracted composables:**

```
frontend/src/composables/
├── useAssetListPagination.ts   # Asset list pagination (~100 lines)
├── useDashboardFilters.ts      # Sort/filter state management (~80 lines)
└── useDashboardCharts.ts       # TrendLineChart/AllocationPieChart control (~60 lines)
```

**Extracted components:**

```
frontend/src/components/dashboard/
├── AssetListSection.vue        # Asset list + van-list pagination (~150 lines)
└── QuickStatsPanel.vue         # Asset count/monthly new/daily cost (~80 lines)
```

**DashboardPage.vue retains:**
- NetWorthCard, StatusSummaryGrid, AlertCards references
- Page layout and component composition
- Overall state coordination

---

### 3.3 auth.py Router Split

**Current:** Single file with adult auth, child auth, WebAuthn, password change

**Split:**

```
backend/app/routers/
├── auth.py                     # Adult login/register/refresh/password (~250 lines)
├── child_auth.py               # Child PIN login/WebAuthn (~180 lines)
└── auth_settings.py            # Password change/settings update (~80 lines)
```

**Router registration change:**

```python
# main.py
app.include_router(auth.router, prefix="/api/v1")
app.include_router(child_auth.router, prefix="/api/v1")  # New
app.include_router(auth_settings.router, prefix="/api/v1")  # New
```

---

### 3.4 AIHubPage.vue Split

**Extracted components:**

```
frontend/src/components/ai/
├── AIFeatureCards.vue          # AI feature entry card grid (~200 lines)
├── AIChatInputFixed.vue        # Bottom fixed chat input area (~150 lines)
└── AIQuickActions.vue          # Quick action buttons (~80 lines)
```

**AIHubPage.vue retains:**
- Page layout, route navigation
- Feature entry component composition

---

### 3.5 Dead Code Cleanup

**Scan scope:**

| Module | Check Items |
|---|---|
| Backend | Unused imports, uncalled functions, obsolete schema fields |
| Frontend | Unreferenced components, unused composables, obsolete store properties |
| Docs | Outdated design docs, completed plan files |

**Cleanup strategy:**
- Static analysis tool scan
- Manual confirmation before deletion (avoid false positives)
- Preserve exports potentially used externally (API schemas)

---

## Files Changed Summary

### PR1 (Security Layer)

| File | Change |
|---|---|
| `backend/app/models/revoked_token.py` | New model |
| `backend/app/auth/deps.py` | Replace in-memory dicts with DB queries |
| `backend/app/main.py` | Add cleanup scheduler task |
| `frontend/src/types/index.ts` | Add guard functions |
| `frontend/src/components/asset/AssetForm.vue` | Replace `as any` with guards |
| `frontend/src/components/liability/LiabilityForm.vue` | Replace `as any` with guards |

### PR2 (Testing Layer)

| File | Change |
|---|---|
| `backend/tests/test_webauthn.py` | New test file |
| `backend/tests/test_child_auth.py` | New test file |
| `backend/tests/test_jti_revocation.py` | New test file |
| `backend/tests/test_file_upload.py` | New test file |
| `backend/tests/test_webdav_sync.py` | New test file |
| `backend/tests/test_file_validation.py` | New test file |
| `backend/tests/test_ai_report.py` | New test file |
| `backend/tests/test_ai_allocation.py` | New test file |
| `backend/tests/test_ai_chat.py` | New test file |

### PR3 (Code Quality Layer)

| File | Change |
|---|---|
| `frontend/src/composables/useAssetListPagination.ts` | New composable |
| `frontend/src/composables/useDashboardFilters.ts` | New composable |
| `frontend/src/composables/useDashboardCharts.ts` | New composable |
| `frontend/src/components/dashboard/AssetListSection.vue` | New component |
| `frontend/src/components/dashboard/QuickStatsPanel.vue` | New component |
| `frontend/src/pages/DashboardPage.vue` | Refactor to use extracted composables/components |
| `backend/app/routers/child_auth.py` | New router (extracted from auth.py) |
| `backend/app/routers/auth_settings.py` | New router (extracted from auth.py) |
| `backend/app/routers/auth.py` | Refactor to core adult auth only |
| `frontend/src/components/ai/AIFeatureCards.vue` | New component |
| `frontend/src/components/ai/AIChatInputFixed.vue` | New component |
| `frontend/src/components/ai/AIQuickActions.vue` | New component |
| `frontend/src/pages/AIHubPage.vue` | Refactor to use extracted components |

---

## Execution Timeline

| Phase | PR | Duration | Dependencies |
|---|---|---|---|
| Phase 1 | PR1: Security Layer | 2-3 days | None (can start immediately) |
| Phase 2 | PR2: Testing Layer | 3-4 days | PR1 merged (tests validate PR1) |
| Phase 3 | PR3: Code Quality | 2-3 days | PR2 merged (tests validate refactor) |

**Total estimated duration:** 7-10 days

---

## Success Criteria

### PR1
- JTI revocation persists after server restart (verified by test)
- No `as any` casts remaining in AssetForm.vue and LiabilityForm.vue
- All existing tests pass

### PR2
- Test coverage: WebAuthn, child auth, JTI revocation (Batch 1)
- Test coverage: File upload, WebDAV, validation (Batch 2)
- Test coverage: AI report, allocation, chat (Batch 3)
- All new tests pass

### PR3
- DashboardPage.vue < 450 lines
- auth.py < 280 lines
- AIHubPage.vue < 350 lines
- All tests pass after refactor