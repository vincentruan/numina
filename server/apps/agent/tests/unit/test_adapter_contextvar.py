"""Test that DeerFlow ContextVar config injection enables concurrent family streaming."""

import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from deerflow.config.app_config import (
    get_app_config,
    pop_current_app_config,
    push_current_app_config,
    reload_app_config,
)

# Path to a real config so reload_app_config() can parse a file in tests.
_CONFIG_PATH = str(
    Path(__file__).parents[2] / "deerflow_config" / "base" / "config.yaml"
)


def _load_config():
    """Load app config from the base deerflow config, substituting required env placeholders."""
    # reload_app_config needs AI_API_KEY / AI_MODEL env vars if config uses them;
    # set minimal stubs so parsing doesn't fail.
    os.environ.setdefault("AI_API_KEY", "test-key")
    os.environ.setdefault("AI_MODEL", "claude-3-haiku-20240307")
    return reload_app_config(_CONFIG_PATH)


def test_push_pop_current_app_config():
    """push_current_app_config sets a per-context override; pop restores it."""
    override = _load_config()
    push_current_app_config(override)
    assert get_app_config() is override

    pop_current_app_config()
    # After pop the ContextVar override is gone; push a second distinct config
    # to confirm the stack is independent of the first push.
    override2 = _load_config()
    push_current_app_config(override2)
    assert get_app_config() is override2
    pop_current_app_config()


def test_contextvar_isolation_in_thread_pool():
    """ContextVar push/pop inside ThreadPoolExecutor threads is correctly isolated."""
    results = []

    def worker(family_id: str):
        config = _load_config()
        push_current_app_config(config)
        try:
            read_config = get_app_config()
            results.append((family_id, read_config is config))
        finally:
            pop_current_app_config()
        return True

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(worker, f"family-{i}") for i in range(4)]
        for f in futures:
            assert f.result() is True

    # All 4 workers should have seen their own pushed config
    assert len(results) == 4
    assert all(saw_own for _, saw_own in results)


def test_run_in_executor_with_context_propagates_family_sandbox_contextvar():
    """``_run_in_executor_with_context`` propagates ``sandbox_family_id`` into the
    pool thread (F2 root cause: ``loop.run_in_executor`` does not).

    ``NuminaLocalSandboxProvider._build_thread_path_mappings`` reads the
    ``sandbox_family_id`` ContextVar to scope sandbox paths. Without
    propagation the provider sees ``None`` and returns empty path mappings,
    so ``write_file`` silently never lands on disk. This test pins the
    propagation contract: a ContextVar set in the async caller is visible
    inside the function submitted via ``_run_in_executor_with_context``.
    """
    import asyncio

    from apps.agent.services.deerflow_adapter.adapter import (
        _get_executor,
        _run_in_executor_with_context,
    )
    from apps.agent.services.runtime.sandbox_provider import (
        get_family_sandbox_context,
        set_family_sandbox_context,
    )

    # A distinct sentinel that proves the *caller's* ContextVar (not a default)
    # crossed the thread boundary.
    sentinel_family = "family-f2-propagation-test-321"

    async def caller() -> str | None:
        set_family_sandbox_context(sentinel_family)
        assert get_family_sandbox_context() == sentinel_family  # set in this task

        loop = asyncio.get_running_loop()
        # The submitted function runs in a pool thread where, without
        # contextvar propagation, get_family_sandbox_context() would be None.
        future = _run_in_executor_with_context(
            loop, _get_executor(), get_family_sandbox_context
        )
        return await future

    observed = asyncio.run(caller())
    assert observed == sentinel_family, (
        f"family_id ContextVar did not propagate into executor thread; "
        f"expected {sentinel_family!r}, got {observed!r} (F2 regression)"
    )


def test_acquire_keys_sandbox_by_family_id():
    """``NuminaLocalSandboxProvider.acquire`` incorporates family_id into the
    LRU cache key and sandbox ID (P2 #13 tenant-isolation fix).

    Without the ``acquire`` override, the harness resolves
    ``effective_user_id="default"`` (Numina never sets DeerFlow's
    ``_current_user`` ContextVar), so the cache key collapses to
    ``("default", thread_id)`` and two families sharing a thread_id would hit
    the same cached LocalSandbox — a cross-tenant read of mapped paths.

    The override passes ``family_id`` as the effective ``user_id`` when no
    explicit ``user_id`` is supplied and a family context is set, so the cache
    key and sandbox ID become family-scoped
    (``("default", thread_id)`` → ``(family_id, thread_id)`` /
    ``f"local:{family_id}:{thread_id}"``).
    """
    from apps.agent.services.runtime.sandbox_provider import (
        get_sandbox_provider,
        set_family_sandbox_context,
    )

    provider = get_sandbox_provider()
    # Isolate from any cache state left by other tests.
    provider.reset()

    thread_id = "thread-13-isolation-test"
    try:
        set_family_sandbox_context("family-A")
        sandbox_id_a = provider.acquire(thread_id)
        assert sandbox_id_a.startswith("local:family-A:"), sandbox_id_a

        set_family_sandbox_context("family-B")
        sandbox_id_b = provider.acquire(thread_id)
        assert sandbox_id_b.startswith("local:family-B:"), sandbox_id_b

        # Distinct families with the same thread_id MUST get distinct sandbox
        # IDs (and therefore distinct cache entries / LocalSandbox instances).
        assert sandbox_id_a != sandbox_id_b, (
            "family_id did not enter the sandbox ID; both families collapsed to "
            f"{sandbox_id_a!r} (P2 #13 tenant-isolation regression)"
        )

        # Same family + thread_id must be stable (cache hit returns same ID).
        set_family_sandbox_context("family-A")
        assert provider.acquire(thread_id) == sandbox_id_a
    finally:
        provider.reset()



def test_run_in_executor_with_context_propagates_active_skill_contextvar():
    """Same propagation contract for the ``numina_active_skill_name`` ContextVar.

    Runtime tool filtering (``filter_tools_by_skill_allowed_tools``) reads this
    ContextVar; if it is lost across the executor boundary the LLM is exposed
    to the full tool set instead of the skill's declared allowed-tools.
    """
    import asyncio

    from apps.agent.services.deerflow_adapter.active_skill_context import (
        get_active_skill,
        set_active_skill,
    )
    from apps.agent.services.deerflow_adapter.adapter import (
        _get_executor,
        _run_in_executor_with_context,
    )

    skill = "asset-report"

    async def caller() -> str | None:
        token = set_active_skill(skill)
        try:
            loop = asyncio.get_running_loop()
            future = _run_in_executor_with_context(
                loop, _get_executor(), get_active_skill
            )
            return await future
        finally:
            from apps.agent.services.deerflow_adapter.active_skill_context import (
                reset_active_skill,
            )
            reset_active_skill(token)

    assert asyncio.run(caller()) == skill
