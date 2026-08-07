"""Regression tests for the DeerFlow sync-tool compatibility patch."""

from __future__ import annotations

import pytest

from apps.agent.services.runtime.sandbox_provider import (
    reset_family_sandbox_context,
    set_family_sandbox_context,
)


@pytest.fixture()
def _fresh_patch(monkeypatch):
    """Force ``apply_sync_tool_patches`` to re-run by resetting ``_patched``.

    The patch is idempotent (module-level ``_patched`` guard), so a prior call
    (e.g. from conftest lifespan setup) would short-circuit. We reset the guard
    and re-apply so each test observes a deterministic state.
    """
    from apps.agent.services.deerflow_adapter import sync_tool_patch as mod

    monkeypatch.setattr(mod, "_patched", False)
    mod.apply_sync_tool_patches()
    yield mod
    # Restore idempotent flag so we don't break other tests that rely on it
    monkeypatch.setattr(mod, "_patched", True)


def test_task_tool_becomes_sync_invocable(_fresh_patch):
    """The ``task`` (subagent) tool must have ``func`` set after patching."""
    from deerflow.tools.tools import SUBAGENT_TOOLS

    task_tool = next(t for t in SUBAGENT_TOOLS if t.name == "task")

    # The patched get_available_tools wraps every returned tool through
    # _ensure_sync_invocable_tool, which sets .func from .coroutine.
    # Simulate that wrapping directly on the task tool (it is the same
    # operation the patched function performs on each list element).
    from deerflow.tools.tools import _ensure_sync_invocable_tool

    _ensure_sync_invocable_tool(task_tool)

    assert task_tool.func is not None, (
        "task tool must have a sync `func` wrapper after _ensure_sync_invocable_tool; "
        "without it StructuredTool._run raises NotImplementedError on the sync stream path"
    )
    assert task_tool.coroutine is not None


def test_package_level_binding_is_patched(_fresh_patch):
    """``deerflow.tools.get_available_tools`` (package import path) must be patched.

    ``DeerFlowClient._get_tools()`` does ``from deerflow.tools import
    get_available_tools`` - the *package* binding, not the submodule. The patch
    must rebind both ``deerflow.tools.tools.get_available_tools`` and
    ``deerflow.tools.get_available_tools``; rebinding only the submodule leaves
    the package re-export pointing at the original unwrapped function.
    """
    import deerflow.tools as _tools_pkg
    import deerflow.tools.tools as _tools_mod

    assert _tools_pkg.get_available_tools is _tools_mod.get_available_tools, (
        "package and submodule must share the same patched function object"
    )
    assert _tools_pkg.get_available_tools.__name__ == "_patched_get_available_tools", (
        "DeerFlowClient._get_tools() imports from deerflow.tools package; "
        "that binding must be the patched wrapper, not the original"
    )


def test_submodule_binding_is_patched(_fresh_patch):
    """``deerflow.tools.tools.get_available_tools`` (submodule) must be patched."""
    import deerflow.tools.tools as _tools_mod

    assert _tools_mod.get_available_tools.__name__ == "_patched_get_available_tools"


def test_patch_is_idempotent(_fresh_patch):
    """Calling ``apply_sync_tool_patches`` twice must not re-wrap or error."""
    from deerflow.tools import get_available_tools as before

    _fresh_patch.apply_sync_tool_patches()

    from deerflow.tools import get_available_tools as after

    assert before is after


def test_patched_get_available_tools_includes_ask_clarification(_fresh_patch):
    """The patched get_available_tools must include ask_clarification."""
    from deerflow.config.app_config import AppConfig
    from deerflow.config.sandbox_config import SandboxConfig
    from deerflow.tools import get_available_tools

    # Create minimal config to avoid YAML parsing issues
    config = AppConfig(
        sandbox=SandboxConfig(use='deerflow.sandbox.local:LocalSandboxProvider'),
        tools=[]
    )
    tools = get_available_tools(app_config=config)
    tool_names = [t.name for t in tools]
    assert "ask_clarification" in tool_names


def test_ask_clarification_tool_is_sync_invocable(_fresh_patch):
    """ask_clarification must have func set (sync-invocable) after patching."""
    from deerflow.config.app_config import AppConfig
    from deerflow.config.sandbox_config import SandboxConfig
    from deerflow.tools import get_available_tools

    # Create minimal config to avoid YAML parsing issues
    config = AppConfig(
        sandbox=SandboxConfig(use='deerflow.sandbox.local:LocalSandboxProvider'),
        tools=[]
    )
    tools = get_available_tools(app_config=config)
    ask_tool = next(t for t in tools if t.name == "ask_clarification")
    assert ask_tool.func is not None


