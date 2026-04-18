---
title: "fix: Enable E2E CI Gate"
type: fix
status: completed
date: 2026-04-18
---

# fix: Enable E2E CI Gate

## Overview

The Playwright E2E test suite (5 spec files, ~20 tests) is fully written and passes locally, but the `npx playwright test` command is commented out in CI. This means every PR merges without regression protection. The fix is to uncomment the test run and verify the existing specs pass reliably against the current seed data.

The family settings API gap identified earlier turned out to be already implemented — `GET /family/settings`, `GET /family/children/{child_id}/balance`, and coin rate fields on `Family` all exist with full test coverage. This plan focuses solely on the CI gate.

## Problem Frame

`.github/workflows/ci.yml` line 134-136 has `npx playwright test` commented out with the note "E2E tests require proper data seeding - skip in CI for now". The seed script (`tests/seed-accounts.sh`) already runs in CI and creates the three test accounts (`test_empty`, `test_rich`, `test_asset`) that all 5 spec files depend on. The blocker was data seeding — which is already solved.

## Requirements Trace

- R1. `npx playwright test` runs in CI and must pass for PRs to merge
- R2. All 5 existing spec files pass against the seeded test accounts
- R3. Playwright HTML report is uploaded as a CI artifact on every run (already configured)
- R4. Child-system routes (`/child/*`) are excluded from the current spec scope with a documented TODO

## Scope Boundaries

- Only the 5 existing spec files are in scope: `smoke`, `auth-guards`, `cross-family-isolation`, `empty-state`, `api-contract`
- No new spec files in this plan (child-system E2E coverage is a separate follow-up)
- No changes to seed data or fixture helpers unless a spec is broken
- No changes to Playwright config (workers=1, retries=0 are fine for now)

## Context & Research

### Relevant Code and Patterns

- `.github/workflows/ci.yml` — e2e job, lines 100-150; `npx playwright test` is commented at ~line 134
- `tests/seed-accounts.sh` — already runs in CI before the commented test step; creates `test_empty`, `test_rich`, `test_asset`
- `tests/lib/fixtures.ts` — `emptyFamily()`, `richFamily()`, `singleAsset()` — all use `loginAs()` helper
- `tests/lib/auth.ts` — `loginAs()` implementation
- `tests/playwright.config.ts` — baseURL `http://localhost`, workers 1, retries 0, testDir `./e2e`
- `tests/e2e/smoke.spec.ts` — 3 tests using `singleAsset()` fixture
- `tests/e2e/auth-guards.spec.ts` — route guard tests using `emptyFamily()`
- `tests/e2e/cross-family-isolation.spec.ts` — isolation tests using `richFamily()` + `emptyFamily()`
- `tests/e2e/empty-state.spec.ts` — 13-page empty-state gauntlet using `emptyFamily()`
- `tests/e2e/api-contract.spec.ts` — OpenAPI snapshot test; auto-creates snapshot on first run

### Institutional Learnings

- `docs/solutions/` — no directly relevant E2E CI solutions documented yet
- Prior CI fix: `ci: skip E2E tests in CI (pre-existing failures, needs data seeding fix)` (commit 21dd4e6) — the comment was added when the children system routes were added and some specs may have needed updating; commit 54f6864 (`fix(e2e): update regression test suite for children system routes`) suggests specs were already updated

## Key Technical Decisions

- **Uncomment only, don't restructure**: The CI job already has the right shape — services, health check, seed step, artifact upload. The single change is removing the `#` comment from the test run step. No job restructuring needed.
- **retries: 0 stays**: Adding retries would mask flaky tests. If a spec is genuinely flaky, fix it rather than retry it.
- **api-contract snapshot**: On first CI run, `api-contract.spec.ts` auto-creates the snapshot fixture. Subsequent runs compare against it. This is intentional — the first green run establishes the baseline.
- **Child routes excluded via existing route lists**: `auth-guards.spec.ts` uses `PROTECTED_ROUTES` and `GUEST_ROUTES` constants. If `/child/*` routes are already in those lists, the test will try to navigate there. Verify and exclude child routes from the guard test if they require PIN auth (child routes use a different auth flow).

## Open Questions

### Resolved During Planning

- **Is seed data sufficient?** Yes — `seed-accounts.sh` creates all three accounts the fixtures need. No `seed-e2e-data.sh` is required for the existing 5 specs.
- **Is the family settings API gap real?** No — `GET /family/settings`, `GET /family/children/{child_id}/balance`, coin rate fields, and `test_family_settings.py` all exist. Not a gap.
- **Why was the test commented out?** Commit 21dd4e6 added the skip when child system routes were introduced. Commit 54f6864 updated the specs for those routes. The skip was likely never re-evaluated after the spec fix.

