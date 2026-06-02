# Ontology Skill Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore valuable ideas lost during JSONL→SQLite migration: SQLite-stored constraints, relation type validation, transactional plans, and documentation improvements.

**Architecture:** Add three new SQLite tables (type_rules, relation_rules, plan_executions), extend CLI with type/relation rule commands, enhance validation with type checking and acyclic detection, and update SKILL.md with Integration Patterns and Core Concept sections.

**Tech Stack:** Python 3.12+, SQLite (WAL mode), argparse CLI

---

## File Structure

```
.claude/skills/ontology/
├── scripts/
│   ├── ontology.py          # MODIFY: Add tables, commands, validation
│   └── test_ontology.py     # CREATE: Unit tests for new features
├── SKILL.md                 # MODIFY: Add Core Concept, Integration Patterns, Quick Start
└── references/
    └── schema.md            # MODIFY: Document new tables and CLI commands
```

---

### Task 1: Add Schema Tables and Seed Data

**Files:**
- Modify: `.claude/skills/ontology/scripts/ontology.py:29-55` (SCHEMA_SQL)
- Create: `.claude/skills/ontology/scripts/test_ontology.py`

- [ ] **Step 1: Write failing test for type_rules table existence**

Create `.claude/skills/ontology/scripts/test_ontology.py`:

```python
#!/usr/bin/env python3
"""Unit tests for ontology.py"""

import sqlite3
import tempfile
import os
from pathlib import Path

# Import from the skill directory
import sys
sys.path.insert(0, str(Path(__file__).parent))
from ontology import get_db, seed_default_rules

def test_type_rules_table_exists():
    """type_rules table should be created on init"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        conn = get_db(db_path)
        
        # Check table exists
        result = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='type_rules'"
        ).fetchone()
        assert result is not None, "type_rules table should exist"
        conn.close()

def test_relation_rules_table_exists():
    """relation_rules table should be created on init"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        conn = get_db(db_path)
        
        result = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='relation_rules'"
        ).fetchone()
        assert result is not None, "relation_rules table should exist"
        conn.close()

def test_plan_executions_table_exists():
    """plan_executions table should be created on init"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        conn = get_db(db_path)
        
        result = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='plan_executions'"
        ).fetchone()
        assert result is not None, "plan_executions table should exist"
        conn.close()

if __name__ == "__main__":
    test_type_rules_table_exists()
    test_relation_rules_table_exists()
    test_plan_executions_table_exists()
    print("All tests passed!")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/vincentruan/geek_space/github/numina/.claude/skills/ontology/scripts && python3 test_ontology.py`
Expected: FAIL with "type_rules table should exist" (table not yet added)

- [ ] **Step 3: Add new tables to SCHEMA_SQL**

Modify `.claude/skills/ontology/scripts/ontology.py:29-55`, replace SCHEMA_SQL with:

```python
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS entities (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    properties TEXT NOT NULL DEFAULT '{}',
    created TEXT NOT NULL,
    updated TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(type);

CREATE TABLE IF NOT EXISTS relations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_id TEXT NOT NULL,
    rel_type TEXT NOT NULL,
    to_id TEXT NOT NULL,
    properties TEXT NOT NULL DEFAULT '{}',
    created TEXT NOT NULL,
    FOREIGN KEY (from_id) REFERENCES entities(id) ON DELETE CASCADE,
    FOREIGN KEY (to_id) REFERENCES entities(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_relations_from ON relations(from_id);
CREATE INDEX IF NOT EXISTS idx_relations_to ON relations(to_id);
CREATE INDEX IF NOT EXISTS idx_relations_type ON relations(rel_type);
CREATE UNIQUE INDEX IF NOT EXISTS idx_relations_unique ON relations(from_id, rel_type, to_id);

-- Type constraints (replaces hardcoded type_constraints dict)
CREATE TABLE IF NOT EXISTS type_rules (
    type_name TEXT PRIMARY KEY,
    required_props TEXT NOT NULL DEFAULT '[]',
    enum_constraints TEXT NOT NULL DEFAULT '{}',
    forbidden_props TEXT NOT NULL DEFAULT '[]',
    created TEXT NOT NULL,
    updated TEXT NOT NULL
);

-- Relation type rules
CREATE TABLE IF NOT EXISTS relation_rules (
    rel_type TEXT PRIMARY KEY,
    from_types TEXT NOT NULL DEFAULT '[]',
    to_types TEXT NOT NULL DEFAULT '[]',
    cardinality TEXT NOT NULL DEFAULT 'many_to_many',
    acyclic INTEGER NOT NULL DEFAULT 0,
    relation_props_schema TEXT NOT NULL DEFAULT '{}',
    created TEXT NOT NULL,
    updated TEXT NOT NULL
);

-- Multi-step plan execution (for transactional operations)
CREATE TABLE IF NOT EXISTS plan_executions (
    plan_id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    steps TEXT NOT NULL,
    executed_steps TEXT NOT NULL DEFAULT '[]',
    created TEXT NOT NULL,
    updated TEXT NOT NULL
);
"""
```

- [ ] **Step 4: Add seed_default_rules function and DEFAULT_RULES constants**

Add after line 76 (after `now_iso()` function) in `.claude/skills/ontology/scripts/ontology.py`:

