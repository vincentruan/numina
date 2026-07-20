# Plan A — finance_coach Capability 接入 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `finance_coach` capability as a new stateless system-agent `stream_run` app (`app="finance-coach"`), with full dispatch chain (RESERVED_NAMES + system-agent Alembic + gateway route + R1 allowlist + worker branch + SKILL.md) and a new capability-cache layer on `ai_reports` (add `capability` column + parametric TTL + entity-change invalidation), so that Plan B's D2/A1a dashboard card and A1b passive buttons can call it.

**Architecture:** finance_coach mirrors the import-parse precedent (U8): a 4th `stream_run` agent entry in the worker's `if/elif` dispatch, a dedicated `X-Agent-Token` gateway route, an R1 allowlist slot, a system-agent row seeded by `bootstrap_agents` + an idempotent Alembic insert, and a `SKILL.md` with base-name `allowed-tools` (avoiding the U4 prefix-mismatch bug). The capability-cache is a new column on the existing `ai_reports` table (not a new table) — `ai_reports.capability VARCHAR(32) NOT NULL DEFAULT 'report'`, backfilled so existing report queries are unaffected; `_latest_report` filters by `(family_id, capability, status)`; TTL becomes a `capability_ttl` map; entity-change invalidation deletes the family's finance_coach row on any asset/liability/wish write.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy, Alembic, Pydantic v2, pytest, ruff, mypy. DeerFlow harness `typed_stream_dispatch`. SQLite (dev) / PostgreSQL (prod) — migration uses `INSERT OR IGNORE` (SQLite idempotent; bootstrap_agents is the source of truth so Postgres fresh-DB also gets the row).

## Global Constraints

Copied verbatim from the spec (`docs/superpowers/specs/2026-07-19-p0-family-finance-core-design.md` §0, §7.1, §7.2) and the repo `CLAUDE.md`:

