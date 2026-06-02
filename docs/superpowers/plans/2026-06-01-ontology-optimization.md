# Ontology Skill Optimization Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Polish the already-implemented ontology hybrid skill — add search/stats commands, trim redundant reference docs, and add FTS5 for "what do I know about X?" queries.

**Architecture:** Extend the existing SQLite-backed ontology.py with FTS5 full-text search and a stats command. Slim down schema.md to avoid duplicating SKILL.md content.

**Tech Stack:** Python 3.12 stdlib (sqlite3, json, argparse), SQLite FTS5

---

### Task 1: Add FTS5 full-text search for entity properties

**Files:**
- Modify: `.claude/skills/ontology/scripts/ontology.py:29-55` (SCHEMA_SQL)
- Modify: `.claude/skills/ontology/scripts/ontology.py:79-87` (create_entity)
- Modify: `.claude/skills/ontology/scripts/ontology.py:118-130` (update_entity)
- Modify: `.claude/skills/ontology/scripts/ontology.py:132-139` (delete_entity)
- Modify: `.claude/skills/ontology/scripts/ontology.py:341-466` (main, add search subcommand)

- [ ] **Step 1: Add FTS5 virtual table to SCHEMA_SQL**

Add after the existing `CREATE INDEX` statements in `SCHEMA_SQL`:

```python
CREATE VIRTUAL TABLE IF NOT EXISTS entities_fts USING fts5(
    id UNINDEXED,
    type,
    properties,
    content=entities,
    content_rowid=rowid
);

CREATE TRIGGER IF NOT EXISTS entities_ai AFTER INSERT ON entities BEGIN
    INSERT INTO entities_fts(rowid, id, type, properties)
    VALUES (new.rowid, new.id, new.type, new.properties);
END;

CREATE TRIGGER IF NOT EXISTS entities_ad AFTER DELETE ON entities BEGIN
    INSERT INTO entities_fts(entities_fts, rowid, id, type, properties)
    VALUES ('delete', old.rowid, old.id, old.type, old.properties);
END;

CREATE TRIGGER IF NOT EXISTS entities_au AFTER UPDATE ON entities BEGIN
    INSERT INTO entities_fts(entities_fts, rowid, id, type, properties)
    VALUES ('delete', old.rowid, old.id, old.type, old.properties);
    INSERT INTO entities_fts(rowid, id, type, properties)
    VALUES (new.rowid, new.id, new.type, new.properties);
END;
```

- [ ] **Step 2: Add `search_entities` function**

Add after `list_entities`:

```python
def search_entities(conn: sqlite3.Connection, query: str, type_name: str = None) -> list:
    if type_name:
        rows = conn.execute(
            "SELECT e.* FROM entities e JOIN entities_fts f ON e.id = f.id "
            "WHERE entities_fts MATCH ? AND e.type = ? ORDER BY rank",
            (query, type_name),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT e.* FROM entities e JOIN entities_fts f ON e.id = f.id "
            "WHERE entities_fts MATCH ? ORDER BY rank",
            (query,),
        ).fetchall()
    return [{"id": r["id"], "type": r["type"], "properties": json.loads(r["properties"]),
             "created": r["created"], "updated": r["updated"]} for r in rows]
```

- [ ] **Step 3: Add `search` subcommand to main()**

Add after the `list` subparser:

```python
# Search
search_p = subparsers.add_parser("search", help="Full-text search across entities")
search_p.add_argument("query", help="Search terms")
search_p.add_argument("--type", "-t", help="Filter by entity type")
```

Add the handler in the elif chain:

```python
elif args.command == "search":
    results = search_entities(conn, args.query, args.type)
    print(json.dumps(results, indent=2, ensure_ascii=False))
```

- [ ] **Step 4: Add `rebuild_fts` function for existing databases**

Add after `search_entities`:

```python
def rebuild_fts(conn: sqlite3.Connection):
    conn.execute("INSERT INTO entities_fts(entities_fts) VALUES ('rebuild')")
    conn.commit()
```

- [ ] **Step 5: Add `rebuild-fts` subcommand**

```python
# Rebuild FTS
subparsers.add_parser("rebuild-fts", help="Rebuild full-text search index")
```

Handler:

```python
elif args.command == "rebuild-fts":
    rebuild_fts(conn)
    print("FTS index rebuilt.")
```

- [ ] **Step 6: Test search functionality**

Run:
```bash
python3 .claude/skills/ontology/scripts/ontology.py --db /tmp/test_fts.db create --type Person --props '{"name":"Alice Chen","email":"alice@example.com","notes":"Backend engineer, loves Rust"}'
python3 .claude/skills/ontology/scripts/ontology.py --db /tmp/test_fts.db create --type Person --props '{"name":"Bob Smith","email":"bob@example.com","notes":"Frontend developer, React expert"}'
python3 .claude/skills/ontology/scripts/ontology.py --db /tmp/test_fts.db search "Rust"
python3 .claude/skills/ontology/scripts/ontology.py --db /tmp/test_fts.db search "engineer" --type Person
```

Expected: First search returns Alice, second also returns Alice.

- [ ] **Step 7: Clean up test db**

```bash
rm -f /tmp/test_fts.db
```

- [ ] **Step 8: Commit**

```bash
git add .claude/skills/ontology/scripts/ontology.py
git commit -m "feat(ontology): add FTS5 full-text search for entity queries"
```

---

### Task 2: Add `stats` command