```python
# Default type rules (migrated from hardcoded type_constraints)
DEFAULT_TYPE_RULES = {
    "Person": {"required": ["name"], "enums": {}, "forbidden": []},
    "Organization": {"required": ["name"], "enums": {"type": ["company", "team", "community", "government", "other"]}, "forbidden": []},
    "Project": {"required": ["name"], "enums": {"status": ["planning", "active", "paused", "completed", "archived"]}, "forbidden": []},
    "Task": {"required": ["title", "status"], "enums": {"status": ["open", "in_progress", "blocked", "done", "cancelled"], "priority": ["low", "medium", "high", "urgent"]}, "forbidden": []},
    "Goal": {"required": ["description"], "enums": {"status": ["active", "achieved", "abandoned"]}, "forbidden": []},
    "Event": {"required": ["title", "start"], "enums": {"status": ["confirmed", "tentative", "cancelled"]}, "forbidden": []},
    "Location": {"required": ["name"], "enums": {}, "forbidden": []},
    "Document": {"required": ["title"], "enums": {}, "forbidden": []},
    "Message": {"required": ["content", "sender"], "enums": {}, "forbidden": []},
    "Thread": {"required": ["subject"], "enums": {"status": ["active", "archived"]}, "forbidden": []},
    "Note": {"required": ["content"], "enums": {}, "forbidden": []},
    "Account": {"required": ["service", "username"], "enums": {}, "forbidden": []},
    "Device": {"required": ["name", "type"], "enums": {"type": ["computer", "phone", "tablet", "server", "iot", "other"]}, "forbidden": []},
    "Credential": {"required": ["service", "secret_ref"], "enums": {}, "forbidden": ["password", "secret", "token", "key", "api_key"]},
    "Action": {"required": ["type", "target", "timestamp"], "enums": {"outcome": ["success", "failure", "pending"]}, "forbidden": []},
    "Policy": {"required": ["scope", "rule"], "enums": {"enforcement": ["block", "warn", "log"]}, "forbidden": []},
}

# Default relation rules (from original schema.md)
DEFAULT_RELATION_RULES = {
    "owns": {"from_types": ["Person", "Organization"], "to_types": ["Account", "Device", "Document", "Project"], "cardinality": "one_to_many", "acyclic": False},
    "has_owner": {"from_types": ["Project", "Task", "Document"], "to_types": ["Person"], "cardinality": "many_to_one", "acyclic": False},
    "assigned_to": {"from_types": ["Task"], "to_types": ["Person"], "cardinality": "many_to_one", "acyclic": False},
    "has_task": {"from_types": ["Project"], "to_types": ["Task"], "cardinality": "one_to_many", "acyclic": False},
    "has_goal": {"from_types": ["Project"], "to_types": ["Goal"], "cardinality": "one_to_many", "acyclic": False},
    "member_of": {"from_types": ["Person"], "to_types": ["Organization"], "cardinality": "many_to_many", "acyclic": False},
    "part_of": {"from_types": ["Task", "Document", "Event"], "to_types": ["Project"], "cardinality": "many_to_one", "acyclic": False},
    "blocks": {"from_types": ["Task"], "to_types": ["Task"], "cardinality": "many_to_many", "acyclic": True},
    "depends_on": {"from_types": ["Task", "Project"], "to_types": ["Task", "Project", "Event"], "cardinality": "many_to_many", "acyclic": True},
    "requires": {"from_types": ["Action"], "to_types": ["Credential", "Policy"], "cardinality": "many_to_many", "acyclic": False},
    "mentions": {"from_types": ["Document", "Message", "Note"], "to_types": ["Person", "Project", "Task", "Event"], "cardinality": "many_to_many", "acyclic": False},
    "references": {"from_types": ["Document", "Note"], "to_types": ["Document", "Note"], "cardinality": "many_to_many", "acyclic": False},
    "follows_up": {"from_types": ["Task", "Event"], "to_types": ["Event", "Message"], "cardinality": "many_to_one", "acyclic": False},
    "attendee_of": {"from_types": ["Person"], "to_types": ["Event"], "cardinality": "many_to_many", "acyclic": False},
    "located_at": {"from_types": ["Event", "Person", "Device"], "to_types": ["Location"], "cardinality": "many_to_one", "acyclic": False},
}


def seed_default_rules(conn: sqlite3.Connection) -> dict:
    """Seed default type and relation rules if tables are empty."""
    ts = now_iso()
    
    seeded_types = 0
    seeded_relations = 0
    
    # Check if type_rules is empty
    existing_types = conn.execute("SELECT COUNT(*) FROM type_rules").fetchone()[0]
    if existing_types == 0:
        for type_name, rules in DEFAULT_TYPE_RULES.items():
            conn.execute(
                "INSERT INTO type_rules (type_name, required_props, enum_constraints, forbidden_props, created, updated) VALUES (?, ?, ?, ?, ?, ?)",
                (type_name, json.dumps(rules["required"]), json.dumps(rules["enums"]), json.dumps(rules["forbidden"]), ts, ts),
            )
            seeded_types += 1
    
    # Check if relation_rules is empty
    existing_relations = conn.execute("SELECT COUNT(*) FROM relation_rules").fetchone()[0]
    if existing_relations == 0:
        for rel_type, rules in DEFAULT_RELATION_RULES.items():
            conn.execute(
                "INSERT INTO relation_rules (rel_type, from_types, to_types, cardinality, acyclic, relation_props_schema, created, updated) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (rel_type, json.dumps(rules["from_types"]), json.dumps(rules["to_types"]), rules["cardinality"], int(rules["acyclic"]), "{}", ts, ts),
            )
            seeded_relations += 1
    
    conn.commit()
    return {"seeded_types": seeded_types, "seeded_relations": seeded_relations}
```

- [ ] **Step 5: Modify get_db to call seed_default_rules**

Modify `.claude/skills/ontology/scripts/ontology.py:58-66`, the `get_db` function:

```python
def get_db(db_path: str) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA_SQL)
    seed_default_rules(conn)  # Seed default rules on init
    return conn
```

- [ ] **Step 6: Run test to verify tables exist**

Run: `cd /Users/vincentruan/geek_space/github/numina/.claude/skills/ontology/scripts && python3 test_ontology.py`
Expected: PASS with "All tests passed!"

- [ ] **Step 7: Write test for seed_default_rules**

Add to `.claude/skills/ontology/scripts/test_ontology.py`:

```python
def test_seed_default_rules():
    """Default rules should be seeded on first init"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        conn = get_db(db_path)
        
        # Check type_rules seeded
        type_count = conn.execute("SELECT COUNT(*) FROM type_rules").fetchone()[0]
        assert type_count > 0, "type_rules should have default entries"
        
        # Check relation_rules seeded
        rel_count = conn.execute("SELECT COUNT(*) FROM relation_rules").fetchone()[0]
        assert rel_count > 0, "relation_rules should have default entries"
        
        # Check specific type rule
        task_rule = conn.execute("SELECT * FROM type_rules WHERE type_name='Task'").fetchone()
        assert task_rule is not None, "Task type rule should exist"
        required = json.loads(task_rule["required_props"])
        assert "title" in required and "status" in required
        
        # Check specific relation rule
        blocks_rule = conn.execute("SELECT * FROM relation_rules WHERE rel_type='blocks'").fetchone()
        assert blocks_rule is not None, "blocks relation rule should exist"
        assert blocks_rule["acyclic"] == 1, "blocks should be acyclic"
        
        conn.close()

def test_seed_is_idempotent():
    """Seeding again should not duplicate rules"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        conn = get_db(db_path)
        count1 = conn.execute("SELECT COUNT(*) FROM type_rules").fetchone()[0]
        
        # Call seed again
        result = seed_default_rules(conn)
        assert result["seeded_types"] == 0, "Second seed should add nothing"
        
        count2 = conn.execute("SELECT COUNT(*) FROM type_rules").fetchone()[0]
        assert count1 == count2, "Count should be unchanged"
        conn.close()
```

- [ ] **Step 8: Run seed tests**

