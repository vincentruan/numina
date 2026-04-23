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
