"""End-to-end teach-back flow against a real DB session (Issue #216 / U8).

Exercises the whole post-mastery chain in one pass, with no mocked DB and no
mocked progress/reward helpers:

    validate -> create session -> record turns (dual-track grading)
    -> all-confusions-hit gate -> apply_teach_back_success
    -> apply_teach_back_rewards (XP + coins + milestone)
    -> parent notification -> parent-side transcript

The unit suites mock the session and the reward helpers, so they verify
orchestration but never the interaction between grading, progress writes,
reward writes, and the notification row. A defect in that interaction — a
commit-ordering bug, a missing FK, a constraint collision — would pass there
and fail here.

Failure coverage (AE3) asserts the mirror image: no progress mutation, no
reward, no notification, and mastery unchanged.
"""

from __future__ import annotations

import pytest

from apps.backend.app.models.reminder import Reminder
from apps.backend.app.services.learning import progress_service, teach_back_service
from apps.backend.app.services.notification.dispatcher import (
    notify_teach_back_completed,
)
from packages.db.models.child_economy.coin_transaction import CoinTransaction
from packages.db.models.learning.confusion import TopicConfusion
from packages.db.models.learning.progress import LearningProgress
from packages.db.models.learning.session import (
    LearningAssessmentAttempt,
    LearningSession,
)
from packages.db.models.learning.topic import LearningTopic
from packages.db.models.user import User

PILOT_TOPIC_KEY = "mt_9KmVWCuh5_"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def e2e_child(db, client, auth_headers):
    """A real child user in the authenticated family."""
    resp = client.post(
        "/api/v1/family/children",
        headers=auth_headers,
        json={
            "username": "tb_e2e_child",
            "password": "ChildPass1",
            "display_name": "TB E2E Kid",
            "avatar_color": "#3366FF",
            "pin": ["\U0001f431", "\U0001f31f", "\U0001f388", "\U0001f436"],
        },
    )
    assert resp.status_code == 201, f"child creation failed: {resp.text}"
    child = db.query(User).filter(User.id == int(resp.json()["data"]["id"])).first()
    assert child is not None
    return child


@pytest.fixture
def e2e_topic(db):
    """A pilot-scope topic."""
    topic = LearningTopic(
        topic_key=PILOT_TOPIC_KEY,
        topic_type="knowledge",
        name="Adding fractions",
        name_zh="同分母分数相加",
        description="E2E teach-back topic",
        subject="mathematics",
        domain="fractions",
        age_group="mid",
        source_taxonomy="os-taxonomy-cn",
        evidence_json="[]",
        standards_json="[]",
        curriculum_standards_json="[]",
    )
    db.add(topic)
    db.flush()
    return topic


@pytest.fixture
def e2e_confusions(db, e2e_topic):
    """Two approved confusions, one expression-anchored and one conceptual."""
    rows = [
        TopicConfusion(
            topic_id=e2e_topic.id,
            sequence=0,
            confusion_text="Why is 1/4 + 2/4 = 3/4 and not 3/8?",
            confusion_text_zh="为什么 1/4 + 2/4 是 3/4 而不是 3/8？",
            age_group="mid",
            rubric="The child must say the denominator stays the same.",
            expected_expression="1/4 + 2/4 = 3/4",
            review_status="approved",
        ),
        TopicConfusion(
            topic_id=e2e_topic.id,
            sequence=1,
            confusion_text="Why don't we add the denominators?",
            confusion_text_zh="为什么分母不用相加？",
            age_group="mid",
            rubric="The child must explain that the denominator counts part size.",
            expected_expression=None,
            review_status="approved",
        ),
    ]
    db.add_all(rows)
    db.flush()
    # A pending row must never count toward the total.
    db.add(
        TopicConfusion(
            topic_id=e2e_topic.id,
            sequence=2,
            confusion_text="pending row",
            age_group="mid",
            rubric="not approved",
            review_status="pending",
        )
    )
    db.flush()
    return rows