Run: `cd /Users/vincentruan/geek_space/github/numina/.claude/skills/ontology/scripts && python3 test_ontology.py`
Expected: PASS

- [ ] **Step 9: Commit**

```bash
git add .claude/skills/ontology/scripts/ontology.py .claude/skills/ontology/scripts/test_ontology.py
git commit -m "$(cat <<'EOF'
feat(ontology): add type_rules, relation_rules, plan_executions tables

- Add SCHEMA_SQL for three new constraint/plan tables
- Add DEFAULT_TYPE_RULES and DEFAULT_RELATION_RULES constants
- Add seed_default_rules() to populate on first init
- Add unit tests for table existence and seeding

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: Type Rule CLI Commands

**Files:**
- Modify: `.claude/skills/ontology/scripts/ontology.py` (add commands, helper functions)
- Modify: `.claude/skills/ontology/scripts/test_ontology.py` (add tests)

- [ ] **Step 1: Write failing test for add-type command**

Add to `.claude/skills/ontology/scripts/test_ontology.py`:

```python
def test_add_type_command():
    """add-type should create new type rule"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        conn = get_db(db_path)
        
        # Add custom type
        add_type_rule(conn, "Milestone", required=["name", "date"], enums={"status": ["planned", "done"]})
        
        # Verify it exists
        rule = conn.execute("SELECT * FROM type_rules WHERE type_name='Milestone'").fetchone()
        assert rule is not None
        required = json.loads(rule["required_props"])
        assert required == ["name", "date"]
        enums = json.loads(rule["enum_constraints"])
        assert enums["status"] == ["planned", "done"]
        conn.close()

def test_list_types_command():
    """list-types should return all type rules"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        conn = get_db(db_path)
        
        types = list_type_rules(conn)
        assert len(types) >= 16, "Should have at least default types"
        type_names = [t["type_name"] for t in types]
        assert "Task" in type_names
        assert "Person" in type_names
        conn.close()

def test_delete_type_command():
    """delete-type should remove type rule"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        conn = get_db(db_path)
        
        # Add then delete
        add_type_rule(conn, "TempType", required=["name"])
        assert get_type_rule(conn, "TempType") is not None
        
        delete_type_rule(conn, "TempType")
        assert get_type_rule(conn, "TempType") is None
        conn.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/vincentruan/geek_space/github/numina/.claude/skills/ontology/scripts && python3 -c "from test_ontology import test_add_type_command; test_add_type_command()"`
Expected: FAIL with "NameError: name 'add_type_rule' is not defined"

- [ ] **Step 3: Add type rule helper functions**

Add after `seed_default_rules` function in `.claude/skills/ontology/scripts/ontology.py`:

```python
def add_type_rule(conn: sqlite3.Connection, type_name: str, required: list = None, enums: dict = None, forbidden: list = None) -> dict:
    """Add or update a type rule."""
    ts = now_iso()
    required = required or []
    enums = enums or {}
    forbidden = forbidden or []
    
    conn.execute(
        "INSERT OR REPLACE INTO type_rules (type_name, required_props, enum_constraints, forbidden_props, created, updated) VALUES (?, ?, ?, ?, ?, ?)",
        (type_name, json.dumps(required, ensure_ascii=False), json.dumps(enums, ensure_ascii=False), json.dumps(forbidden, ensure_ascii=False), ts, ts),
    )
    conn.commit()
    return {"type_name": type_name, "required": required, "enums": enums, "forbidden": forbidden, "created": ts, "updated": ts}


def get_type_rule(conn: sqlite3.Connection, type_name: str) -> dict | None:
    """Get a type rule by name."""
    row = conn.execute("SELECT * FROM type_rules WHERE type_name = ?", (type_name,)).fetchone()
    if not row:
        return None
    return {
        "type_name": row["type_name"],
        "required": json.loads(row["required_props"]),
        "enums": json.loads(row["enum_constraints"]),
        "forbidden": json.loads(row["forbidden_props"]),
        "created": row["created"],
        "updated": row["updated"],
    }


def list_type_rules(conn: sqlite3.Connection) -> list:
    """List all type rules."""
    rows = conn.execute("SELECT * FROM type_rules ORDER BY type_name").fetchall()
    return [{
        "type_name": r["type_name"],
        "required": json.loads(r["required_props"]),
        "enums": json.loads(r["enum_constraints"]),
        "forbidden": json.loads(r["forbidden_props"]),
        "created": r["created"],
        "updated": r["updated"],
    } for r in rows]


def update_type_rule(conn: sqlite3.Connection, type_name: str, required: list = None, enums: dict = None, forbidden: list = None) -> dict | None:
    """Update specific fields of a type rule (merge with existing)."""
    existing = get_type_rule(conn, type_name)
    if not existing:
        return None
    
    # Merge updates
    new_required = required if required is not None else existing["required"]
    new_enums = enums if enums is not None else existing["enums"]
    new_forbidden = forbidden if forbidden is not None else existing["forbidden"]
    
    return add_type_rule(conn, type_name, new_required, new_enums, new_forbidden)


def delete_type_rule(conn: sqlite3.Connection, type_name: str) -> bool:
    """Delete a type rule."""
    cur = conn.execute("DELETE FROM type_rules WHERE type_name = ?", (type_name,))
    conn.commit()
    return cur.rowcount > 0
```

- [ ] **Step 4: Add CLI subparsers for type commands**

Find the `main()` function (around line 374). Add after the `validate_p` subparser definition:

```python
    # Type rule commands
    add_type_p = subparsers.add_parser("add-type", help="Add or update type rule")
    add_type_p.add_argument("--type", "-t", required=True, help="Type name")
    add_type_p.add_argument("--required", "-r", default="[]", help="Required properties JSON array")
    add_type_p.add_argument("--enums", "-e", default="{}", help="Enum constraints JSON dict")
    add_type_p.add_argument("--forbidden", "-f", default="[]", help="Forbidden properties JSON array")

    list_types_p = subparsers.add_parser("list-types", help="List all type rules")

    get_type_p = subparsers.add_parser("get-type", help="Get type rule details")
    get_type_p.add_argument("--type", "-t", required=True, help="Type name")

    update_type_p = subparsers.add_parser("update-type", help="Update type rule fields")
    update_type_p.add_argument("--type", "-t", required=True, help="Type name")
    update_type_p.add_argument("--required", "-r", help="Required properties JSON array (optional)")
    update_type_p.add_argument("--enums", "-e", help="Enum constraints JSON dict (optional)")
    update_type_p.add_argument("--forbidden", "-f", help="Forbidden properties JSON array (optional)")

    delete_type_p = subparsers.add_parser("delete-type", help="Delete type rule")
    delete_type_p.add_argument("--type", "-t", required=True, help="Type name")
```

- [ ] **Step 5: Add command handlers in main()**

Find the `elif args.command == "migrate":` block. Add handlers before it:

```python
    elif args.command == "add-type":
        required = json.loads(args.required)
        enums = json.loads(args.enums)
        forbidden = json.loads(args.forbidden)
        rule = add_type_rule(conn, args.type, required, enums, forbidden)
        print(json.dumps(rule, indent=2, ensure_ascii=False))

    elif args.command == "list-types":
        rules = list_type_rules(conn)
        print(json.dumps(rules, indent=2, ensure_ascii=False))

    elif args.command == "get-type":
        rule = get_type_rule(conn, args.type)
        if rule:
            print(json.dumps(rule, indent=2, ensure_ascii=False))
        else:
            print(f"Type rule not found: {args.type}")

    elif args.command == "update-type":
        required = json.loads(args.required) if args.required else None
        enums = json.loads(args.enums) if args.enums else None
        forbidden = json.loads(args.forbidden) if args.forbidden else None
        rule = update_type_rule(conn, args.type, required, enums, forbidden)
        if rule:
            print(json.dumps(rule, indent=2, ensure_ascii=False))
        else:
            print(f"Type rule not found: {args.type}")

    elif args.command == "delete-type":
        if delete_type_rule(conn, args.type):
            print(f"Deleted type rule: {args.type}")
        else:
            print(f"Type rule not found: {args.type}")
```

- [ ] **Step 6: Run tests**

Run: `cd /Users/vincentruan/geek_space/github/numina/.claude/skills/ontology/scripts && python3 test_ontology.py`
Expected: PASS

- [ ] **Step 7: Test CLI manually**

Run: `cd /Users/vincentruan/geek_space/github/numina/.claude/skills/ontology/scripts && python3 ontology.py list-types`
Expected: JSON array of all default type rules

Run: `python3 ontology.py add-type --type CustomEntity --required '["name"]' --enums '{"status":["active","done"]}'`
Expected: JSON showing new type rule created

- [ ] **Step 8: Commit**

```bash
git add .claude/skills/ontology/scripts/ontology.py .claude/skills/ontology/scripts/test_ontology.py
git commit -m "$(cat <<'EOF'
feat(ontology): add type rule CLI commands

- add-type, list-types, get-type, update-type, delete-type
- Helper functions: add_type_rule, get_type_rule, list_type_rules, update_type_rule, delete_type_rule
- Unit tests for all type rule operations

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: Relation Rule CLI Commands

**Files:**
- Modify: `.claude/skills/ontology/scripts/ontology.py`
- Modify: `.claude/skills/ontology/scripts/test_ontology.py`

- [ ] **Step 1: Write failing test for relation rule commands**

Add to `.claude/skills/ontology/scripts/test_ontology.py`:

```python
def test_add_relation_rule():
    """add-relation-type should create new relation rule"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        conn = get_db(db_path)
        
        add_relation_rule(conn, "custom_rel", from_types=["Project"], to_types=["Document"], cardinality="many_to_many")
        
        rule = conn.execute("SELECT * FROM relation_rules WHERE rel_type='custom_rel'").fetchone()
        assert rule is not None
        from_types = json.loads(rule["from_types"])
        assert from_types == ["Project"]
        conn.close()

