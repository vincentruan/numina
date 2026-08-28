---
title: LLM JSON Validate-Repair Abstraction - Plan
type: refactor
date: 2026-08-28
artifact_contract: ce-unified-plan/v1
artifact_readiness: implementation-ready
product_contract_source: ce-plan-bootstrap
execution: code
---

## Goal Capsule

- **Objective:** Extract the duplicated validate→repair loop (currently copy-pasted across asset-report and finance-coach) into a shared module, add wish-advice validation+repair (the 3rd caller), and establish the pattern as the standard for any future LLM→JSON→frontend AI feature.
- **Authority:** This plan.
- **Stop conditions:** All 3 callers use the shared loop; wish-advice has validate→repair; existing tests pass; new tests cover wish-advice validation and the generic loop.
- **Execution profile:** Standard refactor — move code, add wish-advice validator, replace 3 inline loops with one shared call.

## Product Contract

### Summary

The agent worker has an established validate→repair cycle for LLM JSON output: parse → validate against schema → retry via LLM repair (≤3 attempts, 120s budget) → emit result or error. This pattern currently exists in 2 callers (asset-report, finance-coach) with ~40 lines of near-identical loop code duplicated in each. wish-advice, the 3rd LLM→JSON feature, has no such cycle — malformed output is silently dropped by downstream validators.

This refactor consolidates the loop into a shared module, adds wish-advice to the pattern, and makes it trivial for future AI features to adopt validate→repair from day one.

### Requirements

**Abstraction**
- R1. The shared module exposes a generic `run_json_repair_loop` that accepts per-schema validators and repair functions as callables, eliminating the duplicated loop code.
- R2. The shared module exposes a generic `_llm_repair_json` helper for constructing per-schema repair prompts, reducing per-schema repair functions to ~10 lines each.

**wish-advice validation**
- R3. A `validate_wish_advice_json` function validates the wish-advice schema: `primary_wish_id` (string), `reason` (non-empty string), `suggested_monthly` (number ≥ 0), `redistribution[]` (array with `wish_id`, `suggested_amount ≥ 0`, `note`).
- R4. A `_repair_wish_advice_json_via_llm` function constructs a repair prompt with the wish-advice schema and delegates to the generic LLM repair helper.
- R5. The wish-advice runner uses the shared loop. On validation failure after retries, emits an error frame. On parse failure, emits an error frame (matching finance-coach behavior).

**Migration**
- R6. Asset-report and finance-coach runners are migrated to use the shared loop with no behavioral change.
- R7. Existing `validate_report_json`, `validate_coach_json`, `_repair_report_json_via_llm`, `_repair_coach_json_via_llm` are moved to the shared module. Re-exports from the old location maintain backward compatibility for any external imports.

### Scope Boundaries

**Deferred for later**
- `asset_suggest.py` and `health_report.py` also produce LLM JSON but use different error-handling strategies (defaults / raise). They can adopt the pattern later if needed.
- OpenAI/Anthropic structured output (`response_format: json_schema`) as an alternative to prompt-based JSON enforcement — a separate architectural decision.

**Out of scope**
- Frontend validation changes (WishAdviceCard, FinanceCoachCard) — they remain as defense-in-depth.
- SKILL.md prompt changes — the LLM prompts already specify the correct schemas.
- Dashboard-narrative and literacy-weekly-report — these produce plain text, not JSON.

---

## Planning Contract

### Key Technical Decisions

KTD1. **New module `llm_json_repair.py` in `services/runtime/`.** Validators and repair functions are colocated with the loop they serve. Named `llm_json_repair` (not `json_repair`) to avoid shadowing the `json_repair` pip package already imported in `asset_report_middleware.py`. `parse_report_json` stays in `asset_report_middleware.py` because it's also imported by the import-parse router and has a distinct responsibility (parsing, not validation).

KTD2. **Generic loop via callable parameters, not class hierarchy.** `run_json_repair_loop` accepts `validator`, `repair_fn`, `publish_retry_event`, and `app_name` as parameters. A class/protocol abstraction would be premature for 3 callers with simple interfaces. Callables are the lightest-weight parameterization that eliminates duplication.

