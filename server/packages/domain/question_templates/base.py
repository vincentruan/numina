"""Base types for question template engine."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class GeneratedQuestion:
    """Output from a question template generator.

    Immutable (frozen) so it can be safely passed around without mutation risk.
    """

    template_id: str
    stem: str
    answer: dict
    question_type: str
    difficulty: int
    bloom_level: str
    topic_key: str
    age_group: str
    stem_zh: str | None = None
    options: list[dict] | None = None
    solution: dict | None = None
    parameters: dict = field(default_factory=dict)
