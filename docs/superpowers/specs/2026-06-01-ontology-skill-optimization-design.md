# Ontology Skill Optimization Design Spec

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:writing-plans to create the implementation plan.

**Goal:** Restore valuable ideas lost during JSONL→SQLite migration while maintaining SQLite architecture.

**Architecture:** Three-layer improvement: (1) Documentation — restore Integration Patterns and Core Concept, add codegraph division guidance; (2) Constraint System — move from hardcoded Python to SQLite-stored constraints with CLI management; (3) Validation — add relation type checking and transactional multi-step operations.

**Tech Stack:** Python 3.12+, SQLite (WAL mode), existing CLI pattern

---

## Problem Statement

The ontology skill was migrated from JSONL to SQLite, gaining performance and reliability. However, several valuable ideas were lost:

1. **Integration Patterns** — cross-skill communication and causal action logging
2. **External Schema** — user-definable type constraints (now hardcoded)
3. **Relation Type Validation** — checking from/to type legality
4. **Core Concept Framing** — clear one-line mental model
5. **Transaction Rollback** — atomic multi-step plan execution

These losses reduced ontology from a "composable skill platform" to a "database CRUD tool".

---

## Design Principles

### 1. SQLite-First Constraint Storage

Store type/relation constraints in SQLite `schema_rules` table, managed via CLI:

```
entities table    — domain entities (Person, Task, etc.)
relations table   — entity relationships
schema_rules table — type constraints, relation rules
```

**Why SQLite over YAML:**
- No external file dependency
- Atomic updates with entity operations
- Queryable alongside entities
- Consistent backup/restore path

### 2. Clear Division: Ontology vs Codegraph

| Tool | Domain | Query Pattern |
|------|--------|---------------|
| ontology | People, projects, tasks, events, documents | Domain knowledge CRUD, cross-skill state |
| codegraph | Functions, classes, files, symbols | Code structure, call graphs, impact analysis |

**Integration point:** Documentation in SKILL.md, not runtime coupling. User/AI decides which tool based on question type.

### 3. Validation Layers

```
Layer 1: Entity Property Validation (current)
  - required properties
  - enum constraints
  - forbidden properties

Layer 2: Relation Type Validation (new)
  - from_id type ∈ allowed_from_types
  - to_id type ∈ allowed_to_types
  - cardinality enforcement (one_to_many, many_to_one)

Layer 3: Acyclic Graph Validation (new)
  - blocks, depends_on must not form cycles
  - DFS cycle detection on create_relation
```

---

## Schema Design

### New Tables

```sql
-- Type constraints (replaces hardcoded type_constraints dict)
CREATE TABLE IF NOT EXISTS type_rules (
    type_name TEXT PRIMARY KEY,
    required_props TEXT NOT NULL DEFAULT '[]',    -- JSON array
    enum_constraints TEXT NOT NULL DEFAULT '{}',  -- JSON dict {field: [values]}
    forbidden_props TEXT NOT NULL DEFAULT '[]',   -- JSON array
    created TEXT NOT NULL,
    updated TEXT NOT NULL
);

-- Relation type rules
CREATE TABLE IF NOT EXISTS relation_rules (
    rel_type TEXT PRIMARY KEY,
    from_types TEXT NOT NULL DEFAULT '[]',       -- JSON array of allowed from types
    to_types TEXT NOT NULL DEFAULT '[]',         -- JSON array of allowed to types
    cardinality TEXT NOT NULL DEFAULT 'many_to_many',  -- one_to_many, many_to_one, many_to_many
    acyclic INTEGER NOT NULL DEFAULT 0,          -- 0=false, 1=true
    relation_props_schema TEXT NOT NULL DEFAULT '{}', -- JSON schema for relation properties
    created TEXT NOT NULL,
    updated TEXT NOT NULL
);

-- Multi-step plan execution (for transactional operations)
CREATE TABLE IF NOT EXISTS plan_executions (
    plan_id TEXT PRIMARY KEY,
    status TEXT NOT NULL,  -- pending, executing, committed, rolled_back
    steps TEXT NOT NULL,   -- JSON array of planned operations
    executed_steps TEXT NOT NULL DEFAULT '[]',  -- JSON array of completed ops
    created TEXT NOT NULL,
    updated TEXT NOT NULL
);
```

