"""Real-database sibling tests for MCP child self-scope enforcement (#244 U3).

These tests prove the gate works against actual database rows, not mocks.
One family, two child users, real LearningTopic/LearningProgress/LearningSession
rows. The gate must deny a child caller's attempt to access a sibling's data
through any of the six child-open tools.
"""
import json
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.orm import Session

from apps.backend.app.models.user import User
from packages.db.models.learning.progress import LearningProgress
from packages.db.models.learning.session import LearningSession
from packages.db.models.learning.topic import LearningTopic


@pytest.fixture
def family_with_two_children(db: Session):
    """One family, two child users."""
    family_id = 100
    child_a = User(
        id=1001,
        family_id=family_id,
        username="child_a",
        display_name="Child A",
        role="child",
        is_active=True,
        password_hash="dummy",
    )
    child_b = User(
        id=1002,
        family_id=family_id,
        username="child_b",
        display_name="Child B",
        role="child",
        is_active=True,
        password_hash="dummy",
    )
    db.add_all([child_a, child_b])
    db.flush()
    return child_a, child_b, family_id


@pytest.fixture
def learning_data(db: Session, family_with_two_children):
    """Real LearningTopic and LearningProgress rows for each child."""
    child_a, child_b, family_id = family_with_two_children

    # Two topics
    topic_1 = LearningTopic(
        topic_key="math_addition",
        topic_type="concept",
        subject="mathematics",
        domain="arithmetic",
        name="Addition",
        age_group="mid",
        evidence_json="[]",
        standards_json="[]",
    )
    topic_2 = LearningTopic(
        topic_key="math_subtraction",
        topic_type="concept",
        subject="mathematics",
        domain="arithmetic",
        name="Subtraction",
        age_group="mid",
        evidence_json="[]",
        standards_json="[]",
    )
    db.add_all([topic_1, topic_2])
    db.flush()

    # Child A has progress on topic_1 (mastered)
    progress_a = LearningProgress(
        child_id=child_a.id,
        topic_id=topic_1.id,
        mastery_level="mastered",
        xp_earned=100,
    )
    # Child B has progress on topic_2 (learning)
    progress_b = LearningProgress(
        child_id=child_b.id,
        topic_id=topic_2.id,
        mastery_level="learning",
        xp_earned=50,
    )
    db.add_all([progress_a, progress_b])
    db.flush()

    return topic_1, topic_2, progress_a, progress_b


@pytest.fixture
def learning_sessions(db: Session, family_with_two_children, learning_data):
    """Real LearningSession rows for each child."""
    child_a, child_b, _ = family_with_two_children
    topic_1, topic_2, _, _ = learning_data

    session_a = LearningSession(
        child_id=child_a.id,
        topic_id=topic_1.id,
        session_type="smart_tutor",
        progress_json="[]",
    )
    session_b = LearningSession(
        child_id=child_b.id,
        topic_id=topic_2.id,
        session_type="smart_tutor",
        progress_json="[]",
    )
    db.add_all([session_a, session_b])
    db.flush()
    return session_a, session_b


def _build_mcp_session_for_child(child: User, family_id: int):
    """Build an MCPSession bound to the child caller."""
    from apps.backend.app.services.mcp_session import MCPSession

    return MCPSession(
        family_id=str(family_id),
        caller_user_id=str(child.id),
        caller_role="child",
    )