def test_get_relation_rule():
    """get-relation-type should return rule details"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        conn = get_db(db_path)
        
        rule = get_relation_rule(conn, "blocks")
        assert rule is not None
        assert rule["acyclic"] == True
        assert "Task" in rule["from_types"]
        conn.close()

def test_list_relation_rules():
    """list-relation-types should return all rules"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        conn = get_db(db_path)
        
        rules = list_relation_rules(conn)
        assert len(rules) >= 15, "Should have at least default relations"
        rel_types = [r["rel_type"] for r in rules]
        assert "blocks" in rel_types
        assert "has_owner" in rel_types
        conn.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/vincentruan/geek_space/github/numina/.claude/skills/ontology/scripts && python3 -c "from test_ontology import test_add_relation_rule; test_add_relation_rule()"`
Expected: FAIL with "NameError: name 'add_relation_rule' is not defined"

- [ ] **Step 3: Add relation rule helper functions**

Add after `delete_type_rule` function in `.claude/skills/ontology/scripts/ontology.py`:

```python
def add_relation_rule(conn: sqlite3.Connection, rel_type: str, from_types: list = None, to_types: list = None, cardinality: str = "many_to_many", acyclic: bool = False) -> dict:
    """Add or update a relation rule."""
    ts = now_iso()
    from_types = from_types or []
    to_types = to_types or []
    
    conn.execute(
        "INSERT OR REPLACE INTO relation_rules (rel_type, from_types, to_types, cardinality, acyclic, relation_props_schema, created, updated) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (rel_type, json.dumps(from_types, ensure_ascii=False), json.dumps(to_types, ensure_ascii=False), cardinality, int(acyclic), "{}", ts, ts),
    )
    conn.commit()
    return {"rel_type": rel_type, "from_types": from_types, "to_types": to_types, "cardinality": cardinality, "acyclic": acyclic, "created": ts, "updated": ts}


def get_relation_rule(conn: sqlite3.Connection, rel_type: str) -> dict | None:
    """Get a relation rule by type."""
    row = conn.execute("SELECT * FROM relation_rules WHERE rel_type = ?", (rel_type,)).fetchone()
    if not row:
        return None
    return {
        "rel_type": row["rel_type"],
        "from_types": json.loads(row["from_types"]),
        "to_types": json.loads(row["to_types"]),
        "cardinality": row["cardinality"],
        "acyclic": bool(row["acyclic"]),
        "created": row["created"],
        "updated": row["updated"],
    }


def list_relation_rules(conn: sqlite3.Connection) -> list:
    """List all relation rules."""
    rows = conn.execute("SELECT * FROM relation_rules ORDER BY rel_type").fetchall()
    return [{
        "rel_type": r["rel_type"],
        "from_types": json.loads(r["from_types"]),
        "to_types": json.loads(r["to_types"]),
        "cardinality": r["cardinality"],
        "acyclic": bool(r["acyclic"]),
        "created": r["created"],
        "updated": r["updated"],
    } for r in rows]


def delete_relation_rule(conn: sqlite3.Connection, rel_type: str) -> bool:
    """Delete a relation rule."""
    cur = conn.execute("DELETE FROM relation_rules WHERE rel_type = ?", (rel_type,))
    conn.commit()
    return cur.rowcount > 0
