"""儿童相关工厂 — 任务模板、任务实例、星星币流水。"""

from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional

from sqlalchemy.orm import Session

from models import ChoreInstance, ChoreTemplate, CoinTransaction, User
from factories.users import next_id


class ChoreFactory:
    @staticmethod
    def get_or_create_template(
        db: Session,
        *,
        family_id: int,
        created_by: int,
        name: str,
        emoji: str | None = None,
        coin_reward: int = 5,
        frequency: str = "daily",
        assignment_type: str = "pool",
        assigned_child_ids: list[int] | None = None,
    ) -> tuple[ChoreTemplate, bool]:
        existing = (
            db.query(ChoreTemplate)
            .filter(ChoreTemplate.family_id == family_id, ChoreTemplate.name == name)
            .first()
        )
        if existing:
            return existing, False

        tmpl = ChoreTemplate(
            id=next_id(),
            family_id=family_id,
            created_by=created_by,
            name=name,
            emoji=emoji,
            coin_reward=coin_reward,
            frequency=frequency,
            assignment_type=assignment_type,
        )
        if assigned_child_ids:
            children = db.query(User).filter(User.id.in_(assigned_child_ids)).all()
            tmpl.assignees = children
        db.add(tmpl)
        db.flush()
        return tmpl, True

    @staticmethod
    def get_or_create_instance(
        db: Session,
        *,
        template: ChoreTemplate,
        family_id: int,
        child_user_id: int,
        date_bucket: str,
        status: str = "approved",
        submitted_at: datetime | None = None,
        approved_at: datetime | None = None,
    ) -> tuple[ChoreInstance, bool]:
        existing = (
            db.query(ChoreInstance)
            .filter(
                ChoreInstance.template_id == template.id,
                ChoreInstance.child_user_id == child_user_id,
                ChoreInstance.date_bucket == date_bucket,
            )
            .first()
        )
        if existing:
            return existing, False

        inst = ChoreInstance(
            id=next_id(),
            template_id=template.id,
            family_id=family_id,
            child_user_id=child_user_id,
            chore_name=template.name,
            chore_emoji=template.emoji,
            coin_reward=template.coin_reward,
            date_bucket=date_bucket,
            status=status,
            submitted_at=submitted_at or datetime.utcnow(),
            approved_at=approved_at or datetime.utcnow(),
        )
        db.add(inst)
        db.flush()
        return inst, True


class CoinFactory:
    @staticmethod
    def grant(
        db: Session,
        *,
        family_id: int,
        child_user_id: int,
        amount: int,
        transaction_type: str = "parent_grant",
        ref_id: int | None = None,
        narrative: str | None = None,
        narrative_emoji: str | None = None,
    ) -> CoinTransaction:
        """Grant coins with idempotency.

        Deduplication strategy:
        - If ref_id provided: dedup by (ref_id, transaction_type)
        - If narrative provided and ref_id is None: dedup by (child_user_id, narrative)
        """
        existing = None
        if ref_id is not None:
            existing = (
                db.query(CoinTransaction)
                .filter(
                    CoinTransaction.ref_id == ref_id,
                    CoinTransaction.transaction_type == transaction_type,
                )
                .first()
            )
        elif narrative is not None:
            existing = (
                db.query(CoinTransaction)
                .filter(
                    CoinTransaction.child_user_id == child_user_id,
                    CoinTransaction.narrative == narrative,
                )
                .first()
            )

        if existing:
            return existing

        tx = CoinTransaction(
            id=next_id(),
            family_id=family_id,
            child_user_id=child_user_id,
            amount=amount,
            transaction_type=transaction_type,
            ref_id=ref_id,
            narrative=narrative,
            narrative_emoji=narrative_emoji,
            streak_bonus=0,
        )
        db.add(tx)
        db.flush()
        return tx