def test_exactly_one_ask_clarification_after_patch(_fresh_patch):
    """There must be exactly ONE ask_clarification tool after patching.

    DeerFlow's builtin ask_clarification is a placeholder that returns a static
    string and does NOT call interrupt(). If both the builtin and our custom
    interrupt-based tool coexist, the LLM may select the wrong one and the
    human-in-the-loop feature silently breaks.
    """
    from deerflow.config.app_config import AppConfig
    from deerflow.config.sandbox_config import SandboxConfig
    from deerflow.tools import get_available_tools

    config = AppConfig(
        sandbox=SandboxConfig(use='deerflow.sandbox.local:LocalSandboxProvider'),
        tools=[]
    )
    tools = get_available_tools(app_config=config)
    ask_tools = [t for t in tools if t.name == "ask_clarification"]
    assert len(ask_tools) == 1, (
        f"Expected exactly one ask_clarification tool, found {len(ask_tools)}. "
        "DeerFlow's builtin placeholder must be filtered before adding our interrupt tool."
    )


# ── Active-skill tool filtering (Path C) ──────────────────────────────────────


def test_active_skill_filter_no_active_skill_returns_all(_fresh_patch):
    """With no active skill set, _apply_active_skill_tool_filter returns all tools unchanged."""
    from apps.agent.services.deerflow_adapter.active_skill_context import (
        get_active_skill,
    )
    from apps.agent.services.deerflow_adapter.sync_tool_patch import (
        _apply_active_skill_tool_filter,
    )

    assert get_active_skill() is None  # no active skill in test context

    class _T:
        def __init__(self, name):
            self.name = name

    tools = [_T("web_search"), _T("read_file"), _T("task")]
    assert _apply_active_skill_tool_filter(tools) is tools


def test_active_skill_filter_chat_keeps_only_declared_tools_and_builtins(_fresh_patch, monkeypatch):
    """Active skill = chat → only chat's allowed-tools + framework builtins remain.

    chat/SKILL.md declares allowed-tools (prefixed MCP data tools). The filter
    must keep those plus ALWAYS_AVAILABLE_BUILTIN_TOOL_NAMES (read_file,
    describe_skill, tool_search, review_skill_package) and drop everything else
    (web_search, task, unrelated MCP tools).
    """
    from apps.agent.services.deerflow_adapter import sync_tool_patch as mod
    from apps.agent.services.deerflow_adapter.active_skill_context import (
        reset_active_skill,
        set_active_skill,
    )

    # Point LocalSkillStorage at the real builtin/public/ root so the chat skill
    # (with its allowed-tools declaration) is discoverable. Without this the
    # storage resolves a non-existent path and reports "active skill not found".
    _builtin_root = (
        __import__("pathlib").Path(__file__).resolve().parent.parent.parent
        / "skills" / "builtin"
    )
    from deerflow.skills.storage import local_skill_storage as lss_mod

    _orig_init = lss_mod.LocalSkillStorage.__init__

    def _host_root_init(self, host_path=None, container_path="/mnt/skills", app_config=None):
        _orig_init(self, host_path=str(_builtin_root), container_path=container_path, app_config=app_config)

    monkeypatch.setattr(lss_mod.LocalSkillStorage, "__init__", _host_root_init)

    class _T:
        def __init__(self, name):
            self.name = name

    all_tools = [
        _T("get_family_overview"),
        _T("get_assets"),
        _T("get_liabilities"),
        _T("web_search"),
        _T("web_fetch"),
        _T("read_file"),
        _T("describe_skill"),
        _T("tool_search"),
        _T("task"),
    ]
    # Provide a family_id so the active-skill filter can discover custom skills
    # and resolve the allowlist; without it the filter logs a warning and returns
    # all tools unchanged.
    set_family_sandbox_context("family-test")
    token = set_active_skill("chat")
    try:
        filtered = mod._apply_active_skill_tool_filter(list(all_tools))
    finally:
        reset_active_skill(token)
        reset_family_sandbox_context()
    kept = sorted(t.name for t in filtered)
    # Declared allowed-tools (base names — 1a27f076 unified MCP tool_name_prefix=False)
    assert "get_family_overview" in kept
    assert "get_assets" in kept
    # Framework builtins
    assert "read_file" in kept
    assert "describe_skill" in kept
    # Dropped: web tools and subagent task (not in chat's allowed-tools)
    assert "web_search" not in kept
    assert "web_fetch" not in kept
    assert "task" not in kept


def test_active_skill_filter_chat_search_keeps_web_tools(_fresh_patch, monkeypatch):
    """Active skill = chat-search → web_search/web_fetch kept, MCP data tools dropped."""
    from apps.agent.services.deerflow_adapter import sync_tool_patch as mod
    from apps.agent.services.deerflow_adapter.active_skill_context import (
        reset_active_skill,
        set_active_skill,
    )

    _builtin_root = (
        __import__("pathlib").Path(__file__).resolve().parent.parent.parent
        / "skills" / "builtin"
    )
    from deerflow.skills.storage import local_skill_storage as lss_mod

    _orig_init = lss_mod.LocalSkillStorage.__init__

    def _host_root_init(self, host_path=None, container_path="/mnt/skills", app_config=None):
        _orig_init(self, host_path=str(_builtin_root), container_path=container_path, app_config=app_config)

    monkeypatch.setattr(lss_mod.LocalSkillStorage, "__init__", _host_root_init)

    class _T:
        def __init__(self, name):
            self.name = name

    all_tools = [
        _T("web_search"),
        _T("web_fetch"),
        _T("numina-family-data_get_assets"),
        _T("read_file"),
        _T("task"),
    ]
    set_family_sandbox_context("family-test")
    token = set_active_skill("chat-search")
    try:
        filtered = mod._apply_active_skill_tool_filter(list(all_tools))
    finally:
        reset_active_skill(token)
        reset_family_sandbox_context()
    kept = sorted(t.name for t in filtered)
    assert "web_search" in kept
    assert "web_fetch" in kept
    assert "read_file" in kept
    assert "numina-family-data_get_assets" not in kept
    assert "task" not in kept