**Files:**
- Modify: `.claude/skills/ontology/scripts/ontology.py`

- [ ] **Step 1: Add `graph_stats` function**

Add after `validate_graph`:

```python
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
```

- [ ] **Step 2: Add `stats` subcommand**

```python
subparsers.add_parser("stats", help="Show graph statistics")
```

Handler:

```python
elif args.command == "stats":
    stats = graph_stats(conn)
    print(json.dumps(stats, indent=2, ensure_ascii=False))
```

- [ ] **Step 3: Test stats**

```bash
python3 .claude/skills/ontology/scripts/ontology.py --db /tmp/test_stats.db create --type Person --props '{"name":"Alice"}'
python3 .claude/skills/ontology/scripts/ontology.py --db /tmp/test_stats.db create --type Task --props '{"title":"Do thing","status":"open"}'
python3 .claude/skills/ontology/scripts/ontology.py --db /tmp/test_stats.db relate --from task_001 --rel assigned_to --to pers_001
python3 .claude/skills/ontology/scripts/ontology.py --db /tmp/test_stats.db stats
rm -f /tmp/test_stats.db
```

Expected: `{"entities": 2, "relations": 1, "by_type": {"Person": 1, "Task": 1}, "by_relation": {"assigned_to": 1}}`

- [ ] **Step 4: Commit**

```bash
git add .claude/skills/ontology/scripts/ontology.py
git commit -m "feat(ontology): add stats command for graph overview"
```

---

### Task 3: Trim `references/schema.md` to avoid duplication

**Files:**
- Modify: `.claude/skills/ontology/references/schema.md`

- [ ] **Step 1: Rewrite schema.md**

The current schema.md (323 lines) heavily duplicates SKILL.md's type listing and relation types. Rewrite it to contain only what SKILL.md doesn't: detailed property types, validation rules, and constraint definitions. Remove the relation type section entirely (already in SKILL.md).

New content should be ~120 lines covering:
- Property type reference (string, number, date, enum, ref)
- Validation constraint patterns (required, forbidden, enum, acyclic)
- Date/time format conventions
- ID generation rules
- Cardinality definitions

- [ ] **Step 2: Verify SKILL.md references still make sense**

Read SKILL.md's "References" section and confirm the pointer to schema.md still accurately describes what's there.

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/ontology/references/schema.md
git commit -m "refactor(ontology): trim schema.md to complement SKILL.md without duplication"
```

---

### Task 4: Update SKILL.md and queries.md with new commands

**Files:**
- Modify: `.claude/skills/ontology/SKILL.md`
- Modify: `.claude/skills/ontology/references/queries.md`

- [ ] **Step 1: Add `search` and `stats` to SKILL.md CLI Usage section**

After the existing `validate` entry, add:

```bash
# Full-text search across all entities
python3 scripts/ontology.py search "Alice"
python3 scripts/ontology.py search "backend engineer" --type Person

# Graph statistics
python3 scripts/ontology.py stats

# Rebuild FTS index (after manual db edits)
python3 scripts/ontology.py rebuild-fts
```

- [ ] **Step 2: Update the Domain Questions trigger table in SKILL.md**

Add a row:

```
| "What do I know about X?" | Full-text search |
```

- [ ] **Step 3: Add search examples to queries.md**

Add a "Full-Text Search" section after "Basic CRUD":

```bash
# Search by name
python3 scripts/ontology.py search "Alice"

# Search within a type
python3 scripts/ontology.py search "backend" --type Person

# Search across all entities
python3 scripts/ontology.py search "deadline Friday"
```

- [ ] **Step 4: Commit**

```bash
git add .claude/skills/ontology/SKILL.md .claude/skills/ontology/references/queries.md
git commit -m "docs(ontology): document search and stats commands"
```

---

### Task 5: Final integration test

**Files:**
- No file changes — verification only

- [ ] **Step 1: Run full workflow test**

```bash
DB=/tmp/test_final.db
python3 .claude/skills/ontology/scripts/ontology.py --db $DB create --type Person --props '{"name":"Vincent Ruan","email":"vincent@numina.dev","notes":"Project lead, full-stack"}'
python3 .claude/skills/ontology/scripts/ontology.py --db $DB create --type Project --props '{"name":"Numina","status":"active"}'
python3 .claude/skills/ontology/scripts/ontology.py --db $DB create --type Task --props '{"title":"Implement dashboard","status":"open","priority":"high"}' --id task_dash
python3 .claude/skills/ontology/scripts/ontology.py --db $DB relate --from proj_001 --rel has_owner --to pers_001
python3 .claude/skills/ontology/scripts/ontology.py --db $DB relate --from proj_001 --rel has_task --to task_dash
python3 .claude/skills/ontology/scripts/ontology.py --db $DB search "full-stack"
python3 .claude/skills/ontology/scripts/ontology.py --db $DB related --id proj_001 --dir both
python3 .claude/skills/ontology/scripts/ontology.py --db $DB stats
python3 .claude/skills/ontology/scripts/ontology.py --db $DB validate
rm -f $DB
```

Expected:
- Search returns Vincent
- Related returns owner + task
- Stats shows 3 entities, 2 relations
- Validate passes

- [ ] **Step 2: Verify codegraph integration still works**

```
codegraph_search("ontology")
codegraph_context("how does the ontology skill work")
```

Expected: codegraph finds the ontology.py script and its symbols.

---

Plan complete and saved to `docs/superpowers/plans/2026-06-01-ontology-optimization.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
