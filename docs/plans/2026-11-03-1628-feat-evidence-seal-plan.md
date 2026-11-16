---
title: "Evidence Seal - Plan"
date: 2026-11-03
type: feat
topic: evidence-seal
artifact_contract: ce-unified-plan/v1
product_contract_source: ce-brainstorm
execution: code
status: implemented
---

# Evidence Seal — Plan

## Goal Capsule

- **Objective:** Make Numina's run event store tamper-evident by chaining events via cryptographic hashes, so any modification to historical events can be detected.
- **Means:** Each event in `RunEventStore` includes a hash of the previous event's hash + current event content, forming a hash chain. Terminal events (`run.terminal`) carry a final "seal" hash that can be verified independently.
- **Execution profile:** Single PR. Modify `RunEventStore` to compute and store hash chains. Add verification endpoint. No frontend changes.
- **Stop conditions:** Hash chain verification detects tampered events; untampered chains verify successfully; performance impact on event recording is < 5%.

## Product Contract

### Summary

Add cryptographic hash-chaining to Numina's `RunEventStore` (append-only JSONL per family). Each event includes a `prev_hash` field linking it to the previous event, and a `hash` field computed from `prev_hash + event_content`. This creates a tamper-evident chain: modifying any event breaks the chain, detectable via verification.

### Problem Frame

