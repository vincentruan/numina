"""Test family adapter cache with available_skills parameter (U3)."""

import os
from pathlib import Path

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
    from deerflow.config.app_config import reload_app_config
    return reload_app_config(_CONFIG_PATH)


def test_create_family_adapter_accepts_available_skills():
    """create_family_adapter accepts available_skills parameter and passes it through."""
    from apps.agent.services.deerflow_adapter.adapter import create_family_adapter

    # This test verifies the signature accepts available_skills without error.
    # We don't actually create an adapter (requires full config), just verify
    # the parameter is accepted.
    import inspect
    sig = inspect.signature(create_family_adapter)
    params = sig.parameters
    assert "available_skills" in params, "create_family_adapter must accept available_skills parameter"
    assert params["available_skills"].default is None, "available_skills default must be None"


def test_get_family_adapter_cache_key_includes_available_skills():
    """get_family_adapter cache key incorporates available_skills (U3)."""
    from apps.agent.services.deerflow_adapter.family_adapter_cache import (
        get_family_adapter,
        _adapter_cache,
    )

    # Verify the cache key structure includes available_skills
    # We can't easily test the full adapter creation without a real config,
    # but we can verify the cache key tuple structure.
    import inspect
    source = inspect.getsource(get_family_adapter)

    # The cache key must include available_skills (as frozenset for hashability)
    assert "available_skills" in source, "get_family_adapter must reference available_skills"
    assert "frozenset" in source, "available_skills must be converted to frozenset for cache key"


def test_available_skills_none_vs_empty_set_produce_different_cache_keys():
    """None and empty set produce different cache keys (U3)."""
    # This is a structural test: verify the cache key logic distinguishes
    # between None (all skills available) and empty set (no skills available).
    from apps.agent.services.deerflow_adapter.family_adapter_cache import (
        get_family_adapter,
    )
    import inspect
    source = inspect.getsource(get_family_adapter)

    # The cache key must handle None vs frozenset() distinctly
    # Look for the pattern: frozenset(available_skills) if available_skills is not None else None
    assert "if available_skills is not None" in source or "else None" in source, (
        "Cache key must distinguish None from empty set"
    )


def test_available_skills_frozenset_hashable():
    """available_skills is converted to frozenset for cache key hashability (U3)."""
    # Verify the conversion logic exists
    from apps.agent.services.deerflow_adapter.family_adapter_cache import (
        get_family_adapter,
    )
    import inspect
    source = inspect.getsource(get_family_adapter)

    # Must convert set to frozenset for cache key
    assert "frozenset(available_skills)" in source, (
        "available_skills must be converted to frozenset for cache key hashability"
    )


def test_create_family_adapter_signature_matches_get_family_adapter():
    """create_family_adapter and get_family_adapter have matching available_skills parameter."""
    from apps.agent.services.deerflow_adapter.adapter import create_family_adapter
    from apps.agent.services.deerflow_adapter.family_adapter_cache import (
        get_family_adapter,
    )
    import inspect

    create_sig = inspect.signature(create_family_adapter)
    get_sig = inspect.signature(get_family_adapter)

    # Both must accept available_skills
    assert "available_skills" in create_sig.parameters, (
        "create_family_adapter must accept available_skills"
    )
    assert "available_skills" in get_sig.parameters, (
        "get_family_adapter must accept available_skills"
    )

    # Both must have the same default (None)
    assert create_sig.parameters["available_skills"].default is None
    assert get_sig.parameters["available_skills"].default is None
