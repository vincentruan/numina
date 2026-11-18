---
date: 2026-11-18
module: server
problem_type: integration_issue
component: database
severity: high
root_cause: logic_error
resolution_type: code_fix
symptoms:
  - "POST /api/v1/ai/mcp-token returns 500 DataError: value too long for type character varying(10)"
  - "alembic upgrade head fails with 'Multiple head revisions are present'"
  - "alembic upgrade head fails with DuplicateColumn on an already-present column"
  - "alembic_version pinned at an old revision for weeks while schema looked correct"
  - "仿真测试 Area 20 never reported, MCP token generation broken in production-like dev DB"
tags:
  - alembic
  - schema-drift
  - align-schema
  - idempotent-migrations
  - multiple-heads
applies_when:
  - "align_schema (boot-time create_all-ish) runs before migrations have been stamped"
  - "Adding a column that the model already declares"
  - "alembic reports multiple heads"
---

# Alembic Version Drift: `align_schema` Creates Schema Without Stamping the Migration

## Problem

`POST /api/v1/ai/mcp-token` returned HTTP 500:

```
psycopg2.errors.StringDataRightTruncation:
  value too long for type character varying(10)
INSERT INTO users (..., role, ...) VALUES (..., 'external_token', ...)
```

`users.role` was `VARCHAR(10)` in the database but `'external_token'` is 14
characters. The model declared `String(20)`. The migration that widens the
column (`mcp001token`) had never run.

## Why the migration never ran

Two independent blockers, both silent:

### 1. Three independent heads

`alembic upgrade head` refused to run at all:

```
ERROR: Multiple head revisions are present for given argument 'head'
```

`mc001misc0003`, `mpx001` and `tb001crp0001` all descended from the same
`(h0011q22r3s4, rwc001)` merge point but were never merged back together.
Naming a single branch would silently skip the other two branches' tables.
Most operators just never upgraded.

### 2. `align_schema` makes the schema look migrated

`app/services/db_migrate.py:516` runs `align_schema(engine)` at every backend
boot. It creates missing tables, adds missing columns, and creates missing
indexes straight from `Base.metadata`.

Critically, **it does not write a new `alembic_version`**. So the database
accumulates real schema (tables exist, columns exist) while
`alembic_version` stays pinned. Every check that asks "does this table/column
exist?" says yes — the schema *looks* correct.

The one thing `align_schema` does **not** do is **alter an existing column's
type**. `users.role` was created as `VARCHAR(10)` by an older migration;
`align_schema` sees the column is present and moves on. The widening migration
is the only thing that could fix it — and it was pinned behind the multi-head
conflict.

## Fix

### 1. Merge the heads

```python
# apps/backend/alembic/versions/mrg001lrnheads_merge_learning_branch_heads.py
revision: str = "mrg001lrnheads"
down_revision: tuple[str, ...] = ("mc001misc0003", "mpx001", "tb001crp0001")
```

No DDL — this revision only reconnects the graph. After it, `alembic upgrade
head` resolves to a single target.

**Verify before/after with:** `uv run alembic heads` — must print exactly one line.

### 2. Make the pending migrations idempotent

Add `apps/backend/alembic/ddl.py` with `has_table` / `has_column` /
`has_index` / `add_column` / `create_index` / `drop_column` / `drop_index`
helpers, then use them in every migration whose changes `align_schema` may
have already applied:

```python
from apps.backend.alembic import ddl

def upgrade() -> None:
    ddl.add_column("learning_sessions", sa.Column("progress_json", sa.Text(), ...))
```

For table-creating migrations, guard the whole body:

```python
def upgrade() -> None:
    if ddl.has_table("preset_learning_paths"):
        return  # align_schema already created it from the model
    op.create_table("preset_learning_paths", ...)
```

Migrations that needed this treatment:

| Migration | Change |
|-----------|--------|
| `src001tax001` | 3 columns + 1 index + unique-constraint swap |
| `0147f812a544` | `learning_sessions.progress_json` |
| `1f05a4b6a5de` | 4 columns across 2 tables |
| `brg001infr` | 2 columns |
| `e805c16f361a` | `preset_learning_paths.description_zh` |
| `h0011q22r3s4` | create `topic_hook_questions` |
| `lrnprst00001` | create `preset_learning_paths` |
| `idx002clstr` | index (had its own ad-hoc guard; now uses the helper) |
| `mc001misc0002` | `misconceptions.category` |
| `mc001misc0003` | `practice_attempts.misconception_id` + FK + index |

### 3. Verify

```bash
uv run alembic heads                 # → exactly one head
uv run alembic upgrade head          # → applies cleanly
uv run alembic upgrade head          # → no-op on re-run (idempotency proof)
uv run alembic current               # → the single head
```

## Prevention

- **`align_schema` is not a migration system.** It is a safety net for missing
  tables/columns/indexes. It cannot change column types, cannot drop anything,
  and never records a version. Treat `alembic_version` as the only source of
  truth for "is this database migrated?"
- **Never add an unconditional `op.add_column` in this repo.** Always use
  `ddl.add_column`. If the models already declare the column, a boot may have
  created it first.
- **A green-looking app is not proof of a migrated schema.** The MCP 500 only
  surfaced on the one code path that writes a 14-char role. Type-widening bugs
  hide until a value exceeds the old width.
- **Check `alembic heads` in CI.** Multiple heads should fail the build, not
  wait for someone to try `upgrade head`.
- **When a feature's write path is exercised only by the last test area, move a
  smoke check into the precondition gate.** The MCP token generation was only
  tested by Area 20 — the last area in G1, and the first dropped from any
  partial run. It is now gated in Phase 1.5 step 9.

## Related

- [`auto-migrate-string-default`](./auto-migrate-string-default-quoting-postgresql.md) —
  another auto-migration PostgreSQL pitfall
- [`mcp-caller-bound-principal`](../architecture-patterns/mcp-caller-bound-principal-2026-05-31.md)
- `server/apps/backend/AGENTS.md` §Key Invariants — "Always run `alembic upgrade
  head` before starting the app on an existing database"