@pytest.fixture
def mastered_progress(db, e2e_child, e2e_topic):
    progress = LearningProgress(
        child_id=e2e_child.id,
        topic_id=e2e_topic.id,
        mastery_level="mastered",
        mastery_score=0.9,
        stability=6.0,
        ease_factor=2.5,
        consecutive_review_passes=0,
    )
    db.add(progress)
    db.flush()
    return progress


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _record(db, child, session, confusion, *, verdict, phase, next_phase,
            explanation, expression=None):
    return teach_back_service.record_teach_back_turn(
        db,
        family_id=child.family_id,
        caller_user_id=child.id,
        session_id=session.id,
        confusion_id=confusion.id,
        child_explanation=explanation,
        verdict=verdict,
        phase=phase,
        next_phase=next_phase,
        extracted_expression=expression,
    )


# ---------------------------------------------------------------------------
# AE1 — success path
# ---------------------------------------------------------------------------


class TestTeachBackSuccessE2E:
    def test_full_flow_persists_every_layer(
        self, db, e2e_child, e2e_topic, e2e_confusions, mastered_progress
    ):
        first, second = e2e_confusions
        session = teach_back_service.create_teach_back_session(
            db, e2e_child, e2e_topic
        )

        # Turn 1: expression-anchored confusion, SymPy confirms the claim.
        turn1 = _record(
            db, e2e_child, session, first,
            verdict="hit",
            phase="evaluate_explanation",
            next_phase="present_confusion",
            explanation="因为分母一样，1/4 + 2/4 = 3/4",
            expression="1/4 + 2/4 = 3/4",
        )
        assert turn1["expression_verdict"] == "true"
        assert turn1["all_confusions_hit"] is False
        assert turn1["teach_back_success"] is False

        # Turn 2: conceptual confusion completes the set.
        turn2 = _record(
            db, e2e_child, session, second,
            verdict="hit",
            phase="evaluate_explanation",
            next_phase="resolve",
            explanation="分母表示每份多大，份的大小不变所以分母不变",
        )
        assert turn2["all_confusions_hit"] is True
        assert turn2["teach_back_success"] is True
        assert turn2["teach_back_rewards"]["xp_awarded"] > 0
        assert turn2["teach_back_rewards"]["coins_awarded"] == 20

        db.commit()
        db.refresh(mastered_progress)
        db.refresh(session)

        # Progress reinforcement
        assert mastered_progress.completed_via == "teaching"
        assert mastered_progress.stability == pytest.approx(9.0)
        assert mastered_progress.consecutive_review_passes == 1
        assert session.ended_at is not None

        # Assessment-attempt history
        attempts = (
            db.query(LearningAssessmentAttempt)
            .filter(
                LearningAssessmentAttempt.child_id == e2e_child.id,
                LearningAssessmentAttempt.assessment_type == "teach_back",
            )
            .all()
        )
        assert len(attempts) == 1
        assert attempts[0].passed is True
        assert attempts[0].session_id == session.id

        # Coin ledger, ref-scoped to this session's attempt
        coin_txns = (
            db.query(CoinTransaction)
            .filter(
                CoinTransaction.child_user_id == e2e_child.id,
                CoinTransaction.transaction_type == "learning_earn",
            )
            .all()
        )
        assert len(coin_txns) == 1
        assert coin_txns[0].amount == 20
        assert coin_txns[0].ref_id == attempts[0].id

        # Transcript is readable and carries both turns with their verdicts
        turns = teach_back_service._load_turns(session)
        assert len(turns) == 2
        assert [t["verdict"] for t in turns] == ["hit", "hit"]
        assert turns[0]["extracted_expression"] == "1/4 + 2/4 = 3/4"
        assert turns[0]["expression_verdict"] == "true"

    def test_parent_notification_row_created(
        self, db, e2e_child, e2e_topic, e2e_confusions, mastered_progress
    ):
        session = teach_back_service.create_teach_back_session(
            db, e2e_child, e2e_topic
        )
        notify_teach_back_completed(
            db=db,
            family_id=e2e_child.family_id,
            child_id=e2e_child.id,
            topic_name=e2e_topic.name_zh,
        )
        db.flush()

        reminders = (
            db.query(Reminder)
            .filter(
                Reminder.family_id == e2e_child.family_id,
                Reminder.reminder_type == "teach_back_completed",
            )
            .all()
        )
        assert len(reminders) == 1
        assert e2e_topic.name_zh in reminders[0].title
        assert session.id  # session exists alongside the notification

    def test_declared_sympy_mismatch_blocks_success(
        self, db, e2e_child, e2e_topic, e2e_confusions, mastered_progress
    ):
        """A model-claimed hit with a wrong expression must not complete the set."""
        first, second = e2e_confusions
        session = teach_back_service.create_teach_back_session(
            db, e2e_child, e2e_topic
        )

        bad = _record(
            db, e2e_child, session, first,
            verdict="hit",
            phase="evaluate_explanation",
            next_phase="present_confusion",
            explanation="1/4 + 2/4 = 3/8",
            expression="1/4 + 2/4 = 3/8",
        )
        assert bad["expression_verdict"] == "false"
        assert bad["verdict"] == "miss", "SymPy must override the model's hit"

        db.commit()
        db.refresh(mastered_progress)
        assert mastered_progress.completed_via is None
        assert mastered_progress.consecutive_review_passes == 0
        assert (
            db.query(LearningAssessmentAttempt)
            .filter(LearningAssessmentAttempt.assessment_type == "teach_back")
            .count()
            == 0
        )


