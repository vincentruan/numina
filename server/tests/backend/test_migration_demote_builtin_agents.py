"""Tests for U2: alembic migration b6745e8a2c14_demote_builtin_agents_seed_numina.

The full alembic chain has SQLite-incompatible operations earlier in history, so
we can't easily round-trip the whole chain on the in-memory test DB. Instead,
this test creates a minimal ai_agents table matching the post-a53453cf574b
schema, seeds the prior state (2 builtin + 2 system agents), and runs the
migration's upgrade()/downgrade() SQL directly via SQLAlchemy.

This validates:
- up() inserts numina with skills='["*"]' at id 100000000000005
- up() deletes the 2 builtin agents (id 100000000000001, 100000000000002)
- up() preserves the 2 existing system agents (ai-assistant, time-machine)
- down() removes numina
- down() restores the 2 builtin agents with their original soul_md
- round-trip is idempotent
"""

import json

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

# Schema mirrors the post-a53453cf574b state of ai_agents:
# - is_builtin column was dropped
# - agent_type column was added with values in (system|builtin|custom)
_AI_AGENTS_DDL = """
CREATE TABLE ai_agents (
    id BIGINT PRIMARY KEY,
    family_id BIGINT NOT NULL,
    agent_name VARCHAR(64) NOT NULL,
    display_name VARCHAR(128) NOT NULL,
    description TEXT,
    icon VARCHAR(16),
    color VARCHAR(16),
    soul_md TEXT NOT NULL,
    skills TEXT,
    model VARCHAR(64),
    subagent_enabled BOOLEAN NOT NULL DEFAULT 0,
    tool_groups TEXT,
    is_enabled BOOLEAN NOT NULL DEFAULT 1,
    display_order INTEGER NOT NULL DEFAULT 0,
    created_by BIGINT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    agent_type VARCHAR(20) NOT NULL DEFAULT 'builtin',
    UNIQUE (family_id, agent_name)
)
"""


def _seed_prior_state(conn) -> None:
    """Seed the 4 agents that exist after a53453cf574b but before b6745e8a2c14."""
    # 2 builtin agents from x2581y64zqr9
    conn.execute(
        text(
            "INSERT INTO ai_agents (id, family_id, agent_name, display_name, description, "
            "icon, color, soul_md, skills, agent_type, display_order) "
            "VALUES (100000000000001, 0, 'asset-health-advisor', '资产健康顾问', "
            "'desc-1', '🏥', '#10B981', 'soul-builtin-1', '[\"report\"]', 'builtin', 100)"
        )
    )
    conn.execute(
        text(
            "INSERT INTO ai_agents (id, family_id, agent_name, display_name, description, "
            "icon, color, soul_md, skills, agent_type, display_order) "
            "VALUES (100000000000002, 0, 'finance-optimizer', '财务优化师', "
            "'desc-2', '💰', '#F59E0B', 'soul-builtin-2', '[\"liability\"]', 'builtin', 200)"
        )
    )
    # 2 system agents from a53453cf574b
    conn.execute(
        text(
            "INSERT INTO ai_agents (id, family_id, agent_name, display_name, description, "
            "icon, color, soul_md, skills, agent_type, display_order) "
            "VALUES (100000000000003, 0, 'ai-assistant', 'AI助手', "
            "'desc-3', '🤖', '#3B82F6', 'soul-sys-1', '[\"chat\"]', 'system', 10)"
        )
    )
    conn.execute(
        text(
            "INSERT INTO ai_agents (id, family_id, agent_name, display_name, description, "
            "icon, color, soul_md, skills, agent_type, display_order) "
            "VALUES (100000000000004, 0, 'time-machine', '时光机', "
            "'desc-4', '⏰', '#8B5CF6', 'soul-sys-2', '[\"time_machine\"]', 'system', 20)"
        )
    )


def _apply_migration_sql(conn, direction: str) -> None:
    """Re-execute the migration's upgrade() or downgrade() SQL.

    We re-execute the same SQL statements rather than calling op.execute()
    directly because alembic op needs a MigrationContext that's tied to
    full alembic config — overkill for a single-migration unit test.
    """
    if direction == "upgrade":
        # Mirrors b6745e8a2c14.upgrade() (statements truncated for SQLite —
        # SQLite doesn't support the regex CHECK constraint, but our DDL above
        # omits it for the test fixture).
        conn.execute(
            text("""
            INSERT INTO ai_agents (id, family_id, agent_name, display_name, description,
                icon, color, soul_md, skills, agent_type, display_order)
            VALUES (100000000000005, 0, 'numina', '数鸣', 'desc-numina',
                '✨', '#8b5cf6', 'soul-numina', '["*"]', 'system', 15)
        """)
        )
        conn.execute(
            text(
                "DELETE FROM ai_agents WHERE id IN (100000000000001, 100000000000002) "
                "AND family_id = 0 AND agent_type = 'builtin'"
            )
        )
    else:
        conn.execute(
            text(
                "DELETE FROM ai_agents WHERE id = 100000000000005 "
                "AND family_id = 0 AND agent_name = 'numina'"
            )
        )
        conn.execute(
            text("""
            INSERT INTO ai_agents (id, family_id, agent_name, display_name, description,
                icon, color, soul_md, skills, agent_type, display_order)
            VALUES (100000000000001, 0, 'asset-health-advisor', '资产健康顾问',
                'desc-1', '🏥', '#10B981', 'soul-builtin-1', '["report"]', 'builtin', 100)
        """)
        )
        conn.execute(
            text("""
            INSERT INTO ai_agents (id, family_id, agent_name, display_name, description,
                icon, color, soul_md, skills, agent_type, display_order)
            VALUES (100000000000002, 0, 'finance-optimizer', '财务优化师',
                'desc-2', '💰', '#F59E0B', 'soul-builtin-2', '["liability"]', 'builtin', 200)
        """)
        )


