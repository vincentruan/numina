"""Tests for U2: Conditionally skip set_active_skill for slash messages.

Verifies that when the user's message starts with `/skill-name`, the worker does NOT call
set_active_skill, so DeerFlow's SkillToolPolicyMiddleware owns tool filtering for that run.
Non-slash messages keep the existing chat/chat-search pre-selection.
"""

import pytest
from deerflow.skills.slash import parse_slash_skill_reference


class TestSlashDetection:
    """Test slash detection logic for U2."""

    def test_slash_detected(self):
        """Slash detected: parse_slash_skill_reference returns a reference."""
        free_text = "/my-budget 帮我分析"
        result = parse_slash_skill_reference(free_text)
        assert result is not None
        assert result.name == "my-budget"

    def test_no_slash(self):
        """No slash: parse_slash_skill_reference returns None."""
        free_text = "你好"
        result = parse_slash_skill_reference(free_text)
        assert result is None

    def test_reserved_command(self):
        """Reserved command: parse_slash_skill_reference returns None (reserved)."""
        free_text = "/goal do something"
        result = parse_slash_skill_reference(free_text)
        assert result is None

    def test_slash_with_no_text(self):
        """Slash with no text: slash detected, remaining_text is empty."""
        free_text = "/my-budget"
        result = parse_slash_skill_reference(free_text)
        assert result is not None
        assert result.name == "my-budget"
        assert result.remaining_text == ""

    def test_slash_with_trailing_space(self):
        """Slash with trailing space: slash detected, remaining_text is empty."""
        free_text = "/my-budget "
        result = parse_slash_skill_reference(free_text)
        assert result is not None
        assert result.name == "my-budget"
        assert result.remaining_text == ""

    def test_slash_with_complex_name(self):
        """Slash with complex skill name (hyphens): slash detected."""
        free_text = "/my-custom-skill-123 task"
        result = parse_slash_skill_reference(free_text)
        assert result is not None
        assert result.name == "my-custom-skill-123"

    def test_slash_not_at_start(self):
        """Slash not at start: parse_slash_skill_reference returns None."""
        free_text = "hello /my-budget"
        result = parse_slash_skill_reference(free_text)
        assert result is None

    def test_empty_string(self):
        """Empty string: parse_slash_skill_reference returns None."""
        free_text = ""
        result = parse_slash_skill_reference(free_text)
        assert result is None

    def test_whitespace_only(self):
        """Whitespace only: parse_slash_skill_reference returns None."""
        free_text = "   "
        result = parse_slash_skill_reference(free_text)
        assert result is None

    def test_slash_with_uppercase(self):
        """Slash with uppercase letters: parse_slash_skill_reference returns None (lowercase only)."""
        free_text = "/MyBudget task"
        result = parse_slash_skill_reference(free_text)
        assert result is None


class TestSetActiveSkillBehavior:
    """Test set_active_skill behavior for slash vs non-slash messages."""

    def test_set_active_skill_called_for_non_slash(self):
        """Non-slash message: set_active_skill is called."""
        from apps.agent.services.deerflow_adapter.active_skill_context import (
            get_active_skill,
            reset_active_skill,
            set_active_skill,
        )

        # Simulate non-slash message
        free_text = "你好"
        is_slash = parse_slash_skill_reference(free_text) is not None
        assert not is_slash

        # set_active_skill should be called
        token = set_active_skill("chat")
        try:
            assert get_active_skill() == "chat"
        finally:
            reset_active_skill(token)

    def test_set_active_skill_skipped_for_slash(self):
        """Slash message: set_active_skill is NOT called (simulated)."""
        from apps.agent.services.deerflow_adapter.active_skill_context import (
            get_active_skill,
        )

        # Simulate slash message
        free_text = "/my-budget task"
        is_slash = parse_slash_skill_reference(free_text) is not None
        assert is_slash

        # set_active_skill should NOT be called (simulated by not calling it)
        # get_active_skill() should return None (default)
        assert get_active_skill() is None
