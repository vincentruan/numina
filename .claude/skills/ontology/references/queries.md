# Query Reference

## Domain Queries (via SQLite)

Domain entity queries use the ontology.py script against `.ontology/ontology.db`.

### Basic CRUD

```bash
# Get by ID
python3 scripts/ontology.py get --id task_001

# List by type
python3 scripts/ontology.py list --type Task
python3 scripts/ontology.py list --type Person

# Filter by properties
python3 scripts/ontology.py query --type Task --where '{"status":"open"}'
python3 scripts/ontology.py query --type Task --where '{"priority":"high"}'
python3 scripts/ontology.py query --type Task --where '{"assignee":"p_001"}'
```

### Full-Text Search

```bash
# Search by name
python3 scripts/ontology.py search "Alice"

# Search within a type
python3 scripts/ontology.py search "backend" --type Person

# Search across all entities
python3 scripts/ontology.py search "deadline Friday"

# Multi-word search (matches any term)
python3 scripts/ontology.py search "React frontend"
```

### Graph Overview

```bash
# Entity and relation counts by type
python3 scripts/ontology.py stats
```

### Relation Queries

```bash
# Tasks belonging to a project (outgoing)
python3 scripts/ontology.py related --id proj_001 --rel has_task

# What projects does this task belong to (incoming)
python3 scripts/ontology.py related --id task_001 --rel part_of --dir incoming

# All relations for an entity (both directions)
python3 scripts/ontology.py related --id p_001 --dir both
```

### Common Patterns

```bash
# Who owns this project?
python3 scripts/ontology.py related --id proj_001 --rel has_owner

# What events is this person attending?
python3 scripts/ontology.py related --id p_001 --rel attendee_of --dir incoming

# What's blocking this task?
python3 scripts/ontology.py related --id task_001 --rel blocks --dir incoming
```

### Programmatic Access (Python)

```python
from scripts.ontology import get_db, query_entities, get_related, create_entity

conn = get_db(".ontology/ontology.db")

# Query entities
open_tasks = query_entities(conn, "Task", {"status": "open"})

# Get related
project_tasks = get_related(conn, "proj_001", "has_task")

# Create
entity = create_entity(conn, "Task", {"title": "New task", "status": "open"})

conn.close()
```

## Query Patterns by Use Case

### Task Management

```bash
# All open tasks
python3 scripts/ontology.py query --type Task --where '{"status":"open"}'

# High priority open tasks
python3 scripts/ontology.py query --type Task --where '{"status":"open","priority":"high"}'

# Tasks assigned to someone (use relation, not property)
python3 scripts/ontology.py related --id pers_001 --rel assigned_to --dir incoming

# Tasks within a namespace
python3 scripts/ontology.py query --type Task --where '{"status":"open"}' --namespace family-assets
```

### Project Overview

```bash
# All tasks in project
python3 scripts/ontology.py related --id proj_001 --rel has_task

# Project team members (via member_of, incoming direction)
python3 scripts/ontology.py related --id org_001 --rel member_of --dir incoming

# Project goals
python3 scripts/ontology.py related --id proj_001 --rel has_goal

# Project owner
python3 scripts/ontology.py related --id proj_001 --rel has_owner
```

### People & Contacts

```bash
# All people
python3 scripts/ontology.py list --type Person

# People in an organization
python3 scripts/ontology.py related --id org_001 --rel has_member --dir incoming

# What's assigned to this person
python3 scripts/ontology.py related --id p_001 --rel assigned_to --dir incoming
```

### Events & Calendar

```bash
# All events
python3 scripts/ontology.py list --type Event

# Event attendees
python3 scripts/ontology.py related --id event_001 --rel attendee_of --dir incoming

# Events at a location
python3 scripts/ontology.py related --id loc_001 --rel located_at --dir incoming
```