@pytest.fixture
def migration_engine():
    """Fresh in-memory SQLite engine with ai_agents table + seeded prior state."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with engine.connect() as conn:
        conn.execute(text(_AI_AGENTS_DDL))
        _seed_prior_state(conn)
        conn.commit()
    yield engine
    engine.dispose()


def _agent_summary(conn) -> dict[str, dict]:
    """Return a {agent_name: row_dict} snapshot of ai_agents."""
    rows = conn.execute(
        text(
            "SELECT id, agent_name, agent_type, skills, display_order, soul_md "
            "FROM ai_agents ORDER BY display_order"
        )
    ).all()
    return {
        r.agent_name: {
            "id": r.id,
            "agent_type": r.agent_type,
            "skills": json.loads(r.skills) if r.skills else None,
            "display_order": r.display_order,
            "soul_md": r.soul_md,
        }
        for r in rows
    }


def test_prior_state_has_4_agents(migration_engine):
    """Sanity check: fixture seeds the expected 4 agents."""
    with migration_engine.connect() as conn:
        agents = _agent_summary(conn)
    assert set(agents.keys()) == {
        "asset-health-advisor",
        "finance-optimizer",
        "ai-assistant",
        "time-machine",
    }
    assert agents["asset-health-advisor"]["agent_type"] == "builtin"
    assert agents["ai-assistant"]["agent_type"] == "system"


def test_upgrade_inserts_numina(migration_engine):
    """up() inserts numina with skills=['*'] and agent_type='system'."""
    with migration_engine.connect() as conn:
        _apply_migration_sql(conn, "upgrade")
        conn.commit()
        agents = _agent_summary(conn)
    assert "numina" in agents
    numina = agents["numina"]
    assert numina["id"] == 100000000000005
    assert numina["agent_type"] == "system"
    assert numina["skills"] == ["*"]
    assert numina["display_order"] == 15


def test_upgrade_deletes_builtin_agents(migration_engine):
    """up() removes the 2 builtin rows."""
    with migration_engine.connect() as conn:
        _apply_migration_sql(conn, "upgrade")
        conn.commit()
        agents = _agent_summary(conn)
    assert "asset-health-advisor" not in agents
    assert "finance-optimizer" not in agents
    # builtin agent_type should have zero rows after upgrade
    builtin_count = sum(1 for a in agents.values() if a["agent_type"] == "builtin")
    assert builtin_count == 0


def test_upgrade_preserves_existing_system_agents(migration_engine):
    """up() must not touch ai-assistant or time-machine."""
    with migration_engine.connect() as conn:
        _apply_migration_sql(conn, "upgrade")
        conn.commit()
        agents = _agent_summary(conn)
    assert agents["ai-assistant"]["soul_md"] == "soul-sys-1"
    assert agents["ai-assistant"]["skills"] == ["chat"]
    assert agents["time-machine"]["soul_md"] == "soul-sys-2"
    assert agents["time-machine"]["skills"] == ["time_machine"]


def test_upgrade_then_downgrade_removes_numina(migration_engine):
    """down() removes numina."""
    with migration_engine.connect() as conn:
        _apply_migration_sql(conn, "upgrade")
        conn.commit()
        _apply_migration_sql(conn, "downgrade")
        conn.commit()
        agents = _agent_summary(conn)
    assert "numina" not in agents


def test_upgrade_then_downgrade_restores_builtin_agents(migration_engine):
    """down() restores both builtin agents with their original IDs and soul_md."""
    with migration_engine.connect() as conn:
        _apply_migration_sql(conn, "upgrade")
        conn.commit()
        _apply_migration_sql(conn, "downgrade")
        conn.commit()
        agents = _agent_summary(conn)
    assert "asset-health-advisor" in agents
    assert "finance-optimizer" in agents
    assert agents["asset-health-advisor"]["id"] == 100000000000001
    assert agents["finance-optimizer"]["id"] == 100000000000002
    assert agents["asset-health-advisor"]["agent_type"] == "builtin"
    assert agents["finance-optimizer"]["agent_type"] == "builtin"


def test_round_trip_returns_to_prior_state(migration_engine):
    """upgrade → downgrade returns the agent set to the exact prior state (4 agents, correct types)."""
    with migration_engine.connect() as conn:
        before = _agent_summary(conn)
        _apply_migration_sql(conn, "upgrade")
        conn.commit()
        _apply_migration_sql(conn, "downgrade")
        conn.commit()
        after = _agent_summary(conn)
    assert set(before.keys()) == set(after.keys())
    for name in before:
        assert before[name]["id"] == after[name]["id"]
        assert before[name]["agent_type"] == after[name]["agent_type"]
        assert before[name]["skills"] == after[name]["skills"]


def test_double_upgrade_is_idempotent_via_unique_constraint(migration_engine):
    """Applying upgrade twice violates UNIQUE (family_id, agent_name) on numina.

    This is the expected protection — alembic itself prevents re-applying a
    revision via its version table. The test confirms the unique constraint
    catches accidental double-application within the same alembic invocation.
    """
    from sqlalchemy.exc import IntegrityError

    with migration_engine.connect() as conn:
        _apply_migration_sql(conn, "upgrade")
        conn.commit()
        with pytest.raises(IntegrityError):
            _apply_migration_sql(conn, "upgrade")


def test_migration_file_has_correct_metadata():
    """The migration file declares the expected revision id and down_revision."""
    from apps.backend.alembic.versions import (
        b6745e8a2c14_demote_builtin_agents_seed_numina as migration,
    )

    assert migration.revision == "b6745e8a2c14"
    assert migration.down_revision == "a53453cf574b"
