---
name: ontology
description: Typed knowledge graph for structured agent memory and composable skills. Use when creating/querying entities (Person, Project, Task, Event, Document), linking related objects, enforcing constraints, planning multi-step actions as graph transformations, or when skills need to share state. Trigger on "remember", "what do I know about", "link X to Y", "show dependencies", entity CRUD, or cross-skill data access. Domain knowledge tool — use codegraph for code structure questions.
---

# Ontology

A persistent domain knowledge graph backed by SQLite. Stores typed entities (people, projects, tasks, events, etc.) and their relationships so knowledge accumulates across conversations.

## Core Concept

Everything is an **entity** with a **type**, **properties**, and **relations** to other entities. Every mutation is validated against type constraints before committing.

```
Entity: { id, type, properties, created, updated }
Relation: { from_id, relation_type, to_id, properties }
TypeRule: { type_name, required_props, enum_constraints, forbidden_props }
RelationRule: { rel_type, from_types, to_types, cardinality, acyclic }
```

## When This Skill Applies

This skill handles **domain knowledge** — facts about people, projects, tasks, events, and their relationships. It does NOT handle code navigation (use codegraph tools directly for that).

| User intent | Action |
|-------------|--------|
| "Remember that Alice owns project X" | Create/update entity + relation |
| "What do I know about project X?" | Full-text search |
| "Link person to project" | Create relation |
| "Show all tasks for project Z" | Relation query |
| "What's blocking this task?" | Dependency traversal |
| "Who is assigned to X?" | Relation query |
| "How big is the knowledge graph?" | Stats |
| Planning multi-step work | Model as graph transformations |
| Another skill needs shared state | Read/write ontology entities |

## When to Use: Ontology vs Codegraph

| Question | Tool |
|----------|------|
| "Remember that Alice owns project X" | ontology |
| "What calls function Y?" | codegraph |
| "Link person to project" | ontology |
| "Trace the flow from A to B" | codegraph |
| "Who is assigned to X?" | ontology |
| "What would break if I changed Z?" | codegraph |
| "Create a Task for this" | ontology |
| "Find the definition of Asset class" | codegraph |

**Rule:** Domain knowledge (people, projects, tasks) → ontology. Code structure (functions, classes, files) → codegraph.

## Integration Bridges: Ontology ↔ Codegraph

The ontology/codegraph division is about **primary storage**, not a wall. Real questions often cross both tools. Use these patterns:

### code_ref Property Convention

Entities that reference code symbols use a `code_ref` property:

```bash
python3 scripts/ontology.py create --type Task --props '{"title":"Fix auth bug","status":"open","code_ref":"symbol:AuthService.validate_token"}'
python3 scripts/ontology.py create --type Document --props '{"title":"Asset Model Design","code_ref":"file:server/packages/domain/models/asset.py"}'
```

Format: `symbol:<SymbolName>` or `file:<relative_path>`

### Chained Lookups

```
# "Who owns the code that implements feature X?"
1. ontology: query --type Task --where '{"title":"feature X"}' → get code_ref
2. codegraph: codegraph_node(symbol from code_ref) → get file, callers
3. ontology: related --id task_id --rel assigned_to → get Person

# "What tasks relate to recently changed code?"
1. git log → changed files
2. ontology: search "filename" → entities with matching code_ref
3. ontology: related --id entity_id → get linked Tasks/Projects
```

### When to Store code_ref

- Task directly implements a specific function/module → store code_ref
- Document describes an architectural area → store file path as code_ref
- Person/Project has no single code location → use relations only, query codegraph ad-hoc

## Domain Entity Types

### Core Tier (seeded by default)

```yaml
# Agents & People
Person: { name, email?, phone?, notes? }
Organization: { name, type?, members (via member_of relation) }

# Work
Project: { name, status, goals (via has_goal relation) }
Task: { title, status, due?, priority? }
Goal: { description, target_date?, metrics[] }

# Information
Document: { title, path?, url?, summary?, code_ref? }
Note: { content, tags[], refs[] }

# Meta
Action: { type, target, timestamp, outcome? }
```

### Extension Tier (load via `seed-extensions`)

```yaml
# Time & Place
Event: { title, start, end?, location?, attendees[], recurrence? }
Location: { name, address?, coordinates? }

# Messaging
Message: { content, sender, recipients[], thread? }
Thread: { subject, participants[], messages[] }

# Resources
Account: { service, username, credential_ref? }
Device: { name, type, identifiers[] }
Credential: { service, secret_ref }  # Never store secrets directly

# Governance
Policy: { scope, rule, enforcement }
```

## Storage

Database: `.ontology/ontology.db` (SQLite with WAL mode, at project root)

No external dependencies — uses Python stdlib `sqlite3`.

Entities support **namespace partitioning** — use `--namespace` to scope entities to bounded contexts (e.g., `family-assets`, `work-projects`). Relations can cross namespaces; the graph is unified but listing/search defaults to all namespaces unless filtered.

## Scale & Concurrency

- **Comfortable range:** <10K entities, <50K relations per namespace
- **Concurrent reads:** WAL mode allows multiple readers without blocking
- **Serialized writes:** SQLite allows one writer at a time; writes queue behind the current transaction
- **Multi-agent access:** Keep transactions short (plan execution already does this). If multiple skills write simultaneously, they'll serialize cleanly via SQLite's internal locking — no data corruption, just queuing
- **Beyond this scale:** If you need >10K entities, consider splitting into per-namespace database files or migrating to a dedicated graph store

## CLI Usage

