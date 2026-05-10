"""盲盒工厂 — 配置和礼物创建。"""

from __future__ import annotations

from typing import Optional
from sqlalchemy.orm import Session

from models import BlindBoxConfig, BlindBoxGift
from factories.users import next_id


class BlindBoxFactory:
    @staticmethod
    def get_or_create_config(
        db: Session,
        *,
        family_id: int,
        enabled: bool = True,
    ) -> tuple[BlindBoxConfig, bool]:
        existing = db.query(BlindBoxConfig).filter(BlindBoxConfig.family_id == family_id).first()
        if existing:
            return existing, False

        cfg = BlindBoxConfig(
            id=next_id(),
            family_id=family_id,
            enabled=enabled,
        )
        db.add(cfg)
        db.flush()
        return cfg, True

    @staticmethod
    def get_or_create_gift(
        db: Session,
        *,
        family_id: int,
        created_by: int,
        name: str,
        emoji: str | None = None,
        value_score: int = 5,
        description: str | None = None,
    ) -> tuple[BlindBoxGift, bool]:
        existing = (
            db.query(BlindBoxGift)
            .filter(BlindBoxGift.family_id == family_id, BlindBoxGift.name == name)
            .first()
        )
        if existing:
            return existing, False

        gift = BlindBoxGift(
            id=next_id(),
            family_id=family_id,
            created_by=created_by,
            name=name,
            emoji=emoji,
            value_score=value_score,
            description=description,
        )
        db.add(gift)
        db.flush()
        return gift, True
