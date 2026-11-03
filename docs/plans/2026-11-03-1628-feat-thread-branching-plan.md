---
title: "Thread Branching - Plan"
date: 2026-11-03
type: feat
topic: thread-branching
artifact_contract: ce-unified-plan/v1
product_contract_source: ce-brainstorm
execution: code
status: already-implemented
---

# Thread Branching — Plan

## Goal Capsule

- **Objective:** Users can fork a conversation from a completed assistant turn and explore an alternative path without disturbing the original thread.
- **Status:** **Already implemented on this branch.** `POST /api/threads/{thread_id}/branches` exists at `server/apps/agent/routers/threads.py:1301`, with tests at `server/apps/agent/tests/unit/test_branch_endpoint.py` and frontend integration in `frontend/apps/main/src/api/ai-chat.ts`.
- **Remaining work:** None for the original T26 scope. This plan is retained as the requirements record and to name the small gaps that remain.

## Product Contract

### Summary

Branching creates a new thread that inherits the conversation history up to a chosen completed assistant turn, then diverges independently. The original thread is untouched.

### Problem Frame

Users may want to explore alternative conversation paths without losing the original. After receiving investment advice, a user might branch and explore a more conservative strategy while keeping the original analysis intact. DeerFlow implements this via checkpoint forking; Numina proxies it with family-scoped validation and session sync.

### Key Decisions

- **KD1. Proxy DeerFlow's branch capability, don't reimplement.** DeerFlow's branch logic handles checkpoint resolution, title inheritance, workspace copy, and run-event seeding. Numina adds only family-scoped validation and session sync. (session-settled: user-directed — chosen over custom Numina branch logic: DeerFlow's implementation is battle-tested and handles edge cases.) Governs R1–R3.

- **KD2. Branched thread inherits parent's family_id.** The new thread belongs to the same family. Cross-family branching is not supported. Governs R4.

- **KD3. Session metadata sync is fire-and-forget.** If the backend call fails, the branch still exists in DeerFlow but may not appear in backend queries until the next sync. Governs R5.

- **KD4. Track branch lineage via parent_thread_id.** The new thread's session metadata includes `parent_thread_id` pointing to the source thread, enabling conversation genealogy queries. (session-settled: user-directed — user confirmed lineage tracking is wanted.) Governs R7.

### Requirements

- R1. `POST /api/threads/{thread_id}/branches` accepts a target message and returns the new `thread_id`.
- R2. The caller must belong to the same family as the source thread.
- R3. The branched thread's conversation history includes all messages up to the specified turn.
- R4. The new thread inherits the source thread's `family_id`.
- R5. After branch creation, Numina syncs session metadata to the backend.
- R6. The branched thread appears in `GET /api/threads` for the family.
- R7. The session metadata includes `parent_thread_id` linking to the source thread.

### How This Work Fits Together

This covers T26 (Thread Branching) from issue #176. It is complete; the other P3 tasks are tracked separately:

- T24 (Tool Promotion Middleware): plan ready, not implemented.
- T25 (Task Continuity Tools): plan ready, not implemented.
- T26 (this plan): **implemented**.
- T27 (Evidence Seal): plan ready, not implemented.
- T22 (Container Sandbox), T23 (Scheduled Tasks): independent, no plan yet.

### Scope Boundaries

**Implemented:**
- `POST /api/threads/{thread_id}/branches` endpoint (`threads.py:1301`)
- Family-scoped validation (404 on cross-family, not 403 — avoids an existence oracle)
- Session metadata sync with `parent_thread_id` (model at `ai_chat_sessions.parent_thread_id`, migration `a4c7e9d2f1b8`)
- Branch title derivation with sibling deduplication
- Workspace clone with explicit `workspace_clone_mode` in the response
- Branch lineage surfaced in thread search/get metadata
- Frontend API integration

**Gaps left open (not part of original T26 scope):**
- No `GET /branches` listing endpoint — "show all branches of thread X" is not available.
- Branch merge does not exist.
- No branch-specific E2E coverage in `tests/e2e/`; coverage is unit-level only.

### Key Flows

- F1. Branch a conversation
  - **Trigger:** User wants to explore an alternative path from a specific point.
  - **Steps:** Client posts the target assistant message id(s). Numina validates family ownership, scans checkpoints for the containing turn, deep-copies it to a new thread_id, clones workspace files when the turn is the latest, and creates the backend session row.
  - **Outcome:** New thread_id returned. The user continues in the branch; the original is unaffected.
  - **Covers R1–R7**

### Acceptance Examples

- AE1. Branch from middle of conversation
  - **Given:** A thread has 5 completed turns. User branches from turn 3.
  - **When:** `POST /api/threads/{thread_id}/branches` with turn 3's message id.
  - **Then:** New thread_id returned with messages from turns 1–3. New turns in the branch do not affect the original.
  - **Covers R1, R3**

- AE2. Family isolation
  - **Given:** Thread A belongs to Family X. A user from Family Y attempts to branch it.
  - **When:** `POST /api/threads/{thread_A}/branches` with Family Y's token.
  - **Then:** 404 — the thread is invisible to another family rather than merely forbidden.
  - **Covers R2, R4**

---

## Verification Contract

Implementation predates this plan. To confirm it still holds:

| Check | Command | Scope |
|-------|---------|-------|
| Branch endpoint tests | `cd server && uv run pytest tests/agent/unit/ -v -k branch` | R1–R4 |
| Backup location (legacy tests dir) | `cd server && uv run pytest apps/agent/tests/unit/test_branch_endpoint.py -v` | R1–R4 |
| Lineage metadata tests | `cd server && uv run pytest tests/agent/unit/ -v -k lineage` | R7 |

## Definition of Done

Met: branch creation, family isolation, session sync, `parent_thread_id` lineage, frontend integration, and unit tests all exist on this branch.

---

## Sources

- Numina branch endpoint: `server/apps/agent/routers/threads.py:1301`
- Numina branch tests: `server/apps/agent/tests/unit/test_branch_endpoint.py`
- Lineage column + migration: `server/apps/backend/app/models/ai_chat_session.py:69`, `server/apps/backend/alembic/versions/a4c7e9d2f1b8_add_parent_thread_id_to_ai_chat_sessions.py`
- Backend lineage upsert: `server/apps/backend/app/routers/ai_internal.py:715`
- DeerFlow branch reference: `.claude/skills/deerflow-agent-dev/references/deerflow/backend/app/gateway/routers/threads.py`
- Issue: [vincentruan/numina#176](https://github.com/vincentruan/numina/issues/176) — T26