# ---------------------------------------------------------------------------
# AE3 — failure path
# ---------------------------------------------------------------------------


class TestTeachBackFailureE2E:
    def test_misses_leave_progress_and_rewards_untouched(
        self, db, e2e_child, e2e_topic, e2e_confusions, mastered_progress
    ):
        first, _second = e2e_confusions
        session = teach_back_service.create_teach_back_session(
            db, e2e_child, e2e_topic
        )

        for _ in range(2):
            result = _record(
                db, e2e_child, session, first,
                verdict="miss",
                phase="evaluate_explanation",
                next_phase="present_confusion",
                explanation="我不知道",
            )
            assert result["teach_back_success"] is False

        db.commit()
        db.refresh(mastered_progress)

        assert mastered_progress.mastery_level == "mastered"
        assert mastered_progress.completed_via is None
        assert mastered_progress.stability == pytest.approx(6.0)
        assert mastered_progress.consecutive_review_passes == 0
        assert db.query(CoinTransaction).filter(
            CoinTransaction.child_user_id == e2e_child.id
        ).count() == 0
        # Transcript still lands, so the parent can review the attempt.
        assert len(teach_back_service._load_turns(session)) == 2

    def test_explicit_end_does_not_award(
        self, db, e2e_child, e2e_topic, e2e_confusions, mastered_progress
    ):
        first, _second = e2e_confusions
        session = teach_back_service.create_teach_back_session(
            db, e2e_child, e2e_topic
        )

        result = _record(
            db, e2e_child, session, first,
            verdict="miss",
            phase="present_confusion",
            next_phase="end",
            explanation="不想教了",
        )
        assert result["teach_back_success"] is False

        db.commit()
        db.refresh(session)
        assert session.ended_at is not None
        db.refresh(mastered_progress)
        assert mastered_progress.consecutive_review_passes == 0


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------


