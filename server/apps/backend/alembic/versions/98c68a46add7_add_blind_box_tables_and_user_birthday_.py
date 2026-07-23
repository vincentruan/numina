"""add blind box tables and user birthday fields

Revision ID: 98c68a46add7
Revises: e3cba86157fd
Create Date: 2026-04-24 00:14:59.343882

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '98c68a46add7'
down_revision: str | None = 'b00t5trap0001'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _column_exists(conn, table: str, column: str) -> bool:
    result = conn.execute(sa.text(f"PRAGMA table_info({table})"))
    return any(row[1] == column for row in result)


def upgrade() -> None:
    bind = op.get_bind()

    # ── blind_box_gifts ───────────────────────────────────────────────────────
    if not bind.dialect.has_table(bind, 'blind_box_gifts'):
        op.create_table(
            'blind_box_gifts',
            sa.Column('id', sa.BigInteger(), nullable=False),
            sa.Column('family_id', sa.BigInteger(), nullable=False),
            sa.Column('name', sa.String(length=100), nullable=False),
            sa.Column('description', sa.String(length=200), nullable=True),
            sa.Column('emoji', sa.String(length=10), nullable=True),
            sa.Column('value_score', sa.Integer(), nullable=False),
            sa.Column('source_wish_id', sa.BigInteger(), nullable=True),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('1')),
            sa.Column('created_by', sa.BigInteger(), nullable=False),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(['family_id'], ['families.id']),
            sa.ForeignKeyConstraint(['source_wish_id'], ['child_wishes.id']),
            sa.ForeignKeyConstraint(['created_by'], ['users.id']),
            sa.PrimaryKeyConstraint('id'),
        )

    # ── blind_box_draws ───────────────────────────────────────────────────────
    if not bind.dialect.has_table(bind, 'blind_box_draws'):
        op.create_table(
            'blind_box_draws',
            sa.Column('id', sa.BigInteger(), nullable=False),
            sa.Column('family_id', sa.BigInteger(), nullable=False),
            sa.Column('child_user_id', sa.BigInteger(), nullable=False),
            sa.Column('coins_spent', sa.Integer(), nullable=False),
            sa.Column('gift_id', sa.BigInteger(), nullable=False),
            sa.Column('is_surprise', sa.Boolean(), nullable=False, server_default=sa.text('0')),
            sa.Column('is_bonus', sa.Boolean(), nullable=False, server_default=sa.text('0')),
            sa.Column('source_wish_id', sa.BigInteger(), nullable=True),
            sa.Column('status', sa.String(length=30), nullable=False, server_default=sa.text("'pending_fulfillment'")),
            sa.Column('draw_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.Column('fulfilled_at', sa.DateTime(), nullable=True),
            sa.CheckConstraint("status IN ('pending_fulfillment', 'fulfilled')", name='ck_blind_box_draw_status'),
            sa.ForeignKeyConstraint(['family_id'], ['families.id']),
            sa.ForeignKeyConstraint(['child_user_id'], ['users.id']),
            sa.ForeignKeyConstraint(['gift_id'], ['blind_box_gifts.id']),
            sa.ForeignKeyConstraint(['source_wish_id'], ['child_wishes.id']),
            sa.PrimaryKeyConstraint('id'),
        )

    # ── blind_box_config ──────────────────────────────────────────────────────
    if not bind.dialect.has_table(bind, 'blind_box_config'):
        op.create_table(
            'blind_box_config',
            sa.Column('id', sa.BigInteger(), nullable=False),
            sa.Column('family_id', sa.BigInteger(), nullable=False),
            sa.Column('enabled', sa.Boolean(), nullable=False, server_default=sa.text('1')),
            sa.Column('base_draw_prob', sa.Float(), nullable=False, server_default=sa.text('0.30')),
            sa.Column('special_day_prob', sa.Float(), nullable=False, server_default=sa.text('0.80')),
            sa.Column('weight_scale', sa.Float(), nullable=False, server_default=sa.text('2.0')),
            sa.Column('surprise_threshold_coins', sa.Integer(), nullable=False, server_default=sa.text('200')),
            sa.Column('surprise_prob_normal', sa.Float(), nullable=False, server_default=sa.text('0.05')),
            sa.Column('surprise_prob_parent_bday', sa.Float(), nullable=False, server_default=sa.text('0.60')),
            sa.Column('surprise_prob_sibling_bday', sa.Float(), nullable=False, server_default=sa.text('0.50')),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(['family_id'], ['families.id']),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('family_id', name='uq_blind_box_config_family'),
        )

    # ── bonus_draws ───────────────────────────────────────────────────────────
    if not bind.dialect.has_table(bind, 'bonus_draws'):
        op.create_table(
            'bonus_draws',
            sa.Column('id', sa.BigInteger(), nullable=False),
            sa.Column('family_id', sa.BigInteger(), nullable=False),
            sa.Column('child_user_id', sa.BigInteger(), nullable=False),
            sa.Column('source_wish_id', sa.BigInteger(), nullable=True),
            sa.Column('status', sa.String(length=20), nullable=False, server_default=sa.text("'available'")),
            sa.Column('expires_at', sa.DateTime(), nullable=False),
            sa.Column('used_draw_id', sa.BigInteger(), nullable=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.CheckConstraint("status IN ('available', 'used', 'expired')", name='ck_bonus_draw_status'),
            sa.ForeignKeyConstraint(['family_id'], ['families.id']),
            sa.ForeignKeyConstraint(['child_user_id'], ['users.id']),
            sa.ForeignKeyConstraint(['source_wish_id'], ['child_wishes.id']),
            sa.ForeignKeyConstraint(['used_draw_id'], ['blind_box_draws.id']),
            sa.PrimaryKeyConstraint('id'),
        )

    # ── users: birthday fields ────────────────────────────────────────────────
    if not _column_exists(bind, 'users', 'birthday'):
        with op.batch_alter_table('users') as batch_op:
            batch_op.add_column(sa.Column('birthday', sa.Date(), nullable=True))

    if not _column_exists(bind, 'users', 'birthday_is_lunar'):
        with op.batch_alter_table('users') as batch_op:
            batch_op.add_column(sa.Column('birthday_is_lunar', sa.Boolean(), nullable=False, server_default=sa.text('0')))

    # ── chore_instances: consumed_at ──────────────────────────────────────────
    if bind.dialect.has_table(bind, 'chore_instances') and not _column_exists(bind, 'chore_instances', 'consumed_at'):
        with op.batch_alter_table('chore_instances') as batch_op:
            batch_op.add_column(sa.Column('consumed_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()

    if bind.dialect.has_table(bind, 'chore_instances') and _column_exists(bind, 'chore_instances', 'consumed_at'):
        with op.batch_alter_table('chore_instances') as batch_op:
            batch_op.drop_column('consumed_at')

    if _column_exists(bind, 'users', 'birthday_is_lunar'):
        with op.batch_alter_table('users') as batch_op:
            batch_op.drop_column('birthday_is_lunar')

    if _column_exists(bind, 'users', 'birthday'):
        with op.batch_alter_table('users') as batch_op:
            batch_op.drop_column('birthday')

    if bind.dialect.has_table(bind, 'bonus_draws'):
        op.drop_table('bonus_draws')
    if bind.dialect.has_table(bind, 'blind_box_config'):
        op.drop_table('blind_box_config')
    if bind.dialect.has_table(bind, 'blind_box_draws'):
        op.drop_table('blind_box_draws')
    if bind.dialect.has_table(bind, 'blind_box_gifts'):
        op.drop_table('blind_box_gifts')
