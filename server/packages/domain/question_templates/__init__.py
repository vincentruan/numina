"""Question template engine — programmatic question generation."""
# Bootstrap: import template modules to trigger @register_template decorators
from packages.domain.question_templates import (
    math_arithmetic,
    math_decimal,
    math_estimation,
    math_fractions,
    math_geometry,
    math_measurement,
    math_patterns,
    math_statistics,
    math_word_problems,
)  # noqa: F401
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
]
