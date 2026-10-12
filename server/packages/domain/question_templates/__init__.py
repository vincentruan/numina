"""Question template engine — programmatic question generation."""
from packages.domain.question_templates.base import GeneratedQuestion
from packages.domain.question_templates.registry import (
    TEMPLATE_REGISTRY,
    generate_question,
    list_templates,
    register_template,
)

# Bootstrap: import template modules to trigger @register_template decorators
from packages.domain.question_templates import math_arithmetic  # noqa: F401

__all__ = [
    "GeneratedQuestion",
    "TEMPLATE_REGISTRY",
    "register_template",
    "list_templates",
    "generate_question",
]