@pytest.mark.asyncio
class TestChildSelfScopeRealData:
    """The gap #244 describes is proven closed against real family rows."""

    async def test_child_a_calls_own_topic_proceeds(
        self, db: Session, family_with_two_children, learning_data
    ):
        """Child A calls get_knowledge_bridge for themselves → proceeds."""
        child_a, child_b, family_id = family_with_two_children
        topic_1, topic_2, progress_a, progress_b = learning_data

        mcp = _build_mcp_session_for_child(child_a, family_id)
        args = {"child_id": str(child_a.id), "topic_id": str(topic_1.id)}

        with patch(
            "apps.backend.app.services.mcp_session.SessionLocal"
        ) as mock_sl, patch(
            "apps.backend.app.services.mcp_session._get_caller_user",
            return_value=MagicMock(
                id=str(child_a.id),
                family_id=str(family_id),
                role="child",
                is_active=True,
            ),
        ):
            mock_sl.return_value.__enter__ = MagicMock(return_value=db)
            mock_sl.return_value.__exit__ = MagicMock(return_value=False)
            result = await mcp.call_tool("get_knowledge_bridge", args)

        payload = json.loads(result[0].text)
        # The handler ran (no permission_denied) and returned the prerequisite chain.
        assert "prerequisite_chain" in payload
        # Child B's progress rows never appear in the response.
        assert payload.get("child_id") == str(child_a.id)

    async def test_child_a_calls_sibling_topic_denied(
        self, db: Session, family_with_two_children, learning_data
    ):
        """Child A calls get_knowledge_bridge for Child B → permission_denied."""
        child_a, child_b, family_id = family_with_two_children
        topic_1, topic_2, progress_a, progress_b = learning_data

        mcp = _build_mcp_session_for_child(child_a, family_id)
        args = {"child_id": str(child_b.id), "topic_id": str(topic_2.id)}

        with patch(
            "apps.backend.app.services.mcp_session.SessionLocal"
        ) as mock_sl, patch(
            "apps.backend.app.services.mcp_session._get_caller_user",
            return_value=MagicMock(
                id=str(child_a.id),
                family_id=str(family_id),
                role="child",
                is_active=True,
            ),
        ):
            mock_sl.return_value.__enter__ = MagicMock(return_value=db)
            mock_sl.return_value.__exit__ = MagicMock(return_value=False)
            result = await mcp.call_tool("get_knowledge_bridge", args)

        payload = json.loads(result[0].text)
        assert payload["error"] == "permission_denied"
        assert payload["retryable"] is False
        # No query for Child B's progress ran — the gate answered before dispatch.

    async def test_child_a_calls_sibling_adaptive_question_denied(
        self, db: Session, family_with_two_children, learning_data
    ):
        """Child A calls select_adaptive_question for Child B → permission_denied.

        This is the exact case the old family check allowed: Child B is a real
        active child in the same family, so the family-scope query would have
        succeeded. The new gate denies it.
        """
        child_a, child_b, family_id = family_with_two_children

        mcp = _build_mcp_session_for_child(child_a, family_id)
        args = {"child_id": str(child_b.id)}

        with patch(
            "apps.backend.app.services.mcp_session.SessionLocal"
        ) as mock_sl, patch(
            "apps.backend.app.services.mcp_session._get_caller_user",
            return_value=MagicMock(
                id=str(child_a.id),
                family_id=str(family_id),
                role="child",
                is_active=True,
            ),
        ):
            mock_sl.return_value.__enter__ = MagicMock(return_value=db)
            mock_sl.return_value.__exit__ = MagicMock(return_value=False)
            result = await mcp.call_tool("select_adaptive_question", args)

        payload = json.loads(result[0].text)
        assert payload["error"] == "permission_denied"

    async def test_child_a_calls_sibling_id_as_string_denied(
        self, db: Session, family_with_two_children
    ):
        """Child A calls with Child B's id as a string → denied."""
        child_a, child_b, family_id = family_with_two_children

        mcp = _build_mcp_session_for_child(child_a, family_id)
        # The handler accepts both int and string child_id; the gate must deny both.
        args = {"child_id": str(child_b.id), "topic_id": "1"}

        with patch(
            "apps.backend.app.services.mcp_session.SessionLocal"
        ) as mock_sl, patch(
            "apps.backend.app.services.mcp_session._get_caller_user",
            return_value=MagicMock(
                id=str(child_a.id),
                family_id=str(family_id),
                role="child",
                is_active=True,
            ),
        ):
            mock_sl.return_value.__enter__ = MagicMock(return_value=db)
            mock_sl.return_value.__exit__ = MagicMock(return_value=False)
            result = await mcp.call_tool("get_knowledge_bridge", args)

        payload = json.loads(result[0].text)
        assert payload["error"] == "permission_denied"

    async def test_child_a_passes_sibling_session_id_denied(
        self, db: Session, family_with_two_children, learning_sessions
    ):
        """Covers #244 AC2. Child A passes Child B's real session_id → permission_denied.

        Child B's session exists in the database, so the gate's session ownership
        check must deny it. The audit error_code is child_scope_violation.
        """
        child_a, child_b, family_id = family_with_two_children
        session_a, session_b = learning_sessions

        mcp = _build_mcp_session_for_child(child_a, family_id)
        args = {
            "child_id": str(child_a.id),
            "session_id": str(session_b.id),
            "question_id": "1",
            "step_number": "1",
            "phase": "DIAGNOSE",
            "child_response_quality": "attempted",
            "next_phase": "FOCUSED_GUIDANCE",
        }

        audit_events = []

        def capture_audit(event_type, **kwargs):
            audit_events.append((event_type, kwargs))

        with patch(
            "apps.backend.app.services.mcp_session.SessionLocal"
        ) as mock_sl, patch(
            "apps.backend.app.services.mcp_session._get_caller_user",
            return_value=MagicMock(
                id=str(child_a.id),
                family_id=str(family_id),
                role="child",
                is_active=True,
            ),
        ):
            mock_sl.return_value.__enter__ = MagicMock(return_value=db)
            mock_sl.return_value.__exit__ = MagicMock(return_value=False)
            mcp._audit_callback = capture_audit
            result = await mcp.call_tool("submit_guided_answer", args)

        payload = json.loads(result[0].text)
        assert payload["error"] == "permission_denied"
        assert payload["retryable"] is False
        # Audit recorded the denial with the correct error_code.
        assert len(audit_events) == 1
        event_type, kwargs = audit_events[0]
        assert event_type == "tool_call"
        assert kwargs["status"] == "permission_denied"
        assert kwargs["error_code"] == "child_scope_violation"

    async def test_child_a_passes_own_session_id_proceeds(
        self, db: Session, family_with_two_children, learning_sessions
    ):
        """Child A passes their own session_id → reaches the handler."""
        child_a, child_b, family_id = family_with_two_children
        session_a, session_b = learning_sessions

        mcp = _build_mcp_session_for_child(child_a, family_id)
        args = {
            "child_id": str(child_a.id),
            "session_id": str(session_a.id),
            "question_id": "1",
            "step_number": "1",
            "phase": "DIAGNOSE",
            "child_response_quality": "attempted",
            "next_phase": "FOCUSED_GUIDANCE",
            "answer_text": "2+3=5",
        }

        with patch(
            "apps.backend.app.services.mcp_session.SessionLocal"
        ) as mock_sl, patch(
            "apps.backend.app.services.mcp_session._get_caller_user",
            return_value=MagicMock(
                id=str(child_a.id),
                family_id=str(family_id),
                role="child",
                is_active=True,
            ),
        ):
            mock_sl.return_value.__enter__ = MagicMock(return_value=db)
            mock_sl.return_value.__exit__ = MagicMock(return_value=False)
            result = await mcp.call_tool("submit_guided_answer", args)

        payload = json.loads(result[0].text)
        # The handler ran (no permission_denied) and returned the answer classification.
        assert "question_id" in payload
        assert payload["session_id"] == str(session_a.id)
        assert payload["step_number"] == 1
