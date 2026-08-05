---
date: 2026-08-05
module: backend
problem_type: best_practice
component: ai_agent
severity: medium
root_cause: logic_error
resolution_type: code_fix
symptoms:
  - "DB CheckViolation for agent_name with underscores despite Pydantic allowing them"
  - "Pydantic validation passes — the error only surfaces at the database layer"
  - "Error message: new row for relation 'ai_agents' violates check constraint 'ck_ai_agents_name_format'"
tags:
  - check-constraint
  - pydantic-validation
  - alembic-migration
  - regex-mismatch
applies_when:
  - "DB check constraint regex diverges from Pydantic validator regex"
  - "App-level validation passes but DB layer rejects with CheckViolation"
---

# DB Check Constraint Regex Mismatch with Pydantic

## Problem
The DB `CheckConstraint` on `ai_agents.agent_name` used regex `^[a-z][a-z0-9-]*$` (no underscore), but the Pydantic validator allowed `^[a-z][a-z0-9_-]*$` (with underscore). Agent names like `stock_research_agent` passed app validation but failed at the DB level.

## Symptoms
- `CheckViolation` error when inserting agent names containing underscores
- Pydantic validation passes — the error only surfaces at the database layer
- Error message: `new row for relation "ai_agents" violates check constraint "ck_ai_agents_name_format"`

## What Didn't Work
- Changing Pydantic to reject underscores — the agent names with underscores are intentional and valid
- Only updating the model — existing databases need a migration to drop and recreate the constraint

## Solution
Update the `CheckConstraint` regex to include `_` and add an alembic migration.

**Before** (`server/apps/backend/app/models/ai_agent.py:31`):
```python
CheckConstraint(
    "agent_name ~ '^[a-z][a-z0-9-]*$'",  # Missing underscore
    name="ck_ai_agents_name_format",
    _create_rule=_pg_only,
),
```

**After**:
```python
CheckConstraint(
    "agent_name ~ '^[a-z][a-z0-9_-]*$'",  # Now includes underscore
    name="ck_ai_agents_name_format",
    _create_rule=_pg_only,
),
```

## Why This Works
The DB constraint and the Pydantic validator are independent validation layers that must agree on the allowed format. When they diverge, the stricter layer rejects valid inputs that passed the looser layer. The fix aligns both to allow underscores.

## Prevention
- **Keep DB constraints and app-level validators in sync** — whenever updating a Pydantic regex, check for corresponding DB check constraints.
- **Use the same regex source of truth** — consider defining the regex pattern once and referencing it from both the model and the migration.
- **Test with realistic data** — `stock_research_agent` is a valid name that should have been caught by integration tests.
