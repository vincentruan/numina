# Ontology Schema Reference

Detailed type constraints and validation rules. For the type listing and relation vocabulary, see SKILL.md.

## Database Location

Default: `.ontology/ontology.db` at project root. Override via `--db` flag:

```bash
python3 scripts/ontology.py stats --db /custom/path/ontology.db
```

## Architecture: Core vs Extension Tiers

The ontology uses tiered seeding to keep the default schema focused:

- **Core tier** (8 types, 11 relations): Seeded automatically on first run. Covers people, work, documents, and actions.
- **Extension tier** (8 types, 4 relations): Loaded via `seed-extensions` command. Covers events, locations, messaging, accounts, and governance.

Extension types can also be added individually via `add-type`.

## Property Types

```yaml
string:    UTF-8 text
number:    int or float
boolean:   true/false
date:      "YYYY-MM-DD"
datetime:  ISO 8601 with timezone ("2026-01-15T09:30:00+08:00")
url:       valid URL string
enum:      one of a fixed set of values
ref:       entity ID reference (e.g., "p_001")
code_ref:  code symbol reference ("symbol:ClassName.method" or "file:path/to/file.py")
object:    nested JSON object
array:     JSON array (typed elements noted as type[])
```

## ID Generation

Format: `{type_prefix}_{uuid_hex8}`

- Prefix: first 4 lowercase chars of type name
- Suffix: 8 hex chars from uuid4
- Examples: `pers_a1b2c3d4`, `proj_e5f6a7b8`, `task_12345678`
- Custom IDs accepted via `--id` flag (must be unique)

## Namespace Partitioning

Entities have an optional `namespace` field (default: `"default"`). Use namespaces to separate bounded contexts:

```bash
# Create in a namespace
python3 scripts/ontology.py create --type Person --props '{"name":"Alice"}' --namespace family-assets

# Query within namespace
python3 scripts/ontology.py list --type Task --namespace work

# Relations cross namespaces — the graph is unified
python3 scripts/ontology.py relate --from pers_001 --rel has_task --to task_001
```

Namespaces are for organization, not isolation. Relations can link entities across namespaces.

## Constraint Tables

### entities

Core storage for domain entities:

```sql
CREATE TABLE entities (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    namespace TEXT NOT NULL DEFAULT 'default',
    properties TEXT NOT NULL DEFAULT '{}',
    created TEXT NOT NULL,
    updated TEXT NOT NULL
);

CREATE INDEX idx_entities_type ON entities(type);
CREATE INDEX idx_entities_namespace ON entities(namespace);
CREATE INDEX idx_entities_ns_type ON entities(namespace, type);
```

### relations

Entity relationships:

```sql
CREATE TABLE relations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_id TEXT NOT NULL,
    rel_type TEXT NOT NULL,
    to_id TEXT NOT NULL,
    properties TEXT NOT NULL DEFAULT '{}',
    created TEXT NOT NULL,
    FOREIGN KEY (from_id) REFERENCES entities(id) ON DELETE CASCADE,
    FOREIGN KEY (to_id) REFERENCES entities(id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX idx_relations_unique ON relations(from_id, rel_type, to_id);
```

### type_rules

Stores validation rules for entity types:

```sql
CREATE TABLE type_rules (
    type_name TEXT PRIMARY KEY,
    required_props TEXT NOT NULL DEFAULT '[]',
    enum_constraints TEXT NOT NULL DEFAULT '{}',
    forbidden_props TEXT NOT NULL DEFAULT '[]',
    created TEXT NOT NULL,
    updated TEXT NOT NULL
);
```

Example row:
```json
{
    "type_name": "Task",
    "required_props": ["title", "status"],
    "enum_constraints": {"status": ["open", "in_progress", "blocked", "done"], "priority": ["low", "medium", "high", "urgent"]},
    "forbidden_props": []
}
```

### relation_rules

Stores validation rules for relation types:

```sql
CREATE TABLE relation_rules (
    rel_type TEXT PRIMARY KEY,
    from_types TEXT NOT NULL DEFAULT '[]',
    to_types TEXT NOT NULL DEFAULT '[]',
    cardinality TEXT NOT NULL DEFAULT 'many_to_many',
    acyclic INTEGER NOT NULL DEFAULT 0,
    relation_props_schema TEXT NOT NULL DEFAULT '{}',
    created TEXT NOT NULL,
    updated TEXT NOT NULL
);
```