### Seed Default Rules

On first run, seed built-in type/relation rules (matching current hardcoded constraints):

```python
DEFAULT_TYPE_RULES = {
    "Person": {"required": ["name"]},
    "Task": {"required": ["title", "status"], "enums": {"status": [...], "priority": [...]}},
    "Credential": {"required": ["service", "secret_ref"], "forbidden": ["password", ...]},
    # ... rest of current type_constraints
}

DEFAULT_RELATION_RULES = {
    "has_owner": {"from_types": ["Project", "Task"], "to_types": ["Person"], "cardinality": "many_to_one"},
    "blocks": {"from_types": ["Task"], "to_types": ["Task"], "cardinality": "many_to_many", "acyclic": true},
    # ... rest from original schema.md
}
```

---

## CLI Commands

### New Commands

```bash
# Type rule management
python3 scripts/ontology.py add-type --type CustomEntity --required '["name"]' --enums '{"status":["active","done"]}'
python3 scripts/ontology.py list-types
python3 scripts/ontology.py get-type --type Task
python3 scripts/ontology.py update-type --type Task --required '["title","status","priority"]'
python3 scripts/ontology.py delete-type --type CustomEntity

# Relation rule management
python3 scripts/ontology.py add-relation-type --rel custom_rel --from-types '["Project"]' --to-types '["Document"]' --cardinality many_to_many
python3 scripts/ontology.py list-relation-types
python3 scripts/ontology.py get-relation-type --rel blocks

# Transactional plan execution
python3 scripts/ontology.py plan-create --steps '[{"op":"create","type":"Task","props":{...}},{"op":"relate",...}]'
python3 scripts/ontology.py plan-execute --plan-id plan_001
python3 scripts/ontology.py plan-status --plan-id plan_001
python3 scripts/ontology.py plan-rollback --plan-id plan_001  # Manual rollback if needed
```

### Enhanced Existing Commands

```bash
# relate now validates relation type rules
python3 scripts/ontology.py relate --from proj_001 --rel has_owner --to task_001
# ERROR: has_owner allows from_types=[Project,Task] but proj_001 is Project, OK
# ERROR: has_owner requires to_types=[Person] but task_001 is Task, REJECTED

# validate now checks all three layers
python3 scripts/ontology.py validate
# Checks: entity props + relation types + acyclic graphs
```

---

## SKILL.md Structure (Documentation Changes)

### New/Restored Sections

```markdown
## Core Concept

Everything is an **entity** with a **type**, **properties**, and **relations**.
Every mutation is validated before committing.

## When to Use

| Trigger | Tool |
|---------|------|
| "Remember that Alice owns project X" | ontology (domain knowledge) |
| "What calls function Y?" | codegraph (code structure) |
| "Link person to project" | ontology |
| "Trace the flow from A to B" | codegraph |
| "Who is assigned to X?" | ontology |
| "What would break if I changed Z?" | codegraph |

**Rule:** Domain questions → ontology. Code questions → codegraph.

## Integration Patterns

### Cross-Skill Communication

```python
# Email skill creates commitment
ontology.create("Commitment", {"source": msg_id, "due": "2026-01-31"})

# Task skill picks it up
for c in ontology.query("Commitment", {"status": "pending"}):
    ontology.create("Task", {"title": c["description"], "due": c["due"]})
```

### Causal Action Logging

Every ontology mutation can be logged to external action log:

```python
action_log.record({
    "action": "create_entity",
    "domain": "ontology",
    "context": {"type": "Task", "project": "proj_001"},
    "outcome": "created"
})
```

## Planning as Graph Transformation

Multi-step plans execute atomically. On constraint violation, automatic rollback.

```
Plan: "Create task and link to project"
1. CREATE Task {title: "Draft spec", status: "open"}
2. RELATE Task -> part_of -> proj_001

If step 2 fails (proj_001 not found), step 1 is rolled back.
```

## Quick Start

```bash
# Initialize (automatic on first command)
python3 scripts/ontology.py stats

# Add custom type for your project
python3 scripts/ontology.py add-type --type Asset --required '["name","value"]'