KTD3. **Per-schema repair prompts stay as thin wrappers.** Each schema's repair prompt differs in the JSON schema example and field-specific rules. The generic `_llm_repair_json` helper handles LLM client creation, error formatting, and language preservation instructions. Per-schema functions (`_repair_report_json_via_llm`, etc.) only construct the schema-specific prompt string and delegate.

KTD4. **wish-advice error handling matches finance-coach.** On parse failure → error frame "心愿储蓄建议生成失败，请重试". On validation failure after retries → error frame "心愿储蓄建议格式异常，请重试". Previously wish-advice silently emitted whatever was parsed; now it fails loudly, matching the established pattern.

### Assumptions

- The `json_repair` library and `parse_report_json` are sufficient for parsing all three schemas (they are already used for coach which has a different schema than report).
- The 120s timeout and 3-retry budget are appropriate for wish-advice (same schema complexity as coach).

---

## Implementation Units

### U1. Create `llm_json_repair.py` shared module

**Goal:** Extract the generic repair loop, LLM repair helper, and all existing validators/repair functions into a single shared module.

**Requirements:** R1, R2, R6, R7

**Dependencies:** None

**Files:**
- Create: `server/apps/agent/services/runtime/llm_json_repair.py`
- Modify: `server/apps/agent/services/runtime/asset_report_middleware.py` (remove validators, keep parser)

**Approach:**
1. Create `llm_json_repair.py` with this structure:
   - Module docstring explaining the validate→repair pattern and its role as the standard for all LLM→JSON features
   - Imports: `json_repair` lib, `parse_report_json` from `.asset_report_middleware`, `asyncio`, `logging`
   - Constants: `_VALID_SEVERITIES`, `_VALID_TARGET_TYPES`, `_COACH_REQUIRED_FIELDS`, `_WISH_ADVICE_REQUIRED_FIELDS`
   - Validators: `validate_report_json`, `validate_coach_json`, `validate_wish_advice_json` (moved from middleware)
   - Generic helper: `_llm_repair_json(ai_text, validation_errors, repair_prompt, provider)` — handles LLM client creation, prompt assembly, parse, error handling
   - Per-schema repair functions: `_repair_report_json_via_llm`, `_repair_coach_json_via_llm`, `_repair_wish_advice_json_via_llm` — each builds its schema-specific prompt and delegates to `_llm_repair_json`
   - Generic loop: `run_json_repair_loop(parsed, ai_text, validator, repair_fn, publish_retry_event, *, app_name, max_retries=3, budget_seconds=120)` — the shared validate→repair loop
2. Remove `validate_report_json`, `validate_coach_json`, and their constants from `asset_report_middleware.py`
3. Keep `parse_report_json`, `normalize_report_json`, `normalize_indicator`, `normalize_indicator_data_items` in `asset_report_middleware.py`

**Patterns to follow:** Existing `validate_coach_json` and `_repair_coach_json_via_llm` patterns. The `_llm_repair_json` helper unifies the LLM client creation, error summary formatting, language preservation instruction, and exception handling that is currently duplicated between `_repair_report_json_via_llm` and `_repair_coach_json_via_llm`.

**Test scenarios:**
- `validate_wish_advice_json` with valid data → empty errors
- `validate_wish_advice_json` with missing `primary_wish_id` → error
- `validate_wish_advice_json` with negative `suggested_amount` → error
- `validate_wish_advice_json` with missing `wish_id` in redistribution item → error
- `validate_wish_advice_json` with non-dict input → error
- `validate_wish_advice_json` with empty redistribution → valid (edge case: no advice)
- `run_json_repair_loop` with valid input (no retries needed) → returns (parsed, 0)
- `run_json_repair_loop` with invalid input, repair succeeds on 1st retry → returns (repaired, 1)
- `run_json_repair_loop` with invalid input, all retries fail → returns (last_parsed, max_retries)
- `run_json_repair_loop` with no provider → returns (parsed, 0) immediately
- `run_json_repair_loop` timeout → returns (last_parsed, retry_count)

