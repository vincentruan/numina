#!/usr/bin/env python3
"""Unit tests for ontology.py"""

import sqlite3
import tempfile
import os
import json
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

def test_seed_default_rules():
    """Default rules should be seeded on first init"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        conn = get_db(db_path)

        type_count = conn.execute("SELECT COUNT(*) FROM type_rules").fetchone()[0]
        assert type_count > 0, "type_rules should have default entries"

        rel_count = conn.execute("SELECT COUNT(*) FROM relation_rules").fetchone()[0]
        assert rel_count > 0, "relation_rules should have default entries"

        task_rule = conn.execute("SELECT * FROM type_rules WHERE type_name='Task'").fetchone()
        assert task_rule is not None, "Task type rule should exist"
        required = json.loads(task_rule["required_props"])
        assert "title" in required and "status" in required

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

        result = seed_default_rules(conn)
        assert result["seeded_types"] == 0, "Second seed should add nothing"

        count2 = conn.execute("SELECT COUNT(*) FROM type_rules").fetchone()[0]
        assert count1 == count2, "Count should be unchanged"
        conn.close()

if __name__ == "__main__":
    test_type_rules_table_exists()
    test_relation_rules_table_exists()
    test_plan_executions_table_exists()
    print("All tests passed!")