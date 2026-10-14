"""External question bank import adapters."""
from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

from packages.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ImportedQuestion:
    """A question parsed from an external source, not yet in the DB."""
    stem: str
    answer_json: dict
    question_type: str
    source_name: str
    source_license: str | None = None
    stem_zh: str | None = None
    difficulty: int = 2
    bloom_level: str = "apply"
    topic_key: str | None = None
    options: list[dict] | None = None
    solution: dict | None = None
    source: str = "external"
    review_status: str = "pending"


class Math23KAdapter:
    """Adapter for Math23K dataset (JSON array of {question, answer})."""

    def detect_format(self, raw_data: list) -> bool:
        if not raw_data or not isinstance(raw_data, list):
            return False
        sample = raw_data[0]
        return "question" in sample and "answer" in sample

    def parse(self, raw_data: list) -> Iterator[ImportedQuestion]:
        for item in raw_data:
            yield ImportedQuestion(
                stem=item.get("question", ""),
                stem_zh=item.get("question", ""),
                answer_json={"answer": item.get("answer", "")},
                question_type="application",
                source_name="math23k",
            )

    def validate(self, question: ImportedQuestion) -> list[str]:
        errors = []
        if not question.stem or len(question.stem.strip()) < 5:
            errors.append("stem is empty or too short")
        if not question.answer_json or not question.answer_json.get("answer"):
            errors.append("answer is empty")
        return errors


class SelfJSONAdapter:
    """Adapter for our own JSON export format."""

    def detect_format(self, raw_data: list) -> bool:
        if not raw_data or not isinstance(raw_data, list):
            return False
        sample = raw_data[0]
        return "stem" in sample and "answer" in sample and "question_type" in sample

    def parse(self, raw_data: list) -> Iterator[ImportedQuestion]:
        for item in raw_data:
            yield ImportedQuestion(
                stem=item.get("stem", ""),
                stem_zh=item.get("stem_zh"),
                answer_json=item.get("answer", {}),
                question_type=item.get("question_type", "calculation"),
                source_name="self_json",
                difficulty=item.get("difficulty", 2),
                bloom_level=item.get("bloom_level", "apply"),
                topic_key=item.get("topic_key"),
                options=item.get("options"),
                solution=item.get("solution"),
            )

    def validate(self, question: ImportedQuestion) -> list[str]:
        errors = []
        if not question.stem or len(question.stem.strip()) < 5:
            errors.append("stem is empty or too short")
        if not question.answer_json:
            errors.append("answer is empty")
        return errors


def detect_adapter(raw_data: list):
    """Auto-detect the right adapter for the data."""
    adapters = [Math23KAdapter(), SelfJSONAdapter()]
    for adapter in adapters:
        if adapter.detect_format(raw_data):
            return adapter
    return None