**Verification:** Unit tests pass for all validators and the generic loop.

---

### U2. Migrate `worker.py` imports and remove inlined duplicates

**Goal:** Update worker.py to import from the new `llm_json_repair.py` and remove the old inlined `_repair_report_json_via_llm` and `_repair_coach_json_via_llm`.

**Requirements:** R6, R7

**Dependencies:** U1

**Files:**
- Modify: `server/apps/agent/services/runtime/worker.py`

**Approach:**
1. Change import line 28 from:
   `from .asset_report_middleware import parse_report_json, validate_coach_json, validate_report_json`
   to:
   `from .llm_json_repair import parse_report_json, validate_coach_json, validate_report_json, validate_wish_advice_json, run_json_repair_loop, _repair_report_json_via_llm, _repair_coach_json_via_llm, _repair_wish_advice_json_via_llm`
   (`parse_report_json` re-exported from llm_json_repair for convenience, or imported separately from middleware — pick one; re-export is cleaner)
2. Remove `_repair_report_json_via_llm` function (lines ~494-565)
3. Remove `_repair_coach_json_via_llm` function (lines ~1103-1168)

**Test scenarios:**
- Test expectation: none — pure import/structural change, verified by existing tests passing

**Verification:** `uv run pytest tests/agent/ -v` passes.

---

### U3. Migrate asset-report runner to shared loop

**Goal:** Replace the inline validate→repair loop in `_run_asset_report_pipeline` with a call to `run_json_repair_loop`.

**Requirements:** R1, R6

**Dependencies:** U1, U2

**Files:**
- Modify: `server/apps/agent/services/runtime/worker.py` (lines ~686-749)

**Approach:**
1. Replace the inline loop (validation_errors init, while loop, timeout, retry events, timeout handling) with:
   ```python
   step2_payload, repair_count = await run_json_repair_loop(
       parsed=step2_payload,
       ai_text=ai_text,
       validator=validate_report_json,
       repair_fn=lambda t, e: _repair_report_json_via_llm(t, e, p.selected_provider),
       publish_retry_event=lambda attempt: bridge.publish(p.run_id, "custom", {
           "type": "report.repair_retry", "attempt": attempt, "max_attempts": 3
       }),
       app_name="_run_asset_report_pipeline",
   )
   ```
2. Keep the post-loop validation error check, logging, and result/error emission unchanged
3. Update `retry_count` references to `repair_count` in the logging after the loop

**Patterns to follow:** The existing loop at lines 686-749 — the replacement must preserve all logging, event emission, and error handling behavior.

**Test scenarios:**
- Existing asset-report integration tests continue to pass (behavior unchanged)
- Log messages use the same format (app_name prefix)

**Verification:** `uv run pytest tests/agent/ -v -k "asset_report or report"` passes.

---

### U4. Migrate finance-coach runner to shared loop

**Goal:** Replace the inline validate→repair loop in `_run_finance_coach_agent` with a call to `run_json_repair_loop`.

**Requirements:** R1, R6

**Dependencies:** U1, U2

**Files:**
- Modify: `server/apps/agent/services/runtime/worker.py` (lines ~1244-1310)

**Approach:**
1. Replace the inline loop with `run_json_repair_loop` call (same pattern as U3)
2. Keep post-loop error/result emission unchanged

**Test scenarios:**
- Existing finance-coach integration tests continue to pass

**Verification:** `uv run pytest tests/agent/ -v -k "coach"` passes.

---

### U5. Add wish-advice validate→repair

**Goal:** Add validate→repair to `_run_wish_advice_agent`, matching the finance-coach pattern.

**Requirements:** R3, R4, R5

**Dependencies:** U1, U2

**Files:**
- Modify: `server/apps/agent/services/runtime/worker.py` (lines ~1401-1416)

