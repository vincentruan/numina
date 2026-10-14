"""Math geometry question templates — elementary school level."""

import random

from packages.domain.question_templates.base import GeneratedQuestion
from packages.domain.question_templates.registry import register_template


@register_template("math.geometry.rectangle_perimeter")
def _gen_rectangle_perimeter(params: dict) -> GeneratedQuestion:
    """Calculate the perimeter of a rectangle."""
    length = random.randint(3, 20)
    width = random.randint(2, length)  # width <= length
    perimeter = 2 * (length + width)
    return GeneratedQuestion(
        template_id="math.geometry.rectangle_perimeter",
        stem=f"一个长方形的长是 {length} 厘米，宽是 {width} 厘米，求它的周长",
        stem_zh=f"一个长方形的长是 {length} 厘米，宽是 {width} 厘米，求它的周长",
        answer={"answer": perimeter},
        solution={
            "steps": [
                "周长 = 2 × (长 + 宽)",
                f"= 2 × ({length} + {width})",
                f"= 2 × {length + width}",
                f"= {perimeter} 厘米",
            ]
        },
        question_type="calculation",
        difficulty=2,
        bloom_level="apply",
        topic_key="mt_hRZyKvz1KN",
        age_group="mid",
        parameters={"length": length, "width": width},
    )


@register_template("math.geometry.rectangle_area")
def _gen_rectangle_area(params: dict) -> GeneratedQuestion:
    """Calculate the area of a rectangle."""
    length = random.randint(3, 25)
    width = random.randint(2, 15)
    area = length * width
    return GeneratedQuestion(
        template_id="math.geometry.rectangle_area",
        stem=f"一个长方形的长是 {length} 厘米，宽是 {width} 厘米，求它的面积",
        stem_zh=f"一个长方形的长是 {length} 厘米，宽是 {width} 厘米，求它的面积",
        answer={"answer": area},
        solution={
            "steps": ["面积 = 长 × 宽", f"= {length} × {width}", f"= {area} 平方厘米"]
        },
        question_type="calculation",
        difficulty=2,
        bloom_level="apply",
        topic_key="mt_hRZyKvz1KN",
        age_group="mid",
        parameters={"length": length, "width": width},
    )


@register_template("math.geometry.triangle_area")
def _gen_triangle_area(params: dict) -> GeneratedQuestion:
    """Calculate the area of a triangle."""
    base = random.randint(4, 20)
    # Ensure height produces integer or .5 area
    height = random.randint(2, 16)
    area = base * height / 2
    return GeneratedQuestion(
        template_id="math.geometry.triangle_area",
        stem=f"一个三角形的底是 {base} 厘米，高是 {height} 厘米，求它的面积",
        stem_zh=f"一个三角形的底是 {base} 厘米，高是 {height} 厘米，求它的面积",
        answer={"answer": area},
        solution={
            "steps": [
                "面积 = 底 × 高 ÷ 2",
                f"= {base} × {height} ÷ 2",
                f"= {area} 平方厘米",
            ]
        },
        question_type="calculation",
        difficulty=2,
        bloom_level="apply",
        topic_key="mt_h0CVtqI2xo",
        age_group="mid",
        parameters={"base": base, "height": height},
    )


@register_template("math.geometry.angle_supplementary")
def _gen_supplementary_angle(params: dict) -> GeneratedQuestion:
    """Find the supplementary angle."""
    angle = random.randint(10, 170)
    supplement = 180 - angle
    return GeneratedQuestion(
        template_id="math.geometry.angle_supplementary",
        stem=f"已知一个角是 {angle}°，求它的补角",
        stem_zh=f"已知一个角是 {angle}°，求它的补角",
        answer={"answer": supplement},
        solution={
            "steps": ["补角 = 180° - 已知角", f"= 180° - {angle}°", f"= {supplement}°"]
        },
        question_type="calculation",
        difficulty=1,
        bloom_level="apply",
        topic_key="mt_8OAGVdeTJ_",
        age_group="mid",
        parameters={"angle": angle},
    )


@register_template("math.geometry.circle_circumference")
def _gen_circle_circumference(params: dict) -> GeneratedQuestion:
    """Calculate the circumference of a circle (using π ≈ 3.14)."""
    radius = random.randint(1, 14)
    pi_approx = 3.14
    circumference = round(2 * pi_approx * radius, 2)
    return GeneratedQuestion(
        template_id="math.geometry.circle_circumference",
        stem=f"一个圆的半径是 {radius} 厘米，求它的周长（π 取 3.14）",
        stem_zh=f"一个圆的半径是 {radius} 厘米，求它的周长（π 取 3.14）",
        answer={"answer": circumference},
        solution={
            "steps": [
                "周长 = 2 × π × r",
                f"= 2 × 3.14 × {radius}",
                f"= {circumference} 厘米",
            ]
        },
        question_type="calculation",
        difficulty=3,
        bloom_level="apply",
        topic_key="mt_xq3YHZ2zeR",
        age_group="high",
        parameters={"radius": radius},
    )
