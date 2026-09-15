"""fix ai_agents name constraint to allow underscores

The original check constraint ck_ai_agents_name_format used regex
'^[a-z][a-z0-9-]*$' which does NOT allow underscores, while the
Pydantic schema validator explicitly permits underscores. This
caused agent_name values like 'stock_research_agent' to pass
application validation but fail at the DB level.

Fix: update the DB constraint to '^[a-z][a-z0-9_-]*$' to match
the Pydantic regex.

Revision ID: e4f5g6h7i8j9
Revises: d3e4f5g6h7i8
Create Date: 2026-08-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e4f5g6h7i8j9"
down_revision: str = "d3e4f5g6h7i8"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_constraints = {c["name"] for c in inspector.get_check_constraints("ai_agents")}
    if "ck_ai_agents_name_format" in existing_constraints:
        with op.batch_alter_table("ai_agents") as batch_op:
            batch_op.drop_constraint("ck_ai_agents_name_format", type_="check")
            batch_op.create_check_constraint(
                "ck_ai_agents_name_format",
                "agent_name ~ '^[a-z][a-z0-9_-]*$'",
            )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_constraints = {c["name"] for c in inspector.get_check_constraints("ai_agents")}
    if "ck_ai_agents_name_format" in existing_constraints:
        with op.batch_alter_table("ai_agents") as batch_op:
            batch_op.drop_constraint("ck_ai_agents_name_format", type_="check")
            batch_op.create_check_constraint(
                "ck_ai_agents_name_format",
                "agent_name ~ '^[a-z][a-z0-9-]*$'",
            )
