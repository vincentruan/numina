"""Tests for the teach-back pilot confusion seed script (Issue #216 / U2, #37).

Covers:
- seed is idempotent (running twice yields stable row counts)
- every seeded row is review_status='approved'
- every non-null expected_expression round-trips through the grader
- rows for other age groups survive a re-seed (#38)
"""

import importlib.util
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from apps.backend.app.services.learning.teach_back_grading import (
    extract_expression,
    grade_expression,
)
from packages.db.models.learning.confusion import TopicConfusion
from packages.db.models.learning.topic import LearningTopic

_SERVER_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT_PATH = _SERVER_ROOT / "scripts" / "seed_teach_back_confusions.py"


def _load_seed_module():
    """Import the seed script as a module (scripts/ is not a package)."""
    spec = importlib.util.spec_from_file_location(
        "seed_teach_back_confusions", _SCRIPT_PATH
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["seed_teach_back_confusions"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def seed_module():
    return _load_seed_module()


@pytest.fixture
def pilot_topics(db):
    """Create the six teach-back topics the seed script expects."""
    topics = []
    for key in (
        "mt_9KmVWCuh5_",
        "mt_ndGqFPWyen",
        "mt_FP-mjXaq3B",
        "mt_Fl7b8q9pI1",
        "mt_ZM9mhHsyYZ",
        "mt_TgHxujL81r",
    ):
        topic = LearningTopic(
            topic_key=key,
            topic_type="knowledge",
            name=f"Topic {key}",
            name_zh=f"知识点 {key}",
            subject="mathematics",
            domain="fractions",
            age_group="mid",
            source_taxonomy="os-taxonomy-cn",
        )
        db.add(topic)
        topics.append(topic)
    db.flush()
    return topics


def _run_seed(seed_module, db):
    """Run the seed script's body against the test session.

    The script opens ``SessionLocal()`` and closes it in a ``finally``. The test
    session must survive that, so hand it a proxy that forwards everything
    except ``close`` (a no-op here).
    """

    class _NonClosingProxy:
        def __getattr__(self, name):
            return getattr(db, name)

        def close(self):
            db.flush()

    with patch.object(seed_module, "SessionLocal", return_value=_NonClosingProxy()):
        seed_module.seed_confusions()


class TestSeedIdempotency:
    def test_seed_twice_is_stable(self, seed_module, pilot_topics, db):
        """Running the seed twice yields the same row count."""
        _run_seed(seed_module, db)
        first_count = db.query(TopicConfusion).count()
        assert first_count > 0

        _run_seed(seed_module, db)
        second_count = db.query(TopicConfusion).count()
        assert second_count == first_count

    def test_all_rows_approved(self, seed_module, pilot_topics, db):
        """Every seeded confusion is review_status='approved'."""
        _run_seed(seed_module, db)
        rows = db.query(TopicConfusion).all()
        assert rows, "seed produced no rows"
        assert all(r.review_status == "approved" for r in rows)

    def test_two_to_four_confusions_per_topic(self, seed_module, pilot_topics, db):
        """Each pilot topic gets 2-4 confusions per R2."""
        _run_seed(seed_module, db)
        for topic in pilot_topics:
            count = (
                db.query(TopicConfusion)
                .filter(TopicConfusion.topic_id == topic.id)
                .count()
            )
            assert 2 <= count <= 4, f"{topic.topic_key} has {count} confusions"


class TestSeedDataQuality:
    def test_expected_expressions_round_trip(self, seed_module, pilot_topics, db):
        """Every non-null expected_expression survives the extractor + grader (#39).

        The deterministic SymPy track extracts an expression from the child's text
        and compares it with expected_expression. Seed values must be in the bare
        form the extractor can actually produce, or the track can never pass.
        """
        _run_seed(seed_module, db)
        rows = [r for r in db.query(TopicConfusion).all() if r.expected_expression]
        assert rows, "no seeded confusion has an expected_expression"

        for row in rows:
            extracted = extract_expression(row.expected_expression)
            assert extracted is not None, (
                f"expected_expression {row.expected_expression!r} is not "
                f"extractable by the grader"
            )
            result = grade_expression(row.expected_expression, extracted)
            assert result is True, (
                f"expected_expression {row.expected_expression!r} does not "
                f"grade True against its own extracted form {extracted!r}"
            )

    def test_every_row_has_rubric(self, seed_module, pilot_topics, db):
        """Every confusion carries a non-empty LLM grading rubric (R2)."""
        _run_seed(seed_module, db)
        for row in db.query(TopicConfusion).all():
            assert row.rubric and row.rubric.strip(), (
                f"confusion seq={row.sequence} on topic {row.topic_id} has no rubric"
            )

    def test_expansion_topics_have_expected_expressions(self, seed_module, pilot_topics, db):
        """Each expansion topic (issue #234) has at least one gradeable expression.

        Pins that decimals/percents/fraction-multiply seeds exercise the SymPy
        track — the round-trip test alone would pass if their expected_expression
        values were all null while old fraction topics still supply rows.
        """
        _run_seed(seed_module, db)
        expansion_keys = ("mt_Fl7b8q9pI1", "mt_ZM9mhHsyYZ", "mt_TgHxujL81r")
        key_to_topic = {t.topic_key: t for t in pilot_topics}
        for key in expansion_keys:
            topic = key_to_topic[key]
            expr_rows = (
                db.query(TopicConfusion)
                .filter(
                    TopicConfusion.topic_id == topic.id,
                    TopicConfusion.expected_expression.isnot(None),
                )
                .count()
            )
            assert expr_rows >= 1, f"expansion topic {key} has no expected_expression rows"

    def test_fraction_multiply_rubric_example_grades_true(self, seed_module, pilot_topics, db):
        """The seq-2 rubric's worked example must grade against its expected value.

        Regression: expected_expression was '2/3' (the starting fraction) while the
        rubric asks the child to state '2/3 × 5/4 = 10/12', so a correct answer
        graded False and the model's 'hit' was downgraded to 'miss'.
        """
        _run_seed(seed_module, db)
        topic = next(t for t in pilot_topics if t.topic_key == "mt_TgHxujL81r")
        row = (
            db.query(TopicConfusion)
            .filter(TopicConfusion.topic_id == topic.id, TopicConfusion.sequence == 2)
            .one()
        )
        assert row.expected_expression == "10/12"
        assert grade_expression(row.expected_expression, "2/3 × 5/4 = 10/12") is True


class TestSeedAgeGroupScoping:
    def test_other_age_group_rows_survive_reseed(self, seed_module, pilot_topics, db):
        """Re-seeding only replaces age_group='mid' rows (#38)."""
        topic = pilot_topics[0]
        other = TopicConfusion(
            topic_id=topic.id,
            sequence=0,
            confusion_text="A low-age-group confusion",
            age_group="low",
            rubric="some rubric",
            review_status="approved",
        )
        db.add(other)
        db.flush()
        other_id = other.id

        _run_seed(seed_module, db)

        survived = db.get(TopicConfusion, other_id)
        assert survived is not None, (
            "seed deleted a confusion belonging to a different age_group"
        )
        assert survived.age_group == "low"


class TestSeedMissingTopic:
    def test_missing_topic_warns_without_crashing(self, seed_module, db):
        """No pilot topics on disk -> warn, do not raise."""
        _run_seed(seed_module, db)
        assert db.query(TopicConfusion).count() == 0


class TestSeedSequenceScoping:
    def test_hand_curated_row_outside_seeded_sequences_survives(
        self, seed_module, pilot_topics, db
    ):
        """Re-seed must not destroy hand-curated rows at unseeded sequences (#15)."""
        topic = pilot_topics[0]
        seeded_sequences = {
            c["sequence"] for c in seed_module.SAMPLE_CONFUSIONS[topic.topic_key]
        }
        curated_seq = max(seeded_sequences) + 100
        curated = TopicConfusion(
            topic_id=topic.id,
            sequence=curated_seq,
            confusion_text="A hand-curated pending confusion",
            age_group="mid",
            rubric="hand-written rubric",
            review_status="pending",
        )
        db.add(curated)
        db.flush()
        curated_id = curated.id

        _run_seed(seed_module, db)

        survived = db.get(TopicConfusion, curated_id)
        assert survived is not None, (
            "seed deleted a hand-curated confusion outside the seeded sequence set"
        )
        assert survived.review_status == "pending"
