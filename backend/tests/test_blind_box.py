def test_create_blind_box_gift(db):
    from app.models.blind_box_gift import BlindBoxGift
    gift = BlindBoxGift(
        family_id=1,
        name="乐高积木",
        value_score=8,
        created_by=1,
    )
    db.add(gift)
    db.commit()
    assert gift.id is not None
    assert gift.is_active is True


def test_create_blind_box_draw(db):
    from app.models.blind_box_draw import BlindBoxDraw
    from app.models.blind_box_gift import BlindBoxGift

    gift = BlindBoxGift(family_id=1, name="玩具", value_score=5, created_by=1)
    db.add(gift)
    db.commit()

    draw = BlindBoxDraw(
        family_id=1,
        child_user_id=2,
        coins_spent=100,
        gift_id=gift.id,
        is_surprise=False,
        is_bonus=False,
        status="pending_fulfillment",
    )
    db.add(draw)
    db.commit()
    assert draw.id is not None
    assert draw.draw_at is not None


def test_create_blind_box_config(db):
    from app.models.blind_box_config import BlindBoxConfig

    config = BlindBoxConfig(family_id=1)
    db.add(config)
    db.commit()

    assert config.id is not None
    assert config.enabled is True
    assert config.base_draw_prob == 0.30
    assert config.weight_scale == 2.0
    assert config.surprise_threshold_coins == 200


def test_user_birthday_fields(db):
    from app.models.user import User
    from sqlalchemy import inspect as sa_inspect
    cols = {c.key for c in sa_inspect(User).mapper.column_attrs}
    assert "birthday" in cols
    assert "birthday_is_lunar" in cols
