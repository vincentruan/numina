import random
from datetime import date
from typing import Any


def is_special_day(user: Any, today: date) -> bool:
    """判断今天是否为用户的特殊日期（生日）。农历生日需要 lunardate 转换。"""
    if user.birthday is None:
        return False
    if user.birthday_is_lunar:
        try:
            from lunardate import LunarDate
            lunar_today = LunarDate.fromSolarDate(today.year, today.month, today.day)
            lunar_bday = LunarDate.fromSolarDate(
                user.birthday.year, user.birthday.month, user.birthday.day
            )
            return lunar_today.month == lunar_bday.month and lunar_today.day == lunar_bday.day
        except Exception:
            return False
    return today.month == user.birthday.month and today.day == user.birthday.day


def compute_weights(gifts: list[Any], config: Any) -> list[float]:
    """
    权重 = 1 / (value_score ^ weight_scale)
    低分礼物权重更高，高分礼物更稀有。
    """
    scale = config.weight_scale
    return [1.0 / (g.value_score ** scale) for g in gifts]


def pick_gift(gifts: list[Any], config: Any) -> Any:
    """按权重随机抽取一个礼物。"""
    if not gifts:
        raise ValueError("礼物池为空")
    weights = compute_weights(gifts, config)
    return random.choices(gifts, weights=weights, k=1)[0]


def should_trigger_free_draw(config: Any, is_special: bool) -> bool:
    """根据概率判断是否触发免费抽奖机会。"""
    prob = config.special_day_prob if is_special else config.base_draw_prob
    return random.random() < prob


def should_upgrade_surprise(config: Any, context: dict) -> bool:
    """
    判断是否将本次抽奖升级为超预期惊喜。
    context keys: is_parent_bday, is_sibling_bday
    """
    if context.get("is_parent_bday"):
        prob = config.surprise_prob_parent_bday
    elif context.get("is_sibling_bday"):
        prob = config.surprise_prob_sibling_bday
    else:
        prob = config.surprise_prob_normal
    return random.random() < prob


def blind_box_trigger(db: Any, child: Any) -> Any:
    """任务审批通过后调用。根据概率决定是否自动触发盲盒，触发则创建 BlindBoxDraw 记录并返回。"""
    from datetime import date as date_type

    from app.models.blind_box_config import BlindBoxConfig
    from app.models.blind_box_draw import BlindBoxDraw
    from app.models.blind_box_gift import BlindBoxGift
    from app.models.user import User
    from app.utils.snowflake import next_id

    config = db.query(BlindBoxConfig).filter(BlindBoxConfig.family_id == child.family_id).first()
    if not config or not config.enabled:
        return None

    today = date_type.today()
    is_child_special = is_special_day(child, today)

    family_members = db.query(User).filter(
        User.family_id == child.family_id,
        User.id != child.id,
    ).all()
    is_parent_bday = any(
        m.role in ("owner", "adult") and is_special_day(m, today)
        for m in family_members
    )
    is_sibling_bday = any(
        m.role == "child" and is_special_day(m, today)
        for m in family_members
    )

    is_special = is_child_special or is_parent_bday or is_sibling_bday
    if not should_trigger_free_draw(config, is_special):
        return None

    gifts = db.query(BlindBoxGift).filter(
        BlindBoxGift.family_id == child.family_id,
        BlindBoxGift.is_active == True,  # noqa: E712
    ).all()
    if not gifts:
        return None

    context = {"is_parent_bday": is_parent_bday, "is_sibling_bday": is_sibling_bday}
    surprise = should_upgrade_surprise(config, context)
    pool = [g for g in gifts if g.value_score >= 7] if surprise else gifts
    if not pool:
        pool = gifts

    gift = pick_gift(pool, config)
    draw = BlindBoxDraw(
        id=next_id(),
        family_id=child.family_id,
        child_user_id=child.id,
        coins_spent=0,
        gift_id=gift.id,
        is_surprise=surprise,
        is_bonus=False,
        is_auto_triggered=True,
        shown_to_child=False,
        status="pending_fulfillment",
    )
    db.add(draw)
    db.flush()
    return draw