```bash
# Create (with optional namespace)
python3 scripts/ontology.py create --type Person --props '{"name":"Alice","email":"alice@example.com"}'
python3 scripts/ontology.py create --type Person --props '{"name":"Bob"}' --namespace work

# Get by ID
python3 scripts/ontology.py get --id p_001

# Query with filter (optional namespace scoping)
python3 scripts/ontology.py query --type Task --where '{"status":"open"}'
python3 scripts/ontology.py query --type Task --where '{"status":"open"}' --namespace family-assets

# List all of a type (optional namespace scoping)
python3 scripts/ontology.py list --type Person
python3 scripts/ontology.py list --type Person --namespace work

# Update (merges properties)
python3 scripts/ontology.py update --id p_001 --props '{"phone":"+1234567890"}'

# Delete
python3 scripts/ontology.py delete --id p_001

# Create relation
python3 scripts/ontology.py relate --from proj_001 --rel has_task --to task_001

# Remove relation
python3 scripts/ontology.py unrelate --from proj_001 --rel has_task --to task_001

# Get related entities
python3 scripts/ontology.py related --id proj_001 --rel has_task
python3 scripts/ontology.py related --id p_001 --dir both

# Validate constraints
python3 scripts/ontology.py validate

# Full-text search across all entities (optional namespace scoping)
python3 scripts/ontology.py search "Alice"
python3 scripts/ontology.py search "backend engineer" --type Person
python3 scripts/ontology.py search "asset" --namespace family-assets

# Graph statistics
python3 scripts/ontology.py stats

# Seed extension types (Event, Location, messaging, IAM)
python3 scripts/ontology.py seed-extensions

# Migrate legacy JSONL (one-time, idempotent)
python3 scripts/ontology.py migrate
```

### Type & Relation Rules

```bash
# Manage custom type definitions
python3 scripts/ontology.py add-type --type Milestone --required '["name","date"]'
python3 scripts/ontology.py list-types
python3 scripts/ontology.py get-type --type Milestone

# Manage relation type rules
python3 scripts/ontology.py add-relation-type --rel sponsors --from-types '["Organization"]' --to-types '["Project"]'
python3 scripts/ontology.py list-relation-types
```

### Plan Execution

```bash
# Create multi-step plan
python3 scripts/ontology.py plan-create --steps '[{"op":"create","type":"Task","props":{"title":"Draft","status":"open"}}]'

# Execute atomically (rollback on failure)
python3 scripts/ontology.py plan-execute --plan-id plan_abc123

# Check plan status
python3 scripts/ontology.py plan-status --plan-id plan_abc123
```

## Relation Types

### Core Relations (seeded by default)

```yaml
# Ownership & Assignment
owns: Person/Organization → Document/Project (one_to_many)
has_owner: Project/Task/Document → Person (many_to_one)
assigned_to: Task → Person (many_to_one)

# Hierarchy & Containment
has_task: Project → Task (one_to_many)
has_goal: Project → Goal (one_to_many)
member_of: Person → Organization (many_to_many)
part_of: Task/Document → Project (many_to_one)

# Dependencies
blocks: Task → Task (acyclic)
depends_on: Task/Project → Task/Project (acyclic)

# References
mentions: Document/Note → Person/Project/Task (many_to_many)
references: Document/Note → Document/Note (many_to_many)
```

### Extension Relations (load via `seed-extensions`)

```yaml
requires: Action → Credential/Policy
follows_up: Task/Event → Event/Message (many_to_one)
attendee_of: Person → Event (many_to_many)
located_at: Event/Person/Device → Location (many_to_one)
```

## Integration Patterns

### Cross-Skill Communication

Skills can communicate through shared ontology entities:

```python
# Email skill creates a Task
ontology.create("Task", {
    "title": "Send report by Friday",
    "status": "open",
    "due": "2026-01-31"
})

# Scheduler skill picks up pending tasks
tasks = ontology.query("Task", {"status": "open"})
for t in tasks:
    # Process pending tasks...
```

### Causal Action Logging

Log ontology mutations to an external action log for traceability:

```python
action_log.record({
    "action": "create_entity",
    "domain": "ontology",
    "context": {"type": "Task", "project": "proj_001"},
    "outcome": "created",
    "entity_id": "task_abc123"
})
```

## Planning as Graph Transformation

Model multi-step plans as a sequence of graph operations:

```
Plan: "Create task and assign to project"
1. CREATE Task { title: "Draft spec", status: "open" }
2. RELATE Task -> part_of -> proj_001
3. RELATE Task -> assigned_to -> pers_001
```

Plans execute atomically via `plan-create` + `plan-execute`. On any step failure, all changes are rolled back automatically using SQLite transactions.

## Skill Contract

Skills that use ontology should declare:

```yaml
ontology:
  reads: [Task, Project, Person]
  writes: [Task, Action]
  preconditions:
    - "Task.assignee must exist"
  postconditions:
    - "Created Task has status=open"
```

## References

- `references/schema.md` — Full type definitions and constraint patterns
- `references/queries.md` — Domain query patterns and usage examples

## Quick Start

```bash
# Initialize (automatic on first command - tables + core rules seeded)
python3 scripts/ontology.py stats

# Create entities in a namespace
python3 scripts/ontology.py create --type Person --props '{"name":"Alice"}' --namespace family-assets
python3 scripts/ontology.py create --type Project --props '{"name":"House Purchase","status":"active"}' --namespace family-assets

# Link entities via relations (not properties)
python3 scripts/ontology.py relate --from proj_001 --rel has_owner --to pers_001
python3 scripts/ontology.py relate --from proj_001 --rel assigned_to --to pers_001

# Query within namespace
python3 scripts/ontology.py list --type Task --namespace family-assets

# Need Event/Location/messaging types? Load extensions
python3 scripts/ontology.py seed-extensions

# Validate all constraints
python3 scripts/ontology.py validate
```