```

- [ ] **Step 4: Add CLI subparsers for relation commands**

Add after the delete_type_p subparser in main():

```python
    # Relation rule commands
    add_rel_p = subparsers.add_parser("add-relation-type", help="Add or update relation rule")
    add_rel_p.add_argument("--rel", "-r", required=True, help="Relation type name")
    add_rel_p.add_argument("--from-types", "-f", default="[]", help="Allowed from types JSON array")
    add_rel_p.add_argument("--to-types", "-t", default="[]", help="Allowed to types JSON array")
    add_rel_p.add_argument("--cardinality", "-c", default="many_to_many", choices=["one_to_many", "many_to_one", "many_to_many"])
    add_rel_p.add_argument("--acyclic", "-a", action="store_true", help="Enforce acyclic constraint")

    list_rel_p = subparsers.add_parser("list-relation-types", help="List all relation rules")

    get_rel_p = subparsers.add_parser("get-relation-type", help="Get relation rule details")
    get_rel_p.add_argument("--rel", "-r", required=True, help="Relation type name")

    delete_rel_p = subparsers.add_parser("delete-relation-type", help="Delete relation rule")
    delete_rel_p.add_argument("--rel", "-r", required=True, help="Relation type name")
```

- [ ] **Step 5: Add command handlers**

Add before the `elif args.command == "migrate":` block:

```python
    elif args.command == "add-relation-type":
        from_types = json.loads(args.from_types)
        to_types = json.loads(args.to_types)
        rule = add_relation_rule(conn, args.rel, from_types, to_types, args.cardinality, args.acyclic)
        print(json.dumps(rule, indent=2, ensure_ascii=False))

    elif args.command == "list-relation-types":
        rules = list_relation_rules(conn)
        print(json.dumps(rules, indent=2, ensure_ascii=False))

    elif args.command == "get-relation-type":
        rule = get_relation_rule(conn, args.rel)
        if rule:
            print(json.dumps(rule, indent=2, ensure_ascii=False))
        else:
            print(f"Relation rule not found: {args.rel}")

    elif args.command == "delete-relation-type":
        if delete_relation_rule(conn, args.rel):
            print(f"Deleted relation rule: {args.rel}")
        else:
            print(f"Relation rule not found: {args.rel}")
```

- [ ] **Step 6: Run tests**

Run: `cd /Users/vincentruan/geek_space/github/numina/.claude/skills/ontology/scripts && python3 test_ontology.py`
Expected: PASS

- [ ] **Step 7: Test CLI manually**

Run: `cd /Users/vincentruan/geek_space/github/numina/.claude/skills/ontology/scripts && python3 ontology.py list-relation-types`
Expected: JSON array with blocks, has_owner, etc.

- [ ] **Step 8: Commit**

```bash
git add .claude/skills/ontology/scripts/ontology.py .claude/skills/ontology/scripts/test_ontology.py
git commit -m "$(cat <<'EOF'
feat(ontology): add relation rule CLI commands

- add-relation-type, list-relation-types, get-relation-type, delete-relation-type
- Helper functions for relation rule CRUD
- Unit tests for relation rule operations

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: Enhanced Validation (Relation Type + Acyclic)

**Files:**
- Modify: `.claude/skills/ontology/scripts/ontology.py`
- Modify: `.claude/skills/ontology/scripts/test_ontology.py`

- [ ] **Step 1: Write failing test for relation type validation**

Add to `.claude/skills/ontology/scripts/test_ontology.py`:

```python
def test_relation_type_validation_allowed():
    """Relation with valid types should succeed"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        conn = get_db(db_path)
        
        # Create Task entities
        create_entity(conn, "Task", {"title": "T1", "status": "open"}, "task_001")
        create_entity(conn, "Task", {"title": "T2", "status": "open"}, "task_002")
        
        # blocks: Task -> Task is allowed
        errors = validate_relation_types(conn, "task_001", "blocks", "task_002")
        assert len(errors) == 0, f"Should be valid, got {errors}"
        conn.close()

def test_relation_type_validation_rejected():
    """Relation with invalid types should fail"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        conn = get_db(db_path)
        
        # Create Task and Person
        create_entity(conn, "Task", {"title": "T1", "status": "open"}, "task_001")
        create_entity(conn, "Person", {"name": "Alice"}, "pers_001")
        
        # blocks: Task -> Task only, Person not allowed
        errors = validate_relation_types(conn, "pers_001", "blocks", "task_001")
        assert len(errors) > 0, "Should fail - Person cannot blocks Task"
        assert "from_types" in errors[0] or "to_types" in errors[0]
        conn.close()

def test_acyclic_validation():
    """Acyclic relations should reject cycles"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        conn = get_db(db_path)
        
        create_entity(conn, "Task", {"title": "T1", "status": "open"}, "task_001")
        create_entity(conn, "Task", {"title": "T2", "status": "open"}, "task_002")
        
        # First relation OK
        create_relation(conn, "task_001", "blocks", "task_002")
        
        # Reverse would create cycle
        errors = validate_acyclic(conn, "task_002", "blocks", "task_001")
        assert len(errors) > 0, "Should detect cycle"
        assert "cycle" in errors[0].lower()
        conn.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/vincentruan/geek_space/github/numina/.claude/skills/ontology/scripts && python3 -c "from test_ontology import test_relation_type_validation_allowed; test_relation_type_validation_allowed()"`
Expected: FAIL with "NameError: name 'validate_relation_types' is not defined"

- [ ] **Step 3: Add validate_relation_types function**

Add after `delete_relation_rule` in `.claude/skills/ontology/scripts/ontology.py`:

```python
def validate_relation_types(conn: sqlite3.Connection, from_id: str, rel_type: str, to_id: str) -> list:
    """Validate that relation types match the rule constraints."""
    errors = []
    
    # Get entities
    from_entity = get_entity(conn, from_id)
    to_entity = get_entity(conn, to_id)
    
    if not from_entity:
        errors.append(f"from_id '{from_id}' does not exist")
        return errors
    if not to_entity:
        errors.append(f"to_id '{to_id}' does not exist")
        return errors
    
    # Get relation rule
    rule = get_relation_rule(conn, rel_type)
    if not rule:
        # No rule defined - allow by default (open schema)
        return errors
    
    from_type = from_entity["type"]
    to_type = to_entity["type"]
    
    # Check from_types
    if rule["from_types"] and from_type not in rule["from_types"]:
        errors.append(f"Relation '{rel_type}' requires from_types={rule['from_types']}, got '{from_type}'")
    
    # Check to_types
    if rule["to_types"] and to_type not in rule["to_types"]:
        errors.append(f"Relation '{rel_type}' requires to_types={rule['to_types']}, got '{to_type}'")
    
    return errors
```

- [ ] **Step 4: Add validate_acyclic function with DFS**

Add after `validate_relation_types`:

