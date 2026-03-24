import json
from datetime import date

from sqlalchemy.orm import Session

from app.models.asset import Asset
from app.models.family import Family
from app.models.liability import Liability
from app.models.snapshot import AssetSnapshot
from app.models.user import User
from app.services.exchange_rate import ExchangeRateService


def auto_generate_daily_snapshots(db: Session) -> None:
    """Generate today's snapshots for all families that don't have one yet."""
    today = date.today()
    families = db.query(Family).all()
    for family in families:
        existing = (
            db.query(AssetSnapshot)
            .filter(
                AssetSnapshot.family_id == family.id,
                AssetSnapshot.user_id == None,
                AssetSnapshot.snapshot_date == today,
            )
            .first()
        )
        if not existing:
            generate_snapshots(db, family.id)


def generate_snapshots(db: Session, family_id: str) -> list[AssetSnapshot]:
    today = date.today()
    snapshots = []

    members = db.query(User).filter(User.family_id == family_id, User.is_active == True).all()

    family_total_assets = 0.0
    family_total_liabilities = 0.0

    for member in members:
        total_assets = (
            db.query(Asset)
            .filter(Asset.user_id == member.id, Asset.is_archived == False)
            .with_entities(Asset.current_value, Asset.currency)
            .all()
        )
        member_assets = sum(
            ExchangeRateService.convert(a.current_value or 0, a.currency or "CNY", "CNY", db)
            for a in total_assets
        )

        total_liabilities = (
            db.query(Liability)
            .filter(Liability.user_id == member.id, Liability.is_active == True)
            .with_entities(Liability.remaining_amount, Liability.currency)
            .all()
        )
        member_liabilities = sum(
            ExchangeRateService.convert(l.remaining_amount or 0, getattr(l, "currency", "CNY") or "CNY", "CNY", db)
            for l in total_liabilities
        )

        family_total_assets += member_assets
        family_total_liabilities += member_liabilities

        existing = (
            db.query(AssetSnapshot)
            .filter(
                AssetSnapshot.family_id == family_id,
                AssetSnapshot.user_id == member.id,
                AssetSnapshot.snapshot_date == today,
            )
            .first()
        )
        if existing:
            existing.total_assets = member_assets
            existing.total_liabilities = member_liabilities
            existing.net_worth = member_assets - member_liabilities
            snapshots.append(existing)
        else:
            snap = AssetSnapshot(
                family_id=family_id,
                user_id=member.id,
                snapshot_date=today,
                total_assets=member_assets,
                total_liabilities=member_liabilities,
                net_worth=member_assets - member_liabilities,
            )
            db.add(snap)
            snapshots.append(snap)

    # Family aggregate snapshot (user_id=None)
    existing_family = (
        db.query(AssetSnapshot)
        .filter(
            AssetSnapshot.family_id == family_id,
            AssetSnapshot.user_id == None,
            AssetSnapshot.snapshot_date == today,
        )
        .first()
    )
    if existing_family:
        existing_family.total_assets = family_total_assets
        existing_family.total_liabilities = family_total_liabilities
        existing_family.net_worth = family_total_assets - family_total_liabilities
        snapshots.append(existing_family)
    else:
        family_snap = AssetSnapshot(
            family_id=family_id,
            user_id=None,
            snapshot_date=today,
            total_assets=family_total_assets,
            total_liabilities=family_total_liabilities,
            net_worth=family_total_assets - family_total_liabilities,
        )
        db.add(family_snap)
        snapshots.append(family_snap)

    db.commit()
    return snapshots
