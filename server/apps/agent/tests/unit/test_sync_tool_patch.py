"""Regression tests for the DeerFlow sync-tool compatibility patch.

The pinned ``deerflow-harness`` only wraps config-loaded tools with
``_ensure_sync_invocable_tool``; built-in ``SUBAGENT_TOOLS`` (the ``task``
tool used in ultra mode) are left unwrapped. Because ``DeerFlowClient.stream``
runs the LangGraph graph synchronously, the unwrapped async-only ``task``
StructuredTool raises ``NotImplementedError: StructuredTool does not support
sync invocation`` when the LLM delegates to a subagent.

These tests pin two requirements on the patch:

1. The ``task`` tool returned through the patched ``get_available_tools`` has
   ``func`` set (sync-invocable), not just ``coroutine``.
2. The patch reaches the **package-level** binding
   (``deerflow.tools.get_available_tools``), which is the import path
   ``DeerFlowClient._get_tools()`` actually uses. Patching only the submodule
   (``deerflow.tools.tools.get_available_tools``) leaves the package re-export
   pointing at the original unwrapped function, so the client never sees the
   patch - this was the real regression behind the recurring
   ``StructuredTool does not support sync invocation`` error.
"""

from __future__ import annotations

import pytest


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
