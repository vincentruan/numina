"""Tests for MCP ContextVar propagation assertions.

Verifies that ``assert_mcp_context_complete`` raises ``RuntimeError`` when
critical tenant ContextVars are unset, replacing the silent "all records
empty" failure mode with a fail-fast diagnostic.

Also verifies that ``_family_config_context`` correctly sets and resets
the extensions_config_path ContextVar.
"""

from __future__ import annotations

import pytest

from apps.agent.services.runtime.sandbox_provider import (
    _family_id_context,
    assert_mcp_context_complete,
    get_family_sandbox_context,
    reset_family_sandbox_context,
    set_family_sandbox_context,
)


@pytest.fixture(autouse=True)
def _clean_context():
    """Reset all sandbox ContextVars before and after each test."""
    reset_family_sandbox_context()
    yield
    reset_family_sandbox_context()


class TestAssertMcpContextComplete:
    """assert_mcp_context_complete() — fail-fast tenant context validation."""

    def test_raises_when_family_id_is_none(self):
        """Missing family_id → RuntimeError with diagnostic."""
        assert _family_id_context.get() is None
        with pytest.raises(RuntimeError, match="sandbox_family_id"):
            assert_mcp_context_complete("test-stage")

    def test_error_message_includes_stage(self):
        """Error message includes the stage parameter for diagnostics."""
        with pytest.raises(RuntimeError, match="mcp-tool-load"):
            assert_mcp_context_complete("mcp-tool-load")

    def test_passes_when_family_id_is_set(self):
        """family_id set → no exception."""
        set_family_sandbox_context("family-42", caller_user_id="user-1")
        assert_mcp_context_complete("executor-thread entry")  # no raise

    def test_passes_with_family_id_only(self):
        """family_id set without caller_user_id → still passes.

        caller_user_id can legitimately be None for internal/system dispatch.
        """
        set_family_sandbox_context("family-42")
        assert_mcp_context_complete("executor-thread entry")  # no raise


class TestFamilySandboxContext:
    """set/reset/get family sandbox context lifecycle."""

    def test_set_and_get(self):
        set_family_sandbox_context("family-abc", caller_user_id="user-xyz")
        assert get_family_sandbox_context() == "family-abc"

    def test_reset_clears_family_id(self):
        set_family_sandbox_context("family-abc")
        reset_family_sandbox_context()
        assert get_family_sandbox_context() is None

    def test_context_isolation_via_copy_context(self):
        """ContextVar set in one context does not leak to a sibling.

        This mirrors the F2 root cause: copy_context() must propagate
        the family_id from the async caller into the executor thread.
        """
        import contextvars

        set_family_sandbox_context("family-A")

        def _check_in_other_context() -> str | None:
            return get_family_sandbox_context()

        # A fresh copy of the current context should see the value
        ctx = contextvars.copy_context()
        assert ctx.run(_check_in_other_context) == "family-A"

        # But a new, empty context should NOT see it
        # (simulating a thread that never received copy_context)
        fresh_ctx = contextvars.Context()
        assert fresh_ctx.run(get_family_sandbox_context) is None


class TestRunContextFacade:
    """RunContext.from_contextvars() — read-only snapshot over 5 ContextVars."""

    def test_reads_all_five_contextvars(self):
        """All 5 ContextVars are read into the frozen snapshot."""
        from apps.agent.services.deerflow_adapter.active_skill_context import (
            set_active_skill,
        )
        from apps.agent.services.deerflow_adapter.original_user_content_context import (
            set_original_user_content,
        )
        from apps.agent.services.runtime.run_context import RunContext

        set_family_sandbox_context("family-100", caller_user_id="user-200")
        skill_token = set_active_skill("chat")
        content_token = set_original_user_content("hello world")
        try:
            ctx = RunContext.from_contextvars()
            assert ctx.family_id == "family-100"
            assert ctx.caller_user_id == "user-200"
            assert ctx.active_skill_name == "chat"
            assert ctx.original_user_content == "hello world"
            # extensions_config_path not set → None
            assert ctx.extensions_config_path is None
        finally:
            from apps.agent.services.deerflow_adapter.active_skill_context import (
                reset_active_skill,
            )
            from apps.agent.services.deerflow_adapter.original_user_content_context import (
                reset_original_user_content,
            )

            reset_active_skill(skill_token)
            reset_original_user_content(content_token)

    def test_frozen_dataclass(self):
        """RunContext is immutable after creation."""
        from apps.agent.services.runtime.run_context import RunContext

        ctx = RunContext(
            family_id="f1",
            caller_user_id=None,
            extensions_config_path=None,
            active_skill_name=None,
            original_user_content=None,
        )
        with pytest.raises(AttributeError):
            ctx.family_id = "f2"  # type: ignore[misc]

    def test_has_mandatory_context(self):
        """Only family_id is mandatory for has_mandatory_context."""
        from apps.agent.services.runtime.run_context import RunContext

        # family_id set → mandatory context present
        ctx_with = RunContext(
            family_id="f1",
            caller_user_id=None,
            extensions_config_path=None,
            active_skill_name=None,
            original_user_content=None,
        )
        assert ctx_with.has_mandatory_context is True

        # family_id None → mandatory context missing
        ctx_without = RunContext(
            family_id=None,
            caller_user_id=None,
            extensions_config_path=None,
            active_skill_name=None,
            original_user_content=None,
        )
        assert ctx_without.has_mandatory_context is False

    def test_assert_run_context_complete_uses_facade(self):
        """assert_run_context_complete delegates to RunContext facade."""
        from apps.agent.services.runtime.run_context import (
            RunContext,
            assert_run_context_complete,
        )

        # Empty context → raises
        with pytest.raises(RuntimeError, match="sandbox_family_id"):
            assert_run_context_complete("test-stage")

        # Set family_id → passes
        set_family_sandbox_context("family-99")
        assert_run_context_complete("test-stage")  # no raise

        # Snapshot reflects current state
        ctx = RunContext.from_contextvars()
        assert ctx.family_id == "family-99"


class TestResolveExtensionsConfigPath:
    """_resolve_extensions_config_path() — derive extensions path from config."""

    def test_returns_none_for_no_config_path(self):
        from apps.agent.services.deerflow_adapter.adapter import (
            _resolve_extensions_config_path,
        )

        assert _resolve_extensions_config_path(None) is None

    def test_returns_none_when_file_missing(self, tmp_path):
        from apps.agent.services.deerflow_adapter.adapter import (
            _resolve_extensions_config_path,
        )

        # config.yaml exists but no extensions_config.json alongside it
        config = tmp_path / "config.yaml"
        config.write_text("test: true")
        assert _resolve_extensions_config_path(str(config)) is None

    def test_returns_path_when_file_exists(self, tmp_path):
        from apps.agent.services.deerflow_adapter.adapter import (
            _resolve_extensions_config_path,
        )

        config = tmp_path / "config.yaml"
        config.write_text("test: true")
        extensions = tmp_path / "extensions_config.json"
        extensions.write_text('{"mcpServers": {}}')
        result = _resolve_extensions_config_path(str(config))
        assert result == str(extensions)
