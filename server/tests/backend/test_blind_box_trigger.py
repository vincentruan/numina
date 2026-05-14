from unittest.mock import patch

import pytest

from apps.backend.app.models.blind_box_config import BlindBoxConfig
from apps.backend.app.models.blind_box_gift import BlindBoxGift
from apps.backend.app.models.family import Family
from apps.backend.app.models.user import User
from apps.backend.app.utils.snowflake import next_id


def _make_family(db) -> Family:
    family = Family(name="触发测试家庭", created_by=0)
    db.add(family)
    db.flush()
    return family


def _make_child(db, family_id) -> User:
    child = User(
        id=next_id(),
        family_id=family_id,
        display_name="小测试",
        password_hash="dummy",
        role="child",
    )
    db.add(child)
    db.flush()
    return child


def _make_config(db, family_id, enabled=True) -> BlindBoxConfig:
    config = BlindBoxConfig(
        family_id=family_id,
        enabled=enabled,
        base_draw_prob=0.5,
        special_day_prob=0.9,
        weight_scale=2.0,
        surprise_threshold_coins=200,
        surprise_prob_normal=0.05,
        surprise_prob_parent_bday=0.60,
        surprise_prob_sibling_bday=0.50,
    )
    db.add(config)
    db.flush()
    return config


def _make_gift(db, family_id, created_by, value_score=5) -> BlindBoxGift:
    gift = BlindBoxGift(
        id=next_id(),
        family_id=family_id,
        name="测试礼物",
        value_score=value_score,
        created_by=created_by,
        is_active=True,
    )
    db.add(gift)
    db.flush()
    return gift


def test_trigger_disabled_config(db):
    """config.enabled=False 时应返回 None，不创建抽奖记录。"""
    from apps.backend.app.services.blind_box import blind_box_trigger

    family = _make_family(db)
    child = _make_child(db, family.id)
    _make_config(db, family.id, enabled=False)
    db.commit()

    result = blind_box_trigger(db, child)
    assert result is None


def test_trigger_no_gifts(db):
    """概率触发但礼物池为空时应返回 None。"""
    from apps.backend.app.services.blind_box import blind_box_trigger

    family = _make_family(db)
    child = _make_child(db, family.id)
    _make_config(db, family.id, enabled=True)
    db.commit()

    with patch("app.services.blind_box.should_trigger_free_draw", return_value=True):
        result = blind_box_trigger(db, child)

    assert result is None


def test_trigger_creates_draw(db):
    """概率触发且有礼物时应创建 BlindBoxDraw，is_auto_triggered=True，shown_to_child=False，coins_spent=0。"""
    from apps.backend.app.models.blind_box_draw import BlindBoxDraw
    from apps.backend.app.services.blind_box import blind_box_trigger

    family = _make_family(db)
    child = _make_child(db, family.id)
    _make_config(db, family.id, enabled=True)
    _make_gift(db, family.id, created_by=child.id)
    db.commit()

    with (
        patch("app.services.blind_box.should_trigger_free_draw", return_value=True),
        patch("app.services.blind_box.should_upgrade_surprise", return_value=False),
    ):
        result = blind_box_trigger(db, child)

    assert result is not None
    assert isinstance(result, BlindBoxDraw)
    assert result.is_auto_triggered is True
    assert result.shown_to_child is False
    assert result.coins_spent == 0