# Start using
python3 scripts/ontology.py create --type Person --props '{"name":"Alice"}'
python3 scripts/ontology.py create --type Asset --props '{"name":"House","value":500000}'
python3 scripts/ontology.py relate --from pers_001 --rel owns --to asset_001
```
```

---

## Implementation Tasks

### Task 1: Add Schema Tables
- Create `type_rules` and `relation_rules` tables in SCHEMA_SQL
- Add seed function to populate default rules on first run
- Files: `scripts/ontology.py`

### Task 2: Type Rule CLI Commands
- Implement `add-type`, `list-types`, `get-type`, `update-type`, `delete-type`
- Add `--db` path support consistent with existing commands
- Files: `scripts/ontology.py`

### Task 3: Relation Rule CLI Commands
- Implement `add-relation-type`, `list-relation-types`, `get-relation-type`
- Add relation rule validation to `create_relation()` function
- Files: `scripts/ontology.py`

### Task 4: Enhanced Validation
- Add Layer 2 (relation type validation) to `validate_graph()`
- Add Layer 3 (acyclic check) using DFS
- Files: `scripts/ontology.py`

### Task 5: Plan Execution (Transactional)
- Add `plan_executions` table
- Implement `plan-create`, `plan-execute`, `plan-status`, `plan-rollback`
- Use SQLite transaction for atomic execution
- Files: `scripts/ontology.py`

### Task 6: Update SKILL.md
- Add "Core Concept" section
- Add "When to Use" table with codegraph division
- Restore "Integration Patterns" section
- Restore "Planning as Graph Transformation" with rollback mention
- Add "Quick Start" section
- Update description frontmatter to include "composable skills"
- Files: `SKILL.md`

### Task 7: Update references/schema.md
- Document new type/relation rule tables
- Add CLI command reference for rule management
- Files: `references/schema.md`

---

## Testing Strategy

### Unit Tests

```python
# Test relation type validation
def test_relation_type_validation():
    create_entity("Task", {"title": "T1", "status": "open"}, id="task_001")
    create_entity("Task", {"title": "T2", "status": "open"}, id="task_002")
    # blocks: Task -> Task, allowed
    create_relation("task_001", "blocks", "task_002")  # OK

    create_entity("Person", {"name": "Alice"}, id="pers_001")
    # blocks: Task -> Task, Person not allowed
    create_relation("pers_001", "blocks", "task_001")  # REJECTED

# Test acyclic validation
def test_acyclic_blocks():
    create_relation("task_001", "blocks", "task_002")
    create_relation("task_002", "blocks", "task_001")  # REJECTED, cycle

# Test transactional plan
def test_plan_rollback():
    plan = create_plan([
        {"op": "create", "type": "Task", "props": {"title": "T"}},
        {"op": "relate", "from": "nonexistent", "rel": "has_owner", "to": "pers"}
    ])
    execute_plan(plan["plan_id"])  # Step 2 fails, step 1 rolled back
    assert get_entity("task_*") is None  # Entity was rolled back
```

### Integration Tests

```bash
# Full workflow test
python3 scripts/ontology.py add-type --type Milestone --required '["name","date"]'
python3 scripts/ontology.py create --type Milestone --props '{"name":"Launch","date":"2026-06-01"}'
python3 scripts/ontology.py validate  # Should pass
```

---

## Migration Path

### From Current Version

1. Run existing `ontology.py stats` — new tables auto-created
2. Default rules auto-seeded from built-in dict
3. All existing entities/relations preserved
4. No breaking changes to existing CLI commands

### From Original JSONL Version

Use existing `migrate` command — unchanged from current version.

---

## Success Metrics

| Metric | Current | Target |
|--------|---------|--------|
| SKILL.md "Core Concept" clarity | Missing | One-line summary |
| Integration Patterns documentation | Missing | Full section with examples |
| Custom type support | None (hardcoded) | CLI add-type |
| Relation type validation | None | Full from/to type checking |
| Acyclic graph validation | None | DFS cycle detection |
| Transactional plans | None | Atomic execution + rollback |
| Ontology/codegraph guidance | None | Clear division table |

---

## References

- Original skill: `/Volumes/.../awesome-openclaw-skills-main/skills/ontology/SKILL.md`
- Current skill: `.claude/skills/ontology/SKILL.md`
- Numina domain ontology: `docs/ontology/numina-domain-ontology.md`