### Deferred to Implementation

- **Are any of the 5 specs currently broken?** Run them locally first to confirm before enabling in CI. If broken, fix in the same PR.
- **Does `auth-guards.spec.ts` include `/child/*` routes?** Check `PROTECTED_ROUTES` / `GUEST_ROUTES` constants — child routes use PIN auth, not JWT, so standard `loginAs()` won't work for them. Exclude or skip child routes in the guard test if needed.

## Implementation Units

- [ ] **Unit 1: Verify specs pass locally**

**Goal:** Confirm all 5 specs pass against a running local stack before touching CI.

**Requirements:** R2

**Dependencies:** Local Docker stack running, `seed-accounts.sh` executed

**Files:**
- Read-only: `tests/e2e/*.spec.ts`
- Possibly modify: `tests/e2e/auth-guards.spec.ts` if child routes cause failures

**Approach:**
- Run `npx playwright test` from `tests/` against local stack
- If `auth-guards.spec.ts` fails on `/child/*` routes (PIN auth mismatch), add those routes to a skip list or `test.skip` block with a comment referencing the child PIN auth flow
- If `api-contract.spec.ts` fails due to missing snapshot, run once to generate it, commit the snapshot, then verify it passes on second run
- Fix any other failures before proceeding to Unit 2

**Patterns to follow:**
- `tests/e2e/cross-family-isolation.spec.ts` — pattern for skipping/excluding routes
- `tests/lib/fixtures.ts` — fixture pattern for any new test accounts needed

**Test scenarios:**
- Happy path: all 5 spec files exit 0 with no failed tests
- Edge case: `api-contract.spec.ts` on first run creates snapshot and passes; on second run compares and passes
- Error path: if a spec fails, the failure message identifies the exact assertion and page — fix the assertion or the underlying UI issue

**Verification:**
- `npx playwright test` exits 0 locally with all tests green
- HTML report shows 0 failures

---

- [ ] **Unit 2: Uncomment E2E test step in CI**

**Goal:** Enable the Playwright test run in `.github/workflows/ci.yml`.

**Requirements:** R1, R3

**Dependencies:** Unit 1 (all specs passing locally)

**Files:**
- Modify: `.github/workflows/ci.yml`

**Approach:**
- Remove the `#` comment from the `npx playwright test` step (lines ~134-136)
- Keep `if: always()` on the artifact upload step (already present) so the HTML report uploads even on failure
- Optionally add `continue-on-error: false` explicitly to make intent clear (it's the default)

**Test expectation: none** — this is a CI config change; verification is the CI run itself

**Verification:**
- Push to a branch, open a PR, CI e2e job runs and passes
- Playwright HTML report artifact appears in the Actions run

---

- [ ] **Unit 3: Document child-system E2E gap**

**Goal:** Leave a clear TODO so the child-system spec gap doesn't get forgotten.

**Requirements:** R4

**Dependencies:** Unit 2

**Files:**
- Modify: `docs/plans/2026-04-17-001-comprehensive-implementation-roadmap.md` — mark Regression Testing Phase 1 as complete, note Phase 2 (child-system specs) as next

**Approach:**
- Add a note under "Regression Testing Phase 1" that the CI gate is now enabled
- List the 4 missing spec files from Phase 2 as the next step: `chore-approval-flow.spec.ts`, `wish-fulfillment-flow.spec.ts`, `child-milestone-flow.spec.ts`, `child-navigation.spec.ts`
- Note that child-system specs require a new `childFamily()` fixture that handles PIN auth

**Test expectation: none** — documentation only

**Verification:**
- Roadmap doc updated with accurate status

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| `auth-guards.spec.ts` includes `/child/*` routes that require PIN auth | Check `PROTECTED_ROUTES` constant; skip child routes with `test.skip` and a comment |
| `api-contract.spec.ts` snapshot is stale after recent API changes | Delete stale snapshot, let CI regenerate it on first run, commit the new baseline |
| `empty-state.spec.ts` references a page or selector that no longer exists | Run locally first (Unit 1); fix selector before enabling CI |
| CI Docker stack takes >90s to become healthy | Health check already polls for 90s; if flaky, increase to 120s |

## Sources & References

- Related code: `.github/workflows/ci.yml` (e2e job)
- Related code: `tests/seed-accounts.sh`
- Related code: `tests/playwright.config.ts`
- Related commits: `21dd4e6` (skip added), `54f6864` (specs updated for child routes)
- Prior roadmap: `docs/plans/2026-04-17-001-comprehensive-implementation-roadmap.md` (Regression Testing Phase 1)
