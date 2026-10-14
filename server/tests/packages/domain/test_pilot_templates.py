"""Tests for P7d-lite multi-subject pilot templates."""
import pytest

from packages.domain.question_templates.registry import (
    TEMPLATE_REGISTRY,
    generate_question,
    list_templates,
)


class TestChineseTemplates:
    def test_pinyin_templates_registered(self):
        chinese = list_templates("chinese")
        pinyin = [t for t in chinese if "pinyin" in t]
        assert len(pinyin) >= 2

    def test_literacy_templates_registered(self):
        chinese = list_templates("chinese")
        literacy = [t for t in chinese if "literacy" in t]
        assert len(literacy) >= 1

    def test_chinese_template_generates_valid(self):
        chinese = list_templates("chinese")
        assert len(chinese) >= 3
        gq = generate_question(chinese[0], {})
        assert gq.stem_zh
        assert gq.age_group in ("low", "mid", "high")


class TestEnglishTemplates:
    def test_vocabulary_templates_registered(self):
        english = list_templates("english")
        vocab = [t for t in english if "vocab" in t]
        assert len(vocab) >= 2

    def test_grammar_templates_registered(self):
        english = list_templates("english")
        grammar = [t for t in english if "grammar" in t]
        assert len(grammar) >= 1

    def test_english_template_generates_valid(self):
        english = list_templates("english")
        assert len(english) >= 3
        gq = generate_question(english[0], {})
        assert gq.question_type in ("multiple_choice", "fill_blank")


class TestScienceTemplates:
    def test_life_science_templates_registered(self):
        science = list_templates("science")
        life = [t for t in science if "life" in t]
        assert len(life) >= 2

    def test_matter_science_templates_registered(self):
        science = list_templates("science")
        matter = [t for t in science if "matter" in t]
        assert len(matter) >= 1


class TestMathTemplatesNotBroken:
    def test_math_templates_still_registered(self):
        math = list_templates("math")
        assert len(math) >= 25

    def test_existing_math_template_generates(self):
        math = list_templates("math")
        original = [t for t in math if "arithmetic" in t]
        assert len(original) >= 1
        gq = generate_question(original[0], {})
        assert gq.question_type == "calculation"


class TestTotalPilotCount:
    def test_minimum_pilot_counts(self):
        chinese = list_templates("chinese")
        english = list_templates("english")
        science = list_templates("science")
        assert len(chinese) >= 3, f"Chinese: {len(chinese)} (need ≥3)"
        assert len(english) >= 3, f"English: {len(english)} (need ≥3)"
        assert len(science) >= 3, f"Science: {len(science)} (need ≥3)"