**Approach:**
1. After `parsed = parse_report_json(p.ai_text)`, replace the current "just emit" block with:
   - If `parsed is not None`: call `run_json_repair_loop` with `validate_wish_advice_json` and `_repair_wish_advice_json_via_llm`
   - After loop: if validation errors remain → emit error frame `"心愿储蓄建议格式异常，请重试"`
   - If valid → emit `wish_advice.result` with `repair_count` logged
   - If `parsed is None` → emit error frame `"心愿储蓄建议生成失败，请重试"` (matching coach parse-failure behavior)
2. Add logging for repair count and suggestion count on success

**Patterns to follow:** `_run_finance_coach_agent` post-loop error handling (lines 1292-1335).

**Test scenarios:**
- wish-advice with valid LLM output → `wish_advice.result` emitted, no repair needed
- wish-advice with invalid schema (e.g., missing `suggested_monthly`) → repair attempted, result emitted after repair
- wish-advice with parse failure → error frame emitted, no result
- wish-advice with validation failure after all retries → error frame emitted
- wish-advice with empty redistribution → valid, result emitted (edge case: no advice)

**Verification:** `uv run pytest tests/agent/ -v -k "wish"` passes.

---

### U6. Add/update tests

**Goal:** Add unit tests for `validate_wish_advice_json` and the generic loop; update existing test imports.

**Requirements:** R3, R5

**Dependencies:** U1

**Files:**
- Create: `server/tests/agent/unit/test_llm_json_repair.py`
- Modify: `server/tests/agent/unit/test_worker_wish_advice.py` (add validation source check)

**Approach:**
1. `test_llm_json_repair.py`:
   - Test `validate_wish_advice_json` with valid data, missing fields, invalid types, negative amounts, empty redistribution, non-dict input
   - Test `run_json_repair_loop` with mock validator/repair_fn: no-retry path, single-retry success, all-retries-fail, no-provider, timeout
   - Test `validate_report_json` and `validate_coach_json` still work after move (smoke test)
2. Update `test_worker_wish_advice.py` to verify `validate_wish_advice_json` is referenced in the worker source

**Test scenarios:**
- `validate_wish_advice_json({valid data})` → `[]`
- `validate_wish_advice_json({})` → errors for missing fields
- `validate_wish_advice_json({"primary_wish_id": "1", "reason": "r", "suggested_monthly": -1, "redistribution": []})` → error for negative suggested_monthly
- `validate_wish_advice_json({"primary_wish_id": "1", "reason": "r", "suggested_monthly": 100, "redistribution": [{"wish_id": "1", "suggested_amount": -5, "note": "n"}]})` → error for negative suggested_amount
- `validate_wish_advice_json("not a dict")` → error
- `run_json_repair_loop` with `validator=lambda d: []` → returns immediately with retry_count=0
- `run_json_repair_loop` with `validator=lambda d: ["err"]`, `repair_fn` returns fixed dict → returns fixed dict with retry_count=1

**Verification:** All new tests pass.

---

## Verification Contract

| Command | Scope | Expected |
|---------|-------|----------|
| `cd server && uv run pytest tests/agent/ -v` | All agent tests | All pass |
| `cd server && uv run ruff check apps/agent/services/runtime/llm_json_repair.py apps/agent/services/runtime/worker.py` | Lint new/changed files | No errors |
| `cd server && uv run ruff format --check apps/agent/services/runtime/llm_json_repair.py apps/agent/services/runtime/worker.py` | Format check | Already formatted |

---

## Definition of Done

1. `llm_json_repair.py` exists with `validate_report_json`, `validate_coach_json`, `validate_wish_advice_json`, `run_json_repair_loop`, and all three `_repair_*_via_llm` functions
2. `asset_report_middleware.py` contains only `parse_report_json` and normalization helpers (no validators)
3. `worker.py` imports from `llm_json_repair.py` — no inlined `_repair_*_via_llm` functions remain
4. All 3 runners (asset-report, finance-coach, wish-advice) use `run_json_repair_loop`
5. wish-advice emits error frames on parse/validation failure (not silent drop)
6. `test_llm_json_repair.py` has ≥10 test cases covering all validators and the generic loop
7. `uv run pytest tests/agent/ -v` passes
8. `uv run ruff check` passes on all changed files
9. Cleanup: no dead code, no experimental artifacts left in the diff
