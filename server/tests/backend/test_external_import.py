"""Tests for external question bank import."""
import pytest

from apps.backend.app.services.learning.external_import import (
    Math23KAdapter,
    ImportedQuestion,
    SelfJSONAdapter,
)


class TestMath23KAdapter:
    def test_detect_math23k_format(self):
        adapter = Math23KAdapter()
        sample = [{"question": "小明有3个苹果...", "answer": "3+2=5"}]
        assert adapter.detect_format(sample) is True

    def test_reject_wrong_format(self):
        adapter = Math23KAdapter()
        assert adapter.detect_format([{"stem": "wrong format"}]) is False

    def test_parse_produces_imported_question(self):
        adapter = Math23KAdapter()
        sample = [{"question": "1+1等于多少？", "answer": "2"}]
        results = list(adapter.parse(sample))
        assert len(results) == 1
        assert isinstance(results[0], ImportedQuestion)
        assert results[0].stem == "1+1等于多少？"

    def test_validate_catches_empty_stem(self):
        adapter = Math23KAdapter()
        q = ImportedQuestion(stem="", answer_json={"answer": "2"},
                            question_type="calculation", source_name="math23k")
        errors = adapter.validate(q)
        assert len(errors) > 0


class TestSelfJSONAdapter:
    def test_detect_self_json_format(self):
        adapter = SelfJSONAdapter()
        sample = [{"stem": "1+1=?", "answer": {"answer": 2}, "question_type": "calculation"}]
        assert adapter.detect_format(sample) is True


class TestImportedQuestion:
    def test_has_required_fields(self):
        q = ImportedQuestion(
            stem="test", answer_json={"answer": 42},
            question_type="calculation", source_name="test",
        )
        assert q.stem == "test"
        assert q.source == "external"
        assert q.review_status == "pending"