def test_active_skill_filter_unknown_skill_returns_all(_fresh_patch):
    """Active skill not in storage → filter skipped (allow-all), not fail-closed."""
    from apps.agent.services.deerflow_adapter import sync_tool_patch as mod
    from apps.agent.services.deerflow_adapter.active_skill_context import (
        reset_active_skill,
        set_active_skill,
    )

    class _T:
        def __init__(self, name):
            self.name = name

    all_tools = [_T("web_search"), _T("read_file")]
    token = set_active_skill("nonexistent-skill-xyz")
    try:
        filtered = mod._apply_active_skill_tool_filter(list(all_tools))
    finally:
        reset_active_skill(token)
    # Unknown skill: returns tools unchanged (graceful, logged as warning)
    assert sorted(t.name for t in filtered) == ["read_file", "web_search"]


def test_resolve_config_path_reads_contextvar_before_env(_fresh_patch, monkeypatch):
    """resolve_config_path consults the per-run ContextVar before the env var.

    Regression: DeerFlow's ``ExtensionsConfig.resolve_config_path`` reads the
    process-global ``DEER_FLOW_EXTENSIONS_CONFIG_PATH`` env var (priority 2),
    which is a single process-wide slot that concurrent family runs overwrite →
    cross-family MCP SSE URL leak. The patch inserts a priority-0 ContextVar
    lookup so each run resolves its own extensions config path. An explicit
    ``config_path`` argument still wins (priority 1, original contract).
    """
    from deerflow.config.extensions_config import ExtensionsConfig

    from apps.agent.services.runtime import sandbox_provider as sp

    # No process-global env var — the ContextVar must be the source of truth.
    monkeypatch.delenv("DEER_FLOW_EXTENSIONS_CONFIG_PATH", raising=False)

    # ContextVar unset → resolve_config_path returns None (no leak, no env).
    assert ExtensionsConfig.resolve_config_path() is None

    # ContextVar set → returns that path (verified to exist by the original
    # resolver, so use a real temp file).
    import tempfile
    from pathlib import Path

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        f.write(b"{}")
        ctx_path = f.name
    try:
        tok = sp._extensions_config_path_context.set(ctx_path)
        try:
            resolved = ExtensionsConfig.resolve_config_path()
            assert resolved == Path(ctx_path)
        finally:
            sp._extensions_config_path_context.reset(tok)

        # After reset, ContextVar is unset again → back to None (no stale leak).
        assert ExtensionsConfig.resolve_config_path() is None

        # Explicit config_path arg still takes precedence over the ContextVar.
        tok2 = sp._extensions_config_path_context.set(ctx_path)
        try:
            with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f2:
                f2.write(b"{}")
                explicit_path = f2.name
            resolved_explicit = ExtensionsConfig.resolve_config_path(explicit_path)
            assert resolved_explicit == Path(explicit_path)
        finally:
            sp._extensions_config_path_context.reset(tok2)
    finally:
        Path(ctx_path).unlink(missing_ok=True)


def test_resolve_config_path_isolated_across_contexts(_fresh_patch, monkeypatch):
    """ContextVar-set path does not leak into another run after reset.

    Mirrors the multi-family leak scenario: family-A's run sets its path, then
    family-B's run must NOT see family-A's path (which embeds family-A's id in
    the MCP SSE URL). Process-global env var leaks here because it is a single
    slot; ContextVar is reset per run.
    """
    import tempfile
    from pathlib import Path

    from deerflow.config.extensions_config import ExtensionsConfig

    from apps.agent.services.runtime import sandbox_provider as sp

    monkeypatch.delenv("DEER_FLOW_EXTENSIONS_CONFIG_PATH", raising=False)

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as fa:
        fa.write(b"{}")
        path_a = fa.name

    try:
        # Run A: family-A path set, then reset
        tok_a = sp._extensions_config_path_context.set(path_a)
        assert ExtensionsConfig.resolve_config_path() == Path(path_a)
        sp._extensions_config_path_context.reset(tok_a)

        # Run B: NO path set — must NOT see family-A's stale path
        assert ExtensionsConfig.resolve_config_path() is None
    finally:
        Path(path_a).unlink(missing_ok=True)
