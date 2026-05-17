# Task Breakdown: Async Agent Task Result Persistence

**Requirements Doc:** `docs/brainstorms/2026-05-17-async-agent-task-result-persistence-requirements.md`

## Phase 1: Backend Result Extraction Infrastructure

### Task 1.1: Create Result Parser Service
**File:** `server/apps/backend/app/services/ai_result_parser.py`

Create a service that:
- Extracts structured JSON from answer text using regex (looks for `<!-- STRUCTURED_DATA ... -->` delimiter)
- Falls back to lightweight LLM extraction when regex fails
- Returns `list[dict] | None` for each capability

**Key functions:**
```python
def parse_capability_result(capability: str, answer_text: str, family_id: int, db: Session) -> list[dict] | None
def _extract_structured_block(answer_text: str) -> str | None
async def _llm_fallback_extract(capability: str, answer_text: str, provider_config: dict) -> list[dict] | None
```

**Dependencies:**
- Uses existing AI provider configs (fetch cheapest model from family's config)
- Schema definitions per capability (see Phase 2)

**Verification:** Unit tests with mock answer texts containing valid/invalid structured blocks

---

### Task 1.2: Create Result Writer Service
**File:** `server/apps/backend/app/services/ai_result_writer.py`

Create a service that:
- Clears previous results for family+capability (replace strategy)
- Bulk inserts new structured records into appropriate DB table
- Each capability has its own writer function

**Key functions:**
```python
def write_alerts_results(family_id: int, results: list[dict], db: Session) -> int
def write_disposal_results(family_id: int, results: list[dict], db: Session) -> int
def write_spending_leak_results(family_id: int, results: list[dict], db: Session) -> int
def write_report_results(family_id: int, results: dict, db: Session) -> int
def write_allocation_drift_results(family_id: int, results: dict, db: Session) -> int
def write_liability_results(family_id: int, results: dict, db: Session) -> int
```

**Dependencies:** DB models from Phase 2

**Verification:** Integration tests that write to test DB, verify records exist

---

### Task 1.3: Modify `proxy_capability_events` Helper
**File:** `server/apps/backend/app/routers/_ai_events_helper.py`

After task completion line (~line 98), add:
```python
# Extract structured results from answer and persist to DB
from apps.backend.app.services.ai_result_parser import parse_capability_result
from apps.backend.app.services.ai_result_writer import write_capability_results

results = parse_capability_result(capability, answer, family_id, gen_db)
if results:
    write_capability_results(capability, family_id, results, gen_db)
```

**Verification:** End-to-end test: trigger stream → wait for completion → query DB → verify records

---

## Phase 2: DB Models for Missing Capabilities

### Task 2.1: Create AILiabilityResult Model
**File:** `server/apps/backend/app/models/ai_liability_result.py`

Schema (based on frontend page expectations):
```
id              BigInteger PK (snowflake)
family_id       BigInteger FK(families), indexed
has_liabilities Boolean
total_remaining Float
total_monthly_payment Float
liability_count Integer
narrative       Text (nullable)
recommended_strategy String(20)  -- avalanche/snowball/hybrid
strategy_json   JSON  -- full strategies array from agent
generated_at    DateTime
```

**Migration:** `alembic revision --autogenerate -m "add_ai_liability_result_table"`

**Verification:** `alembic upgrade head` succeeds, table exists in DB

---

### Task 2.2: Create AIAllocationDriftResult Model
**File:** `server/apps/backend/app/models/ai_allocation_drift_result.py`

Schema:
```
id              BigInteger PK (snowflake)
family_id       BigInteger FK(families), indexed
has_significant_drift Boolean
narrative       Text (nullable)
drifts_json     JSON  -- [{category, target_pct, current_pct, drift, exceeds_threshold}]
generated_at    DateTime
```

**Migration:** `alembic revision --autogenerate -m "add_ai_allocation_drift_result_table"`

**Verification:** `alembic upgrade head` succeeds, table exists in DB

---

### Task 2.3: Register New Models in `__init__.py`
**File:** `server/apps/backend/app/models/__init__.py`

Add imports for new models so Alembic can detect them.

---

## Phase 3: Update Backend Routers

### Task 3.1: Add GET Endpoints for Allocation Drift Results
**File:** `server/apps/backend/app/routers/ai_allocation.py`

Add endpoint:
```python
@router.get("/check/result")
def get_allocation_drift_result(current_user, db):
    # Return latest non-dismissed result from ai_allocation_drift_results table
```

Update existing `/check/events` to use the async task flow (it already does via `useAITask`).

---

### Task 3.2: Add GET Endpoint for Liability Results  
**File:** `server/apps/backend/app/routers/ai_liability.py`

Add endpoint:
```python
@router.get("/result")
def get_liability_result(current_user, db):
    # Return latest result from ai_liability_results table
```

---

### Task 3.3: Fix Snowflake Serialization in Spending Leaks GET
**File:** `server/apps/backend/app/routers/ai_spending_leaks.py`

Wrap response in `SnowflakeBase` schema (or manually serialize IDs as strings) to match frontend `id: string` expectation.

---

## Phase 4: Update Skill Prompts (Agent Side)

### Task 4.1: Update alerts Skill Prompt
**File:** `server/apps/agent/skills/custom/alerts/SKILL.md` (or create if not exists)

Add delimiter instruction:
```
在分析结束后，请按以下格式输出结构化数据：

<!-- STRUCTURED_DATA
[
  {"asset_name": "...", "alert_type": "aging", "severity": "high", "suggestion": "...", "remaining_life_days": 30, "daily_cost": 1.5}
]
-->
```

---

### Task 4.2: Update disposal Skill Prompt
**File:** `server/apps/agent/skills/custom/disposal/SKILL.md`

Add delimiter instruction with disposal schema fields.

---

### Task 4.3: Update report Skill Prompt
**File:** `server/apps/agent/skills/custom/report/SKILL.md`

Add delimiter instruction for report schema (nested JSON structure).

---

### Task 4.4: Update spending_leak Skill Prompt
**File:** `server/apps/agent/skills/custom/spending_leak/SKILL.md`

Add delimiter instruction with spending leak schema.

---

### Task 4.5: Update allocation Skill Prompt
**File:** `server/apps/agent/skills/custom/allocation/SKILL.md`

Add delimiter instruction for allocation drift schema.

---

### Task 4.6: Update liability Skill Prompt
**File:** `server/apps/agent/skills/custom/liability/SKILL.md`

Add delimiter instruction for liability advice schema.

---

## Phase 5: Frontend Adjustments

### Task 5.1: Update SpendingLeaksPage GET Call
**File:** `frontend/apps/main/src/api/aiSpendingLeaks.ts`

Fix `getSpendingLeaks()` to return `response.data` instead of raw axios response.

---

### Task 5.2: Update Frontend Types (Optional Cleanup)
**Files:** `frontend/apps/main/src/types/index.ts`

- Fix `LiabilityAdviceResponse` to match actual page usage
- Fix `AllocationDriftResponse` field names

**Note:** This is cleanup, not required for the fix. Frontend already accesses correct fields.

---

## Phase 6: End-to-End Verification

### Task 6.1: Test alerts Capability
1. Trigger `/ai/asset-alerts/refresh/events`
2. Wait for stream to complete
3. Call `GET /ai/asset-alerts` → verify non-empty list

### Task 6.2: Test disposal Capability
Same flow for disposal.

### Task 6.3: Test spending_leak Capability
Same flow for spending leaks.

### Task 6.4: Test report Capability
Same flow for report.

### Task 6.5: Test allocation Capability
Same flow for allocation drift.

### Task 6.6: Test liability Capability
Same flow for liability advice.

---

## Dependency Graph

```
Phase 2 (models) ──→ Phase 1.2 (writer)
         │
         └──→ Phase 3 (routers)

Phase 4 (prompts) ──→ Phase 1.3 (helper integration)

Phase 1 (parser/writer/helper) ──→ Phase 6 (e2e tests)

Phase 5 (frontend) ──→ Phase 6 (e2e tests)
```

---

## Estimated Scope

- **Backend:** ~4 new files (parser, writer, 2 models), ~3 modified files (helper, 2 routers)
- **Agent:** ~6 skill prompt updates (text edits, no code changes)
- **Frontend:** ~1-2 minor fixes
- **Migrations:** 2 new tables
- **Tests:** Unit tests for parser, integration tests for writer, e2e verification for all 6 capabilities

---

## Open Questions (Resolved in Requirements)

- **Result replacement strategy:** Clear previous results before writing new ones (confirmed)
- **Fallback on parse failure:** Graceful degradation — task completes, text preserved, no structured results (confirmed)
- **Frontend UX:** Console shows stream → completes → refreshes card list (confirmed)