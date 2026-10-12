"""Template registration and question generation."""
from collections.abc import Callable

from packages.domain.question_templates.base import GeneratedQuestion

TEMPLATE_REGISTRY: dict[str, Callable[..., GeneratedQuestion]] = {}


def register_template(template_id: str) -> Callable:
    """Decorator to register a question template generator.

    Usage:
        @register_template("math.arithmetic.addition_2digit")
        def generate(params: dict) -> GeneratedQuestion:
            ...
    """

    def decorator(func: Callable[..., GeneratedQuestion]) -> Callable[..., GeneratedQuestion]:
        TEMPLATE_REGISTRY[template_id] = func
        return func

    return decorator


def list_templates(subject: str | None = None) -> list[str]:
    """List registered template IDs, optionally filtered by subject prefix."""
    if subject is None:
        return list(TEMPLATE_REGISTRY.keys())
    return [tid for tid in TEMPLATE_REGISTRY if tid.startswith(f"{subject}.")]


def generate_question(template_id: str, params: dict) -> GeneratedQuestion:
    """Generate a question using a registered template.

    Raises:
        ValueError: If template_id is not registered.
    """
    func = TEMPLATE_REGISTRY.get(template_id)
    if func is None:
        raise ValueError(f"Unknown template: {template_id}")
    return func(params)
