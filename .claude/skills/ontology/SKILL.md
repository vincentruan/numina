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

## Domain Entity Types

```yaml
# Agents & People
Person: { name, email?, phone?, notes? }
Organization: { name, type?, members[] }

# Work
Project: { name, status, goals[], owner? }
Task: { title, status, due?, priority?, assignee?, blockers[] }
Goal: { description, target_date?, metrics[] }

# Time & Place
Event: { title, start, end?, location?, attendees[], recurrence? }
Location: { name, address?, coordinates? }

# Information
Document: { title, path?, url?, summary? }
Message: { content, sender, recipients[], thread? }
Thread: { subject, participants[], messages[] }
Note: { content, tags[], refs[] }

# Resources
Account: { service, username, credential_ref? }
Device: { name, type, identifiers[] }
Credential: { service, secret_ref }  # Never store secrets directly

# Meta
Action: { type, target, timestamp, outcome? }
Policy: { scope, rule, enforcement }
```

## Storage

Database: `memory/ontology/ontology.db` (SQLite with WAL mode)

No external dependencies — uses Python stdlib `sqlite3`.

## CLI Usage

```bash
# Create
python3 scripts/ontology.py create --type Person --props '{"name":"Alice","email":"alice@example.com"}'

# Get by ID
python3 scripts/ontology.py get --id p_001

# Query with filter
python3 scripts/ontology.py query --type Task --where '{"status":"open"}'

# List all of a type
python3 scripts/ontology.py list --type Person

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

# Full-text search across all entities
python3 scripts/ontology.py search "Alice"
python3 scripts/ontology.py search "backend engineer" --type Person

# Graph statistics
python3 scripts/ontology.py stats

# Migrate legacy JSONL (one-time, idempotent)
python3 scripts/ontology.py migrate
```

## Relation Types

```yaml
# Ownership & Assignment
owns: Person/Organization → Account/Device/Document/Project
has_owner: Project/Task/Document → Person (many_to_one)
assigned_to: Task → Person (many_to_one)

# Hierarchy & Containment
has_task: Project → Task (one_to_many)
has_goal: Project → Goal (one_to_many)
member_of: Person → Organization (many_to_many)
part_of: Task/Document/Event → Project (many_to_one)

# Dependencies
blocks: Task → Task (acyclic)
depends_on: Task/Project → Task/Project/Event (acyclic)
requires: Action → Credential/Policy

# References
mentions: Document/Message/Note → Person/Project/Task/Event
references: Document/Note → Document/Note
follows_up: Task/Event → Event/Message

# Events
attendee_of: Person → Event (many_to_many)
located_at: Event/Person/Device → Location (many_to_one)
```

## Integration Patterns

### Cross-Skill Communication

Skills can communicate through shared ontology entities:

```python
# Email skill creates a commitment
ontology.create("Commitment", {
    "source_message": msg_id,
    "description": "Send report by Friday",
    "due": "2026-01-31"
})

# Task skill picks it up later
commitments = ontology.query("Commitment", {"status": "pending"})
for c in commitments:
    ontology.create("Task", {
        "title": c["properties"]["description"],
        "due": c["properties"]["due"],
        "source": c["id"]
    })
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
# Initialize (automatic on first command - tables + default rules seeded)
python3 scripts/ontology.py stats

# Add a custom type for your project
python3 scripts/ontology.py add-type --type Milestone --required '["name","date"]' --enums '{"status":["planned","active","done"]}'

# Create entities
python3 scripts/ontology.py create --type Person --props '{"name":"Alice"}'
python3 scripts/ontology.py create --type Milestone --props '{"name":"Launch","date":"2026-06-01","status":"planned"}'

# Link entities
python3 scripts/ontology.py relate --from pers_001 --rel owns --to mile_001

# Validate all constraints
python3 scripts/ontology.py validate
```