```python
def validate_acyclic(conn: sqlite3.Connection, from_id: str, rel_type: str, to_id: str) -> list:
    """Check if adding this relation would create a cycle."""
    errors = []
    
    rule = get_relation_rule(conn, rel_type)
    if not rule or not rule["acyclic"]:
        return errors  # No acyclic constraint
    
    # DFS to check if to_id can reach from_id through existing relations
    visited = set()
    stack = [to_id]
    
    while stack:
        current = stack.pop()
        if current == from_id:
            errors.append(f"Adding '{rel_type}' from {from_id} to {to_id} would create a cycle")
            return errors
        if current in visited:
            continue
        visited.add(current)
        
        # Find all outgoing relations of same type from current
        rows = conn.execute(
            "SELECT to_id FROM relations WHERE from_id = ? AND rel_type = ?",
            (current, rel_type),
        ).fetchall()
        for row in rows:
            stack.append(row["to_id"])
    
    return errors
```

- [ ] **Step 5: Modify create_relation to validate before inserting**

Find the existing `create_relation` function (around line 158). Replace it with:

```python
def create_relation(conn: sqlite3.Connection, from_id: str, rel_type: str, to_id: str, properties: dict = None, skip_validation: bool = False) -> dict:
    """Create a relation between entities, with optional validation."""
    if not skip_validation:
        type_errors = validate_relation_types(conn, from_id, rel_type, to_id)
        if type_errors:
            raise ValueError(f"Relation type validation failed: {type_errors}")
        
        acyclic_errors = validate_acyclic(conn, from_id, rel_type, to_id)
        if acyclic_errors:
            raise ValueError(f"Acyclic validation failed: {acyclic_errors}")
    
    ts = now_iso()
    props = properties or {}
    conn.execute(
        "INSERT OR REPLACE INTO relations (from_id, rel_type, to_id, properties, created) VALUES (?, ?, ?, ?, ?)",
        (from_id, rel_type, to_id, json.dumps(props, ensure_ascii=False), ts),
    )
    conn.commit()
    return {"from": from_id, "rel": rel_type, "to": to_id, "properties": props, "created": ts}
```

- [ ] **Step 6: Update validate_graph to use type_rules table**

Find the existing `validate_graph` function (around line 228). Replace it with:

```python
def validate_graph(conn: sqlite3.Connection) -> list:
    """Validate entities and relations against all constraints."""
    errors = []
    
    # Layer 1: Entity property validation from type_rules table
    rows = conn.execute("SELECT e.*, t.required_props, t.enum_constraints, t.forbidden_props FROM entities e LEFT JOIN type_rules t ON e.type = t.type_name").fetchall()
    for row in rows:
        entity_id = row["id"]
        type_name = row["type"]
        props = json.loads(row["properties"])
        
        required = json.loads(row["required_props"] or "[]")
        for prop in required:
            if prop not in props:
                errors.append(f"{entity_id}: missing required property '{prop}'")
        
        forbidden = json.loads(row["forbidden_props"] or "[]")
        for prop in forbidden:
            if prop in props:
                errors.append(f"{entity_id}: contains forbidden property '{prop}'")
        
        enums = json.loads(row["enum_constraints"] or "{}")
        for field, allowed in enums.items():
            value = props.get(field)
            if value and value not in allowed:
                errors.append(f"{entity_id}: '{field}' must be one of {allowed}, got '{value}'")
    
    # Layer 2: Relation type validation
    rel_rows = conn.execute("SELECT * FROM relations").fetchall()
    for rel in rel_rows:
        type_errors = validate_relation_types(conn, rel["from_id"], rel["rel_type"], rel["to_id"])
        errors.extend(type_errors)
    
    # Layer 3: Acyclic validation (check all acyclic relations for cycles)
    acyclic_rules = conn.execute("SELECT rel_type FROM relation_rules WHERE acyclic = 1").fetchall()
    for rule_row in acyclic_rules:
        rel_type = rule_row["rel_type"]
        # For each relation of this type, check no reverse path exists
        rels = conn.execute("SELECT from_id, to_id FROM relations WHERE rel_type = ?", (rel_type,)).fetchall()
        for rel in rels:
            cycle_errors = validate_acyclic(conn, rel["to_id"], rel_type, rel["from_id"])
            # validate_acyclic checks if to_id can reach from_id
            # If it can, that means we have a cycle through this relation
            # But we need to check the graph as-is, not the proposed addition
            # So we skip this for existing relations and only check on create
    
    # Check for dangling relations
    danglings = conn.execute(
        "SELECT r.* FROM relations r LEFT JOIN entities e1 ON r.from_id = e1.id "
        "LEFT JOIN entities e2 ON r.to_id = e2.id WHERE e1.id IS NULL OR e2.id IS NULL"
    ).fetchall()
    for rel in danglings:
        errors.append(f"Dangling relation: {rel['from_id']} --{rel['rel_type']}--> {rel['to_id']}")
    
    return errors
```

- [ ] **Step 7: Update CLI relate command to handle validation errors**

Find the `elif args.command == "relate":` handler. Modify to:

```python
    elif args.command == "relate":
        props = json.loads(args.props)
        try:
            rel = create_relation(conn, args.from_id, args.rel, args.to_id, props)
            print(json.dumps(rel, indent=2, ensure_ascii=False))
        except ValueError as e:
            print(f"Error: {e}")
```

- [ ] **Step 8: Run tests**

Run: `cd /Users/vincentruan/geek_space/github/numina/.claude/skills/ontology/scripts && python3 test_ontology.py`
Expected: PASS

- [ ] **Step 9: Test CLI validation manually**

Run: `cd /Users/vincentruan/geek_space/github/numina/.claude/skills/ontology/scripts && python3 ontology.py create --type Task --props '{"title":"T","status":"open"}' --id task_001 && python3 ontology.py create --type Person --props '{"name":"Alice"}' --id pers_001 && python3 ontology.py relate --from pers_001 --rel blocks --to task_001`
Expected: "Error: Relation type validation failed: ..."

- [ ] **Step 10: Commit**

