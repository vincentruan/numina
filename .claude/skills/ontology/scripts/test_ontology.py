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
from ontology import get_db, seed_default_rules, add_type_rule, get_type_rule, list_type_rules, delete_type_rule, add_relation_rule, get_relation_rule, list_relation_rules, delete_relation_rule, validate_graph, now_iso

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

def test_delete_relation_rule():
    """delete-relation-type should remove relation rule"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        conn = get_db(db_path)

        # Add then delete
        add_relation_rule(conn, "temp_rel", from_types=["Task"], to_types=["Task"])
        assert get_relation_rule(conn, "temp_rel") is not None

        # Delete should return True
        assert delete_relation_rule(conn, "temp_rel") == True
        assert get_relation_rule(conn, "temp_rel") is None

        # Deleting non-existent should return False
        assert delete_relation_rule(conn, "nonexistent") == False
        conn.close()

def test_relation_type_validation_allowed():
    """Relation with valid types should succeed"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        conn = get_db(db_path)

        from ontology import create_entity, validate_relation_types
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

        from ontology import create_entity, validate_relation_types
        create_entity(conn, "Task", {"title": "T1", "status": "open"}, "task_001")
        create_entity(conn, "Person", {"name": "Alice"}, "pers_001")

        # blocks: Task -> Task only, Person not allowed
        errors = validate_relation_types(conn, "pers_001", "blocks", "task_001")
        assert len(errors) > 0, "Should fail - Person cannot blocks Task"
        assert "from_types" in errors[0]
        conn.close()

def test_acyclic_validation():
    """Acyclic relations should reject cycles"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        conn = get_db(db_path)

        from ontology import create_entity, create_relation, validate_acyclic
        create_entity(conn, "Task", {"title": "T1", "status": "open"}, "task_001")
        create_entity(conn, "Task", {"title": "T2", "status": "open"}, "task_002")

        # First relation OK
        create_relation(conn, "task_001", "blocks", "task_002")

        # Reverse would create cycle
        errors = validate_acyclic(conn, "task_002", "blocks", "task_001")
        assert len(errors) > 0, "Should detect cycle"
        assert "cycle" in errors[0].lower()
        conn.close()

def test_validate_graph_entity_errors():
    """validate_graph should find entity property violations"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        conn = get_db(db_path)

        # Create entity missing required property
        conn.execute(
            "INSERT INTO entities (id, type, properties, created, updated) VALUES (?, ?, ?, ?, ?)",
            ("task_bad", "Task", json.dumps({"title": "No status"}), now_iso(), now_iso()),
        )
        conn.commit()

        errors = validate_graph(conn)
        assert len(errors) > 0, "Should find missing 'status' property"
        assert any("status" in e for e in errors), "Error should mention 'status'"
        conn.close()

def test_skip_validation_bypass():
    """create_relation with skip_validation=True should bypass checks"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        conn = get_db(db_path)

        from ontology import create_entity, create_relation
        create_entity(conn, "Person", {"name": "Alice"}, "pers_001")
        create_entity(conn, "Task", {"title": "T", "status": "open"}, "task_001")

        # Person blocks Task would normally fail (wrong from_type)
        # But skip_validation allows it
        rel = create_relation(conn, "pers_001", "blocks", "task_001", skip_validation=True)
        assert rel["from"] == "pers_001"
        assert rel["rel"] == "blocks"

        # Verify relation exists
        row = conn.execute(
            "SELECT * FROM relations WHERE from_id=? AND rel_type=? AND to_id=?",
            ("pers_001", "blocks", "task_001"),
        ).fetchone()
        assert row is not None
        conn.close()

def test_plan_create_and_execute():
    """Plan should execute all steps atomically"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        conn = get_db(db_path)

        from ontology import create_plan, execute_plan, get_entity

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

        from ontology import create_plan, execute_plan, get_entity

        steps = [
            {"op": "create", "type": "Task", "props": {"title": "T1", "status": "open"}, "id": "task_001"},
            {"op": "relate", "from": "nonexistent", "rel": "has_owner", "to": "pers_001"},
        ]

        plan = create_plan(conn, steps)
        result = execute_plan(conn, plan["plan_id"])

        assert result["status"] == "rolled_back"

        # Verify first entity was NOT created (rolled back)
        task = get_entity(conn, "task_001")
        assert task is None, "Entity should be rolled back"
        conn.close()

if __name__ == "__main__":
    test_type_rules_table_exists()
    test_relation_rules_table_exists()
    test_plan_executions_table_exists()
    test_seed_default_rules()
    test_seed_is_idempotent()
    test_add_type_command()
    test_list_types_command()
    test_delete_type_command()
    test_add_relation_rule()
    test_get_relation_rule()
    test_list_relation_rules()
    test_delete_relation_rule()
    test_relation_type_validation_allowed()
    test_relation_type_validation_rejected()
    test_acyclic_validation()
    test_validate_graph_entity_errors()
    test_skip_validation_bypass()
    test_plan_create_and_execute()
    test_plan_rollback_on_error()
    print("All tests passed!")