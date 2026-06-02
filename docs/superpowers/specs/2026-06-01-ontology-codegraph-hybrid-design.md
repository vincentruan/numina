# Ontology Skill: Codegraph Hybrid Redesign

## Summary

Rewrite the `.claude/skills/ontology/` skill to use codegraph for all code-navigation queries and a separate SQLite database for domain entity storage. The skill becomes a unified decision router that picks the right backend for each question type.

## Goals

1. Eliminate redundant code-navigation logic — codegraph already provides sub-millisecond AST-parsed symbol lookup, call graph traversal, and impact analysis.
2. Replace JSONL append-only storage with SQLite for domain entities — proper indexing, atomic CRUD, and SQL queries.
3. Provide a clear decision framework in SKILL.md so Claude knows when to use codegraph tools vs. domain entity queries.

## Architecture

```
┌─────────────────────────────────────────────────┐
│              Ontology Skill (SKILL.md)           │
│         Decision Router + Type System            │
├────────────────────┬────────────────────────────┤
│  Code Questions    │   Domain Questions          │
│                    │                             │
│  codegraph_search  │   SQLite: ontology.db      │
│  codegraph_context │   Tables: entities,        │
│  codegraph_trace   │           relations         │
│  codegraph_explore │   Script: ontology.py      │
│  codegraph_node    │                             │
│  codegraph_callers │                             │
│  codegraph_callees │                             │
└────────────────────┴────────────────────────────┘
```

## Domain Entity Storage (SQLite)

### Database: `memory/ontology/ontology.db`

```sql
CREATE TABLE entities (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    properties TEXT NOT NULL,  -- JSON
    created TEXT NOT NULL,
    updated TEXT NOT NULL
);

CREATE INDEX idx_entities_type ON entities(type);

CREATE TABLE relations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_id TEXT NOT NULL,
    rel_type TEXT NOT NULL,
    to_id TEXT NOT NULL,
    properties TEXT NOT NULL DEFAULT '{}',  -- JSON
    created TEXT NOT NULL,
    FOREIGN KEY (from_id) REFERENCES entities(id),
    FOREIGN KEY (to_id) REFERENCES entities(id)
);

CREATE INDEX idx_relations_from ON relations(from_id);
CREATE INDEX idx_relations_to ON relations(to_id);
CREATE INDEX idx_relations_type ON relations(rel_type);
CREATE UNIQUE INDEX idx_relations_unique ON relations(from_id, rel_type, to_id);
```

### Type System (unchanged)

Same types as before: Person, Organization, Project, Task, Goal, Event, Location, Document, Message, Thread, Note, Account, Device, Credential, Action, Policy.

### Relation Types (unchanged)

Same relation vocabulary: owns, has_owner, assigned_to, has_task, has_goal, member_of, part_of, blocks, depends_on, requires, mentions, references, follows_up, attendee_of, located_at.

## Code Navigation (codegraph delegation)

The skill no longer implements any code traversal. Instead, SKILL.md provides a routing table:

| Question Pattern | Codegraph Tool |
|-----------------|----------------|
| "Where is X defined?" | `codegraph_search` |
| "What does this area/feature do?" | `codegraph_context` |
| "How does X reach Y?" | `codegraph_trace` |
| "What calls this?" | `codegraph_callers` |
| "What does this call?" | `codegraph_callees` |
| "What would break if I change X?" | `codegraph_impact` |
| "Show me the source of X" | `codegraph_node` |
| "Survey several related symbols" | `codegraph_explore` |

## Script Interface

`scripts/ontology.py` — rewritten to use SQLite:

```
ontology.py create --type Person --props '{"name":"Alice"}'
ontology.py get --id p_001
ontology.py query --type Task --where '{"status":"open"}'
ontology.py list --type Person
ontology.py update --id p_001 --props '{"email":"alice@new.com"}'
ontology.py delete --id p_001
ontology.py relate --from proj_001 --rel has_task --to task_001
ontology.py unrelate --from proj_001 --rel has_task --to task_001
ontology.py related --id proj_001 --rel has_task [--dir outgoing|incoming|both]
ontology.py validate
ontology.py migrate  # One-time: JSONL → SQLite migration
```

## Migration Path

1. `ontology.py migrate` reads existing `memory/ontology/graph.jsonl`, replays all ops into SQLite.
2. After verification, JSONL file can be archived or deleted.
3. No breaking changes to the skill's external interface (same CLI commands).

## Files Changed

| File | Action |
|------|--------|
| `SKILL.md` | Rewrite: add codegraph routing table, update storage docs |
| `scripts/ontology.py` | Rewrite: SQLite backend, add migrate command |
| `references/schema.md` | Keep: type definitions unchanged |
| `references/queries.md` | Rewrite: split into codegraph examples + SQLite domain queries |

## Constraints

- No external dependencies beyond Python stdlib (`sqlite3`, `json`, `argparse`).
- Domain entity queries must not touch codegraph.db — complete separation.
- Codegraph tools are MCP-based — the skill only documents when to use them, never wraps them.
- Migration must be idempotent (safe to run multiple times).

## Success Criteria

1. `ontology.py create/get/query/list/update/delete/relate/related` all work against SQLite.
2. `ontology.py validate` checks constraints against SQLite data.
3. `ontology.py migrate` successfully imports existing JSONL data (if any).
4. SKILL.md clearly routes code questions to codegraph, domain questions to SQLite.
5. No JSONL dependency remains in the active code path.
