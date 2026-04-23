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


def test_compute_weights_basic():
    from app.services.blind_box import compute_weights

    class FakeGift:
        def __init__(self, id, value_score):
            self.id = id
            self.value_score = value_score

    class FakeConfig:
        weight_scale = 2.0

    gifts = [FakeGift(1, 2), FakeGift(2, 8)]
    weights = compute_weights(gifts, FakeConfig())
    # value_score=2 → weight=1/2^2=0.25; value_score=8 → weight=1/8^2=0.015625
    # 低分礼物权重更高（更容易抽到）
    assert weights[0] > weights[1]
    assert len(weights) == 2


def test_pick_gift_returns_valid():
    from app.services.blind_box import pick_gift

    class FakeGift:
        def __init__(self, id, value_score):
            self.id = id
            self.value_score = value_score

    class FakeConfig:
        weight_scale = 2.0

    gifts = [FakeGift(1, 3), FakeGift(2, 7), FakeGift(3, 5)]
    result = pick_gift(gifts, FakeConfig())
    assert result in gifts


def test_should_trigger_free_draw():
    from app.services.blind_box import should_trigger_free_draw

    class FakeConfig:
        base_draw_prob = 1.0  # 100% 触发
        special_day_prob = 1.0

    assert should_trigger_free_draw(FakeConfig(), is_special=False) is True


def test_is_special_day_birthday():
    from datetime import date
    from app.services.blind_box import is_special_day

    class FakeUser:
        birthday = date(1990, 4, 23)
        birthday_is_lunar = False

    result = is_special_day(FakeUser(), date(2026, 4, 23))
    assert result is True


def test_parent_create_gift(client, auth_headers):
    resp = client.post(
        "/api/v1/blind-box/gifts",
        json={"name": "乐高积木", "value_score": 7, "emoji": "🧱"},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "乐高积木"
    assert data["value_score"] == 7


def test_parent_list_gifts(client, auth_headers):
    client.post(
        "/api/v1/blind-box/gifts",
        json={"name": "玩具车", "value_score": 4},
        headers=auth_headers,
    )
    resp = client.get("/api/v1/blind-box/gifts", headers=auth_headers)
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


def test_parent_get_config(client, auth_headers):
    resp = client.get("/api/v1/blind-box/config", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "enabled" in data
    assert "base_draw_prob" in data


def test_child_draw(client, auth_headers, second_user_headers):
    # 父母先添加礼物
    client.post(
        "/api/v1/blind-box/gifts",
        json={"name": "故事书", "value_score": 3, "emoji": "📚"},
        headers=auth_headers,
    )
    # 孩子抽奖（使用 auth_headers 用户自己抽，因为需要 ChoreInstance）
    resp = client.post(
        "/api/v1/child/blind-box/draw",
        json={"chore_instance_ids": []},  # 空列表应返回 400
        headers=auth_headers,
    )
    assert resp.status_code == 400


def test_child_list_draws(client, auth_headers):
    resp = client.get("/api/v1/child/blind-box/draws", headers=auth_headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