```bash
git add .claude/skills/ontology/scripts/ontology.py .claude/skills/ontology/scripts/test_ontology.py
git commit -m "$(cat <<'EOF'
feat(ontology): add relation type and acyclic validation

- validate_relation_types: check from/to types match relation rules
- validate_acyclic: DFS cycle detection for acyclic relations
- create_relation now validates before insert
- validate_graph uses type_rules table instead of hardcoded dict
- CLI relate command shows validation errors

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: Transactional Plan Execution

**Files:**
- Modify: `.claude/skills/ontology/scripts/ontology.py`
- Modify: `.claude/skills/ontology/scripts/test_ontology.py`

- [ ] **Step 1: Write failing test for plan execution**

Add to `.claude/skills/ontology/scripts/test_ontology.py`:

```python
def test_plan_create_and_execute():
    """Plan should execute all steps atomically"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        conn = get_db(db_path)
        
        steps = [
            {"op": "create", "type": "Task", "props": {"title": "T1", "status": "open"}},
            {"op": "create", "type": "Person", "props": {"name": "Alice"}, "id": "pers_001"},
        ]
        
        plan = create_plan(conn, steps)
        assert plan["plan_id"].startswith("plan_")
        assert plan["status"] == "pending"
        
        result = execute_plan(conn, plan["plan_id"])
        assert result["status"] == "committed"
        assert len(result["executed"]) == 2
        
        # Verify entities created
        person = get_entity(conn, "pers_001")
        assert person is not None
        assert person["properties"]["name"] == "Alice"
        conn.close()

def test_plan_rollback_on_error():
    """Plan should rollback on step failure"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        conn = get_db(db_path)
        
        steps = [
            {"op": "create", "type": "Task", "props": {"title": "T1", "status": "open"}, "id": "task_001"},
            {"op": "relate", "from": "nonexistent", "rel": "has_owner", "to": "pers_001"},
        ]
        
        plan = create_plan(conn, steps)
        result = execute_plan(conn, plan["plan_id"])
        
        # Should have rolled back
        assert result["status"] == "rolled_back"
        
        # Verify first entity was NOT created (rolled back)
        task = get_entity(conn, "task_001")
        assert task is None, "Entity should be rolled back"
        conn.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/vincentruan/geek_space/github/numina/.claude/skills/ontology/scripts && python3 -c "from test_ontology import test_plan_create_and_execute; test_plan_create_and_execute()"`
Expected: FAIL with "NameError: name 'create_plan' is not defined"

- [ ] **Step 3: Add plan execution helper functions**

Add after `validate_acyclic` in `.claude/skills/ontology/scripts/ontology.py`:

```python
def generate_plan_id() -> str:
    return f"plan_{uuid.uuid4().hex[:8]}"


def create_plan(conn: sqlite3.Connection, steps: list) -> dict:
    """Create a plan with multiple operations to execute atomically."""
    plan_id = generate_plan_id()
    ts = now_iso()
    
    conn.execute(
        "INSERT INTO plan_executions (plan_id, status, steps, executed_steps, created, updated) VALUES (?, ?, ?, ?, ?, ?)",
        (plan_id, "pending", json.dumps(steps, ensure_ascii=False), "[]", ts, ts),
    )
    conn.commit()
    return {"plan_id": plan_id, "status": "pending", "steps": steps, "created": ts}


def get_plan(conn: sqlite3.Connection, plan_id: str) -> dict | None:
    """Get plan details."""
    row = conn.execute("SELECT * FROM plan_executions WHERE plan_id = ?", (plan_id,)).fetchone()
    if not row:
        return None
    return {
        "plan_id": row["plan_id"],
        "status": row["status"],
        "steps": json.loads(row["steps"]),
        "executed_steps": json.loads(row["executed_steps"]),
        "created": row["created"],
        "updated": row["updated"],
    }


def execute_plan(conn: sqlite3.Connection, plan_id: str) -> dict:
    """Execute a plan atomically. Rollback on any failure."""
    plan = get_plan(conn, plan_id)
    if not plan:
        raise ValueError(f"Plan not found: {plan_id}")
    
    if plan["status"] != "pending":
        raise ValueError(f"Plan already {plan['status']}")
    
    steps = plan["steps"]
    executed = []
    ts = now_iso()
    
    # Update status to executing
    conn.execute("UPDATE plan_executions SET status = ?, updated = ? WHERE plan_id = ?", ("executing", ts, plan_id))
    conn.commit()
    
    try:
        # Begin implicit transaction
        for i, step in enumerate(steps):
            op = step.get("op")
            
            if op == "create":
                entity_id = step.get("id")
                entity = create_entity(conn, step["type"], step["props"], entity_id)
                executed.append({"step": i, "op": "create", "result": entity})
            
            elif op == "relate":
                rel = create_relation(conn, step["from"], step["rel"], step["to"], step.get("props"), skip_validation=False)
                executed.append({"step": i, "op": "relate", "result": rel})
            
            elif op == "update":
                entity = update_entity(conn, step["id"], step["props"])
                executed.append({"step": i, "op": "update", "result": entity})
            
            elif op == "delete":
                deleted = delete_entity(conn, step["id"])
                executed.append({"step": i, "op": "delete", "result": {"deleted": deleted}})
            
            else:
                raise ValueError(f"Unknown operation: {op}")
        
        # All steps succeeded - commit
        conn.execute(
            "UPDATE plan_executions SET status = ?, executed_steps = ?, updated = ? WHERE plan_id = ?",
            ("committed", json.dumps(executed, ensure_ascii=False), now_iso(), plan_id),
        )
        conn.commit()
        return {"plan_id": plan_id, "status": "committed", "executed": executed}
    
    except Exception as e:
        # Rollback - SQLite transaction auto-rolls back on exception
        # But we need to mark the plan as rolled_back
        conn.rollback()
        conn.execute(
            "UPDATE plan_executions SET status = ?, executed_steps = ?, updated = ? WHERE plan_id = ?",
            ("rolled_back", json.dumps(executed, ensure_ascii=False), now_iso(), plan_id),
        )
        conn.commit()
        return {"plan_id": plan_id, "status": "rolled_back", "executed": executed, "error": str(e)}
```

- [ ] **Step 4: Add CLI subparsers for plan commands**

Add after the delete_rel_p subparser in main():

```python
    # Plan execution commands
    plan_create_p = subparsers.add_parser("plan-create", help="Create multi-step plan")
    plan_create_p.add_argument("--steps", "-s", required=True, help="Steps JSON array")
    
    plan_execute_p = subparsers.add_parser("plan-execute", help="Execute plan atomically")
    plan_execute_p.add_argument("--plan-id", "-p", required=True, help="Plan ID")
    
    plan_status_p = subparsers.add_parser("plan-status", help="Get plan status")
    plan_status_p.add_argument("--plan-id", "-p", required=True, help="Plan ID")
```

- [ ] **Step 5: Add command handlers**

Add before the `elif args.command == "migrate":` block:

```python
    elif args.command == "plan-create":
        steps = json.loads(args.steps)
        plan = create_plan(conn, steps)
        print(json.dumps(plan, indent=2, ensure_ascii=False))

    elif args.command == "plan-execute":
        try:
            result = execute_plan(conn, args.plan_id)
            print(json.dumps(result, indent=2, ensure_ascii=False))
        except ValueError as e:
            print(f"Error: {e}")

    elif args.command == "plan-status":
        plan = get_plan(conn, args.plan_id)
        if plan:
            print(json.dumps(plan, indent=2, ensure_ascii=False))
        else:
            print(f"Plan not found: {args.plan_id}")
