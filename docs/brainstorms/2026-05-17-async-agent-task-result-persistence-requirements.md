# Async Agent Task Result Persistence

**Date:** 2026-05-17
**Status:** Draft
**Scope:** Standard

## Problem Statement

Six async AI capabilities (alerts, disposal, report, spending_leak, allocation, liability) share the same broken flow:

1. User clicks "scan/refresh" → backend creates AITask + streams NDJSON from agent
2. Agent produces **text-only output** (LLM natural language analysis) via DeerFlow
3. `proxy_capability_events` marks task as `completed` when stream ends
4. Frontend `onComplete` callback calls GET endpoint to fetch structured data
5. **GET returns empty list** because no one ever parsed the LLM output into structured DB records

The user sees the task "succeed" (stream completes, console closes) but the result cards are empty. The system conflates "task submission acknowledged" and "stream completed" with "structured results available."

## Solution: Mixed Mode with Backend Post-Processing

### Architecture

```
User clicks → Backend creates AITask → Agent streams NDJSON
                                              ↓
Frontend: TaskConsole shows real-time text (thinking + answering)
                                              ↓
Stream ends → Backend marks task completed
            → Backend extracts structured JSON from answer text
            → Backend writes structured records to DB tables
            → Frontend: console collapses, calls GET → gets real data
```

### Structured Data Extraction Strategy

**Primary:** Regex/template extraction from answer text. Each skill prompt will be updated to require a structured JSON block at the end of the output (fenced with a known delimiter like `<!-- STRUCTURED_DATA ... -->`).

**Fallback:** Lightweight LLM call (cheapest available model from family's provider config) to extract structured data from the full answer text when regex extraction fails.

### Per-Capability Output Schemas

Each capability needs a defined JSON schema for its structured output:

| Capability | DB Table | Key Fields |
|-----------|----------|------------|
| `alerts` | `ai_asset_alerts` | asset_name, alert_type, severity, suggestion, remaining_life_days, daily_cost |
| `disposal` | `ai_disposal_suggestions` | asset_name, category_name, inefficiency_score, suggested_channel, estimated_resale_range, suggestion, daily_cost |
| `report` | `ai_reports` | sections (health_score, allocation_analysis, risk_assessment, recommendations) |
| `spending_leak` | (TBD - check existing model) | leak_type, amount, frequency, suggestion |
| `allocation` | (TBD - check existing model) | category, current_pct, target_pct, drift, suggestion |
| `liability` | (TBD - check existing model) | liability_id, priority, strategy, monthly_saving, suggestion |

### Changes Required

#### 1. Skill Prompts (agent side)

Update each `skills/custom/*/SKILL.md` to append a structured JSON block after the natural language analysis:

```
...你的分析文本...

<!-- STRUCTURED_DATA
[{"asset_name": "...", "alert_type": "aging", ...}]
-->
```

#### 2. Backend Result Parser (`server/apps/backend/app/services/`)

New service: `ai_result_parser.py`

- `parse_capability_result(capability: str, answer_text: str) -> list[dict] | None`
  - Tries regex extraction of `<!-- STRUCTURED_DATA ... -->` block
  - On failure: calls lightweight LLM extraction (using family's cheapest provider)
  - Returns parsed structured data or None

#### 3. Backend Result Writer (`server/apps/backend/app/services/`)

New service: `ai_result_writer.py`

- `write_capability_results(capability: str, family_id: int, results: list[dict], db: Session) -> None`
  - Clears previous results for this family+capability (replace strategy)
  - Bulk inserts new structured records into the appropriate DB table
  - Each capability maps to its own writer function

#### 4. Modify `proxy_capability_events` Helper

After `AITaskService.complete_task(task_id, gen_db)`:
- Call `parse_capability_result(capability, answer)` 
- If results: call `write_capability_results(capability, family_id, results, gen_db)`
- If parse fails: log warning, task still marked completed (graceful degradation — user can see text in session history)

#### 5. Frontend (minimal changes)

- Keep existing `useAITask` composable and `TaskConsole` as-is
- Keep existing `onComplete` callbacks that call `loadAlerts()` / `loadSuggestions()` etc.
- The fix is purely backend — once results are written to DB, existing GET endpoints return real data

### Non-Goals

- No changes to the agent microservice code (only skill prompt updates)
- No changes to the streaming protocol or NDJSON event format
- No changes to the task queue/promotion mechanism
- No new frontend components or UI redesign
- No migration of existing capabilities to a different architecture

### Success Criteria

1. Each of the six capabilities produces structured results in its DB table after task completion
2. Frontend GET endpoints return non-empty data after a successful task run
3. If structured extraction fails, the task still completes (text is preserved in session) — no user-facing error
4. Existing streaming UX (TaskConsole with real-time text) continues to work unchanged

### Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| LLM doesn't follow prompt format reliably | Fallback to LLM extraction; prompt engineering with examples |
| LLM fallback adds latency | Only triggers on regex failure; uses cheapest model; async after stream |
| Old results persist after re-scan | Replace strategy: clear previous results before writing new ones |
| Schema mismatch between LLM output and DB | Validate parsed JSON against expected schema before writing; skip invalid records |

### Implementation Order

1. Create `ai_result_parser.py` with regex extraction + LLM fallback
2. Create `ai_result_writer.py` with per-capability writers
3. Modify `proxy_capability_events` to call parser+writer after task completion
4. Update skill prompts to include structured output delimiter
5. Verify each capability end-to-end (stream → parse → write → GET returns data)
6. Check/create missing DB models for spending_leak, allocation, liability if needed
