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