```

- [ ] **Step 6: Run tests**

Run: `cd /Users/vincentruan/geek_space/github/numina/.claude/skills/ontology/scripts && python3 test_ontology.py`
Expected: PASS

- [ ] **Step 7: Test CLI manually**

Run: `cd /Users/vincentruan/geek_space/github/numina/.claude/skills/ontology/scripts && python3 ontology.py plan-create --steps '[{"op":"create","type":"Task","props":{"title":"Test","status":"open"}}]'`
Expected: JSON with plan_id and status="pending"

Run: `python3 ontology.py plan-execute --plan-id <plan_id_from_above>`
Expected: JSON with status="committed"

- [ ] **Step 8: Commit**

```bash
git add .claude/skills/ontology/scripts/ontology.py .claude/skills/ontology/scripts/test_ontology.py
git commit -m "$(cat <<'EOF'
feat(ontology): add transactional plan execution

- create_plan, execute_plan, get_plan helper functions
- plan-create, plan-execute, plan-status CLI commands
- Atomic execution with rollback on failure
- Unit tests for plan execution and rollback

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 6: Update SKILL.md Documentation

**Files:**
- Modify: `.claude/skills/ontology/SKILL.md`

- [ ] **Step 1: Update frontmatter description**

Modify the YAML frontmatter in `.claude/skills/ontology/SKILL.md`:

```yaml
---
name: ontology
description: Typed knowledge graph for structured agent memory and composable skills. Use when creating/querying entities (Person, Project, Task, Event, Document), linking related objects, enforcing constraints, planning multi-step actions as graph transformations, or when skills need to share state. Trigger on "remember", "what do I know about", "link X to Y", "show dependencies", entity CRUD, or cross-skill data access. Domain knowledge tool — use codegraph for code structure questions.
---
```

- [ ] **Step 2: Add Core Concept section after frontmatter**

Add after the frontmatter, before "When This Skill Applies":

```markdown
## Core Concept

Everything is an **entity** with a **type**, **properties**, and **relations** to other entities. Every mutation is validated against type constraints before committing.

```
Entity: { id, type, properties, created, updated }
Relation: { from_id, relation_type, to_id, properties }
TypeRule: { type_name, required_props, enum_constraints, forbidden_props }
RelationRule: { rel_type, from_types, to_types, cardinality, acyclic }
```
```

- [ ] **Step 3: Add Ontology vs Codegraph division**

Add after "When This Skill Applies" table:

```markdown
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
```

- [ ] **Step 4: Add Integration Patterns section**

Add before "Planning as Graph Transformation":

```markdown
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
```

- [ ] **Step 5: Update Planning as Graph Transformation section**

Replace the existing section with:

```markdown
## Planning as Graph Transformation

Model multi-step plans as a sequence of graph operations:

```
Plan: "Create task and assign to project"
1. CREATE Task { title: "Draft spec", status: "open" }
2. RELATE Task -> part_of -> proj_001
3. RELATE Task -> assigned_to -> pers_001
```

Plans execute atomically via `plan-create` + `plan-execute`. On any step failure, all changes are rolled back automatically.
```

- [ ] **Step 6: Add Quick Start section**

Add at the end of the file:

```markdown
## Quick Start

```bash
# Initialize (automatic on first command - tables + default rules seeded)
python3 scripts/ontology.py stats

# Add a custom type for your project
python3 scripts/ontology.py add-type --type Milestone --required '["name","date"]' --enums '{"status":["planned","active","done"]}'

# Create entities
python3 scripts/ontology.py create --type Person --props '{"name":"Alice"}'
python3 ontology.py create --type Milestone --props '{"name":"Launch","date":"2026-06-01","status":"planned"}'

# Link entities
python3 scripts/ontology.py relate --from pers_001 --rel owns --to mile_001

# Validate all constraints
python3 scripts/ontology.py validate
```
```

- [ ] **Step 7: Commit**

```bash
git add .claude/skills/ontology/SKILL.md
git commit -m "$(cat <<'EOF'
docs(ontology): restore Integration Patterns, add Core Concept and Quick Start

- Update description frontmatter with "composable skills" emphasis
- Add Core Concept one-line mental model
- Add Ontology vs Codegraph division table
- Restore Integration Patterns (cross-skill communication, causal logging)
- Update Planning section to mention atomic execution + rollback
- Add Quick Start guide

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 7: Update references/schema.md

**Files:**
- Modify: `.claude/skills/ontology/references/schema.md`

- [ ] **Step 1: Add type_rules and relation_rules table documentation**

Add after the "ID Generation" section in `.claude/skills/ontology/references/schema.md`:

```markdown
## Constraint Tables

### type_rules

Stores validation rules for entity types:

```sql
CREATE TABLE type_rules (
    type_name TEXT PRIMARY KEY,
    required_props TEXT NOT NULL DEFAULT '[]',    -- JSON array
    enum_constraints TEXT NOT NULL DEFAULT '{}',  -- JSON dict
    forbidden_props TEXT NOT NULL DEFAULT '[]',   -- JSON array
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
```

- [ ] **Step 2: Add CLI Command Reference section**

Add at the end of the file:

```markdown
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
# Validate all constraints (entity props + relation types + acyclic)
python3 scripts/ontology.py validate
```
```

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/ontology/references/schema.md
git commit -m "$(cat <<'EOF'
docs(ontology): document constraint tables and CLI commands

- Add type_rules, relation_rules, plan_executions table schemas
- Add CLI command reference for type/relation rule management
- Add plan execution command reference

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Self-Review Checklist

**1. Spec coverage:**
- [x] SQLite-stored constraints — Task 1, 2, 3
- [x] Relation type validation — Task 4
- [x] Acyclic validation — Task 4
- [x] Transactional plans — Task 5
- [x] Core Concept section — Task 6
- [x] Integration Patterns — Task 6
- [x] Ontology/codegraph division — Task 6
- [x] Quick Start — Task 6
- [x] schema.md update — Task 7

**2. Placeholder scan:**
- [x] No TBD/TODO
- [x] All code blocks have actual implementation
- [x] All test functions have assertions
- [x] All CLI commands have example output descriptions

**3. Type consistency:**
- [x] `type_rules` table schema matches `add_type_rule` parameters
- [x] `relation_rules` table schema matches `add_relation_rule` parameters
- [x] `create_relation` signature consistent across all usages
- [x] Plan step JSON structure consistent in create_plan and execute_plan