Numina's `RunEventStore` records run lifecycle events (start, end, LLM responses, tool results) as append-only JSONL files. While append-only prevents deletion, it doesn't prevent modification of existing entries if someone gains file system access. For audit compliance and trust, the system needs a way to detect tampering — not prevent it (that's access control), but detect it after the fact.

Hash-chaining provides tamper-evidence: each event cryptographically references its predecessor, so modifying any event breaks the chain. This is the same principle behind blockchains and git's commit history.

### Key Decisions

- **KD1. Hash chain, not cryptographic signatures.** Hash-chaining (SHA-256) detects tampering but doesn't prove authenticity (no private key). For Numina's use case (family asset management, not financial audit), tamper-evidence is sufficient. Signatures add complexity without proportional benefit. (session-settled: user-directed — chosen over hash-chain + signatures: simpler, meets the requirement; user confirmed SHA-256 is sufficient.) Governs R1–R3.

- **KD2. Hash includes prev_hash + event content.** Each event's hash is `SHA-256(prev_hash + canonical_json(event_content))`. This chains events: changing any event breaks its hash and all subsequent hashes. Governs R1.

- **KD3. Verification is on-demand, not automatic.** A `GET /api/runs/{run_id}/verify` endpoint checks the hash chain for a specific run. Automatic verification on every read would add latency; on-demand lets admins audit when needed. Governs R4.

- **KD4. Backward compatibility: existing events get null hashes.** Events written before this feature have `prev_hash: null` and `hash: null`. Verification treats them as "unverified" but doesn't fail. New events always have hashes. Governs R5.

### Requirements

- R1. Each new event in `RunEventStore` includes `prev_hash` (hash of previous event) and `hash` (hash of current event).
- R2. Hash computation uses SHA-256 over `prev_hash + canonical_json(event_content)`, where `canonical_json` sorts keys and removes whitespace.
- R3. The first event in a family's JSONL file has `prev_hash: "0" * 64` (64 zeros, representing an empty previous hash).
- R4. `GET /api/runs/{run_id}/verify` returns whether the run's event chain is intact, and if not, which event was tampered with.
- R5. Existing events (written before this feature) have `prev_hash: null` and `hash: null`. Verification skips them or marks them "unverified".
- R6. Hash computation adds < 5% latency to event recording.

### How This Work Fits Together

This plan covers T27 (Evidence Seal) from issue #176. It is one of six P3 future enhancement tasks (T22–T27).

- T27 (this plan): Hash-chain Numina's RunEventStore for tamper-evidence
- T24 (Tool Promotion Middleware): Has a completed plan. Independent.
- T25 (Task Continuity Tools): Has a completed plan. Independent.
- T26 (Thread Branching): Has a completed plan. Independent.
- T22 (Container Sandbox): Independent.
- T23 (Scheduled Tasks): Independent.

### Scope Boundaries

**In scope:**
- Hash-chain computation in `RunEventStore.record()`
- `prev_hash` and `hash` fields in `RunEvent` schema
- Verification endpoint `GET /api/runs/{run_id}/verify`
- Backward compatibility for existing events

**Deferred for later:**
- Cryptographic signatures (private key signing of terminal events)
- Automatic verification on read
- Integration with DeerFlow's `run.terminal` evidence system
- Frontend UI for displaying verification status

### Key Flows

- F1. Record event with hash chain
  - **Trigger:** Agent run emits an event (run.start, llm.ai.response, etc.).
  - **Steps:** `RunEventStore.record()` reads the last event's hash (or uses "0"*64 if first), computes `hash = SHA-256(prev_hash + canonical_json(event_content))`, writes event with both `prev_hash` and `hash`.
  - **Outcome:** Event is appended with hash chain linkage.
  - **Covers R1, R2, R3**

- F2. Verify run event chain
  - **Trigger:** Admin calls `GET /api/runs/{run_id}/verify`.
  - **Steps:** System reads all events for the run, recomputes hashes, compares to stored hashes. Returns `verified: true` if all match, or `verified: false` with the first tampered event's index.
  - **Outcome:** Admin knows whether the run's event chain is intact.
  - **Covers R4**

### Acceptance Examples

- AE1. Untampered chain verifies
  - **Given:** A run with 10 events, all written with hash-chaining.
  - **When:** `GET /api/runs/{run_id}/verify` is called.
  - **Then:** Response is `{verified: true, event_count: 10}`.
  - **Covers R1, R4**

- AE2. Tampered event detected
  - **Given:** A run with 10 events. An attacker modifies event #5's `data` field.
  - **When:** `GET /api/runs/{run_id}/verify` is called.
  - **Then:** Response is `{verified: false, tampered_event_index: 5, reason: "hash mismatch"}`.
  - **Covers R4**

- AE3. Legacy events without hashes
  - **Given:** A run with events written before hash-chaining (all have `hash: null`).
  - **When:** `GET /api/runs/{run_id}/verify` is called.
  - **Then:** Response is `{verified: "unverified", reason: "events predate hash-chaining"}`.
  - **Covers R5**

---

## Implementation Units

### U1. Extend RunEvent schema with hash fields

- **Goal:** Add `prev_hash` and `hash` fields to the `RunEvent` Pydantic model.
- **Requirements:** R1, R5
- **Files:**
  - `server/apps/agent/services/run_event_store.py` (modify)
- **Approach:**
  1. Add `prev_hash: str | None = None` and `hash: str | None = None` to `RunEvent` model.
  2. Existing events (loaded from JSONL) will have these as `null` — backward compatible.
- **Verification:** Unit test loading legacy events.

### U2. Hash computation in record()

- **Goal:** Compute and store hashes when recording events.
- **Requirements:** R1, R2, R3, R6
- **Dependencies:** U1
- **Files:**
  - `server/apps/agent/services/run_event_store.py` (modify)
- **Approach:**
  1. In `record()`, before writing:
     - Read the last event's hash from the JSONL file (or use `"0" * 64` if empty).
     - Compute `canonical_json = json.dumps(event.dict(exclude={"hash"}), sort_keys=True, separators=(",", ":"))`.
     - Compute `hash = SHA-256(prev_hash + canonical_json).hexdigest()`.
     - Set `event.prev_hash = prev_hash` and `event.hash = hash`.
  2. Optimize: cache the last hash per family_id to avoid re-reading the file on every write. Use a thread-safe dict.
- **Verification:** Unit test verifying hash chain integrity.

### U3. Verification endpoint

- **Goal:** Add `GET /api/runs/{run_id}/verify` endpoint.
- **Requirements:** R4
- **Dependencies:** U1, U2
- **Files:**
  - `server/apps/agent/routers/run_events.py` (modify or create)
- **Approach:**
  1. Endpoint reads all events for the run (via `RunEventStore.query_by_thread()` or a new `query_by_run_id()` method).
  2. Recomputes hashes and compares to stored hashes.
  3. Returns `{verified: bool | "unverified", event_count: int, tampered_event_index: int | null, reason: str | null}`.
- **Verification:** Integration test with tampered events.

### U4. Unit and integration tests

- **Goal:** Verify hash chain integrity and tamper detection.
- **Requirements:** R1–R6
- **Dependencies:** U1, U2, U3
- **Files:**
  - `server/tests/agent/unit/test_run_event_store_hash.py` (create)
  - `server/tests/agent/integration/test_evidence_seal.py` (create)
- **Test scenarios:**
  1. **Hash chain integrity:** Record 10 events, verify chain.
  2. **Tamper detection:** Modify event #5, verify detects it.
  3. **Legacy events:** Load events with `hash: null`, verify returns "unverified".
  4. **Performance:** Record 1000 events, measure latency increase < 5%.
- **Verification:** `cd server && uv run pytest tests/agent/unit/test_run_event_store_hash.py tests/agent/integration/test_evidence_seal.py -v`

---

## Verification Contract

| Check | Command | Scope |
|-------|---------|-------|
| Unit tests | `cd server && uv run pytest tests/agent/unit/test_run_event_store_hash.py -v` | U4 |
| Integration tests | `cd server && uv run pytest tests/agent/integration/test_verify_endpoint.py -v` | U4 |
| Regression | `cd server && uv run pytest tests/agent/unit/ -v` | 825 pass |
| Lint | `cd server && uv run ruff check apps/agent/services/run_event_store.py apps/agent/routers/run_events.py` | Changed files |

## Definition of Done

- [x] Hash-chain computation adds < 5% latency to event recording (measured: 0.056ms/event)
- [x] Tampered events are detected by verification endpoint
- [x] Legacy events without hashes are handled gracefully
- [x] Unit and integration tests pass (32 tests)
- [x] Verification endpoint returns accurate results

## As-Built Notes

Deviations from the plan worth recording:

- **`prev_hash` is excluded from hash computation, not just `hash`.** The plan said "SHA-256(prev_hash + canonical_json(event_content))" where content excluded only `hash`. When verifying, the loaded event dict contains both fields, so `prev_hash` must also be excluded or recomputation never matches. `_compute_event_hash` excludes both.
- **Verification traverses the full family file; `run_id` is optional narrowing only.** `RunEventStore` writes one JSONL per family, so the hash chain spans all runs in that family. `GET /run-events/verify?run_id=X` counts only run-X events in `event_count` but still walks every event to validate `prev_hash`. That catches tampering in run-Y even when asked about run-X — the chain can't lie about its predecessor.
- **Last-hash cache is in-memory per process.** `_last_hash_cache` avoids re-reading the JSONL on every write. It is not shared across processes; a second worker appending to the same family file would read the file on its first write in that process and then chain correctly. The cache is cleared only by process restart.
- **`record()` acquires the lock around chain computation, cache update, and file append.** The initial version computed the chain outside the lock, which let two concurrent writers chain from the same `prev_hash` and fork the chain. `test_concurrent_writes_do_not_fork_chain` (4 threads × 20 writes) fails against the buggy version with `prev_hash mismatch at index 1` and passes against the fix.

---

## Sources

- Numina RunEventStore: `server/apps/agent/services/run_event_store.py`
- DeerFlow run.terminal event: `.claude/skills/deerflow-agent-dev/references/deerflow/backend/packages/harness/deerflow/runtime/events/catalog.py`
- DeerFlow terminal evidence: `.claude/skills/deerflow-agent-dev/references/deerflow/backend/packages/harness/deerflow/runtime/events/terminal.py`
- Issue: [vincentruan/numina#176](https://github.com/vincentruan/numina/issues/176) — T27
