#!/usr/bin/env python3
"""
Ontology graph operations backed by SQLite.

Usage:
    python ontology.py create --type Person --props '{"name":"Alice"}'
    python ontology.py get --id p_001
    python ontology.py query --type Task --where '{"status":"open"}'
    python ontology.py relate --from proj_001 --rel has_task --to task_001
    python ontology.py related --id proj_001 --rel has_task
    python ontology.py list --type Person
    python ontology.py update --id p_001 --props '{"email":"new@example.com"}'
    python ontology.py delete --id p_001
    python ontology.py unrelate --from proj_001 --rel has_task --to task_001
    python ontology.py validate
    python ontology.py migrate  # One-time JSONL -> SQLite migration
"""

import argparse
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_DB_PATH = "memory/ontology/ontology.db"
LEGACY_GRAPH_PATH = "memory/ontology/graph.jsonl"

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


def get_db(db_path: str) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA_SQL)
    seed_default_rules(conn)
    return conn


def generate_id(type_name: str) -> str:
    prefix = type_name.lower()[:4]
    suffix = uuid.uuid4().hex[:8]
    return f"{prefix}_{suffix}"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def validate_relation_types(conn: sqlite3.Connection, from_id: str, rel_type: str, to_id: str) -> list:
    """Validate that relation types match the rule constraints."""
    errors = []

    from_entity = get_entity(conn, from_id)
    to_entity = get_entity(conn, to_id)

    if not from_entity:
        errors.append(f"from_id '{from_id}' does not exist")
    if not to_entity:
        errors.append(f"to_id '{to_id}' does not exist")

    # Return early only if entities don't exist (can't check types)
    if errors:
        return errors

    rule = get_relation_rule(conn, rel_type)
    if not rule:
        return errors  # No rule defined - allow by default

    from_type = from_entity["type"]
    to_type = to_entity["type"]

    if rule["from_types"] and from_type not in rule["from_types"]:
        errors.append(f"Relation '{rel_type}' requires from_types={rule['from_types']}, got '{from_type}'")

    if rule["to_types"] and to_type not in rule["to_types"]:
        errors.append(f"Relation '{rel_type}' requires to_types={rule['to_types']}, got '{to_type}'")

    return errors


def validate_acyclic(conn: sqlite3.Connection, from_id: str, rel_type: str, to_id: str) -> list:
    """Check if adding this relation would create a cycle."""
    errors = []

    rule = get_relation_rule(conn, rel_type)
    if not rule or not rule["acyclic"]:
        return errors

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

        rows = conn.execute(
            "SELECT to_id FROM relations WHERE from_id = ? AND rel_type = ?",
            (current, rel_type),
        ).fetchall()
        for row in rows:
            stack.append(row["to_id"])

    return errors


def create_entity(conn: sqlite3.Connection, type_name: str, properties: dict, entity_id: str = None) -> dict:
    entity_id = entity_id or generate_id(type_name)
    ts = now_iso()
    conn.execute(
        "INSERT INTO entities (id, type, properties, created, updated) VALUES (?, ?, ?, ?, ?)",
        (entity_id, type_name, json.dumps(properties, ensure_ascii=False), ts, ts),
    )
    conn.commit()
    return {"id": entity_id, "type": type_name, "properties": properties, "created": ts, "updated": ts}


def get_entity(conn: sqlite3.Connection, entity_id: str) -> dict | None:
    row = conn.execute("SELECT * FROM entities WHERE id = ?", (entity_id,)).fetchone()
    if not row:
        return None
    return {"id": row["id"], "type": row["type"], "properties": json.loads(row["properties"]),
            "created": row["created"], "updated": row["updated"]}


def query_entities(conn: sqlite3.Connection, type_name: str, where: dict) -> list:
    rows = conn.execute("SELECT * FROM entities WHERE type = ?", (type_name,)).fetchall()
    results = []
    for row in rows:
        props = json.loads(row["properties"])
        if all(props.get(k) == v for k, v in where.items()):
            results.append({"id": row["id"], "type": row["type"], "properties": props,
                            "created": row["created"], "updated": row["updated"]})
    return results


