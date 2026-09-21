"""旅游模块工厂 — 幂等创建 Trip / ExpenseCategory / ExpenseEntry / SplitGroup 等。"""

from __future__ import annotations

import random
import string
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from models import (
    ExpenseCategory,
    ExpenseEntry,
    SplitGroup,
    SplitParticipant,
    SplitSettlement,
    Trip,
    TripCoOrganizer,
)
from factories.users import next_id


def _generate_invite_code() -> str:
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=6))


class ExpenseCategoryFactory:
    @staticmethod
    def get_or_create(
        db: Session,
        *,
        name: str,
        icon: str = "label",
        family_id: int | None = None,
        sort_order: int = 0,
        is_system: bool = False,
    ) -> tuple[ExpenseCategory, bool]:
        """幂等创建支出类别。按 (family_id, name) 查重。"""
        q = db.query(ExpenseCategory).filter(ExpenseCategory.name == name)
        if family_id is not None:
            q = q.filter(ExpenseCategory.family_id == family_id)
        else:
            q = q.filter(ExpenseCategory.family_id.is_(None))
        existing = q.first()
        if existing:
            return existing, False

        cat = ExpenseCategory(
            id=next_id(),
            family_id=family_id,
            name=name,
            icon=icon,
            sort_order=sort_order,
            is_system=is_system,
        )
        db.add(cat)
        db.flush()
        return cat, True


class TripFactory:
    @staticmethod
    def get_or_create(
        db: Session,
        *,
        user_id: int,
        family_id: int,
        name: str,
        destination: str,
        departure_date: date,
        return_date: date | None = None,
        status: str = "planning",
        planned_budget: float | None = None,
        initial_funding: float | None = None,
        actual_spend: float = 0,
        currency: str = "CNY",
        wish_id: int | None = None,
        timezone: str | None = None,
        is_active: bool = True,
    ) -> tuple[Trip, bool]:
        """幂等创建行程。按 (family_id, name) 查重。"""
        existing = (
            db.query(Trip)
            .filter(Trip.family_id == family_id, Trip.name == name)
            .first()
        )
        if existing:
            return existing, False

        trip = Trip(
            id=next_id(),
            family_id=family_id,
            user_id=user_id,
            name=name,
            destination=destination,
            departure_date=departure_date,
            return_date=return_date,
            status=status,
            planned_budget=Decimal(str(planned_budget)) if planned_budget is not None else None,
            initial_funding=Decimal(str(initial_funding)) if initial_funding is not None else None,
            actual_spend=Decimal(str(actual_spend)),
            currency=currency,
            wish_id=wish_id,
            timezone=timezone,
            is_active=is_active,
        )
        db.add(trip)
        db.flush()
        return trip, True


class ExpenseEntryFactory:
    @staticmethod
    def create_pair(
        db: Session,
        *,
        family_id: int,
        trip_id: int,
        user_id: int,
        category_id: int | None = None,
        amount: float,
        currency: str = "CNY",
        amount_cny: float | None = None,
        exchange_rate: float | None = None,
        expense_date: date,
        description: str | None = None,
        split_type: str | None = None,
    ) -> tuple[ExpenseEntry, ExpenseEntry]:
        """创建 debit+credit 双Entry 对。返回 (debit, credit)。

        幂等：按 (ref_id=trip_id, expense_date, amount, description) 查重，
        避免 re-seed 时产生重复费用。
        """
        existing_debit = (
            db.query(ExpenseEntry)
            .filter(
                ExpenseEntry.ref_id == trip_id,
                ExpenseEntry.ref_type == "trip",
                ExpenseEntry.leg_type == "debit",
                ExpenseEntry.expense_date == expense_date,
                ExpenseEntry.amount == Decimal(str(amount)),
            )
            .first()
        )
        if existing_debit:
            existing_credit = (
                db.query(ExpenseEntry)
                .filter(
                    ExpenseEntry.transfer_id == existing_debit.transfer_id,
                    ExpenseEntry.leg_type == "credit",
                )
                .first()
            )
            return existing_debit, existing_credit
        transfer_id = next_id()
        if amount_cny is None:
            amount_cny = amount

        debit = ExpenseEntry(
            id=next_id(),
            family_id=family_id,
            transfer_id=transfer_id,
            leg_type="debit",
            ref_id=trip_id,
            ref_type="trip",
            category_id=category_id,
            amount=Decimal(str(amount)),
            currency=currency,
            amount_cny=Decimal(str(amount_cny)),
            exchange_rate=exchange_rate,
            expense_date=expense_date,
            description=description,
            split_type=split_type,
            user_id=user_id,
        )
        credit = ExpenseEntry(
            id=next_id(),
            family_id=family_id,
            transfer_id=transfer_id,
            leg_type="credit",
            ref_id=trip_id,
            ref_type="trip",
            category_id=None,
            amount=Decimal(str(amount)),
            currency=currency,
            amount_cny=Decimal(str(amount_cny)),
            exchange_rate=exchange_rate,
            expense_date=expense_date,
            description=description,
            split_type=split_type,
            user_id=user_id,
        )
        db.add_all([debit, credit])
        db.flush()
        return debit, credit


