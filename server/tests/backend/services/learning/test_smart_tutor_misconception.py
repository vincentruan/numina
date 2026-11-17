"""Tests for Smart Tutor misconception integration (#214 U4)."""

import json
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.orm import Session

from packages.db.models.learning.misconception import Misconception
from packages.db.models.learning.session import LearningSession
from packages.db.models.learning.topic import LearningTopic


@pytest.fixture
def topic(db: Session) -> LearningTopic:
    t = LearningTopic(
        topic_key="mt_tutor_mc_test", topic_type="concept",
        subject="mathematics", domain="arithmetic",
        name="Tutor test", age_group="mid",
        evidence_json="[]", standards_json="[]",
    )
    db.add(t)
    db.flush()
    return t


@pytest.fixture
def misconception(db: Session, topic: LearningTopic) -> Misconception:
    m = Misconception(
        topic_id=topic.id, sequence=0,
        error_pattern_json=json.dumps(
            {"match_type": "symbolic", "expected_wrong": "2/7"}
        ),
        description="Adding numerators and denominators",
        age_group="mid",
        review_status="approved",
        category="concept_confusion",
    )
    db.add(m)
    db.flush()
    return m


class TestParseSmartTutorStepsMisconception:
    def test_empty_progress_returns_empty_misconceptions(self, db: Session, topic):
        """No steps → empty misconception list."""
        from apps.backend.app.routers.learning_family import (
            _parse_smart_tutor_steps,
        )
        session = LearningSession(
            child_id=1, topic_id=topic.id, session_type="smart_tutor",
            progress_json="[]",
        )
        db.add(session)
        db.flush()
        steps, final_phase, misconceptions = _parse_smart_tutor_steps(session)
        assert steps == []
        assert final_phase is None
        assert misconceptions == []

    def test_deduplicates_misconceptions_across_steps(
        self, db: Session, topic, misconception
    ):
        """Same misconception in multiple steps → one entry."""
        from apps.backend.app.routers.learning_family import (
            _parse_smart_tutor_steps,
        )
        steps = [
            {
                "step": 1, "phase": "DIAGNOSE",
                "quality": "incorrect", "next_phase": "MISCONCEPTION_CORRECTION",
                "misconception": {
                    "id": misconception.id,
                    "category": "concept_confusion",
                    "description": misconception.description,
                },
            },
            {
                "step": 2, "phase": "MISCONCEPTION_CORRECTION",
                "quality": "correct", "next_phase": "VERIFY",
                "misconception": {
                    "id": misconception.id,
                    "category": "concept_confusion",
                    "description": misconception.description,
                },
            },
        ]
        session = LearningSession(
            child_id=1, topic_id=topic.id, session_type="smart_tutor",
            progress_json=json.dumps(steps),
        )
        db.add(session)
        db.flush()
        _, _, misconceptions = _parse_smart_tutor_steps(session)
        assert len(misconceptions) == 1
        assert misconceptions[0]["misconception_id"] == str(misconception.id)
        assert misconceptions[0]["category"] == "concept_confusion"

    def test_multiple_distinct_misconceptions(self, db: Session, topic):
        """Two different misconceptions → two entries."""
        from apps.backend.app.routers.learning_family import (
            _parse_smart_tutor_steps,
        )
        m1 = Misconception(
            topic_id=topic.id, sequence=0,
            error_pattern_json="{}", description="M1",
            age_group="mid", review_status="approved",
            category="concept_confusion",
        )
        m2 = Misconception(
            topic_id=topic.id, sequence=1,
            error_pattern_json="{}", description="M2",
            age_group="mid", review_status="approved",
            category="procedural_error",
        )
        db.add_all([m1, m2])
        db.flush()

        steps = [
            {
                "step": 1, "phase": "DIAGNOSE",
                "misconception": {"id": m1.id, "category": "concept_confusion", "description": "M1"},
            },
            {
                "step": 2, "phase": "DIAGNOSE",
                "misconception": {"id": m2.id, "category": "procedural_error", "description": "M2"},
            },
        ]
        session = LearningSession(
            child_id=1, topic_id=topic.id, session_type="smart_tutor",
            progress_json=json.dumps(steps),
        )
        db.add(session)
        db.flush()
        _, _, misconceptions = _parse_smart_tutor_steps(session)
        assert len(misconceptions) == 2
        ids = {m["misconception_id"] for m in misconceptions}
        assert str(m1.id) in ids
        assert str(m2.id) in ids

    def test_steps_without_misconception_field_ignored(self, db: Session, topic):
        """Steps with no misconception field don't contribute."""
        from apps.backend.app.routers.learning_family import (
            _parse_smart_tutor_steps,
        )
        steps = [
            {"step": 1, "phase": "DIAGNOSE", "quality": "correct"},
            {"step": 2, "phase": "VERIFY", "quality": "correct"},
        ]
        session = LearningSession(
            child_id=1, topic_id=topic.id, session_type="smart_tutor",
            progress_json=json.dumps(steps),
        )
        db.add(session)
        db.flush()
        _, _, misconceptions = _parse_smart_tutor_steps(session)
        assert misconceptions == []


# --- MCP record_tutoring_step misconception validation (#214 U4) ---


@pytest.fixture
def child_user(db: Session):
    """Create a child user for MCP session tests."""
    from packages.db.models.user import User

    u = User(username="mcptestchild", role="child", family_id=100, display_name="MCP Test Child", password_hash="x")
    db.add(u)
    db.flush()
    return u


