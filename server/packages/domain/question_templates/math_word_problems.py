"""Math word problem templates — elementary school level."""
import random

from packages.domain.question_templates.base import GeneratedQuestion
from packages.domain.question_templates.registry import register_template


@register_template("math.word_problems.distance_speed_time")
def _gen_distance_problem(params: dict) -> GeneratedQuestion:
    """Distance = speed × time word problem."""
    speed = random.choice([5, 10, 15, 20, 30, 40, 50, 60, 80])
    time_val = random.randint(2, 8)
    distance = speed * time_val
    unit = "千米" if speed >= 30 else "米"
    return GeneratedQuestion(
        template_id="math.word_problems.distance_speed_time",
        stem=f"小明以每小时 {speed} {unit}的速度行进，走了 {time_val} 小时，一共走了多少{unit}?",
        stem_zh=f"小明以每小时 {speed} {unit}的速度行进，走了 {time_val} 小时，一共走了多少{unit}?",
        answer={"answer": distance},
        solution={"steps": [f"路程 = 速度 × 时间", f"= {speed} × {time_val}", f"= {distance} {unit}"]},
        question_type="calculation",
        difficulty=2,
        bloom_level="apply",
        topic_key="mt_word_problems_distance",
        age_group="mid",
        parameters={"speed": speed, "time": time_val},
    )


@register_template("math.word_problems.price_calculation")
def _gen_price_problem(params: dict) -> GeneratedQuestion:
    """Total price = unit price × quantity."""
    items = ["铅笔", "橡皮", "笔记本", "钢笔", "尺子", "文件夹"]
    item = random.choice(items)
    unit_price = random.randint(2, 25)
    quantity = random.randint(3, 12)
    total = unit_price * quantity
    return GeneratedQuestion(
        template_id="math.word_problems.price_calculation",
        stem=f"每支{item} {unit_price} 元，买 {quantity} 支需要多少元?",
        stem_zh=f"每支{item} {unit_price} 元，买 {quantity} 支需要多少元?",
        answer={"answer": total},
        solution={"steps": [f"总价 = 单价 × 数量", f"= {unit_price} × {quantity}", f"= {total} 元"]},
        question_type="calculation",
        difficulty=1,
        bloom_level="apply",
        topic_key="mt_word_problems_price",
        age_group="low",
        parameters={"unit_price": unit_price, "quantity": quantity},
    )


@register_template("math.word_problems.ratio_distribution")
def _gen_ratio_problem(params: dict) -> GeneratedQuestion:
    """Distribute a total according to a ratio."""
    ratio_a = random.randint(1, 5)
    ratio_b = random.randint(1, 5)
    # Ensure total is divisible by sum of ratios
    total_parts = ratio_a + ratio_b
    multiplier = random.randint(2, 10)
    total = total_parts * multiplier
    share_a = ratio_a * multiplier
    share_b = ratio_b * multiplier
    return GeneratedQuestion(
        template_id="math.word_problems.ratio_distribution",
        stem=f"把 {total} 个苹果按 {ratio_a}:{ratio_b} 分给甲和乙，甲分到多少个?乙分到多少个?",
        stem_zh=f"把 {total} 个苹果按 {ratio_a}:{ratio_b} 分给甲和乙，甲分到多少个?乙分到多少个?",
        answer={"a": share_a, "b": share_b},
        solution={"steps": [f"总份数 = {ratio_a} + {ratio_b} = {total_parts}", f"每份 = {total} ÷ {total_parts} = {multiplier}", f"甲 = {ratio_a} × {multiplier} = {share_a}", f"乙 = {ratio_b} × {multiplier} = {share_b}"]},
        question_type="calculation",
        difficulty=3,
        bloom_level="apply",
        topic_key="mt_word_problems_ratio",
        age_group="mid",
        parameters={"total": total, "ratio_a": ratio_a, "ratio_b": ratio_b},
    )


@register_template("math.word_problems.work_rate")
def _gen_work_rate_problem(params: dict) -> GeneratedQuestion:
    """Combined work rate problem."""
    a_hours = random.randint(3, 12)
    b_hours = random.randint(4, 15)
    # Combined time = a*b / (a+b) — may not be integer
    combined = a_hours * b_hours / (a_hours + b_hours)
    combined_rounded = round(combined, 2)
    return GeneratedQuestion(
        template_id="math.word_problems.work_rate",
        stem=f"甲单独完成一项工作需要 {a_hours} 小时，乙单独完成需要 {b_hours} 小时。两人合作需要多少小时完成?",
        stem_zh=f"甲单独完成一项工作需要 {a_hours} 小时，乙单独完成需要 {b_hours} 小时。两人合作需要多少小时完成?",
        answer={"answer": combined_rounded},
        solution={"steps": [f"甲的效率 = 1/{a_hours}", f"乙的效率 = 1/{b_hours}", f"合作效率 = 1/{a_hours} + 1/{b_hours} = {a_hours + b_hours}/({a_hours}×{b_hours})", f"合作时间 = {a_hours}×{b_hours}/({a_hours + b_hours}) = {combined_rounded} 小时"]},
        question_type="calculation",
        difficulty=4,
        bloom_level="apply",
        topic_key="mt_word_problems_work_rate",
        age_group="high",
        parameters={"a_hours": a_hours, "b_hours": b_hours},
    )


@register_template("math.word_problems.age_problem")
def _gen_age_problem(params: dict) -> GeneratedQuestion:
    """Age relationship problem."""
    child_age = random.randint(5, 12)
    parent_age = random.randint(child_age + 20, child_age + 35)
    years_later = random.randint(3, 15)
    future_child = child_age + years_later
    future_parent = parent_age + years_later
    return GeneratedQuestion(
        template_id="math.word_problems.age_problem",
        stem=f"小明今年 {child_age} 岁，爸爸今年 {parent_age} 岁。{years_later} 年后，小明多少岁?爸爸多少岁?",
        stem_zh=f"小明今年 {child_age} 岁，爸爸今年 {parent_age} 岁。{years_later} 年后，小明多少岁?爸爸多少岁?",
        answer={"child_future": future_child, "parent_future": future_parent},
        solution={"steps": [f"{years_later}年后小明 = {child_age} + {years_later} = {future_child} 岁", f"{years_later}年后爸爸 = {parent_age} + {years_later} = {future_parent} 岁"]},
        question_type="calculation",
        difficulty=1,
        bloom_level="apply",
        topic_key="mt_word_problems_age",
        age_group="low",
        parameters={"child_age": child_age, "parent_age": parent_age, "years_later": years_later},
    )