class SplitGroupFactory:
    @staticmethod
    def get_or_create(
        db: Session,
        *,
        trip_id: int,
        created_by_user_id: int,
        invite_code: str | None = None,
        is_active: bool = True,
    ) -> tuple[SplitGroup, bool]:
        """幂等创建分摊组。按 invite_code 查重（全局唯一），再按 trip_id 查重。"""
        # 优先按 invite_code 查重（跨进程 re-seed 时 trip_id 会变）
        if invite_code:
            existing = db.query(SplitGroup).filter(SplitGroup.invite_code == invite_code).first()
            if existing:
                return existing, False

        existing = (
            db.query(SplitGroup)
            .filter(SplitGroup.trip_id == trip_id)
            .first()
        )
        if existing:
            return existing, False

        group = SplitGroup(
            id=next_id(),
            trip_id=trip_id,
            invite_code=invite_code or _generate_invite_code(),
            created_by_user_id=created_by_user_id,
            is_active=is_active,
        )
        db.add(group)
        db.flush()
        return group, True


class SplitParticipantFactory:
    @staticmethod
    def get_or_create(
        db: Session,
        *,
        group_id: int,
        name: str,
        family_id: int | None = None,
    ) -> tuple[SplitParticipant, bool]:
        """幂等创建分摊参与者。按 (group_id, name) 查重。"""
        existing = (
            db.query(SplitParticipant)
            .filter(SplitParticipant.group_id == group_id, SplitParticipant.name == name)
            .first()
        )
        if existing:
            return existing, False

        participant = SplitParticipant(
            id=next_id(),
            group_id=group_id,
            name=name,
            family_id=family_id,
        )
        db.add(participant)
        db.flush()
        return participant, True


class SplitSettlementFactory:
    @staticmethod
    def get_or_create(
        db: Session,
        *,
        trip_id: int,
        from_participant_name: str,
        to_participant_name: str,
        amount: float,
        currency: str = "CNY",
        is_complete: bool = False,
        settled_at: datetime | None = None,
        settled_by_user_id: int | None = None,
    ) -> tuple[SplitSettlement, bool]:
        """幂等创建结算记录。按 (trip_id, from_name, to_name) 查重。"""
        existing = (
            db.query(SplitSettlement)
            .filter(
                SplitSettlement.trip_id == trip_id,
                SplitSettlement.from_participant_name == from_participant_name,
                SplitSettlement.to_participant_name == to_participant_name,
            )
            .first()
        )
        if existing:
            return existing, False

        settlement = SplitSettlement(
            id=next_id(),
            trip_id=trip_id,
            from_participant_name=from_participant_name,
            to_participant_name=to_participant_name,
            amount=Decimal(str(amount)),
            currency=currency,
            is_complete=is_complete,
            settled_at=settled_at,
            settled_by_user_id=settled_by_user_id,
        )
        db.add(settlement)
        db.flush()
        return settlement, True


class TripCoOrganizerFactory:
    @staticmethod
    def get_or_create(
        db: Session,
        *,
        trip_id: int,
        user_id: int,
    ) -> tuple[TripCoOrganizer, bool]:
        """幂等创建共同组织者。按 (trip_id, user_id) 查重。"""
        existing = (
            db.query(TripCoOrganizer)
            .filter(TripCoOrganizer.trip_id == trip_id, TripCoOrganizer.user_id == user_id)
            .first()
        )
        if existing:
            return existing, False

        co = TripCoOrganizer(
            id=next_id(),
            trip_id=trip_id,
            user_id=user_id,
        )
        db.add(co)
        db.flush()
        return co, True