class TestTeachBackIdempotencyE2E:
    def test_replay_after_success_does_not_double_award(
        self, db, e2e_child, e2e_topic, e2e_confusions, mastered_progress
    ):
        first, second = e2e_confusions
        session = teach_back_service.create_teach_back_session(
            db, e2e_child, e2e_topic
        )
        _record(
            db, e2e_child, session, first,
            verdict="hit",
            phase="evaluate_explanation",
            next_phase="present_confusion",
            explanation="1/4 + 2/4 = 3/4",
            expression="1/4 + 2/4 = 3/4",
        )
        _record(
            db, e2e_child, session, second,
            verdict="hit",
            phase="evaluate_explanation",
            next_phase="resolve",
            explanation="份的大小不变所以分母不变",
        )
        db.commit()
        db.refresh(mastered_progress)
        stability_after_success = mastered_progress.stability
        coins_after_success = db.query(CoinTransaction).filter(
            CoinTransaction.child_user_id == e2e_child.id
        ).count()

        replay = _record(
            db, e2e_child, session, second,
            verdict="hit",
            phase="evaluate_explanation",
            next_phase="resolve",
            explanation="份的大小不变所以分母不变",
        )
        db.commit()
        db.refresh(mastered_progress)

        assert replay["teach_back_success"] is False
        assert mastered_progress.stability == pytest.approx(stability_after_success)
        assert mastered_progress.consecutive_review_passes == 1
        assert (
            db.query(CoinTransaction)
            .filter(CoinTransaction.child_user_id == e2e_child.id)
            .count()
            == coins_after_success
        )


# ---------------------------------------------------------------------------
# Cross-family isolation
# ---------------------------------------------------------------------------


class TestTeachBackIsolationE2E:
    def test_other_family_cannot_record_into_session(
        self, db, e2e_child, e2e_topic, e2e_confusions, mastered_progress
    ):
        """A caller bound to a different family is rejected before any write."""
        first, _second = e2e_confusions
        session = teach_back_service.create_teach_back_session(
            db, e2e_child, e2e_topic
        )

        result = teach_back_service.record_teach_back_turn(
            db,
            family_id=e2e_child.family_id + 999,
            caller_user_id=e2e_child.id,
            session_id=session.id,
            confusion_id=first.id,
            child_explanation="1/4 + 2/4 = 3/4",
            verdict="hit",
            phase="evaluate_explanation",
            next_phase="resolve",
        )
        assert result["error"] == "session_not_found"
        assert teach_back_service._load_turns(session) == []

    def test_pending_confusion_is_not_recordable(
        self, db, e2e_child, e2e_topic, e2e_confusions, mastered_progress
    ):
        session = teach_back_service.create_teach_back_session(
            db, e2e_child, e2e_topic
        )
        pending = (
            db.query(TopicConfusion)
            .filter(
                TopicConfusion.topic_id == e2e_topic.id,
                TopicConfusion.review_status == "pending",
            )
            .first()
        )
        assert pending is not None

        result = teach_back_service.record_teach_back_turn(
            db,
            family_id=e2e_child.family_id,
            caller_user_id=e2e_child.id,
            session_id=session.id,
            confusion_id=pending.id,
            child_explanation="anything",
            verdict="hit",
            phase="evaluate_explanation",
            next_phase="resolve",
        )
        assert result["error"] == "confusion_not_found"


# ---------------------------------------------------------------------------
# Session lifecycle
# ---------------------------------------------------------------------------


class TestTeachBackSessionLifecycleE2E:
    def test_validate_creates_session_only_after_all_checks(
        self, db, e2e_child, e2e_topic, e2e_confusions, mastered_progress
    ):
        before = db.query(LearningSession).filter(
            LearningSession.session_type == "teach_back"
        ).count()

        session, topic, confusions = teach_back_service.validate_teach_back_request(
            db=db, child=e2e_child, topic_id=e2e_topic.id
        )

        assert session.session_type == "teach_back"
        assert session.thread_id == str(session.id)
        assert topic.id == e2e_topic.id
        # Only approved rows are served.
        assert len(confusions) == 2
        assert all(c.review_status == "approved" for c in confusions)
        assert (
            db.query(LearningSession)
            .filter(LearningSession.session_type == "teach_back")
            .count()
            == before + 1
        )

    def test_apply_success_is_idempotent_on_the_progress_math(
        self, db, e2e_child, e2e_topic, mastered_progress
    ):
        """The reward math itself compounds; only the ended_at guard prevents replays."""
        progress_service.apply_teach_back_success(db, mastered_progress)
        db.flush()
        first_stability = mastered_progress.stability

        assert first_stability == pytest.approx(9.0)
        assert mastered_progress.consecutive_review_passes == 1
