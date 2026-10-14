"""Question template engine — programmatic question generation."""

# Bootstrap: import template modules to trigger @register_template decorators
from packages.domain.question_templates import (  # noqa: F401
    chinese_literacy,
    chinese_pinyin,
    english_grammar,
    english_vocabulary,
    math_arithmetic,
    math_decimal,
    math_estimation,
    math_fractions,
    math_geometry,
    math_measurement,
    math_patterns,
    math_statistics,
    math_word_problems,
    science_life,
    science_matter,
)
from packages.domain.question_templates.base import GeneratedQuestion
from packages.domain.question_templates.registry import (
    TEMPLATE_REGISTRY,
    generate_question,
    list_templates,
    register_template,
)

__all__ = [
    "GeneratedQuestion",
    "TEMPLATE_REGISTRY",
    "register_template",
    "list_templates",
    "generate_question",
    # Note: template modules below are imported for @register_template side effects.
    # They are not part of the public API but must be loaded for registration.
]
