# Ontology Schema Reference

Detailed type constraints and validation rules. For the type listing and relation vocabulary, see SKILL.md.

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
object:    nested JSON object
array:     JSON array (typed elements noted as type[])
```

## ID Generation

Format: `{type_prefix}_{uuid_hex8}`

- Prefix: first 4 lowercase chars of type name
- Suffix: 8 hex chars from uuid4
- Examples: `pers_a1b2c3d4`, `proj_e5f6a7b8`, `task_12345678`
- Custom IDs accepted via `--id` flag (must be unique)

## Constraint Tables

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

```yaml
Person:       [name]
Organization: [name]
Project:      [name]
Task:         [title, status]
Goal:         [description]
Event:        [title, start]
Location:     [name]
Document:     [title]
Message:      [content, sender]
Thread:       [subject]
Note:         [content]
Account:      [service, username]
Device:       [name, type]
Credential:   [service, secret_ref]
Action:       [type, target, timestamp]
Policy:       [scope, rule]
```

### Enum Constraints

Properties restricted to specific values:

```yaml
Task.status:   [open, in_progress, blocked, done, cancelled]
Task.priority: [low, medium, high, urgent]
Project.status: [planning, active, paused, completed, archived]
Organization.type: [company, team, community, government, other]
Event.status:  [confirmed, tentative, cancelled]
Goal.status:   [active, achieved, abandoned]
Device.type:   [computer, phone, tablet, server, iot, other]
Policy.enforcement: [block, warn, log]
Action.outcome: [success, failure, pending]
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
  - depends_on (Task/Project → Task/Project/Event)

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

### Validation

```bash
# Validate all constraints (entity props + relation types + dangling refs)
python3 scripts/ontology.py validate
```

- Date-only fields use `YYYY-MM-DD` format