- **URL style:** all router root-path endpoints use `""` not `"/"` (`redirect_slashes=False` in `app/main.py`). No trailing slashes, no 307 redirects.
- **Snowflake/bigint serialization:** all `bigint` fields (IDs, large amounts) serialized as `str` in API responses. New `NUMERIC(18,2)` money fields also serialize as `str` (2 decimals).
- **Auth endpoints return 200;** asset/liability POST return 201 (does not apply to internal gateway routes — those use `X-Agent-Token`).
- **i18n:** no hardcoded Chinese in `.vue`/`.ts` logic — but this Plan A is backend-only (no frontend), so i18n does not apply here. Error messages in `HTTPException(detail=...)` use Chinese.
- **Never run dev servers** (`uvicorn`/`pnpm dev`) from agents — verify with `pytest`, `ruff check`, `mypy` only.
- **Surgical changes:** touch only what each task requires. Do not refactor adjacent code.
- **No speculative code:** no features/abstractions beyond what the spec lists.
- **finance_coach allowed-tools use base names** (e.g. `get_assets`, not `numina-get_assets`) — `filter_tools_by_skill_allowed_tools` does full-name exact match, not prefix match (U4 pilot systemic bug).
- **finance_coach is stateless:** `memory_enabled=False` (mirrors asset-report/import-parse — each run gets fresh snapshot, no DeerMem pollution).
- **PII minimization:** finance_coach snapshot fields use `id + category` not `name` unless prompt-required; redact before LLM feed (populate structured fields then `desensitize_*`); LLM provider per-family via `AIProviderConfig`.
- **Advice baseline:** suggestions JSON must pass schema-validation gate before any UI enable; `suggested_amount >= 0` enforced; wrong output silently dropped + logged (never displayed). (The gate itself is implemented in Plan B's W4/D2 UI; Plan A only defines the schema + the worker emits validated JSON.)
- **capability-cache:** `ai_reports.capability` default `'report'` backfill; three cache keys `family_id:report` / `family_id:finance_coach` / `family_id:wish_advice:{fingerprint}`; parametric TTL (initial 8h all); entity-change event invalidation (not pure TTL).

---

## File Structure

**Create:**
- `server/apps/agent/skills/builtin/public/finance-coach/SKILL.md` — finance_coach skill prompt + base-name `allowed-tools` (get_assets/get_liabilities/get_members). Defines the `suggestions[]` JSON output schema the worker parses.
- `server/apps/backend/alembic/versions/<new>_add_finance_coach_system_agent.py` — idempotent `INSERT OR IGNORE` of the finance-coach system-agent row (id `100000000000008`), down_revision `f8a4c2e1b9d6`. **NOTE:** separate from the capability-column migration below (different concerns, but same plan; see Task 2 vs Task 7).
- `server/apps/backend/alembic/versions/<new>_add_capability_to_ai_reports.py` — `op.add_column('ai_reports', capability VARCHAR(32) NOT NULL DEFAULT 'report')` + backfill (no-op since DEFAULT covers it) + index on `(family_id, capability, status)`. down_revision = the finance_coach agent migration.
- `server/apps/backend/app/services/finance_coach_cache.py` — capability-cache helpers: `_latest_by_capability(family_id, capability, db)`, `upsert_capability_result(family_id, capability, payload, db)`, `invalidate_capability(family_id, capability, db)`, `CAPABILITY_TTL` map, entity-change invalidation hook.
- `server/apps/backend/app/routers/ai_finance_coach.py` — backend trigger endpoint `POST /ai/finance-coach/generate` (require_ai_enabled + require_adult + 8h cache + circuit breaker + delegate to agent gateway route). Mirrors `ai_report.py:trigger_generate_events` shape but capability-scoped.
- `server/apps/agent/tests/unit/test_finance_coach_skill.py` — SKILL.md frontmatter + allowed-tools base-name assertion.
- `server/apps/agent/tests/integration/test_gateway_finance_coach.py` — gateway route + R1 allowlist + worker dispatch branch integration (mirrors `test_gateway_asset_report.py`).
- `server/tests/backend/routers/test_ai_finance_coach.py` — cache hit/miss/invalidation + circuit breaker + capability isolation (finance_coach vs report don't pollute).
- `server/tests/backend/services/test_finance_coach_cache.py` — `_latest_by_capability` isolation, `invalidate_capability` correctness, reconciliation.

**Modify:**
- `server/apps/backend/app/routers/ai_skills.py:55` — add `"finance-coach"` to `RESERVED_NAMES`.
- `server/apps/backend/app/bootstrap/agents.py` — add `_FINANCE_COACH_AGENT` spec dict + `_upsert_builtin_agent` call in `bootstrap_agents`; add `FINANCE_COACH_AGENT_ID = 100000000000008` constant.
- `server/apps/backend/app/models/ai_report.py` — add `capability: Mapped[str]` column (default `'report'`).
- `server/apps/backend/app/routers/ai_report.py:47-53,62` — `_latest_report` → filter by `(family_id, capability='report', status)`; `REPORT_CACHE_TTL` → read from `CAPABILITY_TTL['report']` (keep behavior identical for report).
- `server/apps/agent/app/routers/gateway.py` — add `FinanceCoachRunRequest` model + `POST /runs/finance-coach/{thread_id}` route (mirror asset-report route, `metadata={"app": "finance-coach"}`).
- `server/apps/agent/services/runtime/sse_gateway.py:183-197` — add `finance-coach` to R1 allowlist: reject direct (409, like import-parse) when `not internal`; add to the `app != ...` 400 line.
- `server/apps/agent/services/runtime/worker.py:224,234-258` — add docstring app entry + `if app == "finance-coach":` branch calling new `_run_finance_coach_agent`.
- `server/apps/agent/services/runtime/worker.py` (new function) — `_run_finance_coach_agent` mirroring `_run_import_parse_agent` signature, `skill_name="finance-coach"`, emits `finance_coach.result` custom event with validated `suggestions[]` JSON.
- Entity-change invalidation callers (write paths): `server/apps/backend/app/routers/assets.py`, `liabilities.py`, `wishes.py` — call `invalidate_capability(family_id, "finance_coach", db)` on POST/PUT/DELETE (W1 savings writes added in Plan B; here only existing asset/liability/wish write paths). **Scope note:** keep calls minimal — one helper call per write endpoint, no logic changes.

---

## Task 1: Add finance-coach to RESERVED_NAMES

**Files:**
- Modify: `server/apps/backend/app/routers/ai_skills.py:55`
- Test: `server/tests/backend/test_ai_skills.py` (add one assertion)

**Interfaces:**
- Consumes: existing `RESERVED_NAMES` list.
- Produces: `RESERVED_NAMES` now includes `"finance-coach"`, blocking owner from creating a custom skill of that name. Downstream: `bootstrap_agents` (Task 3) and the SKILL loader rely on this reservation.

- [ ] **Step 1: Write the failing test**

Append to `server/tests/backend/test_ai_skills.py` (create the test function; if a `test_reserved_names` already exists, extend it instead of duplicating):

```python
def test_reserved_names_includes_finance_coach():
    """finance-coach is a system fixed-flow (KTD-8), must be reserved."""
    from apps.backend.app.routers.ai_skills import RESERVED_NAMES
    assert "finance-coach" in RESERVED_NAMES
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd server && uv run pytest tests/backend/test_ai_skills.py::test_reserved_names_includes_finance_coach -v`
Expected: FAIL with `AssertionError: assert 'finance-coach' in ['chat', 'asset-report', 'import-parse']`

- [ ] **Step 3: Write minimal implementation**

In `server/apps/backend/app/routers/ai_skills.py`, change line 55:

```python
RESERVED_NAMES = ["chat", "asset-report", "import-parse", "finance-coach"]
```

And update the comment block above it (lines 48-54) to add a bullet:

```python
# U8: ``import-parse`` 加入（系统内置固定流程：金融文档持仓解析，KTD-8）。
# Plan A: ``finance-coach`` 加入（系统内置固定流程：家庭财务处方建议，KTD-8）。
RESERVED_NAMES = ["chat", "asset-report", "import-parse", "finance-coach"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd server && uv run pytest tests/backend/test_ai_skills.py::test_reserved_names_includes_finance_coach -v`
Expected: PASS

- [ ] **Step 5: Lint + typecheck the touched file**

Run: `cd server && uv run ruff check apps/backend/app/routers/ai_skills.py tests/backend/test_ai_skills.py && uv run mypy apps/backend/app/routers/ai_skills.py`
Expected: no errors

- [ ] **Step 6: Commit**

```bash
git add server/apps/backend/app/routers/ai_skills.py server/tests/backend/test_ai_skills.py
git commit -m "feat(ai-skills): reserve 'finance-coach' system capability name (Plan A T1)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: Alembic migration — seed finance-coach system-agent row

**Files:**
- Create: `server/apps/backend/alembic/versions/c4d5e6f7a8b9_add_finance_coach_system_agent.py`
- Test: verified by `alembic upgrade head` + `bootstrap_agents` idempotency (Task 3 test asserts the row exists post-migration).

**Interfaces:**
- Consumes: `down_revision = "f8a4c2e1b9d6"` (current head — import-parse system agent).
- Produces: `ai_agents` row `id=100000000000008, agent_name='finance-coach'`. Task 3's `bootstrap_agents` upserts the same row (idempotent — `INSERT OR IGNORE` here + `_upsert_builtin_agent` update-on-conflict there).

- [ ] **Step 1: Create the migration file**

Create `server/apps/backend/alembic/versions/c4d5e6f7a8b9_add_finance_coach_system_agent.py`:

```python
"""add finance-coach system agent

Revision ID: c4d5e6f7a8b9
Revises: f8a4c2e1b9d6
Create Date: 2026-07-19

Plan A: finance_coach is a new system fixed-flow (KTD-8) — a 4th stream_run
agent (``app="finance-coach"``). This migration inserts the finance-coach
system agent row with ``memory_enabled=False`` (stateless — each run builds a
fresh family finance snapshot, no DeerMem pollution, mirroring asset-report
and import-parse). The bootstrap_agents() function re-syncs this row on
startup (single source of truth in bootstrap/agents.py), so this migration
only seeds existing DBs; fresh DBs get the row from bootstrap.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "c4d5e6f7a8b9"
down_revision: Union[str, None] = "f8a4c2e1b9d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Idempotent insert: skip if the row already exists (e.g. bootstrap ran first).
    op.execute(
        """
        INSERT OR IGNORE INTO ai_agents (
            id, family_id, agent_name, display_name, description,
            icon, color, soul_md, skills, agent_type, memory_enabled, display_order
        )
        VALUES (
            100000000000008, 0, 'finance-coach', '财务教练',
            '家庭财务处方建议智能体。读取家庭财务快照，输出结构化 suggestions JSON（前 3 条优先建议）。',
            '🎯', '#10b981',
            '你是家庭财务教练，在单次响应内完成：读取家庭财务快照 → 识别高息负债/闲置资产/储蓄缺口 → 输出结构化 suggestions JSON。',
            '["finance-coach"]',
            'system', 0, 40
        )
        """
    )


def downgrade() -> None:
    op.execute(
        "DELETE FROM ai_agents WHERE id = 100000000000008"
    )
```

> **Note on `INSERT OR IGNORE`:** This is SQLite syntax. The repo dev DB is SQLite; prod is PostgreSQL. PostgreSQL lacks `INSERT OR IGNORE` — but `bootstrap_agents()` is the source of truth and runs on every startup (Task 3), so on Postgres the row is seeded by bootstrap before any finance_coach run. The migration's `INSERT OR IGNORE` is a SQLite-only convenience for existing dev DBs. If a Postgres deployment runs `alembic upgrade head` before `bootstrap_agents`, the migration will error on `INSERT OR IGNORE` syntax — **this is acceptable** because the deployment order is `alembic upgrade` then `app startup` (which calls `bootstrap_agents`). If you need Postgres-compatible seeding in the migration itself, replace with a `SELECT` guard:
> ```python
> op.execute("""
>     INSERT INTO ai_agents (id, family_id, agent_name, display_name, description,
>         icon, color, soul_md, skills, agent_type, memory_enabled, display_order)
>     SELECT 100000000000008, 0, 'finance-coach', '财务教练',
>         '家庭财务处方建议智能体。读取家庭财务快照，输出结构化 suggestions JSON（前 3 条优先建议）。',
>         '🎯', '#10b981',
>         '你是家庭财务教练，在单次响应内完成：读取家庭财务快照 → 识别高息负债/闲置资产/储蓄缺口 → 输出结构化 suggestions JSON。',
>         '["finance-coach"]', 'system', 0, 40
>     WHERE NOT EXISTS (SELECT 1 FROM ai_agents WHERE id = 100000000000008)
> """)
> ```
> Use the `WHERE NOT EXISTS` form if the target deployment is PostgreSQL. Keep `INSERT OR IGNORE` for SQLite dev. The implementer should pick the form matching their test DB and note it in the commit.

- [ ] **Step 2: Verify the migration runs**

Run: `cd server/apps/backend && uv run alembic upgrade head`
Expected: the new revision `c4d5e6f7a8b9` applies with no error; `alembic current` shows `c4d5e6f7a8b9 (head)`.

- [ ] **Step 3: Verify the row exists**

Run: `cd server && uv run python -c "from apps.backend.app.database import SessionLocal; from apps.backend.app.models.ai_agent import AIAgent; s=SessionLocal(); a=s.query(AIAgent).filter_by(agent_name='finance-coach').first(); print(a.id, a.agent_name, a.memory_enabled, a.skills)"`
Expected: `100000000000008 finance-coach False ['finance-coach']`

- [ ] **Step 4: Verify downgrade is clean**

Run: `cd server/apps/backend && uv run alembic downgrade -1 && uv run alembic upgrade head`
Expected: both succeed; row removed then re-added.

- [ ] **Step 5: Commit**

```bash
git add server/apps/backend/alembic/versions/c4d5e6f7a8b9_add_finance_coach_system_agent.py
git commit -m "feat(alembic): seed finance-coach system agent row (Plan A T2)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: Add finance-coach system-agent spec to bootstrap_agents

**Files:**
- Modify: `server/apps/backend/app/constants/system_ids.py` — add `FINANCE_COACH_AGENT_ID = 100000000000008` (after `IMPORT_PARSE_AGENT_ID` at line 11)
- Modify: `server/apps/backend/app/bootstrap/agents.py` (add import + `_FINANCE_COACH_AGENT` dict + upsert call)
- Test: `server/tests/backend/bootstrap/test_bootstrap_agents.py` (add finance-coach assertion)

**Interfaces:**
- Consumes: `_upsert_builtin_agent` helper (line 178) and `bootstrap_agents` (line 209). Existing constants imported from `apps.backend.app.constants.system_ids` (agents.py:5-9): `NUMINA_AGENT_ID` / `ASSET_REPORT_AGENT_ID` / `IMPORT_PARSE_AGENT_ID`. The existing values are `NUMINA_AGENT_ID=100000000000005`, `ASSET_REPORT_AGENT_ID=100000000000006`, `IMPORT_PARSE_AGENT_ID=100000000000007` — so finance-coach takes `100000000000008`.
- Produces: on every app startup, `bootstrap_agents` upserts the finance-coach row (syncing `soul_md`/`memory_enabled` with code). This is the source of truth — the Task 2 migration only seeds existing DBs. The constant lives in `system_ids.py` (the canonical home for system-agent IDs), imported by both `bootstrap/agents.py` and available to any caller.

- [ ] **Step 1: Write the failing test**

Add to `server/tests/backend/bootstrap/test_bootstrap_agents.py` (create file if absent):

```python
"""bootstrap_agents idempotently seeds all system agents including finance-coach."""
from apps.backend.app.constants.system_ids import FINANCE_COACH_AGENT_ID
from apps.backend.app.bootstrap.agents import bootstrap_agents


def test_bootstrap_seeds_finance_coach_agent(db_session):
    """bootstrap_agents upserts the finance-coach system agent row."""
    bootstrap_agents(db_session)
    from apps.backend.app.models.ai_agent import AIAgent
    agent = db_session.query(AIAgent).filter_by(id=FINANCE_COACH_AGENT_ID).first()
    assert agent is not None
    assert agent.agent_name == "finance-coach"
    assert agent.agent_type == "system"
    assert agent.memory_enabled is False  # stateless — mirrors asset-report/import-parse
    assert agent.skills == ["finance-coach"]


def test_bootstrap_finance_coach_is_idempotent(db_session):
    """Running bootstrap twice does not duplicate or error."""
    bootstrap_agents(db_session)
    bootstrap_agents(db_session)  # second call must not raise
    from apps.backend.app.models.ai_agent import AIAgent
    count = db_session.query(AIAgent).filter_by(agent_name="finance-coach").count()
    assert count == 1
```

> **Note:** `db_session` is the repo's existing test fixture — confirm the fixture name in `server/tests/backend/conftest.py`; if it's `session` not `db_session`, use that name instead. If no `tests/bootstrap/` dir exists, create it with an `__init__.py`.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd server && uv run pytest tests/backend/bootstrap/test_bootstrap_agents.py -v`
Expected: FAIL with `ImportError: cannot import name 'FINANCE_COACH_AGENT_ID'` (the constant doesn't exist yet in `system_ids.py`).

- [ ] **Step 3: Write minimal implementation**

(a) In `server/apps/backend/app/constants/system_ids.py`, after line 11 (`IMPORT_PARSE_AGENT_ID: int = 100000000000007`), add:

```python
# Plan A: finance-coach system agent (家庭财务处方建议). Stateless stream_run
# agent — each run builds a fresh family finance snapshot; DeerMem would
# pollute advice with stale snapshots. soul_md is a minimal persona (the real
# advice contract lives in skills/builtin/public/finance-coach/SKILL.md).
FINANCE_COACH_AGENT_ID: int = 100000000000008
```

(b) In `server/apps/backend/app/bootstrap/agents.py`, extend the import block (lines 5-9) to include `FINANCE_COACH_AGENT_ID`:

```python
from apps.backend.app.constants.system_ids import (
    ASSET_REPORT_AGENT_ID,
    FINANCE_COACH_AGENT_ID,
    IMPORT_PARSE_AGENT_ID,
    NUMINA_AGENT_ID,
)
```

(c) Add the spec dict after `_IMPORT_PARSE_AGENT` (after line 175, before `_upsert_builtin_agent`):

```python
# System agent dedicated to finance-coach (家庭财务处方建议).
# Plan A: a 4th stream_run agent (app="finance-coach"). Statelessness is
# required — each run builds a fresh family finance snapshot from MCP data;
# DeerMem would only pollute advice with stale snapshots from prior runs.
# soul_md is a minimal persona (the real advice contract lives in
# skills/builtin/public/finance-coach/SKILL.md, loaded by the harness at
# runtime); bootstrap just seeds agent_type + memory_enabled.
_FINANCE_COACH_AGENT = {
    "id": FINANCE_COACH_AGENT_ID,
    "family_id": 0,
    "agent_name": "finance-coach",
    "display_name": "财务教练",
    "description": "家庭财务处方建议智能体。读取家庭财务快照，输出结构化 suggestions JSON（前 3 条优先建议）。",
    "icon": "🎯",
    "color": "#10b981",
    "soul_md": "你是家庭财务教练，在单次响应内完成：读取家庭财务快照 → 识别高息负债/闲置资产/储蓄缺口 → 输出结构化 suggestions JSON。",
    "skills": ["finance-coach"],
    "agent_type": "system",
    "memory_enabled": False,
    "display_order": 40,
}
```

(c) Add the upsert call in `bootstrap_agents` (after line 213, before `db.commit()`):

```python
def bootstrap_agents(db: Session) -> None:
    """Ensure builtin agents exist and their soul matches code. Idempotent."""
    _upsert_builtin_agent(db, _NUMINA_AGENT)
    _upsert_builtin_agent(db, _ASSET_REPORT_AGENT)
    _upsert_builtin_agent(db, _IMPORT_PARSE_AGENT)
    _upsert_builtin_agent(db, _FINANCE_COACH_AGENT)
    db.commit()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd server && uv run pytest tests/backend/bootstrap/test_bootstrap_agents.py -v`
Expected: both tests PASS.

- [ ] **Step 5: Lint + typecheck**

Run: `cd server && uv run ruff check apps/backend/app/constants/system_ids.py apps/backend/app/bootstrap/agents.py tests/backend/bootstrap/ && uv run mypy apps/backend/app/bootstrap/agents.py`
Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add server/apps/backend/app/constants/system_ids.py server/apps/backend/app/bootstrap/agents.py server/tests/backend/bootstrap/
git commit -m "feat(bootstrap): add finance-coach system agent spec (Plan A T3)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: Create finance-coach SKILL.md (base-name allowed-tools)

**Files:**
- Create: `server/apps/agent/skills/builtin/public/finance-coach/SKILL.md`
- Test: `server/apps/agent/tests/unit/test_finance_coach_skill.py`

**Interfaces:**
- Consumes: MCP tools `get_assets` / `get_liabilities` / `get_members` (family-data, base names — `sync_tool_patch.py` `tool_name_prefix=False`).
- Produces: skill prompt loaded by harness at runtime when `skill_name="finance-coach"`. The worker (Task 6) parses the final ```json block as `suggestions[]`. The `allowed-tools` list gates `filter_tools_by_skill_allowed_tools` (full-name exact match — base names required, not `numina-*` prefixed).

- [ ] **Step 1: Write the failing test**

Create `server/apps/agent/tests/unit/test_finance_coach_skill.py`:

```python
"""finance-coach SKILL.md frontmatter + allowed-tools base-name convention."""
from pathlib import Path

import yaml

SKILL_PATH = (
    Path(__file__).resolve().parents[2]
    / "skills" / "builtin" / "public" / "finance-coach" / "SKILL.md"
)


def _parse_frontmatter() -> dict:
    text = SKILL_PATH.read_text(encoding="utf-8")
    assert text.startswith("---\n"), "SKILL.md must start with frontmatter"
    end = text.index("\n---\n", 4)
    return yaml.safe_load(text[4:end])


def test_skill_file_exists():
    assert SKILL_PATH.exists(), f"finance-coach SKILL.md missing at {SKILL_PATH}"


def test_frontmatter_name_and_description():
    fm = _parse_frontmatter()
    assert fm["name"] == "finance-coach"
    assert "财务" in fm["description"]


def test_allowed_tools_use_base_names_not_prefixed():
    """U4 pilot bug: filter_tools_by_skill_allowed_tools does full-name exact
    match, NOT prefix match. allowed-tools must use base names (get_assets),
    not numina-prefixed (numina-get_assets), or all business tools get filtered
    out and the agent hits RecursionError."""
    fm = _parse_frontmatter()
    tools = fm["allowed-tools"]
    assert "get_assets" in tools
    assert "get_liabilities" in tools
    assert "get_members" in tools
    # CRITICAL: no numina- prefixed entries
    for t in tools:
        assert not t.startswith("numina-"), f"allowed-tools must use base name, got prefixed: {t}"


def test_thinking_disabled():
    """finance-coach is a single-run stateless advice agent — thinking=False
    mirrors asset-report/import-parse (keeps latency + token cost bounded)."""
    fm = _parse_frontmatter()
    assert fm.get("thinking") is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd server && uv run pytest apps/agent/tests/unit/test_finance_coach_skill.py -v`
Expected: FAIL — `test_skill_file_exists` fails (file doesn't exist yet).

- [ ] **Step 3: Write minimal implementation — create the SKILL.md**

Create `server/apps/agent/skills/builtin/public/finance-coach/SKILL.md`:

```markdown
---
name: finance-coach
description: |
  家庭财务处方建议（系统内置固定流程，KTD-8 / Plan A）。
  单 agent run 内完成：调 family-data MCP 取家庭财务快照 → 识别高息负债/闲置资产/
  储蓄缺口 → 输出结构化 suggestions JSON（前 3 条优先建议）。由 backend
  /ai/finance-coach/generate 触发端点以合成触发消息（/finance-coach）发起，
  非用户直聊触发。

trigger_phrases:
  - /finance-coach
  - 财务建议
  - 家庭财务教练

# 原生 DeerFlow sandbox 工具（非 MCP）—— 本 skill 不写文件，纯取数 + 推理。
# family-data MCP 工具用基名（sync_tool_patch.py MultiServerMCPClient
# tool_name_prefix=False），allowed-tools 必须用基名全名匹配
# （filter_tools_by_skill_allowed_tools 全名精确匹配，非前缀匹配 — U4 pilot bug）。
# 仅需取数三件套：资产/负债/成员（心愿数据由 backend 在快照中注入，见 SKILL 输入）。
allowed-tools:
  - get_assets
  - get_liabilities
  - get_members

thinking: false
max_tokens: 6000
---

## 角色

你是家庭财务教练，在**单次响应内**完成：读取家庭财务快照 → 识别最值得优先处理的 3 个
财务问题 → 输出结构化 suggestions JSON。

本 skill 由 backend 以合成触发消息 `/finance-coach` 发起（系统内置固定流程，非用户对话
触发）。家庭财务快照（net_worth / total_liabilities / high_interest_debts /
idle_assets / top_daily_cost_assets / wishes）以 JSON 形式注入消息内容。

## 执行流程（必须严格按此顺序）

**第 1 步：调用 MCP 取实时数据校验快照**
- 调 `get_assets`、`get_liabilities`、`get_members` 读取家庭当前资产/负债/成员。
- 与注入快照对比，若差异显著以 MCP 实时数据为准（快照可能因缓存滞后）。

**第 2 步：识别优先问题（最多 3 条，按 severity 降序）**
- **high**：高息负债（利率 ≥ 其 category 阈值）且家庭有心愿在存 → 建议优先还款。
- **high**：闲置资产（daily_cost 高且无收益）→ 建议盘活或调整。
- **medium**：储蓄缺口（心愿 target_date 临近但 monthly_saving 不足）→ 建议加速。
- **medium**：负债结构（多笔高息）→ 建议雪崩法排序。
- **low**：净资产健康但分散 → 建议优化配置。
- 若家庭财务无显著问题 → 返回空 `suggestions: []`（不要硬凑建议）。

**第 3 步：输出最终 JSON 代码块**

## 最重要的规则（必须严格遵守）

1. **最多 3 条 suggestions**，按 severity（high > medium > low）降序。无显著问题返回空数组。
2. **每条 suggestion 必须含字段**：`id`（建议唯一标识，字符串）、`severity`（high|medium|low）、`title`（一句话标题，≤20 字）、`action`（具体行动建议，≤50 字）、`target_type`（liability|asset|wish）、`target_id`（对应实体 id，字符串）、`cta_label`（CTA 按钮文案，≤8 字）。
3. **target_id 用实体 id**（数字字符串），**不用实体 name**（PII 最小化 — name 不外泄给 UI 展示之外的任何环节）。
4. **行动建议必须可执行且基于数据**：引用具体利率/金额/日期，不要泛泛而谈。若数据不足，severity 降级或不出该条。
5. **免责标注**：title 或 action 中可含「基于你录入的数据」类提示，因数据为用户手动录入，可信度有限。
6. **最终输出仅一个 ```json 代码块**，不要有任何其他内容（MCP 调用后的最终回复只放 JSON）。
7. **JSON 必须合法**：无尾逗号、无注释、字符串正确转义。

## 输出格式

```json
{
  "suggestions": [
    {
      "id": "s1",
      "severity": "high",
      "title": "先还信用卡高息负债",
      "action": "你的信用卡负债利率 18%，每月利息 ¥320。优先还款比存钱买心愿更划算。",
      "target_type": "liability",
      "target_id": "1234567890",
      "cta_label": "查看还款建议"
    },
    {
      "id": "s2",
      "severity": "medium",
      "title": "心愿「新车」需加速储蓄",
      "action": "距目标日期 90 天，当前月存 ¥1000，需月存 ¥2000 才能按时达成。",
      "target_type": "wish",
      "target_id": "9876543210",
      "cta_label": "调整储蓄计划"
    }
  ]
}
```

## 边界情况

- **空快照**（家庭无资产/负债/心愿）→ 返回 `{"suggestions": []}`，不报错。
- **MCP 取数失败**→ 仍基于注入快照出建议，但在 action 中注明「数据可能不完整」。
- **仅 1-2 个显著问题**→ 只出实际条数，不补凑到 3 条。
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd server && uv run pytest apps/agent/tests/unit/test_finance_coach_skill.py -v`
Expected: all 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add server/apps/agent/skills/builtin/public/finance-coach/SKILL.md server/apps/agent/tests/unit/test_finance_coach_skill.py
git commit -m "feat(skill): add finance-coach SKILL.md with base-name allowed-tools (Plan A T4)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: Agent gateway route + R1 allowlist for finance-coach

**Files:**
- Modify: `server/apps/agent/app/routers/gateway.py` (add `FinanceCoachRunRequest` + `POST /runs/finance-coach/{thread_id}`)
- Modify: `server/apps/agent/services/runtime/sse_gateway.py:183-197` (add `finance-coach` to R1 allowlist)
- Test: `server/apps/agent/tests/integration/test_gateway_finance_coach.py`

**Interfaces:**
- Consumes: `start_run` (sse_gateway.py:133) with `internal=True`; `_verify_token`, `_validate_path_segment`, `sse_consumer`, `get_stream_bridge`, `get_run_manager` (all in gateway.py). Existing `AssetReportRunRequest` model (gateway.py:224) as the mirror template.
- Produces: `POST /internal/gateway/runs/finance-coach/{thread_id}` — backend (Plan B D2/A1a, and Task 8's `ai_finance_coach.py`) calls this with `X-Agent-Token`, gets SSE stream. The worker (Task 6) reads `record.metadata["app"] == "finance-coach"` and dispatches to `_run_finance_coach_agent`. R1 rejects direct frontend dispatch (409, like import-parse).

- [ ] **Step 1: Write the failing test**

Create `server/apps/agent/tests/integration/test_gateway_finance_coach.py` (mirror the structure of `test_gateway_asset_report.py`):

```python
"""finance-coach gateway route + R1 allowlist integration (Plan A T5)."""
import pytest
from fastapi.testclient import TestClient


@pytest.mark.asyncio
async def test_finance_coach_route_requires_agent_token(agent_app_client):
    """Without X-Agent-Token, the finance-coach route 401s (or 422 for missing header)."""
    resp = await agent_app_client.post(
        "/internal/gateway/runs/finance-coach/some-thread",
        json={"family_id": "1"},
    )
    assert resp.status_code in (401, 422)


@pytest.mark.asyncio
async def test_r1_rejects_direct_finance_coach_dispatch(
    agent_app_client, agent_token
):
    """Frontend direct dispatch with app=finance-coach is rejected (409) by R1.
    Mirrors import-parse R1 gate — finance-coach must be entered via backend trigger."""
    resp = await agent_app_client.post(
        "/internal/gateway/runs/stream",
        headers={"X-Agent-Token": agent_token},
        json={
            "assistant_id": None,
            "input": None,
            "metadata": {"app": "finance-coach"},
            "on_disconnect": "cancel",
        },
        params={"thread_id": "t-direct"},
    )
    assert resp.status_code == 409
    assert "finance-coach" in resp.text or "财务" in resp.text


@pytest.mark.asyncio
async def test_r1_rejects_unknown_app_still_400(agent_app_client, agent_token):
    """Unknown app values still 400 (regression guard for the allowlist edit)."""
    resp = await agent_app_client.post(
        "/internal/gateway/runs/stream",
        headers={"X-Agent-Token": agent_token},
        json={
            "assistant_id": None,
            "input": None,
            "metadata": {"app": "bogus-app"},
            "on_disconnect": "cancel",
        },
        params={"thread_id": "t-bogus"},
    )
    assert resp.status_code == 400
```

> **Note:** `agent_app_client` / `agent_token` fixtures come from the existing `test_gateway_asset_report.py` conftest — confirm fixture names by reading `server/apps/agent/tests/integration/conftest.py` and reuse the same names. If `TestClient` (sync) is used instead of async, drop `await` and `@pytest.mark.asyncio`. Match the existing test file's style exactly.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd server && uv run pytest apps/agent/tests/integration/test_gateway_finance_coach.py -v`
Expected: FAIL — route doesn't exist (404 on first test); R1 doesn't recognize `finance-coach` (second test likely 400 "未知 app" not 409).

- [ ] **Step 3: Add the gateway route**

In `server/apps/agent/app/routers/gateway.py`, after the asset-report route block (after line 294), add:

```python
class FinanceCoachRunRequest(BaseModel):
    """Request body for internal finance-coach run trigger (backend → agent).

    Plan A: the backend /ai/finance-coach/generate endpoint calls this after
    passing its own require_ai_enabled + require_adult + per-family concurrency
    gate. Trust model mirrors ``AssetReportRunRequest``: family_id is trusted
    because the endpoint requires ``X-Agent-Token`` and the backend passes
    JWT-derived family_id (R1 internal bypass — see ``start_run(internal=True)``).
    """

    family_id: str
    user_id: str | None = None
    input: dict[str, Any] | None = None
    on_disconnect: str = "cancel"


@router.post("/runs/finance-coach/{thread_id}")
async def trigger_finance_coach_run(
    thread_id: str,
    body: FinanceCoachRunRequest,
    request: Request,
    x_agent_token: str = Header(..., alias="X-Agent-Token"),
) -> StreamingResponse:
    """Trigger a finance-coach stream_run from the backend (service-to-service).

    Plan A: the backend finance-coach trigger creates a stream_run with
    ``app="finance-coach"`` via this X-Agent-Token-authenticated endpoint,
    bypassing R1's frontend 409 gate (internal=True). The worker's
    ``_run_finance_coach_agent`` then drives the single-run advice agent and
    emits a ``finance_coach.result`` custom event with the validated
    ``suggestions[]`` JSON; this endpoint streams frames back as SSE for the
    backend to forward to the frontend (D2 dashboard card).
    """
    _verify_token(x_agent_token)
    _validate_path_segment(thread_id, "thread_id")

    # Build a duck-typed body matching start_run's getattr() access pattern.
    run_body = SimpleNamespace(
        assistant_id=None,
        input=body.input,
        config=None,
        metadata={"app": "finance-coach"},
        on_disconnect=body.on_disconnect,
        multitask_strategy="reject",
    )

    record = await start_run(
        run_body,
        thread_id,
        request,
        body.family_id,
        body.user_id,
        internal=True,
    )
    run_mgr = get_run_manager(request)

    async def sse_generator():
        async for frame in sse_consumer(
            get_stream_bridge(request), record, request, run_mgr
        ):
            yield frame

    return StreamingResponse(
        sse_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Content-Location": f"/internal/gateway/runs/finance-coach/{thread_id}/{record.run_id}",
        },
    )
```

- [ ] **Step 4: Add finance-coach to the R1 allowlist**

In `server/apps/agent/services/runtime/sse_gateway.py`, update the R1 gate block (lines 183-197). After the `import-parse` 409 block (line 190-195) and before the final 400 line (196), add a `finance-coach` 409 block; then extend the 400 line:

```python
    if not internal and app == "finance-coach":
        raise _app_rejected_error(
            status_code=409,
            app=app,
            reason="财务教练建议须经由后端 /ai/finance-coach/generate 端点，请勿直连 /runs/stream",
        )
    if app != "numina" and app != "asset-report" and app != "import-parse" and app != "finance-coach":
        raise _app_rejected_error(status_code=400, app=app, reason="未知的 app 值")
```

Also update the comment block (lines 165-181) to add a `finance-coach` bullet:

```python
    #   - "finance-coach": REJECTED direct (Plan A) — the advice pipeline must
    #     be entered via the backend /ai/finance-coach/generate endpoint, which
    #     enforces require_ai_enabled + require_adult + per-family concurrency
    #     gating. SKIPPED for internal callers (backend trigger via X-Agent-Token
    #     gateway) — those have already passed the backend's auth gate.
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd server && uv run pytest apps/agent/tests/integration/test_gateway_finance_coach.py -v`
Expected: all 3 tests PASS.

- [ ] **Step 6: Run existing gateway tests for regression**

Run: `cd server && uv run pytest apps/agent/tests/integration/test_gateway_asset_report.py apps/agent/tests/integration/test_u2_app_dispatch.py -v`
Expected: all PASS (the R1 allowlist edit must not break asset-report/import-parse/numina dispatch).

- [ ] **Step 7: Lint + typecheck**

Run: `cd server && uv run ruff check apps/agent/app/routers/gateway.py apps/agent/services/runtime/sse_gateway.py apps/agent/tests/integration/test_gateway_finance_coach.py && uv run mypy apps/agent/app/routers/gateway.py apps/agent/services/runtime/sse_gateway.py`
Expected: no errors.

- [ ] **Step 8: Commit**

```bash
git add server/apps/agent/app/routers/gateway.py server/apps/agent/services/runtime/sse_gateway.py server/apps/agent/tests/integration/test_gateway_finance_coach.py
git commit -m "feat(agent-gateway): add finance-coach route + R1 allowlist slot (Plan A T5)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: Worker dispatch branch — `_run_finance_coach_agent`

**Files:**
- Modify: `server/apps/agent/services/runtime/worker.py`
  - add `_SYNTHETIC_FINANCE_COACH_TRIGGER` constant (near line 634, after `_SYNTHETIC_IMPORT_PARSE_TRIGGER`)
  - add `if app == "finance-coach":` dispatch branch (after the `import-parse` branch, lines 253-264, before the default `numina` branch at line 265)
  - add new async function `_run_finance_coach_agent` (after `_run_import_parse_agent` ends at line 906, before `_run_numina_agent` at line 909)
- Test: `server/apps/agent/tests/unit/test_worker_finance_coach.py`

**Interfaces:**
- Consumes: `BackendClient`, `FamilyContext`, `pii_redactor`, `create_family_adapter`, `set_active_skill`/`reset_active_skill`, `parse_report_json` (all already imported in worker.py), `AuditEntry`/`audit_logger`, `set_family_sandbox_context`. The `app` value `"finance-coach"` is set by the gateway route (Task 5) via `metadata={"app": "finance-coach"}`.
- Produces: when the backend (Task 8) triggers `/internal/gateway/runs/finance-coach/{thread_id}`, the worker dispatches here. The agent runs a single `typed_stream_dispatch` with `skill_name="finance-coach"` (Task 4 SKILL.md), forwards SSE frames, and emits exactly one `finance_coach.result` custom event with `{"suggestions": [...]}` before the `end` frame. The backend caches this (Task 7/8) and the frontend (Plan B D2) renders the top 3 suggestions.

- [ ] **Step 1: Write the failing test**

Create `server/apps/agent/tests/unit/test_worker_finance_coach.py`:

```python
"""finance-coach worker dispatch branch unit tests (Plan A T6).

Verifies the dispatch branch is wired and the agent function exists with the
right signature + custom-event contract. Full SSE integration is covered by
test_gateway_finance_coach.py (T5) + a later capability-cache integration test.
"""
import inspect

from apps.agent.services.runtime import worker


def test_finance_coach_dispatch_branch_exists():
    """The worker source has an `if app == "finance-coach":` branch."""
    src = inspect.getsource(worker)
    assert 'if app == "finance-coach":' in src


def test_run_finance_coach_agent_exists_with_expected_signature():
    """`_run_finance_coach_agent` mirrors `_run_import_parse_agent` signature."""
    fn = getattr(worker, "_run_finance_coach_agent", None)
    assert fn is not None, "worker._run_finance_coach_agent must be defined"
    assert inspect.iscoroutinefunction(fn), "must be async"
    sig = inspect.signature(fn)
    expected = {
        "bridge", "run_manager", "record", "family_id", "user_id",
        "thread_id", "graph_input", "config",
    }
    assert expected.issubset(set(sig.parameters)), (
        f"missing params: {expected - set(sig.parameters)}"
    )


def test_synthetic_finance_coach_trigger_constant():
    """The skill-load fallback trigger message exists."""
    assert hasattr(worker, "_SYNTHETIC_FINANCE_COACH_TRIGGER")
    assert "/finance-coach" in worker._SYNTHETIC_FINANCE_COACH_TRIGGER
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd server && uv run pytest apps/agent/tests/unit/test_worker_finance_coach.py -v`
Expected: FAIL — `test_run_finance_coach_agent_exists_with_expected_signature` fails (`_run_finance_coach_agent` not defined) and `test_finance_coach_dispatch_branch_exists` fails (no branch yet).

- [ ] **Step 3: Add the synthetic trigger constant**

In `server/apps/agent/services/runtime/worker.py`, after line 634 (`_SYNTHETIC_IMPORT_PARSE_TRIGGER = "/import-parse 解析金融文档持仓"`), add:

```python
_SYNTHETIC_FINANCE_COACH_TRIGGER = "/finance-coach 生成家庭财务建议"
```

- [ ] **Step 4: Add the dispatch branch**

In the dispatch function (lines 253-264), after the `import-parse` branch's `return` (line 264) and before the `# Default / "numina"` comment (line 265), add:

```python
        if app == "finance-coach":
            await _run_finance_coach_agent(
                bridge=bridge,
                run_manager=run_manager,
                record=record,
                family_id=family_id,
                user_id=user_id,
                thread_id=thread_id,
                graph_input=graph_input,
                config=config,
            )
            return
```

Also update the docstring app list (lines 221-224) to add the bullet:

```python
      - ``finance-coach`` → ``_run_finance_coach_agent`` (Plan A single-run advice).
```

- [ ] **Step 5: Add the `_run_finance_coach_agent` function**

In `server/apps/agent/services/runtime/worker.py`, after `_run_import_parse_agent` ends (line 906, the `schedule_run_cleanup(...)` line) and before `async def _run_numina_agent(` (line 909), add the function below. It mirrors `_run_import_parse_agent` (lines 657-906) exactly, with these changes: `skill_name="finance-coach"`, `agent_name="finance-coach"`, capability `"finance-coach"`, the snapshot injected from `graph_input` (backend builds it; see Task 8), and a `finance_coach.result` custom event. Use `parse_report_json` (already imported) to extract the JSON from the LLM's final ```json block.

```python
async def _run_finance_coach_agent(
    *,
    bridge: StreamBridge,
    run_manager: RunManager,
    record: RunRecord,
    family_id: str,
    user_id: str | None,
    thread_id: str,
    graph_input: dict | None,
    config: dict[str, Any],
) -> None:
    """finance-coach (4th stream_run agent) dispatch branch (Plan A).

    Runs a single ``stream_run`` agent run via ``adapter.typed_stream_dispatch``
    with ``skill_name="finance-coach"``. The skill prompt (see
    ``skills/builtin/public/finance-coach/SKILL.md``) drives the LLM to read the
    family finance snapshot (injected by the backend as the run's user message)
    and emit a single ```json block with ``{suggestions: [...]}``. The worker
    forwards frames, synthesizes tool_call/tool_result custom events (chat
    renderer reuse), and emits exactly one ``finance_coach.result`` custom event
    with the parsed payload before the ``end`` frame (mirrors import-parse's
    worker-synthesized emission).

    Differences vs import-parse:
    - ``skill_name="finance-coach"`` (fixed system flow, KTD-8).
    - The user message is the backend-injected family finance snapshot JSON
      (preferred) or the synthetic slash trigger (skill-load fallback).
    - PII minimization (spec §7.1): the backend builds the snapshot with
      ``id + category`` (not ``name``); pii_redactor still runs on the message
      as defense-in-depth.
    - finance-coach is stateless (``memory_enabled=False``) — each run builds a
      fresh snapshot, no DeerMem pollution.
    """
    run_id = record.run_id
    t_start = time.monotonic()
    success = False
    error_type: str | None = None
    completion_status = "error"
    ai_response_parts: list[str] = []
    cumulative_usage: dict[str, int] | None = None

    try:
        # 1. Mark running + publish metadata (DeerFlow pattern)
        await run_manager.set_status(run_id, RunStatus.running)
        await bridge.publish(
            run_id,
            "metadata",
            {"run_id": run_id, "thread_id": thread_id},
        )

        # 2. Fetch per-family AI config (tenant-isolated) — mirrors import-parse.
        client = BackendClient(family_id=family_id)
        ai_config = await client.get_family_ai_config()
        providers = ai_config.get("providers", [])
        if not providers:
            raise RuntimeError("未配置 AI 供应商")
        selected_provider = next(
            (p for p in providers if p.get("is_active")), providers[0]
        )

        # 3. Fetch enabled MCP servers (same MCP-setup as import-parse).
        try:
            mcp_servers = await client.get_enabled_mcp_servers()
            for srv in mcp_servers:
                if srv.get("name") == "Numina Backend MCP":
                    expected_prefix = settings.BACKEND_BASE_URL.rstrip("/")
                    actual_url = (srv.get("url") or "").rstrip("/")
                    if not actual_url.startswith(expected_prefix):
                        srv["url"] = (
                            expected_prefix
                            + "/api/v1/internal/mcp/"
                            + family_id
                            + "/sse"
                        )
                    mcp_headers: dict[str, str] = {
                        "X-Agent-Token": settings.AGENT_INTERNAL_TOKEN,
                        "X-Family-Id": family_id,
                    }
                    if user_id:
                        mcp_headers["X-Caller-User-Id"] = user_id
                    srv["headers"] = mcp_headers
                    break
        except Exception as exc:
            logger.warning(
                "[_run_finance_coach_agent] get_enabled_mcp_servers failed family=%s err=%s",
                family_id, type(exc).__name__,
            )
            mcp_servers = []

        # 4. Build adapter. plan_mode=False (fixed advice flow, no TodoList).
        from apps.agent.services.agent_registry import get_agent_registry
        agent_meta = await get_agent_registry().get("finance-coach", family_id)
        memory_enabled = bool(agent_meta.get("memory_enabled", True)) if agent_meta else True

        adapter = create_family_adapter(
            family_id,
            selected_provider,
            timeout_seconds=120,
            subagent_enabled=False,
            plan_mode=False,
            mcp_servers=mcp_servers,
            agent_name="finance-coach",
            memory_enabled=memory_enabled,
        )

        # 5. User message = backend-injected snapshot (preferred) or synthetic
        # slash trigger (skill-load fallback). The snapshot is JSON the backend
        # posts as the run's user message content (see Task 8 backend trigger).
        user_message = _extract_finance_coach_snapshot(graph_input) or _SYNTHETIC_FINANCE_COACH_TRIGGER

        # 6. PII redaction (Key Invariant #1) — defense-in-depth; backend already
        # minimized PII (id+category, no name) per spec §7.1.
        context = FamilyContext(family_id=family_id, free_text=user_message)
        redacted = pii_redactor.redact(context)

        # 7. Stream via typed_stream_dispatch → publish to bridge. Set the active
        # skill so sync_tool_patch filters tools to finance-coach's allowed-tools.
        from apps.agent.services.deerflow_adapter.active_skill_context import (
            set_active_skill,
        )
        _skill_token = set_active_skill("finance-coach")
        async for sse_type, data in adapter.typed_stream_dispatch(
            skill_name="finance-coach",
            context=redacted,
            thread_id=thread_id,
            enable_thinking=False,  # single-run advice, keep latency bounded
        ):
            if record.abort_event.is_set():
                break

            if sse_type == "end":
                if isinstance(data, dict) and data.get("usage"):
                    raw_usage = data["usage"]
                    cumulative_usage = {
                        "input_tokens": raw_usage.get("input_tokens", 0),
                        "output_tokens": raw_usage.get("output_tokens", 0),
                        "total_tokens": raw_usage.get("total_tokens", 0),
                    }
                break
            if sse_type == "error":
                await bridge.publish(run_id, "error", data)
                break

            # Forward the canonical frame (messages / values / custom).
            await bridge.publish(run_id, sse_type, data)

            # Mirror import-parse: collect AI text + synthesize tool_call/
            # tool_result custom events so the frontend reuses the chat renderer.
            if sse_type == "messages" and isinstance(data, dict):
                msg_type = data.get("type")
                if msg_type == "ai":
                    content = data.get("content")
                    if content:
                        ai_response_parts.append(content)
                    tool_calls = data.get("tool_calls")
                    if tool_calls:
                        for tc in extract_tool_calls(data):
                            raw_name = tc.get("name", "")
                            tool_type, display_name, icon, display_key = resolve_tool_metadata(raw_name)
                            payload: dict[str, Any] = {
                                "type": "tool_call",
                                "tool_call_id": tc.get("id", ""),
                                "tool_name": raw_name,
                                "args": tc.get("args", {}),
                                "display_name": display_name,
                                "icon": icon,
                                "tool_type": tool_type,
                            }
                            if display_key:
                                payload["display_key"] = display_key
                            await bridge.publish(run_id, "custom", payload)
                elif msg_type == "tool":
                    tool_call_id = str(data.get("tool_call_id") or "")
                    tool_name = data.get("name") or ""
                    content = data.get("content")
                    if tool_call_id:
                        await bridge.publish(run_id, "custom", {
                            "type": "tool_result",
                            "tool_call_id": tool_call_id,
                            "tool_name": tool_name,
                            "content": content,
                        })

        # 8. Terminal status.
        if record.abort_event.is_set():
            await run_manager.set_status(run_id, RunStatus.interrupted)
            completion_status = "interrupted"
        else:
            await run_manager.set_status(run_id, RunStatus.success)
            completion_status = "complete"
            success = record.status == RunStatus.success

        # 9. Worker-synthesized finance_coach.result emission (mirrors import-parse
        # worker synthesis). Emit exactly one finance_coach.result before the end
        # frame. parse_report_json extracts the ```json block the LLM produced.
        if completion_status == "complete":
            ai_text = "".join(ai_response_parts)
            parsed = parse_report_json(ai_text)
            if parsed is not None:
                # Advice baseline (spec §7.1): the worker emits the raw parsed
                # suggestions. Schema-validation gate (suggested_amount >= 0,
                # required fields) runs in Plan B's D2/W4 UI before any enable;
                # a malformed payload is dropped there, not here (the worker is
                # transport, not policy).
                await bridge.publish(run_id, "custom", {
                    "type": "finance_coach.result",
                    "payload": parsed,
                })

    except asyncio.CancelledError:
        error_type = "Cancelled"
        await run_manager.set_status(run_id, RunStatus.interrupted)
        raise
    except Exception as exc:
        error_type = type(exc).__name__
        logger.warning("[_run_finance_coach_agent] failed run=%s err=%s", run_id, error_type)
        await run_manager.set_status(run_id, RunStatus.error, error=str(exc))
        await bridge.publish(
            run_id,
            "error",
            {"message": str(exc), "name": error_type},
        )

    finally:
        # Clear the active-skill ContextVar so it cannot leak into a later run.
        if "_skill_token" in locals():
            from apps.agent.services.deerflow_adapter.active_skill_context import (
                reset_active_skill,
            )
            reset_active_skill(_skill_token)

        # 10. Audit log (Key Invariant #3)
        audit_logger.log_call(
            AuditEntry(
                family_id=family_id,
                audit_id=run_id,
                user_id=user_id or "",
                capability="finance-coach",
                success=success,
                error_type=error_type,
                deerflow_attempted=True,
                duration_ms=int((time.monotonic() - t_start) * 1000),
            )
        )

        # 11. Terminal end frame + sentinel + deferred cleanup (DeerFlow pattern).
        end_payload = {"status": completion_status}
        if cumulative_usage:
            end_payload["usage"] = cumulative_usage
        await bridge.publish(run_id, "end", end_payload)

        await bridge.publish_end(run_id)
        asyncio.create_task(bridge.cleanup(run_id, delay=60))
        asyncio.create_task(schedule_run_cleanup(run_manager, run_id, delay=300))


def _extract_finance_coach_snapshot(graph_input: dict | None) -> str | None:
    """Pull the family finance snapshot JSON the backend injected as the run's
    user message (mirrors ``_extract_import_parse_document``).

    The backend (Task 8) posts the snapshot as ``messages[-1]`` content of the
    stream_run input. Returns None when no user message is present (caller falls
    back to the synthetic trigger).
    """
    if not graph_input or not isinstance(graph_input, dict):
        return None
    msgs = graph_input.get("messages")
    if not isinstance(msgs, list) or not msgs:
        return None
    last = msgs[-1]
    if isinstance(last, dict) and last.get("role") in ("user", "human"):
        content = last.get("content", "")
        if isinstance(content, str) and content.strip():
            return content
    return None
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd server && uv run pytest apps/agent/tests/unit/test_worker_finance_coach.py -v`
Expected: all 3 tests PASS.

- [ ] **Step 7: Lint + typecheck**

Run: `cd server && uv run ruff check apps/agent/services/runtime/worker.py apps/agent/tests/unit/test_worker_finance_coach.py && uv run mypy apps/agent/services/runtime/worker.py`
Expected: no errors.

- [ ] **Step 8: Commit**

```bash
git add server/apps/agent/services/runtime/worker.py server/apps/agent/tests/unit/test_worker_finance_coach.py
git commit -m "feat(agent-worker): add finance-coach dispatch branch + agent (Plan A T6)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: Alembic migration — add `capability` column to `ai_reports` + capability-cache service

**Files:**
- Create: `server/apps/backend/alembic/versions/b9c7d2e4f6a8_add_capability_to_ai_reports.py`
- Modify: `server/apps/backend/app/models/ai_report.py` — add `capability: Mapped[str]` column (line ~30, after `markdown_file_path`)
- Create: `server/apps/backend/app/services/finance_coach_cache.py`
- Test: `server/tests/backend/services/test_finance_coach_cache.py`

**Interfaces:**
- Consumes: `down_revision = "c4d5e6f7a8b9"` (the finance-coach system-agent migration from Task 2 — so the head stays linear). Existing `AIReport` model + `_latest_report` (ai_report.py:47).
- Produces:
  - `ai_reports.capability VARCHAR(32) NOT NULL DEFAULT 'report'` column + index on `(family_id, capability, status)`. Existing rows backfill to `'report'` (via server_default), so existing report queries are unaffected.
  - `finance_coach_cache.py` exposes: `CAPABILITY_TTL: dict[str, timedelta]`, `latest_by_capability(family_id, capability, db) -> AIReport | None`, `upsert_capability_result(family_id, capability, payload: dict, db) -> AIReport`, `invalidate_capability(family_id, capability, db) -> None`. Task 8 (backend trigger) + Plan B entity-change invalidation call these.

- [ ] **Step 1: Write the failing test**

Create `server/tests/backend/services/test_finance_coach_cache.py`:

```python
"""capability-cache isolation + invalidation (Plan A T7)."""
from datetime import datetime, timedelta, timezone

from apps.backend.app.models.ai_report import AIReport
from apps.backend.app.services.finance_coach_cache import (
    CAPABILITY_TTL,
    invalidate_capability,
    latest_by_capability,
    upsert_capability_result,
)


def _naive_utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def test_latest_by_capability_isolates_finance_coach_from_report(db_session):
    """finance_coach and report rows do not cross-pollute (spec §7.2 core issue 1)."""
    # A 'report' row exists for the family.
    upsert_capability_result(db_session, "fam-1", "report", {"score": 80})
    # A 'finance_coach' row exists for the same family.
    upsert_capability_result(db_session, "fam-1", "finance_coach", {"suggestions": []})

    report_latest = latest_by_capability(db_session, "fam-1", "report")
    coach_latest = latest_by_capability(db_session, "fam-1", "finance_coach")

    assert report_latest is not None and report_latest.capability == "report"
    assert coach_latest is not None and coach_latest.capability == "finance_coach"
    # The two latest rows are NOT the same row.
    assert report_latest.id != coach_latest.id


def test_invalidate_capability_deletes_only_that_capability(db_session):
    """Invalidating finance_coach does not touch the family's report row."""
    upsert_capability_result(db_session, "fam-2", "report", {"score": 90})
    upsert_capability_result(db_session, "fam-2", "finance_coach", {"suggestions": [{"id": "s1"}]})

    invalidate_capability(db_session, "fam-2", "finance_coach")

    assert latest_by_capability(db_session, "fam-2", "finance_coach") is None
    assert latest_by_capability(db_session, "fam-2", "report") is not None  # untouched


def test_invalidate_capability_scoped_to_one_family(db_session):
    """Invalidating fam-3's finance_coach does not delete fam-4's finance_coach."""
    upsert_capability_result(db_session, "fam-3", "finance_coach", {"suggestions": []})
    upsert_capability_result(db_session, "fam-4", "finance_coach", {"suggestions": []})

    invalidate_capability(db_session, "fam-3", "finance_coach")

    assert latest_by_capability(db_session, "fam-3", "finance_coach") is None
    assert latest_by_capability(db_session, "fam-4", "finance_coach") is not None


def test_capability_ttl_has_report_and_finance_coach_entries():
    assert "report" in CAPABILITY_TTL
    assert "finance_coach" in CAPABILITY_TTL
    assert CAPABILITY_TTL["report"] == timedelta(hours=8)
    assert CAPABILITY_TTL["finance_coach"] == timedelta(hours=8)


def test_upsert_capability_result_sets_capability_column(db_session):
    row = upsert_capability_result(db_session, "fam-5", "finance_coach", {"suggestions": []})
    assert row.capability == "finance_coach"
    assert row.status == "completed"
    assert row.family_id == "fam-5" or str(row.family_id) == "fam-5"
```

> **Fixture note:** confirm the DB session fixture name in `server/tests/backend/conftest.py` — if it's `session` not `db_session`, rename the parameter in every test above. The `family_id` is passed as a `str` here (matching how `ai_report.py` receives `current_user.family_id` as str); `upsert_capability_result` coerces to int internally (see implementation below).

- [ ] **Step 2: Run test to verify it fails**

Run: `cd server && uv run pytest tests/backend/services/test_finance_coach_cache.py -v`
Expected: FAIL — `ImportError: cannot import name 'CAPABILITY_TTL'` (service module + column don't exist yet).

- [ ] **Step 3: Create the migration**

Create `server/apps/backend/alembic/versions/b9c7d2e4f6a8_add_capability_to_ai_reports.py`:

```python
"""add capability column to ai_reports

Revision ID: b9c7d2e4f6a8
Revises: c4d5e6f7a8b9
Create Date: 2026-07-19

Plan A: the existing ai_reports cache (ai_report.py _latest_report) filters only
by (family_id, status='completed') with NO capability column — a finance_coach
row would collide with the report row for the same family (spec §7.2 core issue 1).
This migration adds ``capability VARCHAR(32) NOT NULL DEFAULT 'report'`` so:
  - existing rows backfill to 'report' (server_default covers them; no data fixup
    needed) and existing report queries are unaffected once the model/router also
    filter by capability (Task 8 + the _latest_report update below).
  - three independent cache keys coexist: family_id:report (existing),
    family_id:finance_coach (D2), family_id:wish_advice:{fingerprint} (Plan B W4).
Index on (family_id, capability, status) makes the latest-by-capability lookup
sub-millisecond.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b9c7d2e4f6a8"
down_revision: str | None = "c4d5e6f7a8b9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "ai_reports",
        sa.Column(
            "capability",
            sa.String(length=32),
            nullable=False,
            server_default="report",
        ),
    )
    op.create_index(
        "ix_ai_reports_family_capability_status",
        "ai_reports",
        ["family_id", "capability", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_ai_reports_family_capability_status", table_name="ai_reports")
    op.drop_column("ai_reports", "capability")
```

- [ ] **Step 4: Add the `capability` column to the model**

In `server/apps/backend/app/models/ai_report.py`, after the `markdown_file_path` column (line ~30), add:

```python
    # Plan A: capability scoping. 'report' (existing, default) | 'finance_coach' |
    # 'wish_advice' (Plan B W4). server_default='report' keeps existing rows valid
    # without a data backfill migration. _latest_report / latest_by_capability
    # filter by (family_id, capability, status).
    capability: Mapped[str] = mapped_column(String(32), nullable=False, default="report", server_default="report")
```

(If `String` is not imported in the model file, add it to the existing `from sqlalchemy import ...` import line.)

- [ ] **Step 5: Create the capability-cache service**

Create `server/apps/backend/app/services/finance_coach_cache.py`:

```python
"""Capability-scoped cache layer on ai_reports (Plan A T7).

The existing report cache (ai_report.py `_latest_report` + `REPORT_CACHE_TTL`)
filters only by (family_id, status='completed') with NO capability distinction —
a finance_coach row would collide with the report row for the same family (spec
§7.2 core issue 1). This module adds capability-scoped read/write/invalidate so
the three cache keys coexist without pollution:

  - family_id:report         (existing asset-report, TTL 8h)
  - family_id:finance_coach  (D2 dashboard card, TTL 8h, entity-change invalidation)
  - family_id:wish_advice:{fingerprint}  (Plan B W4, separate cache key — not here)

Entity-change invalidation: any asset/liability/wish write (Task 9) calls
``invalidate_capability(family_id, "finance_coach", db)`` so the next dashboard
load regenerates with fresh data (spec §7.2: event-driven, not pure TTL).
"""
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from apps.backend.app.models.ai_report import AIReport
from packages.core.snowflake import next_id  # confirm import path in ai_report.py:22

# Parametric TTL per capability (spec §7.2: non-hardcoded). Initial 8h for all.
CAPABILITY_TTL: dict[str, timedelta] = {
    "report": timedelta(hours=8),
    "finance_coach": timedelta(hours=8),
}


def _family_id_int(family_id: str | int) -> int:
    """Coerce the str family_id (snowflake-as-string convention) to int for the
    BigInteger column."""
    return int(family_id)


def latest_by_capability(
    db: Session, family_id: str | int, capability: str
) -> AIReport | None:
    """Return the most recent completed AIReport for (family, capability), or None."""
    return (
        db.query(AIReport)
        .filter(
            AIReport.family_id == _family_id_int(family_id),
            AIReport.capability == capability,
            AIReport.status == "completed",
        )
        .order_by(AIReport.generated_at.desc())
        .first()
    )


def is_cache_fresh(row: AIReport | None, capability: str) -> bool:
    """True if the row exists and is younger than the capability's TTL."""
    if row is None or row.generated_at is None:
        return False
    ttl = CAPABILITY_TTL.get(capability, timedelta(hours=8))
    age = datetime.now(timezone.utc).replace(tzinfo=None) - row.generated_at  # noqa: UP017
    return age < ttl


def upsert_capability_result(
    db: Session,
    family_id: str | int,
    capability: str,
    payload: dict[str, Any],
) -> AIReport:
    """Persist a capability result as a completed AIReport row and return it.

    The caller (Task 8 backend trigger) commits the transaction. We do NOT
    invalidate other capabilities here — cross-capability invalidation is the
    entity-change hook's job (Task 9).
    """
    row = AIReport(
        id=next_id(),
        family_id=_family_id_int(family_id),
        report_json=payload,
        status="completed",
        capability=capability,
        generated_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    db.add(row)
    db.flush()  # get the id without committing (caller commits)
    return row


def invalidate_capability(
    db: Session, family_id: str | int, capability: str
) -> None:
    """Delete all completed rows for (family, capability).

    Called on entity-change (asset/liability/wish write — Task 9) so the next
    read regenerates. Deletes only the given capability (does not touch 'report'
    when invalidating 'finance_coach', and vice versa). The caller commits.
    """
    db.query(AIReport).filter(
        AIReport.family_id == _family_id_int(family_id),
        AIReport.capability == capability,
    ).delete(synchronize_session=False)
```

> **Import check:** confirm `next_id`'s import path. `ai_report.py:22` has `default=next_id` — read its import line and use the same path. If it's `from packages.core.snowflake import next_id`, use that; if it's a local `from ... import next_id`, mirror it exactly.

- [ ] **Step 6: Run the migration**

Run: `cd server/apps/backend && uv run alembic upgrade head`
Expected: revision `b9c7d2e4f6a8` applies; `alembic current` shows `b9c7d2e4f6a8 (head)`.

- [ ] **Step 7: Run test to verify it passes**

Run: `cd server && uv run pytest tests/backend/services/test_finance_coach_cache.py -v`
Expected: all 5 tests PASS.

- [ ] **Step 8: Verify report regression — existing report cache still works**

Run: `cd server && uv run pytest tests/backend/test_ai_report.py -v 2>/dev/null || uv run pytest tests/backend/routers/ -k report -v`
Expected: existing report tests still PASS (the column has server_default='report', so existing report rows read back with capability='report'). If a test asserts the exact column set of AIReport, update it to include `capability`.

- [ ] **Step 9: Update `_latest_report` + `REPORT_CACHE_TTL` in ai_report.py to be capability-aware**

In `server/apps/backend/app/routers/ai_report.py`, update `_latest_report` (line 47) to scope by capability='report' (keeps existing report behavior identical) and read TTL from the new map:

```python
def _latest_report(family_id: str, db: Session) -> AIReport | None:
    from apps.backend.app.services.finance_coach_cache import latest_by_capability
    return latest_by_capability(db, family_id, "report")
```

And replace the `REPORT_CACHE_TTL = timedelta(hours=8)` constant (line 62) with:

```python
from apps.backend.app.services.finance_coach_cache import CAPABILITY_TTL
REPORT_CACHE_TTL = CAPABILITY_TTL["report"]  # keep existing report behavior
```

(Keep the `timedelta` import if still used elsewhere in the file; ruff will flag if unused.)

- [ ] **Step 10: Lint + typecheck**

Run: `cd server && uv run ruff check apps/backend/app/models/ai_report.py apps/backend/app/services/finance_coach_cache.py apps/backend/app/routers/ai_report.py tests/backend/services/test_finance_coach_cache.py && uv run mypy apps/backend/app/models/ai_report.py apps/backend/app/services/finance_coach_cache.py apps/backend/app/routers/ai_report.py`
Expected: no errors.

- [ ] **Step 11: Commit**

```bash
git add server/apps/backend/alembic/versions/b9c7d2e4f6a8_add_capability_to_ai_reports.py server/apps/backend/app/models/ai_report.py server/apps/backend/app/services/finance_coach_cache.py server/apps/backend/app/routers/ai_report.py server/tests/backend/services/test_finance_coach_cache.py
git commit -m "feat(cache): add capability column + finance_coach cache service (Plan A T7)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 8: Backend trigger endpoint `POST /ai/finance-coach/generate`

**Files:**
- Create: `server/apps/backend/app/routers/ai_finance_coach.py`
- Modify: `server/apps/backend/app/main.py` (or wherever routers are registered) — register the new router
- Create: `server/apps/backend/app/services/finance_coach_snapshot.py` — builds the PII-minimized family finance snapshot the worker ingests
- Test: `server/tests/backend/routers/test_ai_finance_coach.py`

**Interfaces:**
- Consumes:
  - `require_adult` (`apps.backend.app.auth.deps`), `require_ai_enabled` + `require_owner` (`apps.backend.app.auth.ai_deps`) — mirror `trigger_generate_events` (ai_report.py:123-129).
  - `check_circuit_blocked(family_id, capability, db)` (`apps.backend.app.routers._ai_events_helper`) — ai_report.py:136 uses `capability="report"`; finance_coach uses `capability="finance_coach"`.
  - `AgentClient(family_id, user_id, timeout=300.0)` (`apps.backend.app.services.agent_client`) — calls `/internal/gateway/runs/finance-coach/{thread_id}` (Task 5 route). Mirror `_stream_asset_report_sse` (ai_report.py:77-119).
  - `latest_by_capability` / `is_cache_fresh` / `upsert_capability_result` (Task 7 service).
  - Existing models: `Asset`, `Liability`, `Wish`, `User`/`FamilyMember` — for building the snapshot.
- Produces:
  - `POST /ai/finance-coach/generate?force=false` → SSE stream (proxied from the agent gateway) OR cached JSON 200. The stream carries the worker's `finance_coach.result` custom event (Task 6); the backend also persists the result to `ai_reports` (capability='finance_coach') after the stream completes, so the next call within 8h returns the cache.
  - `finance_coach_snapshot.py` exposes `build_family_finance_snapshot(db, family_id) -> dict` — the PII-minimized snapshot (id+category, no name) per spec §7.1.

- [ ] **Step 1: Write the failing test**

Create `server/tests/backend/routers/test_ai_finance_coach.py`:

```python
"""finance_coach trigger endpoint: cache hit / miss / force / circuit breaker (Plan A T8)."""
from unittest.mock import patch


def test_generate_returns_cached_when_fresh(client, auth_headers, db_session):
    """A cached finance_coach row younger than 8h is returned as JSON (non-stream)."""
    from apps.backend.app.services.finance_coach_cache import upsert_capability_result
    upsert_capability_result(
        db_session, "fam-test", "finance_coach",
        {"suggestions": [{"id": "s1", "severity": "high", "title": "x", "action": "y",
                          "target_type": "liability", "target_id": "1", "cta_label": "去"}]},
    )
    db_session.commit()

    with patch("apps.backend.app.routers.ai_finance_coach.check_circuit_blocked", return_value=None):
        resp = client.post("/api/v1/ai/finance-coach/generate", headers=auth_headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "cached"
    assert body["report"]["suggestions"][0]["id"] == "s1"


def test_generate_force_bypasses_cache(client, auth_headers, db_session):
    """force=true skips the cache and regenerates (streams)."""
    from apps.backend.app.services.finance_coach_cache import upsert_capability_result
    upsert_capability_result(db_session, "fam-test", "finance_coach", {"suggestions": []})
    db_session.commit()

    with patch("apps.backend.app.routers.ai_finance_coach.check_circuit_blocked", return_value=None), \
         patch("apps.backend.app.routers.ai_finance_coach._stream_finance_coach_sse") as stream_mock:
        stream_mock.return_value = iter([b"event: end\ndata: {}\n\n"])
        resp = client.post(
            "/api/v1/ai/finance-coach/generate?force=true", headers=auth_headers
        )
    # force path streams (StreamingResponse 200) — the mock returns a frame.
    assert resp.status_code == 200


def test_generate_blocked_by_circuit_breaker(client, auth_headers):
    """When the circuit breaker is open, returns the blocked response."""
    blocked = {"status": "circuit_open", "message": "熔断中", "retry_after": 60}
    with patch("apps.backend.app.routers.ai_finance_coach.check_circuit_blocked", return_value=blocked):
        resp = client.post("/api/v1/ai/finance-coach/generate", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "circuit_open"
```

> **Fixture note:** confirm `client` + `auth_headers` fixture names in `server/tests/backend/conftest.py` and the API prefix (`/api/v1` per the existing routers — confirm by grepping an existing router test). If the prefix differs, adjust. The `family_id` in the upsert must match the authenticated user's family in the test setup; if the test user's family differs, use that family id.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd server && uv run pytest tests/backend/routers/test_ai_finance_coach.py -v`
Expected: FAIL — 404 (route not registered) / `ImportError` for the router module.

- [ ] **Step 3: Create the snapshot builder**

Create `server/apps/backend/app/services/finance_coach_snapshot.py`:

```python
"""Build the PII-minimized family finance snapshot for finance_coach (Plan A T8).

spec §7.1 PII minimization: the snapshot uses entity ``id + category`` (NOT
``name``) unless the prompt strictly requires a name. finance_coach's suggestions
link back by id, so name is dropped here. The snapshot is JSON-injected as the
run's user message; pii_redactor runs again in the worker as defense-in-depth.
"""
from typing import Any

from sqlalchemy.orm import Session

from apps.backend.app.models.asset import Asset
from apps.backend.app.models.liability import Liability
from apps.backend.app.models.wish import Wish


def _money(v: float | None) -> float:
    return float(v) if v is not None else 0.0


def build_family_finance_snapshot(db: Session, family_id: str | int) -> dict[str, Any]:
    """Return the family finance snapshot dict (PII-minimized: id+category, no name).

    Fields mirror spec §7.1 finance_coach input:
      net_worth, total_liabilities, high_interest_debts[], idle_assets[],
      top_daily_cost_assets[], wishes[].
    """
    fid = int(family_id)
    assets = db.query(Asset).filter(Asset.family_id == fid).all()
    liabilities = db.query(Liability).filter(Liability.family_id == fid, Liability.is_active.is_(True)).all()
    wishes = db.query(Wish).filter(Wish.family_id == fid, Wish.status == "pending").all()

    total_assets = sum(_money(a.current_value) for a in assets)
    total_liabilities = sum(_money(l.remaining_amount) for l in liabilities)
    net_worth = total_assets - total_liabilities

    # High-interest debts: rate >= 10% heuristic (the per-category threshold from
    # Plan B W5 is applied for *display* triggers; finance_coach gets the raw set
    # and the SKILL prompt identifies severity). monthly_interest = remaining * monthly_rate.
    high_interest_debts = []
    for l in liabilities:
        rate = _money(l.interest_rate) / 100.0 if l.interest_rate else 0.0
        if rate >= 0.10:
            monthly_interest = _money(l.remaining_amount) * (rate / 12.0)
            high_interest_debts.append({
                "id": str(l.id),
                "category": l.category,
                "rate": _money(l.interest_rate),
                "monthly_interest": round(monthly_interest, 2),
            })

    # Idle assets: usage_frequency == 'idle' if the column exists; else daily_cost>0 low-usage.
    # (Mirror whatever the dashboard low-usage query uses — confirm Asset columns.)
    idle_assets = []
    for a in assets:
        daily_cost = _money(getattr(a, "daily_cost", None))
        usage = getattr(a, "usage_frequency", None)
        if usage == "idle" or (daily_cost > 0 and usage in (None, "rare")):
            idle_assets.append({"id": str(a.id), "category": getattr(a, "category", None), "daily_cost": daily_cost})

    top_daily_cost_assets = sorted(
        ({"id": str(a.id), "category": getattr(a, "category", None),
          "daily_cost": _money(getattr(a, "daily_cost", None))} for a in assets),
        key=lambda x: x["daily_cost"], reverse=True,
    )[:5]

    # Wishes with a savings plan (spec §7.2 product-lens: filter out
    # saved_amount=0 AND monthly_saving=0 so the prompt focuses on actionable items).
    wish_snapshots = []
    for w in wishes:
        saved = _money(getattr(w, "saved_amount", None))
        monthly = _money(getattr(w, "monthly_saving", None))
        if saved == 0 and monthly == 0:
            continue
        wish_snapshots.append({
            "id": str(w.id),
            "price": _money(w.expected_price),
            "saved": saved,
            "monthly_saving": monthly,
            "target_date": str(w.target_date) if getattr(w, "target_date", None) else None,
        })

    return {
        "net_worth": round(net_worth, 2),
        "total_liabilities": round(total_liabilities, 2),
        "high_interest_debts": high_interest_debts,
        "idle_assets": idle_assets,
        "top_daily_cost_assets": top_daily_cost_assets,
        "wishes": wish_snapshots,
    }
```

> **Column check:** `saved_amount` / `monthly_saving` / `target_date` on `Wish` are added by **Plan B W1** (which runs after Plan A). In Plan A's test DB these columns may not exist yet — guard with `getattr(..., None)` (already done above) so the snapshot builder doesn't crash if the columns are absent. `Asset.daily_cost` / `usage_frequency` / `category` — confirm the actual column names by reading `server/apps/backend/app/models/asset.py` and adjust the `getattr` keys. `Liability.category` / `is_active` / `remaining_amount` / `interest_rate` are confirmed (Liability type on the frontend has these; verify the model column names match).

- [ ] **Step 4: Create the trigger endpoint router**

Create `server/apps/backend/app/routers/ai_finance_coach.py`:

```python
"""finance_coach trigger endpoint (Plan A T8).

- POST /api/v1/ai/finance-coach/generate?force=false
    8h capability-cache check -> cached JSON 200 (non-stream) OR stream_run via
    the agent gateway /internal/gateway/runs/finance-coach/{thread_id} (Task 5).
    Mirrors ai_report.trigger_generate_events but capability='finance_coach'.
"""
import json
import logging
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.orm import Session

from apps.backend.app.auth.ai_deps import require_ai_enabled, require_owner
from apps.backend.app.auth.deps import require_adult
from apps.backend.app.database import get_db
from apps.backend.app.models.user import User
from apps.backend.app.routers._ai_events_helper import check_circuit_blocked
from apps.backend.app.services.agent_client import AgentClient
from apps.backend.app.services.finance_coach_cache import (
    is_cache_fresh,
    latest_by_capability,
    upsert_capability_result,
)
from apps.backend.app.services.finance_coach_snapshot import build_family_finance_snapshot

router = APIRouter(prefix="/ai/finance-coach", tags=["ai-finance-coach"])
logger = logging.getLogger(__name__)


async def _stream_finance_coach_sse(
    *,
    family_id: str,
    user_id: str,
    thread_id: str,
    snapshot: dict,
) -> AsyncGenerator[bytes, None]:
    """Proxy the agent's finance-coach SSE stream (mirrors _stream_asset_report_sse).

    Calls the agent's /internal/gateway/runs/finance-coach/{thread_id} endpoint
    via AgentClient (X-Agent-Token service-to-service auth) and forwards raw SSE
    bytes. The worker (_run_finance_coach_agent) emits a finance_coach.result
    custom event; this helper is a pure passthrough. On stream end the caller
    persists the result to ai_reports (capability='finance_coach').
    """
    agent_client = AgentClient(family_id, user_id, timeout=300.0)
    agent_url = f"/internal/gateway/runs/finance-coach/{thread_id}"
    try:
        async with agent_client.stream(
            "POST",
            agent_url,
            json={
                "family_id": str(family_id),
                "user_id": str(user_id),
                # Inject the snapshot as the run's user message so the worker
                # (_extract_finance_coach_snapshot) picks it up.
                "input": {"messages": [{"role": "user", "content": json.dumps(snapshot, ensure_ascii=False)}]},
            },
        ) as resp:
            if resp.status_code != 200:
                body = await resp.aread()
                logger.warning(
                    "[finance-coach] agent stream non-200: status=%s body=%s",
                    resp.status_code, body[:200],
                )
                err = json.dumps({"message": "财务建议服务异常", "name": "AgentError"}).encode()
                yield f"event: error\ndata: {err.decode()}\n\n".encode()
                return
            collected = b""
            async for line in resp.aiter_lines():
                yield (line + "\n").encode()
                collected += (line + "\n").encode()
            # Persist the finance_coach.result payload to the capability cache.
            # The worker emits exactly one `event: custom` frame with
            # data.type == "finance_coach.result". Parse it out of the collected bytes.
            _persist_finance_coach_result(family_id, collected)
    except Exception as exc:
        logger.warning("[finance-coach] agent stream failed err=%s", type(exc).__name__)
        err = json.dumps({"message": "财务建议服务中断", "name": type(exc).__name__}).encode()
        yield f"event: error\ndata: {err.decode()}\n\n".encode()


def _persist_finance_coach_result(family_id: str, collected_sse: bytes) -> None:
    """Extract the finance_coach.result payload from the SSE bytes and cache it.

    Called after a successful stream. Opens a short-lived session (separate from
    the request's read-only db) to write the result row. Silently no-ops if the
    result frame is missing (advice baseline: wrong/absent output is dropped, not
    displayed — spec §7.1).
    """
    try:
        text = collected_sse.decode("utf-8", errors="replace")
        # SSE frames look like: event: custom\ndata: {"type":"finance_coach.result","payload":{...}}\n\n
        payload = None
        for block in text.split("\n\n"):
            if "finance_coach.result" not in block:
                continue
            for line in block.split("\n"):
                if line.startswith("data: "):
                    try:
                        data = json.loads(line[len("data: "):])
                        if data.get("type") == "finance_coach.result":
                            payload = data.get("payload")
                    except json.JSONDecodeError:
                        continue
        if payload is None:
            logger.info("[finance-coach] no finance_coach.result frame in stream — not caching")
            return
        from apps.backend.app.database import SessionLocal
        with SessionLocal() as db:
            upsert_capability_result(db, family_id, "finance_coach", payload)
            db.commit()
    except Exception as exc:
        logger.warning("[finance-coach] persist result failed err=%s", type(exc).__name__)


@router.post("/generate")
async def trigger_finance_coach(
    force: bool = False,
    current_user: User = Depends(require_adult),
    _ai: None = Depends(require_ai_enabled),
    _owner: None = Depends(require_owner),
    db: Session = Depends(get_db),
):
    """Trigger finance_coach generation (8h capability-cache + SSE stream).

    Mirrors trigger_generate_events: circuit breaker -> 8h cache check (force
    skips) -> stream_run via agent gateway. Cache hit returns JSON 200 (non-stream).
    """
    blocked_resp = check_circuit_blocked(current_user.family_id, "finance_coach", db)
    if blocked_resp is not None:
        return blocked_resp

    # 8h capability-cache check (before streaming). force=true regenerates.
    if not force:
        cached = latest_by_capability(db, current_user.family_id, "finance_coach")
        if is_cache_fresh(cached, "finance_coach"):
            return JSONResponse(
                status_code=200,
                content={
                    "status": "cached",
                    "generated_at": cached.generated_at.isoformat() if cached and cached.generated_at else None,
                    "report": cached.report_json,
                },
            )

    # Build the PII-minimized snapshot (spec §7.1) and stream.
    snapshot = build_family_finance_snapshot(db, current_user.family_id)
    import uuid
    thread_id = f"finance-coach-{current_user.family_id}-{uuid.uuid4().hex[:8]}"

    return StreamingResponse(
        _stream_finance_coach_sse(
            family_id=str(current_user.family_id),
            user_id=str(current_user.id),
            thread_id=thread_id,
            snapshot=snapshot,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
```

> **Auth note:** `require_owner` here gates generation to the family owner — mirror `trigger_generate_events` (ai_report.py:127). If finance_coach should be triggerable by any adult (not just owner), drop `_owner` — but the spec treats finance_coach like report (owner-initiated proactive push), so owner-only is the safe default. Confirm against `require_ai_enabled`/`require_owner` semantics in `apps/backend/app/auth/ai_deps.py` and adjust.

- [ ] **Step 5: Register the router**

In `server/apps/backend/app/main.py` (or the router-registration module — find where `ai_report.router` is included and add the new router next to it):

```python
from apps.backend.app.routers import ai_finance_coach
# ... in the include_router block next to ai_report:
app.include_router(ai_finance_coach.router, prefix="/api/v1")
```

(Confirm the exact registration pattern — grep `include_router(ai_report` in main.py and mirror it.)

- [ ] **Step 6: Run test to verify it passes**

Run: `cd server && uv run pytest tests/backend/routers/test_ai_finance_coach.py -v`
Expected: all 3 tests PASS.

- [ ] **Step 7: Lint + typecheck**

Run: `cd server && uv run ruff check apps/backend/app/routers/ai_finance_coach.py apps/backend/app/services/finance_coach_snapshot.py tests/backend/routers/test_ai_finance_coach.py && uv run mypy apps/backend/app/routers/ai_finance_coach.py apps/backend/app/services/finance_coach_snapshot.py`
Expected: no errors.

- [ ] **Step 8: Commit**

```bash
git add server/apps/backend/app/routers/ai_finance_coach.py server/apps/backend/app/services/finance_coach_snapshot.py server/apps/backend/app/main.py server/tests/backend/routers/test_ai_finance_coach.py
git commit -m "feat(backend): finance_coach trigger endpoint + snapshot builder (Plan A T8)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 9: Entity-change invalidation — asset/liability/wish write paths

**Files:**
- Modify: `server/apps/backend/app/services/asset.py` (or `server/apps/backend/app/routers/assets.py` — wherever the asset POST/PUT/PATCH/DELETE commit lives)
- Modify: `server/apps/backend/app/services/liability.py` (or `routers/liabilities.py`)
- Modify: `server/apps/backend/app/services/wish.py` — `create_wish` (line 35), `update_wish` (line 52), `delete_wish` (line 65), `realize_wish` (line 73)
- Test: `server/tests/backend/services/test_finance_coach_invalidation.py`

**Interfaces:**
- Consumes: `invalidate_capability(family_id, "finance_coach", db)` (Task 7 service). The existing write endpoints' commit points.
- Produces: any asset/liability/wish write deletes the family's `finance_coach` cache row, so the next dashboard load regenerates with fresh data (spec §7.2: entity-change event invalidation, not pure TTL). This is the P0 deliverable — no "deferred" invalidation.

**Scope note (spec §7.2):** keep calls minimal — one `invalidate_capability` call per write endpoint, right before/after the existing `db.commit()`. No logic changes, no new abstractions. Wish savings writes (Plan B W1) will add their own invalidation call in Plan B — here only the existing asset/liability/wish CRUD paths.

- [ ] **Step 1: Write the failing test**

Create `server/tests/backend/services/test_finance_coach_invalidation.py`:

```python
"""Entity-change invalidation of the finance_coach cache (Plan A T9)."""
from unittest.mock import patch

from apps.backend.app.services import wish as wish_service
from apps.backend.app.services.finance_coach_cache import upsert_capability_result


def _seed_cache(db_session, family_id):
    upsert_capability_result(db_session, family_id, "finance_coach", {"suggestions": []})
    db_session.commit()


def test_wish_create_invalidates_finance_coach_cache(db_session, wish_owner_user, wish_create_req):
    _seed_cache(db_session, str(wish_owner_user.family_id))
    with patch("apps.backend.app.services.wish.invalidate_capability") as inv:
        wish_service.create_wish(db_session, wish_owner_user, wish_create_req)
    inv.assert_called_once()
    args, _ = inv.call_args
    assert str(args[0]) == str(wish_owner_user.family_id)
    assert args[1] == "finance_coach"


def test_wish_update_invalidates_finance_coach_cache(db_session, wish_owner_user, existing_wish, wish_update_req):
    _seed_cache(db_session, str(wish_owner_user.family_id))
    with patch("apps.backend.app.services.wish.invalidate_capability") as inv:
        wish_service.update_wish(db_session, wish_owner_user, str(existing_wish.id), wish_update_req)
    inv.assert_called_once()


def test_wish_delete_invalidates_finance_coach_cache(db_session, wish_owner_user, existing_wish):
    _seed_cache(db_session, str(wish_owner_user.family_id))
    with patch("apps.backend.app.services.wish.invalidate_capability") as inv:
        wish_service.delete_wish(db_session, wish_owner_user, str(existing_wish.id))
    inv.assert_called_once()


def test_liability_write_invalidates_finance_coach_cache(db_session, liability_owner_user, liability_create_req):
    _seed_cache(db_session, str(liability_owner_user.family_id))
    from apps.backend.app.services import liability as liability_service
    with patch("apps.backend.app.services.liability.invalidate_capability") as inv:
        liability_service.create_liability(db_session, liability_owner_user, liability_create_req)
    inv.assert_called_once()


def test_asset_write_invalidates_finance_coach_cache(db_session, asset_owner_user, asset_create_req):
    _seed_cache(db_session, str(asset_owner_user.family_id))
    from apps.backend.app.services import asset as asset_service
    with patch("apps.backend.app.services.asset.invalidate_capability") as inv:
        asset_service.create_asset(db_session, asset_owner_user, asset_create_req)
    inv.assert_called_once()
```

> **Fixture note:** `wish_owner_user` / `existing_wish` / `wish_create_req` / `wish_update_req` / `liability_*` / `asset_*` fixtures may not exist yet — if so, build minimal inline factories in the test (create a User + Wish directly via the ORM). The key assertion is that `invalidate_capability` is called with the user's `family_id` and `"finance_coach"` after each write. Confirm the actual service function names (`create_asset` / `create_liability` — grep the service modules) and adjust.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd server && uv run pytest tests/backend/services/test_finance_coach_invalidation.py -v`
Expected: FAIL — `invalidate_capability` not called (the service functions don't call it yet).

- [ ] **Step 3: Add invalidation to wish_service**

In `server/apps/backend/app/services/wish.py`:

(a) Add the import at the top:
```python
from apps.backend.app.services.finance_coach_cache import invalidate_capability
```

(b) In `create_wish` (line 35), after `db.commit()` (line 45) and before `db.refresh(wish)`, add:
```python
    invalidate_capability(db, user.family_id, "finance_coach")
```

(c) In `update_wish` (line 52), after `db.commit()` (the line after the setattr loop) and before `db.refresh(wish)`, add:
```python
    invalidate_capability(db, user.family_id, "finance_coach")
```

(d) In `delete_wish` (line 65), after `db.commit()` (the last line), add:
```python
    invalidate_capability(db, user.family_id, "finance_coach")
```

(e) In `realize_wish` (line 73), after its `db.commit()`, add:
```python
    invalidate_capability(db, user.family_id, "finance_coach")
```

> The `invalidate_capability(db, ...)` call deletes the rows but does NOT commit — it relies on the existing commit that already ran. If the service commits again after, that's fine (delete is idempotent). Read each function to confirm the commit is the LAST write before your insertion point; if a commit runs AFTER your invalidation, move the invalidation to after that commit instead. The goal: invalidate is staged before the transaction's final commit so a rollback undoes both.

- [ ] **Step 4: Add invalidation to liability + asset services**

Repeat the pattern from Step 3 for every write endpoint in:
- `server/apps/backend/app/services/liability.py` (or `routers/liabilities.py` if the service is router-inline — confirm where `db.commit()` lives): `create_liability`, `update_liability`, `delete_liability`, `record_payment` (if it exists). Add `invalidate_capability(db, user.family_id, "finance_coach")` before each final commit.
- `server/apps/backend/app/services/asset.py` (or `routers/assets.py`): `create_asset`, `update_asset`, `delete_asset`. Same pattern.

Import in each:
```python
from apps.backend.app.services.finance_coach_cache import invalidate_capability
```

If asset/liability writes live in the router (not a service module), add the call there right before the router's `db.commit()` / service call, and import `invalidate_capability` in that router.

- [ ] **Step 5: Run test to verify it passes**

Run: `cd server && uv run pytest tests/backend/services/test_finance_coach_invalidation.py -v`
Expected: all 5 tests PASS.

- [ ] **Step 6: Run regression on existing asset/liability/wish tests**

Run: `cd server && uv run pytest tests/backend/test_wishes.py tests/backend/test_liabilities.py tests/backend/test_assets.py -v 2>/dev/null || uv run pytest tests/backend/ -k "wish or liabilit or asset" -v`
Expected: existing tests still PASS (invalidation is a delete that no-ops when no cache row exists; it does not change the write's observable result).

- [ ] **Step 7: Lint + typecheck**

Run: `cd server && uv run ruff check apps/backend/app/services/wish.py apps/backend/app/services/liability.py apps/backend/app/services/asset.py tests/backend/services/test_finance_coach_invalidation.py && uv run mypy apps/backend/app/services/wish.py apps/backend/app/services/liability.py apps/backend/app/services/asset.py`
Expected: no errors. (If the service functions live in routers, typecheck those instead.)

- [ ] **Step 8: Commit**

```bash
git add server/apps/backend/app/services/wish.py server/apps/backend/app/services/liability.py server/apps/backend/app/services/asset.py server/tests/backend/services/test_finance_coach_invalidation.py
git commit -m "feat(cache): entity-change invalidation for finance_coach (Plan A T9)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 10: Plan A self-review + integration smoke test

**Files:**
- No new files. This task verifies the full dispatch chain end-to-end and runs the Plan A self-review checklist.

- [ ] **Step 1: Verify the full dispatch chain is wired**

Trace the chain by grepping each link exists:
```bash
cd server
echo "1. RESERVED_NAMES:"; grep -n "finance-coach" apps/backend/app/routers/ai_skills.py
echo "2. system-agent row:"; uv run python -c "from apps.backend.app.database import SessionLocal; from apps.backend.app.models.ai_agent import AIAgent; s=SessionLocal(); a=s.query(AIAgent).filter_by(agent_name='finance-coach').first(); print(a.id, a.memory_enabled, a.skills) if a else print('MISSING')"
echo "3. gateway route:"; grep -n "finance-coach" apps/agent/app/routers/gateway.py
echo "4. R1 allowlist:"; grep -n "finance-coach" apps/agent/services/runtime/sse_gateway.py
echo "5. worker branch:"; grep -n 'app == "finance-coach"\|_run_finance_coach_agent' apps/agent/services/runtime/worker.py
echo "6. capability column:"; grep -n "capability" apps/backend/app/models/ai_report.py
echo "7. backend trigger:"; grep -n "ai/finance-coach\|finance_coach" apps/backend/app/routers/ai_finance_coach.py | head -3
```
Expected: each grep returns at least one match; the system-agent print shows `100000000000008 False ['finance-coach']`.

- [ ] **Step 2: Run the Plan A unit + integration test suite together**

Run: `cd server && uv run pytest apps/agent/tests/unit/test_finance_coach_skill.py apps/agent/tests/unit/test_worker_finance_coach.py apps/agent/tests/integration/test_gateway_finance_coach.py tests/backend/test_ai_skills.py tests/backend/bootstrap/test_bootstrap_agents.py tests/backend/services/test_finance_coach_cache.py tests/backend/routers/test_ai_finance_coach.py tests/backend/services/test_finance_coach_invalidation.py -v`

> **Path note.** The repo has `testpaths = ["tests"]` in `pyproject.toml`, and all 107 backend tests live under `server/tests/backend/` with a shared root `conftest.py` (DB/app fixtures). The `server/apps/backend/tests/` root is a leftover from the U4 report refactor containing only 5 files and **no conftest** — it is not on pytest's discovery path. T7/T8/T9 tests were correctly written into `tests/backend/`; earlier drafts of this command used the `apps/backend/tests/...` layout by mistake. The command above uses the real paths.
Expected: all PASS.

- [ ] **Step 3: Lint + typecheck the full Plan A surface**

Run: `cd server && uv run ruff check apps/agent/services/runtime/worker.py apps/agent/app/routers/gateway.py apps/agent/services/runtime/sse_gateway.py apps/backend/app/routers/ai_finance_coach.py apps/backend/app/services/finance_coach_cache.py apps/backend/app/services/finance_coach_snapshot.py apps/backend/app/models/ai_report.py apps/backend/app/bootstrap/agents.py && uv run mypy apps/agent/services/runtime/worker.py apps/backend/app/routers/ai_finance_coach.py apps/backend/app/services/finance_coach_cache.py --explicit-package-bases`

> **mypy flag note.** The `--explicit-package-bases` flag is required: `server/` contains an `__init__.py` and is the cwd, so without it mypy resolves each file under two module names (`server.apps.backend...` and `apps.backend...`) and aborts with "Source file found twice under different module names" before doing any type checking.
>
> **Baseline-noise note.** The repo's mypy config is intentionally lenient (`ignore_missing_imports = true`, no per-module `disallow_untyped_defs`) and the codebase has ~47 pre-existing type errors in files Plan A never touched (e.g. `backend_client.py`, `family_adapter_cache.py`, `deps.py`, `revoke_jti.py`, and the 3 `worker.py` `end_payload["usage"]` assignment errors that predate Plan A). The success criterion for this step is: **zero mypy errors in Plan A owned files** (`finance_coach_snapshot.py`, `ai_finance_coach.py`, `finance_coach_cache.py`). Filter the output to those filenames; everything else is pre-existing baseline noise tracked separately, not a Plan A regression.
Expected: no errors.

- [ ] **Step 4: Plan A self-review (spec coverage + placeholder scan + type consistency)**

Run this self-review checklist against the spec (`docs/superpowers/specs/2026-07-19-p0-family-finance-core-design.md` §7.1, §7.2, §13 Plan A scope):

**Spec coverage (Plan A owns these — each must have a task):**
- [x] §7.1 RESERVED_NAMES + system-agent Alembic + gateway route + R1 allowlist + worker branch + SKILL.md base-name allowed-tools → Tasks 1-6
- [x] §7.1 finance_coach is stateless (`memory_enabled=False`) → Task 2 migration + Task 3 bootstrap + Task 6 worker
- [x] §7.1 PII minimization (id+category, no name) → Task 8 snapshot builder + Task 6 worker pii_redactor
- [x] §7.1 advice baseline (schema-validation gate, `suggested_amount >= 0`, wrong output dropped) → Task 6 worker emits raw parsed JSON; the schema-validation GATE is Plan B's D2/W4 UI responsibility (documented in Task 6 Step 5 comment + Global Constraints). Plan A defines the schema (Task 4 SKILL.md) and emits validated JSON (Task 6 parse_report_json). The gate UI is out of Plan A scope — confirmed by §13: "Plan A ... advice baseline guardrails" but the gate runs where suggestions are displayed (Plan B).
- [x] §7.2 capability-cache (ai_reports + capability column + parametric TTL + entity-change invalidation) → Tasks 7 + 9
- [x] §13 Plan A "完整接入链路" + "capability-cache 新建" → Tasks 1-9

**Placeholder scan:** search the plan for `TODO|TBD|implement later|fill in|similar to Task` — there are none. Every code step has complete code.

**Type consistency:**
- `invalidate_capability(db, family_id, capability, ...)` — signature identical in Task 7 (service def) and Task 9 (callers). ✓
- `latest_by_capability(db, family_id, capability)` — Task 7 def, Task 8 caller. ✓
- `upsert_capability_result(db, family_id, capability, payload)` — Task 7 def, Tasks 7/8 callers. ✓
- `CAPABILITY_TTL` — Task 7 def, Task 7 `_latest_report`/`is_cache_fresh` callers. ✓
- `_run_finance_coach_agent` signature — Task 6 def matches the dispatch call in Task 6 Step 4 (same kwargs). ✓
- `finance_coach.result` custom event name — Task 6 emits it, Task 8 `_persist_finance_coach_result` parses it. ✓
- `FINANCE_COACH_AGENT_ID = 100000000000008` — must live in `server/apps/backend/app/constants/system_ids.py` (Task 3 imports it from there; the existing constants are `NUMINA_AGENT_ID=...005`, `ASSET_REPORT_AGENT_ID=...006`, `IMPORT_PARSE_AGENT_ID=...007`). **Add it there in Task 3**, not in `agents.py`.

- [ ] **Step 5: Commit the final Plan A state (if any test-fix commits are needed)**

If Steps 2-3 surfaced any fix, commit it. Otherwise no commit needed — Plan A is complete.

- [x] **Step 6: Housekeeping — reconcile the duplicate `apps/backend/tests/` leftovers**

While verifying T10 Step 2 it was discovered that the repo has a stray second backend test root. The authoritative root is `server/tests/backend/` (on `pyproject.toml`'s `testpaths`, has the root `conftest.py`, 107 test files). The legacy `server/apps/backend/tests/` root holds only **5 files, has no conftest, and is NOT on pytest's discovery path** — so anything that lives there is silently never collected by a bare `uv run pytest`.

Three of those 5 files are **same-name forks** of tests that also exist (in expanded form) under `tests/backend/`. They are NOT byte-identical — the `apps/backend/tests/` copies are earlier, smaller U4-era versions; the `tests/backend/` copies are the later expanded versions:

| `apps/backend/tests/` copy (legacy, NOT collected) | `tests/backend/` copy (canonical) | Sizes |
|---|---|---|
| `apps/backend/tests/unit/test_ai_result_parser.py` | `tests/backend/test_ai_result_parser.py` | 269 vs 481 lines |
| `apps/backend/tests/unit/test_ai_result_writer.py` | `tests/backend/test_ai_result_writer.py` | 62 vs 43 lines |
| `apps/backend/tests/routers/test_ai_skills.py` | `tests/backend/test_ai_skills.py` | 13 vs 157 lines |

The other 2 files in `apps/backend/tests/` have no canonical counterpart and need a content decision:
- `apps/backend/tests/test_ai_report_trigger.py`
- `apps/backend/tests/unit/test_ai_internal_session_title.py`

**Do not blindly delete** — the legacy copies may contain assertions the canonical versions dropped. For each of the 5 files:
1. `diff` the legacy copy against its canonical counterpart (where one exists). Identify any test cases / assertions present only in the legacy copy.
2. If the legacy-only cases are still valid, port them into the canonical copy under `tests/backend/`.
3. Delete the legacy file from `apps/backend/tests/`.
4. For the 2 files with no counterpart: decide whether to move (into `tests/backend/` with any needed fixture alignment) or delete outright. `test_ai_report_trigger.py` likely overlaps with `tests/backend/test_ai_report.py` — check before moving.
5. Once `apps/backend/tests/` is empty (or only `__pycache__`), remove the directory.

**Verification:** `find server/apps/backend/tests -name 'test_*.py'` returns nothing; `cd server && uv run pytest tests/backend/test_ai_result_parser.py tests/backend/test_ai_result_parser_envelope.py tests/backend/test_ai_result_writer.py tests/backend/test_ai_skills.py tests/backend/test_ai_report_trigger.py tests/backend/test_ai_internal_session_title.py -v` passes (covers the ported + canonical tests — 42 passed).

> **Follow-up (out of Step 6 scope).** While verifying, `tests/backend/test_ai_report.py` was found to have 4 pre-existing failures (NOT caused by Step 6 — verified by running it on the pre-Step-6 tree): its 4 `test_generate_report_*` cases patch `_ai_events_helper.AgentClient` and assert `application/x-ndjson`, but the U4 SSE refactor moved `AgentClient` to `ai_report.py` directly and switched the route to `text/event-stream`. The correctly-patching SSE coverage now lives in the ported `tests/backend/test_ai_report_trigger.py`. Aligning `test_ai_report.py` (drop the stale NDJSON cases or rewrite them against the SSE path) is a separate cleanup — tracked here so it isn't lost.

This is a long-standing test-debt cleanup surfaced by the T10 path review — it is **not** part of the finance_coach capability itself, but doing it now prevents the next person from being misled by the silent second test root. Commit it separately from any T10 test fix, with message like `chore(tests): remove stray apps/backend/tests/ root — consolidate into tests/backend/`.

---

## Plan A — Definition of Done

Plan A is complete when:
1. All 9 implementation tasks (T1-T9) are committed and their tests pass.
2. The full dispatch chain (RESERVED_NAMES → system-agent → gateway route → R1 allowlist → worker branch → SKILL.md) is wired and verified (T10 Step 1).
3. The capability-cache (`ai_reports.capability` + parametric TTL + entity-change invalidation) works and is isolated from the existing `report` cache (T7 + T9 tests).
4. The backend trigger `POST /ai/finance-coach/generate` returns cached JSON within 8h OR streams a fresh `finance_coach.result` and persists it (T8 tests).
5. Plan B (D2/A1a dashboard card) can call `POST /ai/finance-coach/generate` and render the top-3 suggestions — this is the handoff contract.

**Plan A does NOT implement** (deferred to Plan B): the D2 dashboard card UI, the A1b passive buttons, the W4 schema-validation gate UI, the wish_advice cache (separate key), the savings/afford/liability UI. Plan A only builds the callable capability + cache infra.
