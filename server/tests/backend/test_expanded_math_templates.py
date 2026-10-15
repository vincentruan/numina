"""Tests for expanded math templates — fractions, geometry, word problems, extended arithmetic.

Each template is validated by:
1. Generating 100 random instances and verifying answer correctness
2. Boundary value tests (min/max params)
3. Template registration verification
"""


# Import template modules to trigger registration
import packages.domain.question_templates.math_arithmetic  # noqa: F401
import packages.domain.question_templates.math_fractions  # noqa: F401
import packages.domain.question_templates.math_geometry  # noqa: F401
import packages.domain.question_templates.math_word_problems  # noqa: F401
from packages.domain.question_templates.registry import (
    TEMPLATE_REGISTRY,
    generate_question,
)

# --- Registration tests ---


def test_fractions_templates_registered():
    """All fraction templates are registered."""
    expected = [
        "math.fractions.comparison",
        "math.fractions.addition_same_denominator",
        "math.fractions.subtraction_same_denominator",
        "math.fractions.to_decimal",
        "math.fractions.simple_reduction",
    ]
    for tid in expected:
        assert tid in TEMPLATE_REGISTRY, f"Template {tid} not registered"


def test_geometry_templates_registered():
    """All geometry templates are registered."""
    expected = [
        "math.geometry.rectangle_perimeter",
        "math.geometry.rectangle_area",
        "math.geometry.triangle_area",
        "math.geometry.angle_supplementary",
        "math.geometry.circle_circumference",
    ]
    for tid in expected:
        assert tid in TEMPLATE_REGISTRY, f"Template {tid} not registered"


def test_word_problem_templates_registered():
    """All word problem templates are registered."""
    expected = [
        "math.word_problems.distance_speed_time",
        "math.word_problems.price_calculation",
        "math.word_problems.ratio_distribution",
        "math.word_problems.work_rate",
        "math.word_problems.age_problem",
    ]
    for tid in expected:
        assert tid in TEMPLATE_REGISTRY, f"Template {tid} not registered"


def test_extended_arithmetic_templates_registered():
    """Extended arithmetic templates are registered."""
    expected = [
        "math.arithmetic.addition_3digit",
        "math.arithmetic.subtraction_3digit",
        "math.arithmetic.multiplication_estimate",
        "math.arithmetic.division_with_remainder",
        "math.arithmetic.mixed_operations",
    ]
    for tid in expected:
        assert tid in TEMPLATE_REGISTRY, f"Template {tid} not registered"


# --- Correctness tests (100 random instances each) ---


def _verify_template_correctness(template_id: str, verify_fn, n: int = 100):
    """Generate n instances and verify each answer using verify_fn."""
    for _ in range(n):
        gq = generate_question(template_id, {})
        assert verify_fn(gq), f"Template {template_id} produced wrong answer: stem={gq.stem}, answer={gq.answer}"


def test_fractions_comparison_correct():
    def verify(gq):
        params = gq.parameters
        a_num, a_den = params["a_num"], params["a_den"]
        b_num, b_den = params["b_num"], params["b_den"]
        lhs = a_num * b_den
        rhs = b_num * a_den
        expected = ">" if lhs > rhs else ("<" if lhs < rhs else "=")
        return gq.answer["value"] == expected

    _verify_template_correctness("math.fractions.comparison", verify)


def test_fractions_addition_same_denominator_correct():
    def verify(gq):
        params = gq.parameters
        expected_num = params["a_num"] + params["b_num"]
        return gq.answer["answer"] == expected_num

    _verify_template_correctness("math.fractions.addition_same_denominator", verify)


def test_fractions_subtraction_same_denominator_correct():
    def verify(gq):
        params = gq.parameters
        expected_num = params["a_num"] - params["b_num"]
        return gq.answer["answer"] == expected_num

    _verify_template_correctness("math.fractions.subtraction_same_denominator", verify)


def test_fractions_to_decimal_correct():
    def verify(gq):
        params = gq.parameters
        expected = params["numerator"] / params["denominator"]
        return abs(gq.answer["answer"] - expected) < 0.001

    _verify_template_correctness("math.fractions.to_decimal", verify)


def test_fractions_simple_reduction_correct():
    def verify(gq):
        params = gq.parameters
        from math import gcd
        g = gcd(params["numerator"], params["denominator"])
        expected = f"{params['numerator'] // g}/{params['denominator'] // g}"
        return gq.answer["value"] == expected

    _verify_template_correctness("math.fractions.simple_reduction", verify)


def test_geometry_rectangle_perimeter_correct():
    def verify(gq):
        params = gq.parameters
        expected = 2 * (params["length"] + params["width"])
        return gq.answer["answer"] == expected

    _verify_template_correctness("math.geometry.rectangle_perimeter", verify)


def test_geometry_rectangle_area_correct():
    def verify(gq):
        params = gq.parameters
        expected = params["length"] * params["width"]
        return gq.answer["answer"] == expected

    _verify_template_correctness("math.geometry.rectangle_area", verify)


def test_geometry_triangle_area_correct():
    def verify(gq):
        params = gq.parameters
        expected = params["base"] * params["height"] / 2
        return gq.answer["answer"] == expected

    _verify_template_correctness("math.geometry.triangle_area", verify)


def test_geometry_angle_supplementary_correct():
    def verify(gq):
        params = gq.parameters
        expected = 180 - params["angle"]
        return gq.answer["answer"] == expected

    _verify_template_correctness("math.geometry.angle_supplementary", verify)


