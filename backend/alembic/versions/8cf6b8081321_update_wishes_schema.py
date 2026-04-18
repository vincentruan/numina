"""update_wishes_schema

Revision ID: 8cf6b8081321
Revises: d9f505ab1696
Create Date: 2026-03-25 10:37:50.865931

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8cf6b8081321'
down_revision: Union[str, None] = 'd9f505ab1696'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_context().connection
    inspector = sa.inspect(conn)
    wish_cols = {c['name'] for c in inspector.get_columns('wishes')}

    # If 'status' already exists the schema migration has already been applied
    # (either by a prior migration run or by create_all on a fresh DB).
    if 'status' in wish_cols:
        return

    # Use batch operations for SQLite compatibility
    with op.batch_alter_table('wishes', schema=None) as batch_op:
        # Add new columns
        batch_op.add_column(sa.Column('description', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('status', sa.String(20), nullable=True))
        batch_op.add_column(sa.Column('realized_asset_id', sa.String(36), nullable=True))
        batch_op.add_column(sa.Column('currency', sa.String(10), nullable=True))

    # Migrate data: priority int -> string (0=low, 1=medium, 2=high)
    op.execute("""
        UPDATE wishes SET
            status = CASE
                WHEN is_fulfilled = 1 THEN 'realized'
                ELSE 'pending'
            END,
            realized_asset_id = fulfilled_asset_id,
            description = notes,
            currency = 'CNY'
    """)

    # Recreate table with new schema (SQLite doesn't support ALTER COLUMN)
    # Priority needs to change from INTEGER to VARCHAR
    op.execute("""
        CREATE TABLE wishes_new (
            id VARCHAR(36) NOT NULL,
            family_id VARCHAR(36) NOT NULL,
            user_id VARCHAR(36) NOT NULL,
            name VARCHAR(200) NOT NULL,
            description TEXT,
            expected_price FLOAT,
            priority VARCHAR(20) DEFAULT 'medium',
            status VARCHAR(20) DEFAULT 'pending',
            category_id VARCHAR(36),
            currency VARCHAR(10) DEFAULT 'CNY',
            realized_asset_id VARCHAR(36),
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
            PRIMARY KEY (id),
            FOREIGN KEY(family_id) REFERENCES families (id),
            FOREIGN KEY(user_id) REFERENCES users (id),
            FOREIGN KEY(category_id) REFERENCES categories (id),
            FOREIGN KEY(realized_asset_id) REFERENCES assets (id)
        )
    """)

    # Migrate data
    op.execute("""
        INSERT INTO wishes_new (id, family_id, user_id, name, description, expected_price, priority, status, category_id, currency, realized_asset_id, created_at, updated_at)
        SELECT id, family_id, user_id, name, description, expected_price,
            CASE
                WHEN priority = 0 THEN 'low'
                WHEN priority = 1 THEN 'medium'
                WHEN priority = 2 THEN 'high'
                ELSE 'medium'
            END,
            status, category_id, currency, realized_asset_id, created_at, updated_at
        FROM wishes
    """)

    # Drop old table and rename new one
    op.execute("DROP TABLE wishes")
    op.execute("ALTER TABLE wishes_new RENAME TO wishes")


def downgrade() -> None:
    # Recreate table with old schema
    op.execute("""
        CREATE TABLE wishes_old (
            id VARCHAR(36) NOT NULL,
            family_id VARCHAR(36) NOT NULL,
            user_id VARCHAR(36) NOT NULL,
            name VARCHAR(200) NOT NULL,
            category_id VARCHAR(36),
            expected_price FLOAT,
            target_date DATE,
            priority INTEGER NOT NULL DEFAULT 1,
            notes TEXT,
            is_fulfilled BOOLEAN NOT NULL DEFAULT 0,
            fulfilled_asset_id VARCHAR(36),
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
            PRIMARY KEY (id),
            FOREIGN KEY(family_id) REFERENCES families (id),
            FOREIGN KEY(user_id) REFERENCES users (id),
            FOREIGN KEY(category_id) REFERENCES categories (id),
            FOREIGN KEY(fulfilled_asset_id) REFERENCES assets (id)
        )
    """)

    # Migrate data back
    op.execute("""
        INSERT INTO wishes_old (id, family_id, user_id, name, category_id, expected_price, target_date, priority, notes, is_fulfilled, fulfilled_asset_id, created_at, updated_at)
        SELECT id, family_id, user_id, name, category_id, expected_price, NULL,
            CASE
                WHEN priority = 'low' THEN 0
                WHEN priority = 'medium' THEN 1
                WHEN priority = 'high' THEN 2
                ELSE 1
            END,
            description,
            CASE
                WHEN status = 'realized' THEN 1
                ELSE 0
            END,
            realized_asset_id, created_at, updated_at
        FROM wishes
    """)

    # Drop new table and rename old one
    op.execute("DROP TABLE wishes")
    op.execute("ALTER TABLE wishes_old RENAME TO wishes")