Example row:
```json
{
    "rel_type": "blocks",
    "from_types": ["Task"],
    "to_types": ["Task"],
    "cardinality": "many_to_many",
    "acyclic": 1
}
```

### plan_executions

Tracks multi-step plan execution state:

```sql
CREATE TABLE plan_executions (
    plan_id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    steps TEXT NOT NULL,
    executed_steps TEXT NOT NULL DEFAULT '[]',
    created TEXT NOT NULL,
    updated TEXT NOT NULL
);
```

Status values: `pending`, `executing`, `committed`, `rolled_back`

## Validation Constraints

### Required Properties

Entity must have these properties set (non-null) to pass validation:

#### Core Tier

```yaml
Person:       [name]
Organization: [name]
Project:      [name]
Task:         [title, status]
Goal:         [description]
Document:     [title]
Note:         [content]
Action:       [type, target, timestamp]
```

#### Extension Tier

```yaml
Event:        [title, start]
Location:     [name]
Message:      [content, sender]
Thread:       [subject]
Account:      [service, username]
Device:       [name, type]
Credential:   [service, secret_ref]
Policy:       [scope, rule]
```

### Enum Constraints

Properties restricted to specific values:

```yaml
# Core tier
Task.status:   [open, in_progress, blocked, done, cancelled]
Task.priority: [low, medium, high, urgent]
Project.status: [planning, active, paused, completed, archived]
Organization.type: [company, team, community, government, other]
Action.outcome: [success, failure, pending]

# Extension tier
Event.status:  [confirmed, tentative, cancelled]
Goal.status:   [active, achieved, abandoned]
Device.type:   [computer, phone, tablet, server, iot, other]
Policy.enforcement: [block, warn, log]
```

### Forbidden Properties

Properties that must NOT exist on an entity (security constraint):

```yaml
Credential: [password, secret, token, key, api_key]
```

Credentials must use `secret_ref` to reference external secret storage.

### Relation Constraints

```yaml
acyclic:
  - blocks (Task → Task)
  - depends_on (Task/Project → Task/Project)

cardinality:
  many_to_one:  has_owner, assigned_to, part_of, located_at, follows_up
  one_to_many:  has_task, has_goal, owns
  many_to_many: member_of, blocks, depends_on, mentions, references, attendee_of
```

### Dangling Relation Check

Relations where `from_id` or `to_id` references a non-existent entity are flagged as errors during validation.

## Date/Time Conventions

- Store all timestamps in ISO 8601 with UTC offset
- `created` and `updated` are auto-managed by the script
- User-facing dates (due, start, end, target_date) should include timezone
## CLI Command Reference

### Type Rule Commands

```bash
# Add custom type
python3 scripts/ontology.py add-type --type CustomType --required '["name"]' --enums '{"status":["a","b"]}'

# List all types
python3 scripts/ontology.py list-types

# Get type details
python3 scripts/ontology.py get-type --type Task

# Update type (merge with existing)
python3 scripts/ontology.py update-type --type Task --required '["title","status","priority"]'

# Delete custom type
python3 scripts/ontology.py delete-type --type CustomType
```

### Relation Rule Commands

```bash
# Add custom relation
python3 scripts/ontology.py add-relation-type --rel custom_rel --from-types '["Project"]' --to-types '["Document"]' --cardinality many_to_many

# List all relations
python3 scripts/ontology.py list-relation-types

# Get relation details
python3 scripts/ontology.py get-relation-type --rel blocks

# Delete custom relation
python3 scripts/ontology.py delete-relation-type --rel custom_rel
```

### Plan Execution Commands

```bash
# Create plan
python3 scripts/ontology.py plan-create --steps '[{"op":"create","type":"Task","props":{"title":"T","status":"open"}}]'

# Execute plan atomically
python3 scripts/ontology.py plan-execute --plan-id plan_abc123

# Check plan status
python3 scripts/ontology.py plan-status --plan-id plan_abc123
```

### Extension & Namespace Commands

```bash
# Load extension-tier types (Event, Location, messaging, IAM)
python3 scripts/ontology.py seed-extensions

# Create entity in a namespace
python3 scripts/ontology.py create --type Person --props '{"name":"Alice"}' --namespace family-assets

# Query within namespace
python3 scripts/ontology.py list --type Task --namespace work
python3 scripts/ontology.py search "asset" --namespace family-assets
```

### Validation

```bash
# Validate all constraints (entity props + relation types + dangling refs)
python3 scripts/ontology.py validate
```

- Date-only fields use `YYYY-MM-DD` format
