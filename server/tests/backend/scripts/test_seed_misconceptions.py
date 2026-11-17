"""Tests for the misconception seed script (issue #214)."""

import json

import pytest
from sqlalchemy.orm import Session

from packages.db.models.learning.misconception import (
    MISCONCEPTION_CATEGORIES,
    Misconception,
)
from packages.db.models.learning.question import Question
from packages.db.models.learning.topic import LearningTopic

# The seeded catalog covers three question types, so three match types appear.
KNOWN_MATCH_TYPES = {"parametric", "text_match", "option_select"}

# question_type -> the answer key scoring_service.check_answer reads for it.
SCORING_ANSWER_KEY = {"calculation": "answer", "fill_blank": "value", "multiple_choice": "key"}


@pytest.fixture
def fraction_topic(db: Session):
    """Create the pilot topic keyed mt_9KmVWCuh5_ for seeding."""
    t = LearningTopic(
        topic_key="mt_9KmVWCuh5_",
        topic_type="concept",
        subject="mathematics",
        domain="arithmetic",
        name="Understanding fractions",
        age_group="mid",
        evidence_json="[]",
        standards_json="[]",
    )
    db.add(t)
    db.flush()
    return t


class TestSeedMisconceptions:
    def test_seed_creates_misconceptions_with_diagnostic_questions(
        self, db, fraction_topic, monkeypatch
    ):
        """Seeding creates one misconception per catalog entry, each with an approved diagnostic question."""
        from scripts import seed_misconceptions as seed_mod

        # Point SessionLocal at the test DB so the script writes where we can verify.
        monkeypatch.setattr(seed_mod, "SessionLocal", lambda: db)

        seed_mod.seed_misconceptions()

        expected_count = len(seed_mod.SAMPLE_MISCONCEPTIONS["mt_9KmVWCuh5_"])
        misconceptions = (
            db.query(Misconception)
            .filter_by(topic_id=fraction_topic.id)
            .order_by(Misconception.sequence)
            .all()
        )
        assert len(misconceptions) == expected_count
        for m in misconceptions:
            assert m.review_status == "approved"
            assert m.age_group == "mid"
            assert m.category in MISCONCEPTION_CATEGORIES
            assert m.diagnostic_question_id is not None
            # Diagnostic question exists and is approved.
            diag_q = db.query(Question).filter_by(id=m.diagnostic_question_id).first()
            assert diag_q is not None
            assert diag_q.review_status == "approved"
            # Error pattern is valid JSON with a known match_type.
            pattern = m.error_pattern
            assert pattern is not None
            assert pattern["match_type"] in KNOWN_MATCH_TYPES

    def test_seed_is_idempotent(self, db, fraction_topic, monkeypatch):
        """Re-running the seed keeps the same counts (upsert, not duplicate)."""
        from scripts import seed_misconceptions as seed_mod

        monkeypatch.setattr(seed_mod, "SessionLocal", lambda: db)

        seed_mod.seed_misconceptions()
        count_1 = db.query(Misconception).filter_by(topic_id=fraction_topic.id).count()
        q_count_1 = db.query(Question).filter_by(topic_id=fraction_topic.id).count()

        seed_mod.seed_misconceptions()
        count_2 = db.query(Misconception).filter_by(topic_id=fraction_topic.id).count()
        q_count_2 = db.query(Question).filter_by(topic_id=fraction_topic.id).count()

        expected = len(seed_mod.SAMPLE_MISCONCEPTIONS["mt_9KmVWCuh5_"])
        assert count_1 == count_2 == expected
        assert q_count_1 == q_count_2 == expected

    def test_reseed_overwrites_corrected_diagnostic_question(
        self, db, fraction_topic, monkeypatch
    ):
        """A stale diagnostic question is corrected on re-run, not reused untouched.

        Reproduces the pre-fix failure mode: earlier seed runs wrote
        question_type='fill_in_blank' and an MCQ answer keyed 'answer'. Both
        grade as wrong for every child. Re-running must repair them.
        """
        from scripts import seed_misconceptions as seed_mod

        monkeypatch.setattr(seed_mod, "SessionLocal", lambda: db)

        stale = Question(
            topic_id=fraction_topic.id,
            question_type="fill_in_blank",
            stem="In the fraction 3/4, the number 3 is called the ___",
            answer_json=json.dumps({"answer": "numerator"}),
            difficulty=1,
            bloom_level="remember",
            source="seed",
            age_group="mid",
            review_status="approved",
        )
        db.add(stale)
        db.flush()
        stale_id = stale.id

        seed_mod.seed_misconceptions()

        repaired = db.query(Question).filter_by(id=stale_id).first()
        assert repaired.question_type == "fill_blank"
        assert repaired.answer == {"value": "numerator"}

    def test_missing_topic_skipped_with_warning(self, db, monkeypatch, capsys):
        """A missing topic_key is skipped with a warning; others still seeded."""
        from scripts import seed_misconceptions as seed_mod

        # No topic with that key exists in the test DB.
        monkeypatch.setattr(seed_mod, "SessionLocal", lambda: db)

        seed_mod.seed_misconceptions()

        output = capsys.readouterr().out
        assert "not found, skipping" in output
        # No misconceptions were seeded (the only topic key is missing).
        assert db.query(Misconception).count() == 0

    def test_seeded_rows_are_gradable(self, db, fraction_topic, monkeypatch):
        """Every seeded diagnostic question scores correctly via check_answer.

        Detection is worthless if the linked question can't be graded — a wrong
        question_type or answer key marks the child wrong unconditionally.
        """
        from scripts import seed_misconceptions as seed_mod

        monkeypatch.setattr(seed_mod, "SessionLocal", lambda: db)
        seed_mod.seed_misconceptions()

        from apps.backend.app.services.learning.scoring_service import check_answer

        questions = db.query(Question).filter_by(topic_id=fraction_topic.id).all()
        assert questions
        for q in questions:
            assert q.question_type in SCORING_ANSWER_KEY, (
                f"non-canonical question_type {q.question_type!r} on {q.stem!r}"
            )
            answer = q.answer
            key = SCORING_ANSWER_KEY[q.question_type]
            assert key in answer, f"{q.question_type} answer must carry {key!r}: {answer}"
            assert check_answer(q.question_type, answer, answer) is True

    def test_multiple_choice_questions_have_options(self, db, fraction_topic, monkeypatch):
        """Seeded MCQ diagnostic questions carry renderable options with a valid key."""
        from scripts import seed_misconceptions as seed_mod

        monkeypatch.setattr(seed_mod, "SessionLocal", lambda: db)
        seed_mod.seed_misconceptions()

        mcqs = (
            db.query(Question)
            .filter_by(topic_id=fraction_topic.id, question_type="multiple_choice")
            .all()
        )
        assert mcqs, "expected at least one seeded multiple_choice diagnostic question"

        for q in mcqs:
            assert q.options_json is not None
            options = q.options
            assert options is not None and len(options) >= 2
            keys = [opt["key"] for opt in options]
            assert len(keys) == len(set(keys)), f"duplicate option keys: {keys}"
            # The correct answer must select an option that actually exists.
            assert q.answer["key"] in keys

    def test_no_seeded_fill_in_blank_question_type(self, db, fraction_topic, monkeypatch):
        """'fill_in_blank' is not a scorable question_type — seeded rows must use 'fill_blank'."""
        from scripts import seed_misconceptions as seed_mod

        monkeypatch.setattr(seed_mod, "SessionLocal", lambda: db)
        seed_mod.seed_misconceptions()

        assert (
            db.query(Question)
            .filter_by(topic_id=fraction_topic.id, question_type="fill_in_blank")
            .count()
            == 0
        )

    def test_seeded_non_calc_misconceptions_are_detectable(
        self, db, fraction_topic, monkeypatch
    ):
        """Seeded text_match and option_select rows actually fire on the payloads the child app sends."""
        from scripts import seed_misconceptions as seed_mod

        monkeypatch.setattr(seed_mod, "SessionLocal", lambda: db)
        seed_mod.seed_misconceptions()

        from apps.backend.app.services.learning.misconception_detector import (
            detect_misconception,
        )

        questions = {
            q.stem: q for q in db.query(Question).filter_by(topic_id=fraction_topic.id).all()
        }

        # fill_blank: child answers "denominator" where "numerator" was correct.
        # The child app emits {"value": ...} for fill_blank.
        q3 = questions["In the fraction 3/4, the number 3 is called the ___"]
        hit = detect_misconception(db, fraction_topic.id, {"value": "denominator"}, q3)
        assert hit is not None and hit.sequence == 3

        # ... and the Chinese equivalent, since the stem is bilingual.
        hit_zh = detect_misconception(db, fraction_topic.id, {"value": "分母"}, q3)
        assert hit_zh is not None and hit_zh.sequence == 3

        # multiple_choice: child selects key "A". The child app emits {"key": ...}.
        q5 = questions["What is 1/3 + 1/6?"]
        hit_mc = detect_misconception(db, fraction_topic.id, {"key": "A"}, q5)
        assert hit_mc is not None and hit_mc.sequence == 5

        q6 = questions["What is 1/4 + 1/6?"]
        hit_mc2 = detect_misconception(db, fraction_topic.id, {"key": "B"}, q6)
        assert hit_mc2 is not None and hit_mc2.sequence == 6

        # Keys that appear in no wrong_options list stay unmatched. (Detection is
        # topic-scoped, not question-scoped — same as every other match type — so
        # "B" would match sequence 6's pattern even on q5. That is benign here
        # because detection only runs for answers already scored wrong.)
        assert detect_misconception(db, fraction_topic.id, {"key": "D"}, q5) is None
        assert detect_misconception(db, fraction_topic.id, {"key": "D"}, q6) is None

    def test_seeded_misconceptions_are_detectable(self, db, fraction_topic, monkeypatch):
        """The seeded fraction_add_numerators misconception actually detects 2/7."""
        from scripts import seed_misconceptions as seed_mod

        monkeypatch.setattr(seed_mod, "SessionLocal", lambda: db)
        seed_mod.seed_misconceptions()

        from apps.backend.app.services.learning.misconception_detector import (
            detect_misconception,
        )

        q = Question(
            topic_id=fraction_topic.id,
            question_type="calculation",
            stem="What is 1/3 + 1/4?",
            answer_json=json.dumps({"answer": "7/12", "fractions": [[1, 3], [1, 4]]}),
            difficulty=2,
            bloom_level="apply",
            source="test",
            age_group="mid",
            review_status="approved",
        )
        db.add(q)
        db.flush()

        result = detect_misconception(db, fraction_topic.id, {"answer": "2/7"}, q)
        assert result is not None
        assert result.sequence == 0  # fraction_add_numerators is the first

        # The whole-numbers variant also detected.
        result2 = detect_misconception(db, fraction_topic.id, {"answer": "2"}, q)
        assert result2 is not None
        assert result2.sequence == 1