def test_geometry_circle_circumference_correct():
    def verify(gq):
        params = gq.parameters
        expected = round(2 * 3.14 * params["radius"], 2)
        return abs(gq.answer["answer"] - expected) < 0.01

    _verify_template_correctness("math.geometry.circle_circumference", verify)


def test_word_problems_distance_correct():
    def verify(gq):
        params = gq.parameters
        expected = params["speed"] * params["time"]
        return gq.answer["answer"] == expected

    _verify_template_correctness("math.word_problems.distance_speed_time", verify)


def test_word_problems_price_correct():
    def verify(gq):
        params = gq.parameters
        expected = params["unit_price"] * params["quantity"]
        return gq.answer["answer"] == expected

    _verify_template_correctness("math.word_problems.price_calculation", verify)


def test_word_problems_ratio_correct():
    def verify(gq):
        # Answer is now a single string "甲X个，乙Y个"
        params = gq.parameters
        total_parts = params["ratio_a"] + params["ratio_b"]
        expected_a = params["total"] * params["ratio_a"] / total_parts
        expected_b = params["total"] * params["ratio_b"] / total_parts
        return f"甲{int(expected_a)}个" in gq.answer["answer"] and f"乙{int(expected_b)}个" in gq.answer["answer"]

    _verify_template_correctness("math.word_problems.ratio_distribution", verify)


def test_word_problems_work_rate_correct():
    def verify(gq):
        params = gq.parameters
        # Combined rate: 1/a + 1/b = (a+b)/(a*b), time = a*b/(a+b)
        expected = params["a_hours"] * params["b_hours"] / (params["a_hours"] + params["b_hours"])
        return abs(gq.answer["answer"] - expected) < 0.01

    _verify_template_correctness("math.word_problems.work_rate", verify)


def test_word_problems_age_correct():
    def verify(gq):
        params = gq.parameters
        future_child = params["child_age"] + params["years_later"]
        future_parent = params["parent_age"] + params["years_later"]
        return f"小明{future_child}岁" in gq.answer["answer"] and f"爸爸{future_parent}岁" in gq.answer["answer"]

    _verify_template_correctness("math.word_problems.age_problem", verify)


def test_arithmetic_3digit_addition_correct():
    def verify(gq):
        params = gq.parameters
        return gq.answer["answer"] == params["a"] + params["b"]

    _verify_template_correctness("math.arithmetic.addition_3digit", verify)


def test_arithmetic_3digit_subtraction_correct():
    def verify(gq):
        params = gq.parameters
        return gq.answer["answer"] == params["a"] - params["b"]

    _verify_template_correctness("math.arithmetic.subtraction_3digit", verify)


def test_arithmetic_multiplication_estimate_correct():
    def verify(gq):
        params = gq.parameters
        # Half-up rounding (四舍五入)
        a_round = int(params["a"] / 10 + 0.5) * 10
        b_round = int(params["b"] / 10 + 0.5) * 10
        return gq.answer["answer"] == a_round * b_round

    _verify_template_correctness("math.arithmetic.multiplication_estimate", verify)


def test_arithmetic_division_remainder_correct():
    def verify(gq):
        params = gq.parameters
        expected_q = params["dividend"] // params["divisor"]
        expected_r = params["dividend"] % params["divisor"]
        expected_str = f"{expected_q}……{expected_r}"
        return gq.answer["value"] == expected_str

    _verify_template_correctness("math.arithmetic.division_with_remainder", verify)


def test_arithmetic_mixed_operations_correct():
    def verify(gq):
        params = gq.parameters
        a, b, c = params["a"], params["b"], params["c"]
        op = params["op"]
        if op == "add_then_multiply":
            expected = (a + b) * c
        elif op == "multiply_then_add":
            expected = a * b + c
        else:  # subtract_then_divide
            # Template ensures (a - b) is divisible by c
            expected = (a - b) // c
        return gq.answer["answer"] == expected

    _verify_template_correctness("math.arithmetic.mixed_operations", verify)


# --- Boundary tests ---


def test_fractions_no_zero_denominator():
    """Fraction templates never produce zero denominators."""
    for _ in range(50):
        gq = generate_question("math.fractions.comparison", {})
        assert gq.parameters["a_den"] > 0
        assert gq.parameters["b_den"] > 0


def test_geometry_positive_dimensions():
    """Geometry templates never produce zero or negative dimensions."""
    for template_id in ["math.geometry.rectangle_perimeter", "math.geometry.rectangle_area", "math.geometry.triangle_area"]:
        for _ in range(50):
            gq = generate_question(template_id, {})
            for key in gq.parameters:
                assert gq.parameters[key] > 0, f"{template_id}: {key}={gq.parameters[key]} <= 0"


def test_subtraction_non_negative():
    """Subtraction templates never produce negative results."""
    for template_id in ["math.arithmetic.subtraction_3digit", "math.fractions.subtraction_same_denominator"]:
        for _ in range(50):
            gq = generate_question(template_id, {})
            assert gq.answer["answer"] >= 0, f"{template_id}: negative result {gq.answer['answer']}"


def test_all_templates_have_required_fields():
    """Every template produces GeneratedQuestion with all required fields."""
    for template_id in TEMPLATE_REGISTRY:
        gq = generate_question(template_id, {})
        assert gq.stem, f"{template_id}: empty stem"
        assert gq.answer is not None, f"{template_id}: null answer"
        assert gq.question_type, f"{template_id}: empty question_type"
        assert gq.topic_key, f"{template_id}: empty topic_key"
        assert gq.age_group in ("low", "mid", "high"), f"{template_id}: invalid age_group {gq.age_group}"
        assert 1 <= gq.difficulty <= 5, f"{template_id}: difficulty {gq.difficulty} out of range"