def list_entities(conn: sqlite3.Connection, type_name: str = None) -> list:
    if type_name:
        rows = conn.execute("SELECT * FROM entities WHERE type = ?", (type_name,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM entities").fetchall()
    return [{"id": r["id"], "type": r["type"], "properties": json.loads(r["properties"]),
             "created": r["created"], "updated": r["updated"]} for r in rows]


def search_entities(conn: sqlite3.Connection, query: str, type_name: str = None) -> list:
    pattern = f"%{query}%"
    if type_name:
        rows = conn.execute(
            "SELECT * FROM entities WHERE type = ? AND (properties LIKE ? OR id LIKE ?)",
            (type_name, pattern, pattern),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM entities WHERE properties LIKE ? OR id LIKE ?",
            (pattern, pattern),
        ).fetchall()
    return [{"id": r["id"], "type": r["type"], "properties": json.loads(r["properties"]),
             "created": r["created"], "updated": r["updated"]} for r in rows]


def update_entity(conn: sqlite3.Connection, entity_id: str, properties: dict) -> dict | None:
    row = conn.execute("SELECT * FROM entities WHERE id = ?", (entity_id,)).fetchone()
    if not row:
        return None
    existing = json.loads(row["properties"])
    existing.update(properties)
    ts = now_iso()
    conn.execute(
        "UPDATE entities SET properties = ?, updated = ? WHERE id = ?",
        (json.dumps(existing, ensure_ascii=False), ts, entity_id),
    )
    conn.commit()
    return {"id": entity_id, "type": row["type"], "properties": existing, "created": row["created"], "updated": ts}


def delete_entity(conn: sqlite3.Connection, entity_id: str) -> bool:
    row = conn.execute("SELECT id FROM entities WHERE id = ?", (entity_id,)).fetchone()
    if not row:
        return False
    conn.execute("DELETE FROM entities WHERE id = ?", (entity_id,))
    conn.commit()
    return True


def create_relation(conn: sqlite3.Connection, from_id: str, rel_type: str, to_id: str, properties: dict = None, skip_validation: bool = False) -> dict:
    """Create a relation between entities, with validation."""
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


def delete_relation(conn: sqlite3.Connection, from_id: str, rel_type: str, to_id: str) -> bool:
    cur = conn.execute(
        "DELETE FROM relations WHERE from_id = ? AND rel_type = ? AND to_id = ?",
        (from_id, rel_type, to_id),
    )
    conn.commit()
    return cur.rowcount > 0


def get_related(conn: sqlite3.Connection, entity_id: str, rel_type: str = None, direction: str = "outgoing") -> list:
    results = []

    if direction in ("outgoing", "both"):
        if rel_type:
            rows = conn.execute(
                "SELECT r.rel_type, r.properties as rel_props, e.* FROM relations r "
                "JOIN entities e ON e.id = r.to_id WHERE r.from_id = ? AND r.rel_type = ?",
                (entity_id, rel_type),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT r.rel_type, r.properties as rel_props, e.* FROM relations r "
                "JOIN entities e ON e.id = r.to_id WHERE r.from_id = ?",
                (entity_id,),
            ).fetchall()
        for row in rows:
            results.append({
                "relation": row["rel_type"],
                "direction": "outgoing",
                "entity": {"id": row["id"], "type": row["type"],
                           "properties": json.loads(row["properties"]),
                           "created": row["created"], "updated": row["updated"]},
            })

    if direction in ("incoming", "both"):
        if rel_type:
            rows = conn.execute(
                "SELECT r.rel_type, r.properties as rel_props, e.* FROM relations r "
                "JOIN entities e ON e.id = r.from_id WHERE r.to_id = ? AND r.rel_type = ?",
                (entity_id, rel_type),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT r.rel_type, r.properties as rel_props, e.* FROM relations r "
                "JOIN entities e ON e.id = r.from_id WHERE r.to_id = ?",
                (entity_id,),
            ).fetchall()
        for row in rows:
            results.append({
                "relation": row["rel_type"],
                "direction": "incoming",
                "entity": {"id": row["id"], "type": row["type"],
                           "properties": json.loads(row["properties"]),
                           "created": row["created"], "updated": row["updated"]},
            })

    return results


def validate_graph(conn: sqlite3.Connection) -> list:
    """Validate entities and relations against all constraints."""
    errors = []

    # Layer 1: Entity property validation from type_rules table
    rows = conn.execute(
        "SELECT e.*, t.required_props, t.enum_constraints, t.forbidden_props "
        "FROM entities e LEFT JOIN type_rules t ON e.type = t.type_name"
    ).fetchall()

    for row in rows:
        entity_id = row["id"]
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

    # Layer 3: Dangling relation check
    danglings = conn.execute(
        "SELECT r.* FROM relations r "
        "LEFT JOIN entities e1 ON r.from_id = e1.id "
        "LEFT JOIN entities e2 ON r.to_id = e2.id "
        "WHERE e1.id IS NULL OR e2.id IS NULL"
    ).fetchall()
    for rel in danglings:
        errors.append(f"Dangling relation: {rel['from_id']} --{rel['rel_type']}--> {rel['to_id']}")

    return errors


def graph_stats(conn: sqlite3.Connection) -> dict:
    entity_count = conn.execute("SELECT COUNT(*) FROM entities").fetchone()[0]
    relation_count = conn.execute("SELECT COUNT(*) FROM relations").fetchone()[0]
    type_counts = {}
    for row in conn.execute("SELECT type, COUNT(*) as cnt FROM entities GROUP BY type ORDER BY cnt DESC"):
        type_counts[row["type"]] = row["cnt"]
    rel_type_counts = {}
    for row in conn.execute("SELECT rel_type, COUNT(*) as cnt FROM relations GROUP BY rel_type ORDER BY cnt DESC"):
        rel_type_counts[row["rel_type"]] = row["cnt"]
    return {
        "entities": entity_count,
        "relations": relation_count,
        "by_type": type_counts,
        "by_relation": rel_type_counts,
    }


def migrate_jsonl(conn: sqlite3.Connection, jsonl_path: str) -> dict:
    """Migrate legacy JSONL graph to SQLite. Idempotent."""
    path = Path(jsonl_path)
    if not path.exists():
        return {"status": "skipped", "reason": "no JSONL file found"}

    created = 0
    updated = 0
    related = 0
    deleted = 0

    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            op = record.get("op")

            if op == "create":
                entity = record["entity"]
                ts = entity.get("created", record.get("timestamp", now_iso()))
                try:
                    conn.execute(
                        "INSERT INTO entities (id, type, properties, created, updated) VALUES (?, ?, ?, ?, ?)",
                        (entity["id"], entity["type"],
                         json.dumps(entity.get("properties", {}), ensure_ascii=False), ts, ts),
                    )
                    created += 1
                except sqlite3.IntegrityError:
                    pass  # Already exists — idempotent

            elif op == "update":
                entity_id = record["id"]
                row = conn.execute("SELECT properties FROM entities WHERE id = ?", (entity_id,)).fetchone()
                if row:
                    existing = json.loads(row["properties"])
                    existing.update(record.get("properties", {}))
                    ts = record.get("timestamp", now_iso())
                    conn.execute(
                        "UPDATE entities SET properties = ?, updated = ? WHERE id = ?",
                        (json.dumps(existing, ensure_ascii=False), ts, entity_id),
                    )
                    updated += 1

            elif op == "delete":
                conn.execute("DELETE FROM entities WHERE id = ?", (record["id"],))
                deleted += 1

            elif op == "relate":
                ts = record.get("timestamp", now_iso())
                props = record.get("properties", {})
                try:
                    conn.execute(
                        "INSERT OR REPLACE INTO relations (from_id, rel_type, to_id, properties, created) "
                        "VALUES (?, ?, ?, ?, ?)",
                        (record["from"], record["rel"], record["to"],
                         json.dumps(props, ensure_ascii=False), ts),
                    )
                    related += 1
                except sqlite3.IntegrityError:
                    pass

            elif op == "unrelate":
                conn.execute(
                    "DELETE FROM relations WHERE from_id = ? AND rel_type = ? AND to_id = ?",
                    (record["from"], record["rel"], record["to"]),
                )

    conn.commit()
    return {"status": "done", "created": created, "updated": updated, "related": related, "deleted": deleted}


def main():
    parser = argparse.ArgumentParser(description="Ontology graph operations (SQLite backend)")
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="Database path")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Create
    create_p = subparsers.add_parser("create", help="Create entity")
    create_p.add_argument("--type", "-t", required=True, help="Entity type")
    create_p.add_argument("--props", "-p", default="{}", help="Properties JSON")
    create_p.add_argument("--id", help="Entity ID (auto-generated if omitted)")

    # Get
    get_p = subparsers.add_parser("get", help="Get entity by ID")
    get_p.add_argument("--id", required=True, help="Entity ID")

    # Query
    query_p = subparsers.add_parser("query", help="Query entities by type + filter")
    query_p.add_argument("--type", "-t", required=True, help="Entity type")
    query_p.add_argument("--where", "-w", default="{}", help="Filter JSON")

    # List
    list_p = subparsers.add_parser("list", help="List entities")
    list_p.add_argument("--type", "-t", help="Entity type (optional)")

    # Search
    search_p = subparsers.add_parser("search", help="Full-text search across entities")
    search_p.add_argument("query", help="Search terms")
    search_p.add_argument("--type", "-t", help="Filter by entity type")

    # Update
    update_p = subparsers.add_parser("update", help="Update entity properties")
    update_p.add_argument("--id", required=True, help="Entity ID")
    update_p.add_argument("--props", "-p", required=True, help="Properties JSON to merge")

    # Delete
    delete_p = subparsers.add_parser("delete", help="Delete entity")
    delete_p.add_argument("--id", required=True, help="Entity ID")

    # Relate
    relate_p = subparsers.add_parser("relate", help="Create relation")
    relate_p.add_argument("--from", dest="from_id", required=True, help="From entity ID")
    relate_p.add_argument("--rel", "-r", required=True, help="Relation type")
    relate_p.add_argument("--to", dest="to_id", required=True, help="To entity ID")
    relate_p.add_argument("--props", "-p", default="{}", help="Relation properties JSON")

    # Unrelate
    unrelate_p = subparsers.add_parser("unrelate", help="Remove relation")
    unrelate_p.add_argument("--from", dest="from_id", required=True, help="From entity ID")
    unrelate_p.add_argument("--rel", "-r", required=True, help="Relation type")
    unrelate_p.add_argument("--to", dest="to_id", required=True, help="To entity ID")

    # Related
    related_p = subparsers.add_parser("related", help="Get related entities")
    related_p.add_argument("--id", required=True, help="Entity ID")
    related_p.add_argument("--rel", "-r", help="Relation type filter")
    related_p.add_argument("--dir", "-d", choices=["outgoing", "incoming", "both"], default="outgoing")

    # Validate
    subparsers.add_parser("validate", help="Validate graph constraints")

    # Stats
    subparsers.add_parser("stats", help="Show graph statistics")

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

    # Migrate
    migrate_p = subparsers.add_parser("migrate", help="Migrate JSONL to SQLite (idempotent)")
    migrate_p.add_argument("--jsonl", default=LEGACY_GRAPH_PATH, help="Source JSONL path")

    args = parser.parse_args()
    conn = get_db(args.db)

    if args.command == "create":
        props = json.loads(args.props)
        entity = create_entity(conn, args.type, props, args.id)
        print(json.dumps(entity, indent=2, ensure_ascii=False))

    elif args.command == "get":
        entity = get_entity(conn, args.id)
        if entity:
            print(json.dumps(entity, indent=2, ensure_ascii=False))
        else:
            print(f"Entity not found: {args.id}")

    elif args.command == "query":
        where = json.loads(args.where)
        results = query_entities(conn, args.type, where)
        print(json.dumps(results, indent=2, ensure_ascii=False))

    elif args.command == "list":
        results = list_entities(conn, args.type)
        print(json.dumps(results, indent=2, ensure_ascii=False))

    elif args.command == "search":
        results = search_entities(conn, args.query, args.type)
        print(json.dumps(results, indent=2, ensure_ascii=False))

    elif args.command == "update":
        props = json.loads(args.props)
        entity = update_entity(conn, args.id, props)
        if entity:
            print(json.dumps(entity, indent=2, ensure_ascii=False))
        else:
            print(f"Entity not found: {args.id}")

    elif args.command == "delete":
        if delete_entity(conn, args.id):
            print(f"Deleted: {args.id}")
        else:
            print(f"Entity not found: {args.id}")

    elif args.command == "relate":
        props = json.loads(args.props)
        try:
            rel = create_relation(conn, args.from_id, args.rel, args.to_id, props)
            print(json.dumps(rel, indent=2, ensure_ascii=False))
        except ValueError as e:
            print(f"Error: {e}")

    elif args.command == "unrelate":
        if delete_relation(conn, args.from_id, args.rel, args.to_id):
            print(f"Removed: {args.from_id} --{args.rel}--> {args.to_id}")
        else:
            print("Relation not found")

    elif args.command == "related":
        results = get_related(conn, args.id, args.rel, args.dir)
        print(json.dumps(results, indent=2, ensure_ascii=False))

    elif args.command == "validate":
        errors = validate_graph(conn)
        if errors:
            print("Validation errors:")
            for err in errors:
                print(f"  - {err}")
        else:
            print("Graph is valid.")

    elif args.command == "stats":
        stats = graph_stats(conn)
        print(json.dumps(stats, indent=2, ensure_ascii=False))

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

    elif args.command == "migrate":
        result = migrate_jsonl(conn, args.jsonl)
        print(json.dumps(result, indent=2, ensure_ascii=False))

    conn.close()


if __name__ == "__main__":
    main()