@pytest.fixture
def tutoring_session(db: Session, child_user, topic) -> LearningSession:
    """Create a Smart Tutor session for the child."""
    s = LearningSession(
        child_id=child_user.id,
        topic_id=topic.id,
        session_type="smart_tutor",
    )
    db.add(s)
    db.flush()
    return s


def _build_mcp_session(family_id: str = "100"):
    """Build an MCPSession bound to the given family."""
    from apps.backend.app.services.mcp_session import MCPSession

    return MCPSession(
        family_id=family_id,
        caller_user_id="u1",
        caller_role="owner",
    )


class TestRecordTutoringStepMisconceptionValidation:
    """MCP record_tutoring_step validates misconception_id against the session topic."""

    @pytest.mark.asyncio
    async def test_valid_misconception_id_resolves(
        self, db: Session, tutoring_session, child_user, misconception
    ):
        """Valid misconception_id → step record contains resolved id/category/description."""
        mcp = _build_mcp_session(family_id=str(child_user.family_id))
        args = {
            "session_id": str(tutoring_session.id),
            "question_id": "1",
            "step_number": "1",
            "phase": "DIAGNOSE",
            "child_response_quality": "attempted",
            "next_phase": "MISCONCEPTION_CORRECTION",
            "misconception_id": str(misconception.id),
        }
        caller_mock = MagicMock(
            id=str(child_user.id), family_id=str(child_user.family_id),
            role="owner", is_active=True,
        )
        with patch(
            "apps.backend.app.services.mcp_session.SessionLocal"
        ) as mock_sl, patch(
            "apps.backend.app.services.mcp_session._get_caller_user",
            return_value=caller_mock,
        ):
            mock_sl.return_value.__enter__ = MagicMock(return_value=db)
            mock_sl.return_value.__exit__ = MagicMock(return_value=False)
            result = await mcp.call_tool("record_tutoring_step", args)

        payload = json.loads(result[0].text)
        assert payload.get("ok") is True

        # Verify the step record was persisted with resolved misconception fields.
        db.refresh(tutoring_session)
        steps = json.loads(tutoring_session.progress_json)
        assert len(steps) == 1
        mc = steps[0]["misconception"]
        assert mc["id"] == misconception.id
        assert mc["category"] == misconception.category
        assert mc["description"] == misconception.description

    @pytest.mark.asyncio
    async def test_nonexistent_misconception_id_rejected(
        self, db: Session, tutoring_session, child_user
    ):
        """Non-existent misconception_id → error response."""
        mcp = _build_mcp_session(family_id=str(child_user.family_id))
        args = {
            "session_id": str(tutoring_session.id),
            "question_id": "1",
            "step_number": "1",
            "phase": "DIAGNOSE",
            "child_response_quality": "attempted",
            "next_phase": "MISCONCEPTION_CORRECTION",
            "misconception_id": "9999999",
        }
        caller_mock = MagicMock(
            id=str(child_user.id), family_id=str(child_user.family_id),
            role="owner", is_active=True,
        )
        with patch(
            "apps.backend.app.services.mcp_session.SessionLocal"
        ) as mock_sl, patch(
            "apps.backend.app.services.mcp_session._get_caller_user",
            return_value=caller_mock,
        ):
            mock_sl.return_value.__enter__ = MagicMock(return_value=db)
            mock_sl.return_value.__exit__ = MagicMock(return_value=False)
            result = await mcp.call_tool("record_tutoring_step", args)

        payload = json.loads(result[0].text)
        assert payload.get("error") == "misconception_not_found"

    @pytest.mark.asyncio
    async def test_misconception_from_different_topic_rejected(
        self, db: Session, tutoring_session, child_user
    ):
        """misconception_id from a different topic → error response."""
        # Create a second topic with its own misconception
        other_topic = LearningTopic(
            topic_key="mt_other_topic", topic_type="concept",
            subject="mathematics", domain="geometry",
            name="Other topic", age_group="mid",
            evidence_json="[]", standards_json="[]",
        )
        db.add(other_topic)
        db.flush()
        other_m = Misconception(
            topic_id=other_topic.id, sequence=0,
            error_pattern_json="{}", description="Other topic's M",
            age_group="mid", review_status="approved",
            category="concept_confusion",
        )
        db.add(other_m)
        db.flush()

        mcp = _build_mcp_session(family_id=str(child_user.family_id))
        args = {
            "session_id": str(tutoring_session.id),
            "question_id": "1",
            "step_number": "1",
            "phase": "DIAGNOSE",
            "child_response_quality": "attempted",
            "next_phase": "MISCONCEPTION_CORRECTION",
            "misconception_id": str(other_m.id),
        }
        caller_mock = MagicMock(
            id=str(child_user.id), family_id=str(child_user.family_id),
            role="owner", is_active=True,
        )
        with patch(
            "apps.backend.app.services.mcp_session.SessionLocal"
        ) as mock_sl, patch(
            "apps.backend.app.services.mcp_session._get_caller_user",
            return_value=caller_mock,
        ):
            mock_sl.return_value.__enter__ = MagicMock(return_value=db)
            mock_sl.return_value.__exit__ = MagicMock(return_value=False)
            result = await mcp.call_tool("record_tutoring_step", args)

        payload = json.loads(result[0].text)
        # Cross-topic misconception should be rejected
        assert payload.get("error") == "misconception_not_found"
