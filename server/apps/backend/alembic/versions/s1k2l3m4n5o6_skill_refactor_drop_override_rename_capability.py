"""drop family_skill_configs + ai_skills.custom_prompt; rename capability->skill_id

Revision ID: s1k2l3m4n5o6
Revises: f6e87bc90e3a
Create Date: 2026-07-24

Scope (档2→档3 skill architecture refactor):
  1. Drop table ``family_skill_configs`` — per-family builtin prompt override
     retired (决策2: builtin skills are not user-overridable; skill_id is
     globally unique via RESERVED_NAMES). Builtin enable/disable also retired
     (决策3: builtin skills are system fixed-flows, is_enabled恒True, no db row).
  2. Drop column ``ai_skills.custom_prompt`` — prompt override lives only in
     custom-skill SKILL.md files under DeerFlow's user-scoped storage now.
  3. Rename column ``capability`` → ``skill_id`` on ``ai_reports``,
     ``ai_extraction_audits``, ``ai_extraction_circuits``, ``ai_tasks`` — the
     identifier holds a skill_id/agent_name (e.g. "report", "finance_coach"),
     so the column name now matches its semantic. Values are UNCHANGED.
     Indexes / unique constraints renamed accordingly.

Fresh-DB guard: the bootstrap migration (b00t5trap0001) now creates these
tables/columns with the new names directly from the updated model definitions,
so every operation below is guarded by has_table / has_column and is a no-op
on a freshly-bootstrapped DB.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "s1k2l3m4n5o6"
down_revision: str | None = "f6e87bc90e3a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_table(name: str) -> bool:
    bind = op.get_bind()
    return bind.dialect.has_table(bind, name)


def _columns(table: str) -> set[str]:
    bind = op.get_bind()
    return {
        c["name"]
        for c in bind.dialect.get_columns(bind, table)
        if c.get("name") is not None
    }


def _index_names(table: str) -> set[str]:
    bind = op.get_bind()
    result: set[str] = set()
    for idx in bind.dialect.get_indexes(bind, table):
        name = idx.get("name")
        if name is not None:
            result.add(str(name))
    return result


def _capability_to_skill_id(
    table: str,
    existing_type: sa.types.TypeEngine,
    server_default=None,
) -> None:
    """Rename ``capability`` -> ``skill_id`` on *table*.

    Handles two DB states:
    - ``skill_id`` absent: straightforward rename (the original intent).
    - ``skill_id`` already present (e.g. a prior partial run or manual
      ``ALTER TABLE ADD COLUMN skill_id`` left both columns coexisting):
      copy ``capability`` into ``skill_id`` where the latter is empty/null,
      then drop ``capability``. This avoids ``DuplicateColumnError`` from
      ``alter_column(new_column_name=...)`` when the target name is taken.

    The drop uses raw ``ALTER TABLE DROP COLUMN`` (SQLite >= 3.35) instead
    of ``batch_alter_table``: the latter reflects existing column defaults
    and rebuilds the CREATE TABLE, which chokes when a pre-existing
    ``skill_id`` carries a non-constant server_default (e.g.
    ``DEFAULT (report)``) - SQLite rejects that as "default value is not
    constant" on the temp-table recreate. Tables whose ``capability``
    column is part of a UNIQUE constraint (which blocks DROP COLUMN) are
    handled separately in ``upgrade()`` via ``batch_alter_table``.
    """
    cols = _columns(table)
    if "skill_id" not in cols:
        kwargs: dict = {"existing_type": existing_type, "existing_nullable": False}
        if server_default is not None:
            kwargs["server_default"] = server_default
        with op.batch_alter_table(table) as batch_op:
            batch_op.alter_column("capability", new_column_name="skill_id", **kwargs)
    else:
        # skill_id already present (prior partial run or manual ALTER TABLE).
        # Copy surviving data from capability, then drop it via raw SQL
        # (see docstring for why not batch_alter_table).
        bind = op.get_bind()
        bind.execute(
            sa.text(
                f"UPDATE {table} SET skill_id = capability "
                f"WHERE skill_id IS NULL OR skill_id = ''"
            )
        )
        bind.execute(sa.text(f"ALTER TABLE {table} DROP COLUMN capability"))


def upgrade() -> None:
    # ── 1. Drop family_skill_configs table ─────────────────────────────────
    if _has_table("family_skill_configs"):
        op.drop_index(
            "ix_family_skill_configs_family_id",
            table_name="family_skill_configs",
            if_exists=True,
        )
        op.drop_table("family_skill_configs")

    # ── 2. Drop ai_skills.custom_prompt column ─────────────────────────────
    if _has_table("ai_skills") and "custom_prompt" in _columns("ai_skills"):
        with op.batch_alter_table("ai_skills") as batch_op:
            batch_op.drop_column("custom_prompt")

    # ── 3. Rename capability → skill_id (+ indexes/constraints) ────────────
    # ai_reports
    if _has_table("ai_reports") and "capability" in _columns("ai_reports"):
        idxs = _index_names("ai_reports")
        if "ix_ai_reports_family_capability_status" in idxs:
            op.drop_index(
                "ix_ai_reports_family_capability_status", table_name="ai_reports"
            )
        _capability_to_skill_id("ai_reports", sa.String(length=32), sa.text("'report'"))
        if "ix_ai_reports_family_skill_status" not in _index_names("ai_reports"):
            op.create_index(
                "ix_ai_reports_family_skill_status",
                "ai_reports",
                ["family_id", "skill_id", "status"],
            )

    # ai_extraction_audits
    if _has_table("ai_extraction_audits") and "capability" in _columns(
        "ai_extraction_audits"
    ):
        idxs = _index_names("ai_extraction_audits")
        if "ix_ai_extraction_audits_family_capability_time" in idxs:
            op.drop_index(
                "ix_ai_extraction_audits_family_capability_time",
                table_name="ai_extraction_audits",
            )
        if "ix_ai_extraction_audits_capability" in idxs:
            op.drop_index(
                "ix_ai_extraction_audits_capability", table_name="ai_extraction_audits"
            )
        _capability_to_skill_id("ai_extraction_audits", sa.String(length=32))
        idxs = _index_names("ai_extraction_audits")
        if "ix_ai_extraction_audits_skill_id" not in idxs:
            op.create_index(
                "ix_ai_extraction_audits_skill_id", "ai_extraction_audits", ["skill_id"]
            )
        if "ix_ai_extraction_audits_family_skill_time" not in idxs:
            op.create_index(
                "ix_ai_extraction_audits_family_skill_time",
                "ai_extraction_audits",
                ["family_id", "skill_id", "extracted_at"],
            )

    # ai_extraction_circuits
    if _has_table("ai_extraction_circuits") and "capability" in _columns(
        "ai_extraction_circuits"
    ):
        # batch_alter_table recreates the table, dropping capability and the
        # old unique constraint (uq_extraction_circuit_family_capability /
        # sqlite_autoindex) that references it. Re-declare the unique
        # constraint on (family_id, skill_id) in the same batch. Safe here
        # because this table's skill_id has no server_default (no
        # non-constant-default rebuild issue).
        bind = op.get_bind()
        bind.execute(
            sa.text(
                "UPDATE ai_extraction_circuits SET skill_id = capability "
                "WHERE skill_id IS NULL OR skill_id = ''"
            )
        )
        existing_uqs = {
            uq["name"]
            for uq in bind.dialect.get_unique_constraints(
                bind, "ai_extraction_circuits"
            )
        }
        with op.batch_alter_table("ai_extraction_circuits") as batch_op:
            batch_op.drop_column("capability")
            if "uq_extraction_circuit_family_skill" not in existing_uqs:
                batch_op.create_unique_constraint(
                    "uq_extraction_circuit_family_skill",
                    ["family_id", "skill_id"],
                )

    # ai_tasks
    if _has_table("ai_tasks") and "capability" in _columns("ai_tasks"):
        idxs = _index_names("ai_tasks")
        if "ix_ai_tasks_capability" in idxs:
            op.drop_index("ix_ai_tasks_capability", table_name="ai_tasks")
        _capability_to_skill_id("ai_tasks", sa.String(length=50))
        if "ix_ai_tasks_skill_id" not in _index_names("ai_tasks"):
            op.create_index("ix_ai_tasks_skill_id", "ai_tasks", ["skill_id"])


def downgrade() -> None:
    # Downgrade is best-effort: restores old column names + the retired table/column.
    # Not fully reversible (family_skill_configs data, once dropped, is gone).

    # ai_tasks
    if _has_table("ai_tasks") and "skill_id" in _columns("ai_tasks"):
        idxs = _index_names("ai_tasks")
        if "ix_ai_tasks_skill_id" in idxs:
            op.drop_index("ix_ai_tasks_skill_id", table_name="ai_tasks")
        with op.batch_alter_table("ai_tasks") as batch_op:
            batch_op.alter_column(
                "skill_id",
                new_column_name="capability",
                existing_type=sa.String(length=50),
                existing_nullable=False,
            )
        op.create_index("ix_ai_tasks_capability", "ai_tasks", ["capability"])

    # ai_extraction_circuits
    if _has_table("ai_extraction_circuits") and "skill_id" in _columns(
        "ai_extraction_circuits"
    ):
        with op.batch_alter_table("ai_extraction_circuits") as batch_op:
            batch_op.alter_column(
                "skill_id",
                new_column_name="capability",
                existing_type=sa.String(length=32),
                existing_nullable=False,
            )
            batch_op.create_unique_constraint(
                "uq_extraction_circuit_family_capability", ["family_id", "capability"]
            )

    # ai_extraction_audits
    if _has_table("ai_extraction_audits") and "skill_id" in _columns(
        "ai_extraction_audits"
    ):
        idxs = _index_names("ai_extraction_audits")
        if "ix_ai_extraction_audits_family_skill_time" in idxs:
            op.drop_index(
                "ix_ai_extraction_audits_family_skill_time",
                table_name="ai_extraction_audits",
            )
        if "ix_ai_extraction_audits_skill_id" in idxs:
            op.drop_index(
                "ix_ai_extraction_audits_skill_id", table_name="ai_extraction_audits"
            )
        with op.batch_alter_table("ai_extraction_audits") as batch_op:
            batch_op.alter_column(
                "skill_id",
                new_column_name="capability",
                existing_type=sa.String(length=32),
                existing_nullable=False,
            )
        op.create_index(
            "ix_ai_extraction_audits_capability", "ai_extraction_audits", ["capability"]
        )
        op.create_index(
            "ix_ai_extraction_audits_family_capability_time",
            "ai_extraction_audits",
            ["family_id", "capability", "extracted_at"],
        )

    # ai_reports
    if _has_table("ai_reports") and "skill_id" in _columns("ai_reports"):
        idxs = _index_names("ai_reports")
        if "ix_ai_reports_family_skill_status" in idxs:
            op.drop_index("ix_ai_reports_family_skill_status", table_name="ai_reports")
        with op.batch_alter_table("ai_reports") as batch_op:
            batch_op.alter_column(
                "skill_id",
                new_column_name="capability",
                existing_type=sa.String(length=32),
                existing_server_default="report",
                existing_nullable=False,
            )
        op.create_index(
            "ix_ai_reports_family_capability_status",
            "ai_reports",
            ["family_id", "capability", "status"],
        )

    # ai_skills.custom_prompt
    if _has_table("ai_skills") and "custom_prompt" not in _columns("ai_skills"):
        with op.batch_alter_table("ai_skills") as batch_op:
            batch_op.add_column(sa.Column("custom_prompt", sa.Text(), nullable=True))

    # family_skill_configs
    if not _has_table("family_skill_configs"):
        op.create_table(
            "family_skill_configs",
            sa.Column("id", sa.BigInteger(), primary_key=True),
            sa.Column("family_id", sa.BigInteger(), nullable=False),
            sa.Column("capability", sa.String(length=50), nullable=False),
            sa.Column(
                "is_enabled", sa.Boolean(), nullable=False, server_default=sa.true()
            ),
            sa.Column("custom_prompt", sa.Text(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
            sa.UniqueConstraint("family_id", "capability", name="uq_family_skill"),
        )
        op.create_index(
            "ix_family_skill_configs_family_id", "family_skill_configs", ["family_id"]
        )
