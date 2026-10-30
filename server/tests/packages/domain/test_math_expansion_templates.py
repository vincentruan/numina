"""Tests for P7b math template expansion."""

from packages.domain.question_templates.registry import (
    TEMPLATE_REGISTRY,
    generate_question,
)


class TestDecimalTemplates:
    def test_decimal_addition_generates(self):
        assert any("decimal" in tid for tid in TEMPLATE_REGISTRY)

    def test_decimal_addition_valid_output(self):
        gq = generate_question("math.decimal.addition", {})
        assert gq.question_type == "calculation"
        assert "answer" in gq.answer
        # topic_key references the standardized taxonomy key (mt_ prefix)
        assert gq.topic_key.startswith("mt_")


class TestEstimationTemplates:
    def test_estimation_generates(self):
        gq = generate_question("math.estimation.rounding", {})
        assert gq.question_type in ("calculation", "fill_blank", "multiple_choice")


class TestMeasurementTemplates:
    def test_unit_conversion_generates(self):
        gq = generate_question("math.measurement.unit_conversion", {})
        assert gq.answer

    def test_perimeter_area_generates(self):
        template_ids = [tid for tid in TEMPLATE_REGISTRY if "perimeter" in tid or "area" in tid]
        assert len(template_ids) >= 1


class TestStatisticsTemplates:
    def test_mean_generates(self):
        template_ids = [tid for tid in TEMPLATE_REGISTRY if "mean" in tid or "statistics" in tid]
        assert len(template_ids) >= 1


class TestPatternTemplates:
    def test_pattern_generates(self):
        gq = generate_question("math.patterns.number_sequence", {})
        assert gq.bloom_level in ("analyze", "understand", "apply")


class TestTemplateCount:
    def test_at_least_11_new_templates(self):
        new_prefixes = ["decimal", "estimation", "measurement", "statistics", "pattern"]
        new_templates = [
            tid for tid in TEMPLATE_REGISTRY
            if any(p in tid for p in new_prefixes)
        ]
        assert len(new_templates) >= 11, f"Only {len(new_templates)} new templates found, need ≥11"
