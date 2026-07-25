"""Tests for U1: ORIGINAL_USER_CONTENT_KEY injection via ContextVar.

Verifies that the adapter sets the raw user text in a ContextVar, and the
HumanMessage patch merges it into additional_kwargs under ORIGINAL_USER_CONTENT_KEY,
so DeerFlow's SkillActivationMiddleware can parse slash commands through JSON wrapping.
"""

import pytest
from langchain_core.messages import HumanMessage

from apps.agent.services.deerflow_adapter.original_user_content_context import (
    get_original_user_content,
    reset_original_user_content,
    set_original_user_content,
)


@pytest.fixture(autouse=True)
def _apply_patches():
    """Apply sync_tool_patch before tests (idempotent)."""
    from apps.agent.services.deerflow_adapter.sync_tool_patch import apply_sync_tool_patches

    apply_sync_tool_patches()
    yield


class TestOriginalUserContentContext:
    """Test the ContextVar for original user content."""

    def test_set_and_get(self):
        """set_original_user_content sets the value, get_original_user_content reads it."""
        token = set_original_user_content("/my-budget task")
        try:
            assert get_original_user_content() == "/my-budget task"
        finally:
            reset_original_user_content(token)

    def test_reset_restores_previous_value(self):
        """reset_original_user_content restores the previous value."""
        token1 = set_original_user_content("first")
        try:
            assert get_original_user_content() == "first"
            token2 = set_original_user_content("second")
            try:
                assert get_original_user_content() == "second"
            finally:
                reset_original_user_content(token2)
            assert get_original_user_content() == "first"
        finally:
            reset_original_user_content(token1)

    def test_default_is_none(self):
        """Default value is None (no original content)."""
        # In a fresh context, the value should be None
        import contextvars

        ctx = contextvars.copy_context()
        assert ctx.run(get_original_user_content) is None


class TestHumanMessagePatch:
    """Test that HumanMessage.__init__ injects ORIGINAL_USER_CONTENT_KEY."""

    def test_happy_path_injects_key(self):
        """When ContextVar is set, HumanMessage gets ORIGINAL_USER_CONTENT_KEY in additional_kwargs."""
        from deerflow.utils.messages import ORIGINAL_USER_CONTENT_KEY

        token = set_original_user_content("/my-budget task")
        try:
            msg = HumanMessage(content='{"family_id": "123", "free_text": "/my-budget task"}')
            assert ORIGINAL_USER_CONTENT_KEY in msg.additional_kwargs
            assert msg.additional_kwargs[ORIGINAL_USER_CONTENT_KEY] == "/my-budget task"
        finally:
            reset_original_user_content(token)

    def test_no_original_content_key_absent(self):
        """When ContextVar is None, ORIGINAL_USER_CONTENT_KEY is not injected."""
        from deerflow.utils.messages import ORIGINAL_USER_CONTENT_KEY

        # Ensure ContextVar is None (default)
        msg = HumanMessage(content='{"family_id": "123", "free_text": "hello"}')
        assert ORIGINAL_USER_CONTENT_KEY not in msg.additional_kwargs

    def test_does_not_overwrite_existing_key(self):
        """If additional_kwargs already has ORIGINAL_USER_CONTENT_KEY, don't overwrite."""
        from deerflow.utils.messages import ORIGINAL_USER_CONTENT_KEY

        token = set_original_user_content("from-context")
        try:
            msg = HumanMessage(
                content="content",
                additional_kwargs={ORIGINAL_USER_CONTENT_KEY: "from-caller"},
            )
            # Caller-provided value should win
            assert msg.additional_kwargs[ORIGINAL_USER_CONTENT_KEY] == "from-caller"
        finally:
            reset_original_user_content(token)

    def test_preserves_other_additional_kwargs(self):
        """Injection preserves other keys in additional_kwargs."""
        from deerflow.utils.messages import ORIGINAL_USER_CONTENT_KEY

        token = set_original_user_content("/my-budget task")
        try:
            msg = HumanMessage(
                content="content",
                additional_kwargs={"run_id": "abc123", "other_key": "value"},
            )
            assert msg.additional_kwargs["run_id"] == "abc123"
            assert msg.additional_kwargs["other_key"] == "value"
            assert msg.additional_kwargs[ORIGINAL_USER_CONTENT_KEY] == "/my-budget task"
        finally:
            reset_original_user_content(token)

    def test_multiline_with_leading_whitespace(self):
        """Multi-line text with leading whitespace is preserved verbatim."""
        from deerflow.utils.messages import ORIGINAL_USER_CONTENT_KEY

        multiline_text = "  /my-budget\n  analyze my expenses\n  "
        token = set_original_user_content(multiline_text)
        try:
            msg = HumanMessage(content="content")
            assert msg.additional_kwargs[ORIGINAL_USER_CONTENT_KEY] == multiline_text
        finally:
            reset_original_user_content(token)


class TestRoundTripWithDeerFlow:
    """Test that DeerFlow's get_original_user_content_text reads the injected key."""

    def test_get_original_user_content_text_reads_injected_key(self):
        """get_original_user_content_text returns the injected ORIGINAL_USER_CONTENT_KEY."""
        from deerflow.utils.messages import (
            ORIGINAL_USER_CONTENT_KEY,
            get_original_user_content_text,
        )

        token = set_original_user_content("/my-budget task")
        try:
            msg = HumanMessage(content='{"family_id": "123", "free_text": "/my-budget task"}')
            # DeerFlow's function should read from additional_kwargs
            result = get_original_user_content_text(msg.content, msg.additional_kwargs)
            assert result == "/my-budget task"
        finally:
            reset_original_user_content(token)

    def test_fallback_to_content_when_key_absent(self):
        """When ORIGINAL_USER_CONTENT_KEY is absent, fall back to content text."""
        from deerflow.utils.messages import get_original_user_content_text

        msg = HumanMessage(content="plain text")
        result = get_original_user_content_text(msg.content, msg.additional_kwargs)
        assert result == "plain text"
