"""add index on learning_clusters.source_taxonomy

Revision ID: idx002clstr
Revises: e805c16f361a
Create Date: 2026-10-21

Idempotent: the backend's boot-time ``align_schema`` creates missing indexes
straight from ``Base.metadata``, so on a fresh container this index may
already exist by the time ``alembic upgrade head`` runs.  Creating it
unconditionally would raise "index already exists" and pin
``alembic_version`` at the previous revision.

"""
from alembic import op

revision = "idx002clstr"
down_revision = "e805c16f361a"
branch_labels = None
depends_on = None

_TABLE = "learning_clusters"
_INDEX = "ix_learning_clusters_source_taxonomy"


def _has_index(table: str, index: str) -> bool:
    bind = op.get_bind()
    if not bind.dialect.has_table(bind, table):
        return False
    return any(i["name"] == index for i in bind.dialect.get_indexes(bind, table))


def upgrade() -> None:
    if not _has_index(_TABLE, _INDEX):
        op.create_index(_INDEX, _TABLE, ["source_taxonomy"])


def downgrade() -> None:
    # ``align_schema`` re-creates this index from the model on the next boot,
    # so a bare drop is not a complete rollback.  To fully revert, drop the
    # column's ``index=True`` in the model and redeploy the previous image.
    if _has_index(_TABLE, _INDEX):
        op.drop_index(_INDEX, table_name=_TABLE)
