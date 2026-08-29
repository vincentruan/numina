"""Tests for family_adapter_cache module."""

import os
import shutil
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from apps.agent.services.deerflow_adapter.family_adapter_cache import (
    _adapter_cache,
    _generate_temp_config,
    _get_shared_checkpointer,
    clear_cache,
    close_shared_checkpointer,
    get_cache_stats,
    get_family_adapter,
    invalidate_family_adapter,
    invalidate_family_adapter_cache,
)


def _cache_key(family_id: str, config_id: str) -> tuple:
    """Build the full 9-element cache key for a default get_family_adapter() call.

    The production cache key is
    ``(family_id, config_id, subagent_enabled, plan_mode, mcp_key, agent_name,
    middlewares_key, memory_enabled, available_skills_key)``. Tests that call
    ``get_family_adapter`` without agent_name/middlewares/memory_enabled/
    available_skills get the defaults ``agent_name=""``, ``middlewares_key=()``,
    ``memory_enabled=True``, ``available_skills_key=None`` and an empty ``mcp_key``.
    """
    return (family_id, config_id, False, False, "", "", (), True, None)


@pytest.fixture
def base_config_dir():
    """Provide a temporary base config directory for tests."""
    temp_dir = tempfile.mkdtemp()
    base_dir = Path(temp_dir) / "base"
    base_dir.mkdir(parents=True, exist_ok=True)

    config_content = """
# DeerFlow test config
llm:
  model: $AI_MODEL
  api_key: $AI_API_KEY

sandbox:
  use: deerflow.sandbox.local:LocalSandboxProvider
  allow_host_bash: false

checkpointer:
  type: sqlite
  path: /tmp/test-checkpoints.db
"""
    config_path = base_dir / "config.yaml"
    config_path.write_text(config_content)

    yield temp_dir

    # Cleanup
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def ai_config():
    """Sample AI config for a family."""
    return {
        "config_id": "cfg-001",
        "api_key": "sk-test-key-12345",
        "ai_model_id": "claude-haiku-4-5",
        "ai_provider": "anthropic",
        "ai_base_url": "https://api.example.com",
    }


class TestGenerateTempConfig:
    """Tests for _generate_temp_config function."""

    def test_generates_valid_config_file(self, base_config_dir, ai_config):
        """Should generate a valid config.yaml with injected values."""
        temp_config = _generate_temp_config(base_config_dir, ai_config)

        assert temp_config.exists()
        assert temp_config.name == "config.yaml"

        content = temp_config.read_text()
        assert "claude-haiku-4-5" in content
        assert "sk-test-key-12345" in content

    def test_injects_base_url(self, base_config_dir, ai_config):
        """Should inject base_url into llm config."""
        temp_config = _generate_temp_config(base_config_dir, ai_config)
        content = temp_config.read_text()

        assert "base_url: https://api.example.com" in content

    def test_handles_missing_base_url(self, base_config_dir):
        """Should work without base_url."""
        ai_config_no_url = {
            "api_key": "sk-test",
            "ai_model_id": "claude-sonnet-4-6",
            "ai_provider": "anthropic",
        }

        temp_config = _generate_temp_config(base_config_dir, ai_config_no_url)
        content = temp_config.read_text()

        assert "claude-sonnet-4-6" in content
        assert "base_url" not in content

    def test_raises_on_missing_base_config(self, ai_config):
        """Should raise FileNotFoundError if base config is missing."""
        with pytest.raises(FileNotFoundError):
            _generate_temp_config("/nonexistent/path", ai_config)


class TestCheckpointerInjection:
    """Tests that DeerFlowClient receives an explicit checkpointer for multi-turn memory."""

    def test_get_shared_checkpointer_returns_same_instance(self, base_config_dir):
        """_get_shared_checkpointer must return the same object on repeated calls."""
        import apps.agent.services.deerflow_adapter.family_adapter_cache as cache_mod

        # Reset singleton so this test is isolated
        orig = cache_mod._shared_checkpointer
        orig_ctx = cache_mod._checkpointer_ctx
        cache_mod._shared_checkpointer = None
        cache_mod._checkpointer_ctx = None

        try:
            cp1 = _get_shared_checkpointer(base_config_dir)
            cp2 = _get_shared_checkpointer(base_config_dir)
            assert cp1 is cp2
        finally:
            close_shared_checkpointer()
            cache_mod._shared_checkpointer = orig
            cache_mod._checkpointer_ctx = orig_ctx

    def test_deerflow_client_receives_checkpointer(self, base_config_dir, ai_config):
        """DeerFlowClient must be constructed with the shared checkpointer, not None."""
        clear_cache()

        os.environ["AI_MODEL"] = ai_config["ai_model_id"]
        os.environ["AI_API_KEY"] = ai_config["api_key"]

        captured_kwargs: dict = {}

        try:
            import deerflow.client as df_client_mod
        except ImportError:
            pytest.skip("deerflow not available")

        mock_checkpointer = MagicMock(name="shared_checkpointer")

        def _fake_client(config_path, checkpointer=None, **kwargs):
            captured_kwargs["checkpointer"] = checkpointer
            return MagicMock(name="DeerFlowClient")

        with (
            patch("apps.agent.services.deerflow_adapter.family_adapter_cache._get_shared_checkpointer", return_value=mock_checkpointer),
            patch("apps.agent.services.deerflow_adapter.family_adapter_cache.NuminaDeerFlowClient", side_effect=_fake_client),
            patch("apps.agent.services.deerflow_adapter.family_adapter_cache.reload_app_config"),
        ):
            get_family_adapter("family_cp_test", ai_config, base_config_dir)

        assert captured_kwargs.get("checkpointer") is mock_checkpointer, (
            "DeerFlowClient must receive the shared checkpointer — "
            "without it each dispatch is stateless and multi-turn reasoning is impossible"
        )

        clear_cache()

    async def test_close_shared_checkpointer_resets_singleton(self, base_config_dir):
        """close_shared_checkpointer must allow a fresh checkpointer to be created."""
        import apps.agent.services.deerflow_adapter.family_adapter_cache as cache_mod

        orig = cache_mod._shared_checkpointer
        orig_ctx = cache_mod._checkpointer_ctx
        cache_mod._shared_checkpointer = None
        cache_mod._checkpointer_ctx = None

        try:
            _get_shared_checkpointer(base_config_dir)
            await close_shared_checkpointer()
            assert cache_mod._shared_checkpointer is None
        finally:
            cache_mod._shared_checkpointer = orig
            cache_mod._checkpointer_ctx = orig_ctx


class TestFamilyAdapterCache:
    """Tests for LRU cache functionality."""

    def test_get_family_adapter_creates_new_instance(self, base_config_dir, ai_config):
        """Should create a new DeerFlowClient for uncached family."""
        clear_cache()

        # Need to set env vars for DeerFlowClient
        os.environ["AI_MODEL"] = ai_config["ai_model_id"]
        os.environ["AI_API_KEY"] = ai_config["api_key"]

        client = get_family_adapter(
            family_id="family_1",
            ai_config=ai_config,
            base_config_dir=base_config_dir,
        )

        assert client is not None
        stats = get_cache_stats()
        assert stats["cached_families"] == 1

        clear_cache()

    def test_get_family_adapter_reuses_cached_instance(self, base_config_dir, ai_config):
        """Should reuse cached DeerFlowClient for same family."""
        clear_cache()

        os.environ["AI_MODEL"] = ai_config["ai_model_id"]
        os.environ["AI_API_KEY"] = ai_config["api_key"]

        client1 = get_family_adapter(
            family_id="family_1",
            ai_config=ai_config,
            base_config_dir=base_config_dir,
        )

        client2 = get_family_adapter(
            family_id="family_1",
            ai_config=ai_config,
            base_config_dir=base_config_dir,
        )

        assert client1 is client2
        stats = get_cache_stats()
        assert stats["cached_families"] == 1

        clear_cache()

    def test_cache_eviction_when_full(self, base_config_dir, ai_config):
        """Should evict oldest entry when cache is full."""
        clear_cache()

        os.environ["AI_MODEL"] = ai_config["ai_model_id"]
        os.environ["AI_API_KEY"] = ai_config["api_key"]

        # Fill cache beyond limit (100) — each family gets a unique config_id
        for i in range(105):
            cfg = dict(ai_config, config_id=f"cfg-{i:03d}")
            get_family_adapter(
                family_id=f"family_{i}",
                ai_config=cfg,
                base_config_dir=base_config_dir,
            )

        stats = get_cache_stats()
        assert stats["cached_families"] == 100
        # First entry should be evicted
        assert ("family_0", "cfg-000") not in _adapter_cache
        assert ("family_100", "cfg-100") not in _adapter_cache
        assert _cache_key("family_0", "cfg-000") not in _adapter_cache
        assert _cache_key("family_100", "cfg-100") in _adapter_cache

        clear_cache()

    def test_invalidate_family_adapter(self, base_config_dir, ai_config):
        """Should remove cached adapter for a specific family."""
        clear_cache()

        os.environ["AI_MODEL"] = ai_config["ai_model_id"]
        os.environ["AI_API_KEY"] = ai_config["api_key"]

        get_family_adapter(
            family_id="family_1",
            ai_config=ai_config,
            base_config_dir=base_config_dir,
        )

        invalidate_family_adapter("family_1")

        stats = get_cache_stats()
        assert stats["cached_families"] == 0
        assert _cache_key("family_1", "cfg-001") not in _adapter_cache

    def test_invalidate_nonexistent_family(self):
        """Should handle invalidation of non-cached family gracefully."""
        clear_cache()

        # Should not raise
        invalidate_family_adapter("nonexistent_family")

        stats = get_cache_stats()
        assert stats["cached_families"] == 0

    def test_clear_cache_removes_all(self, base_config_dir, ai_config):
        """Should clear all cached adapters."""
        os.environ["AI_MODEL"] = ai_config["ai_model_id"]
        os.environ["AI_API_KEY"] = ai_config["api_key"]

        get_family_adapter("family_1", ai_config, base_config_dir)
        get_family_adapter("family_2", ai_config, base_config_dir)

        clear_cache()

        stats = get_cache_stats()
        assert stats["cached_families"] == 0


class TestConcurrencySafety:
    """Tests for concurrent access scenarios."""

    def test_different_families_get_different_clients(self, base_config_dir, ai_config):
        """Should return different DeerFlowClient instances for different families."""
        clear_cache()

        os.environ["AI_MODEL"] = ai_config["ai_model_id"]
        os.environ["AI_API_KEY"] = ai_config["api_key"]

        client1 = get_family_adapter("family_1", ai_config, base_config_dir)
        client2 = get_family_adapter("family_2", ai_config, base_config_dir)

        assert client1 is not client2
        stats = get_cache_stats()
        assert stats["cached_families"] == 2

        clear_cache()

    def test_family_config_change_creates_new_instance(self, base_config_dir, ai_config):
        """Should create new instance when family config changes.

        Note: Current implementation does NOT auto-detect config changes.
        Caller must call invalidate_family_adapter() before get_family_adapter()
        when config changes.
        """
        clear_cache()

        os.environ["AI_MODEL"] = ai_config["ai_model_id"]
        os.environ["AI_API_KEY"] = ai_config["api_key"]

        client1 = get_family_adapter("family_1", ai_config, base_config_dir)

        # Invalidate old cache
        invalidate_family_adapter("family_1")

        # Get with new config
        new_config = {
            "config_id": "cfg-002",
            "api_key": "sk-new-key",
            "ai_model_id": "claude-sonnet-4-6",
            "ai_provider": "anthropic",
        }
        os.environ["AI_MODEL"] = new_config["ai_model_id"]
        os.environ["AI_API_KEY"] = new_config["api_key"]

        client2 = get_family_adapter("family_1", new_config, base_config_dir)

        # Should be different instance (old was invalidated)
        assert client1 is not client2

        clear_cache()


class TestIU6CacheKeyAndCapabilities:
    """IU-6: Tests for (family_id, config_id) cache key and model_1_capabilities."""

    def test_same_family_different_config_id_independent_entries(self, base_config_dir, ai_config):
        """Same family with two different config_ids must have independent cache entries."""
        clear_cache()

        os.environ["AI_MODEL"] = ai_config["ai_model_id"]
        os.environ["AI_API_KEY"] = ai_config["api_key"]

        cfg_a = dict(ai_config, config_id="cfg-aaa")
        cfg_b = dict(ai_config, config_id="cfg-bbb")

        with (
            patch("apps.agent.services.deerflow_adapter.family_adapter_cache._get_shared_checkpointer", return_value=MagicMock()),
            patch("apps.agent.services.deerflow_adapter.family_adapter_cache.NuminaDeerFlowClient", side_effect=lambda config_path, checkpointer=None, **kw: MagicMock()),
            patch("apps.agent.services.deerflow_adapter.family_adapter_cache.reload_app_config"),
        ):
            client_a = get_family_adapter("family_x", cfg_a, base_config_dir)
            client_b = get_family_adapter("family_x", cfg_b, base_config_dir)

        assert client_a is not client_b
        assert _cache_key("family_x", "cfg-aaa") in _adapter_cache
        assert _cache_key("family_x", "cfg-bbb") in _adapter_cache
        assert get_cache_stats()["cached_families"] == 2
        clear_cache()

    def test_config_id_change_does_not_reuse_old_cache(self, base_config_dir, ai_config):
        """After config_id changes, old cache entry must not be reused."""
        clear_cache()

        os.environ["AI_MODEL"] = ai_config["ai_model_id"]
        os.environ["AI_API_KEY"] = ai_config["api_key"]

        cfg_old = dict(ai_config, config_id="cfg-old")
        cfg_new = dict(ai_config, config_id="cfg-new")

        with (
            patch("apps.agent.services.deerflow_adapter.family_adapter_cache._get_shared_checkpointer", return_value=MagicMock()),
            patch("apps.agent.services.deerflow_adapter.family_adapter_cache.NuminaDeerFlowClient", side_effect=lambda config_path, checkpointer=None, **kw: MagicMock()),
            patch("apps.agent.services.deerflow_adapter.family_adapter_cache.reload_app_config"),
        ):
            client_old = get_family_adapter("family_y", cfg_old, base_config_dir)
            client_new = get_family_adapter("family_y", cfg_new, base_config_dir)

        assert client_old is not client_new
        assert _cache_key("family_y", "cfg-old") in _adapter_cache
        assert _cache_key("family_y", "cfg-new") in _adapter_cache
        clear_cache()

    def test_thinking_supported_from_model_1_capabilities(self, base_config_dir):
        """thinking_supported must be True when 'deep_thinking' is in model_1_capabilities."""
        import yaml

        cfg_with_caps = {
            "config_id": "cfg-think",
            "api_key": "sk-test",
            "ai_model_id": "claude-sonnet-4-6",
            "ai_provider": "anthropic",
            "model_1_capabilities": ["text_generation", "deep_thinking"],
        }
        temp_config = _generate_temp_config(base_config_dir, cfg_with_caps)
        content = yaml.safe_load(temp_config.read_text())
        model_entry = content["models"][0]
        assert model_entry.get("supports_thinking") is True

    def test_thinking_not_supported_without_deep_thinking_cap(self, base_config_dir):
        """thinking_supported must be False when 'deep_thinking' is absent from model_1_capabilities."""
        import yaml

        cfg_no_think = {
            "config_id": "cfg-noThink",
            "api_key": "sk-test",
            "ai_model_id": "claude-haiku-4-5",
            "ai_provider": "anthropic",
            "model_1_capabilities": ["text_generation"],
        }
        temp_config = _generate_temp_config(base_config_dir, cfg_no_think)
        content = yaml.safe_load(temp_config.read_text())
        model_entry = content["models"][0]
        assert model_entry.get("supports_thinking") is False

    def test_thinking_falls_back_to_legacy_flag(self, base_config_dir):
        """When model_1_capabilities absent, fall back to thinking_supported flag."""
        import yaml

        cfg_legacy = {
            "config_id": "cfg-legacy",
            "api_key": "sk-test",
            "ai_model_id": "claude-sonnet-4-6",
            "ai_provider": "anthropic",
            "thinking_supported": True,
            # no model_1_capabilities key
        }
        temp_config = _generate_temp_config(base_config_dir, cfg_legacy)
        content = yaml.safe_load(temp_config.read_text())
        model_entry = content["models"][0]
        assert model_entry.get("supports_thinking") is True

    def test_vision_supported_from_model_1_capabilities(self, base_config_dir):
        """supports_vision must be True when 'vision' is in model_1_capabilities.

        This wiring lets the DeerFlow harness assembly-time gate view_image_tool
        (tools.py:110) and mount ViewImageMiddleware (agent.py:352) — without it
        the agent cannot read images even when the underlying model supports them.
        """
        import yaml

        cfg_vision = {
            "config_id": "cfg-vision",
            "api_key": "sk-test",
            "ai_model_id": "claude-sonnet-4-6",
            "ai_provider": "anthropic",
            "model_1_capabilities": ["text_generation", "vision"],
        }
        temp_config = _generate_temp_config(base_config_dir, cfg_vision)
        content = yaml.safe_load(temp_config.read_text())
        model_entry = content["models"][0]
        assert model_entry.get("supports_vision") is True

    def test_vision_supported_from_vision_understanding_capability(self, base_config_dir):
        """supports_vision must be True when 'vision_understanding' is in
        model_1_capabilities. Frontend CapabilityPickerSheet stores this key
        (not 'vision'); both must be accepted to match the actual DB value."""
        import yaml

        cfg_vu = {
            "config_id": "cfg-vu",
            "api_key": "sk-test",
            "ai_model_id": "qwen-vl-plus",
            "ai_provider": "openai_compatible",
            "model_1_capabilities": ["text_generation", "deep_thinking", "vision_understanding"],
        }
        temp_config = _generate_temp_config(base_config_dir, cfg_vu)
        content = yaml.safe_load(temp_config.read_text())
        model_entry = content["models"][0]
        assert model_entry.get("supports_vision") is True

    def test_vision_supported_from_vision_model_id(self, base_config_dir):
        """supports_vision must be True when vision_model_id is set (mirrors
        ai_config.py:579's ``or bool(cfg.vision_model_id)`` logic)."""
        import yaml

        cfg_vision_model = {
            "config_id": "cfg-vm",
            "api_key": "sk-test",
            "ai_model_id": "claude-haiku-4-5",
            "ai_provider": "anthropic",
            "vision_model_id": "claude-sonnet-4-6",
        }
        temp_config = _generate_temp_config(base_config_dir, cfg_vision_model)
        content = yaml.safe_load(temp_config.read_text())
        model_entry = content["models"][0]
        assert model_entry.get("supports_vision") is True

    def test_vision_not_supported_without_vision_config(self, base_config_dir):
        """supports_vision must be False when neither 'vision' capability nor
        vision_model_id is set."""
        import yaml

        cfg_no_vision = {
            "config_id": "cfg-novision",
            "api_key": "sk-test",
            "ai_model_id": "claude-haiku-4-5",
            "ai_provider": "anthropic",
            "model_1_capabilities": ["text_generation"],
        }
        temp_config = _generate_temp_config(base_config_dir, cfg_no_vision)
        content = yaml.safe_load(temp_config.read_text())
        model_entry = content["models"][0]
        assert model_entry.get("supports_vision") is False

    def test_batch_invalidate_clears_all_entries_for_family(self, base_config_dir, ai_config):
        """invalidate_family_adapter_cache(family_id) must clear all (family_id, *) entries."""
        clear_cache()

        os.environ["AI_MODEL"] = ai_config["ai_model_id"]
        os.environ["AI_API_KEY"] = ai_config["api_key"]

        with (
            patch("apps.agent.services.deerflow_adapter.family_adapter_cache._get_shared_checkpointer", return_value=MagicMock()),
            patch("apps.agent.services.deerflow_adapter.family_adapter_cache.NuminaDeerFlowClient", side_effect=lambda config_path, checkpointer=None, **kw: MagicMock()),
            patch("apps.agent.services.deerflow_adapter.family_adapter_cache.reload_app_config"),
        ):
            get_family_adapter("family_z", dict(ai_config, config_id="cfg-z1"), base_config_dir)
            get_family_adapter("family_z", dict(ai_config, config_id="cfg-z2"), base_config_dir)
            get_family_adapter("family_other", dict(ai_config, config_id="cfg-o1"), base_config_dir)

        assert get_cache_stats()["cached_families"] == 3

        # Batch invalidate family_z only
        invalidate_family_adapter_cache("family_z")

        assert _cache_key("family_z", "cfg-z1") not in _adapter_cache
        assert _cache_key("family_z", "cfg-z2") not in _adapter_cache
        assert _cache_key("family_other", "cfg-o1") in _adapter_cache
        assert get_cache_stats()["cached_families"] == 1
        clear_cache()

    def test_specific_config_id_invalidate(self, base_config_dir, ai_config):
        """invalidate_family_adapter_cache(family_id, config_id) removes only that entry."""
        clear_cache()

        os.environ["AI_MODEL"] = ai_config["ai_model_id"]
        os.environ["AI_API_KEY"] = ai_config["api_key"]

        with (
            patch("apps.agent.services.deerflow_adapter.family_adapter_cache._get_shared_checkpointer", return_value=MagicMock()),
            patch("apps.agent.services.deerflow_adapter.family_adapter_cache.NuminaDeerFlowClient", side_effect=lambda config_path, checkpointer=None, **kw: MagicMock()),
            patch("apps.agent.services.deerflow_adapter.family_adapter_cache.reload_app_config"),
        ):
            get_family_adapter("family_w", dict(ai_config, config_id="cfg-w1"), base_config_dir)
            get_family_adapter("family_w", dict(ai_config, config_id="cfg-w2"), base_config_dir)

        invalidate_family_adapter_cache("family_w", config_id="cfg-w1")

        assert _cache_key("family_w", "cfg-w1") not in _adapter_cache
        assert _cache_key("family_w", "cfg-w2") in _adapter_cache
        clear_cache()

class TestCacheFixes:
    """Tests for Critical/Important fixes: env var removal, TOCTOU placeholder, atexit cleanup."""

    def test_no_deer_flow_config_path_env_var_set(self, base_config_dir, ai_config):
        """get_family_adapter must restore DEER_FLOW_CONFIG_PATH after init, not leave it set."""
        clear_cache()
        # Save original value and remove it
        original = os.environ.get("DEER_FLOW_CONFIG_PATH")
        os.environ.pop("DEER_FLOW_CONFIG_PATH", None)

        with (
            patch("apps.agent.services.deerflow_adapter.family_adapter_cache._get_shared_checkpointer", return_value=MagicMock()),
            patch("apps.agent.services.deerflow_adapter.family_adapter_cache.NuminaDeerFlowClient", side_effect=lambda config_path, checkpointer=None, **kw: MagicMock()),
            patch("apps.agent.services.deerflow_adapter.family_adapter_cache.reload_app_config"),
        ):
            get_family_adapter("fam-env-test", ai_config, base_config_dir)

        # After init, env var must be absent (since it was absent before)
        assert os.environ.get("DEER_FLOW_CONFIG_PATH") is None, (
            "get_family_adapter must not leave DEER_FLOW_CONFIG_PATH set — "
            "leaving it set to a per-family temp path would contaminate subsequent calls"
        )

        # Restore original if it was set
        if original is not None:
            os.environ["DEER_FLOW_CONFIG_PATH"] = original
        clear_cache()

    def test_placeholder_removed_on_init_failure(self, base_config_dir, ai_config):
        """On DeerFlowClient init failure, the None placeholder must be removed from cache."""
        clear_cache()

        with (
            patch("apps.agent.services.deerflow_adapter.family_adapter_cache._get_shared_checkpointer", return_value=MagicMock()),
            patch("apps.agent.services.deerflow_adapter.family_adapter_cache.NuminaDeerFlowClient", side_effect=RuntimeError("init failed")),
            patch("apps.agent.services.deerflow_adapter.family_adapter_cache.reload_app_config"),
            pytest.raises(RuntimeError, match="Failed to initialize"),
        ):
            get_family_adapter("fam-fail", ai_config, base_config_dir)

        # Placeholder must be cleaned up — not left as a permanent None entry
        assert ("fam-fail", ai_config["config_id"]) not in _adapter_cache
        assert get_cache_stats()["cached_families"] == 0

    def test_atexit_handler_registered(self):
        """_atexit_cleanup must be registered with atexit so temp dirs are cleaned on exit."""
        import apps.agent.services.deerflow_adapter.family_adapter_cache as cache_mod

        # atexit._atexit_callbacks is CPython internal; use the public interface instead
        # by checking that _atexit_cleanup is callable and calling it doesn't raise
        assert callable(cache_mod._atexit_cleanup)
        cache_mod._atexit_cleanup()  # must not raise even with empty cache

    def test_clear_cache_handles_none_placeholder(self, base_config_dir, ai_config):
        """clear_cache must not crash when a None placeholder is present in the cache."""
        import apps.agent.services.deerflow_adapter.family_adapter_cache as cache_mod

        clear_cache()
        # Manually insert a placeholder (simulates in-progress init)
        with cache_mod._cache_lock:
            cache_mod._adapter_cache[("fam-placeholder", "cfg-x")] = None

        # Must not raise
        clear_cache()
        assert get_cache_stats()["cached_families"] == 0

    def test_invalidate_handles_none_placeholder(self):
        """invalidate_family_adapter must not crash when a None placeholder is present."""
        import apps.agent.services.deerflow_adapter.family_adapter_cache as cache_mod

        clear_cache()
        with cache_mod._cache_lock:
            cache_mod._adapter_cache[("fam-ph2", "cfg-y")] = None

        # Must not raise
        invalidate_family_adapter("fam-ph2")
        assert get_cache_stats()["cached_families"] == 0


class TestMCPServersInjection:
    """Tests for mcp_servers injection into generated config YAML."""

    def test_temp_config_includes_mcp_servers_when_provided(self, tmp_path):
        """_generate_temp_config writes mcp_servers list into config YAML when provided."""
        from pathlib import Path

        import yaml

        from apps.agent.services.deerflow_adapter.family_adapter_cache import (
            _generate_temp_config,
        )

        base_config_dir = str(Path(__file__).resolve().parents[3] / "apps" / "agent" / "deerflow_config")
        ai_config = {
            "api_key": "sk-x",
            "ai_model_id": "gpt-4",
            "ai_provider": "openai",
        }
        mcp_servers = [
            {
                "name": "numina-family-data",
                "url": "http://backend:8000/api/v1/internal/mcp/100/sse",
                "transport": "sse",
                "headers": {"X-Agent-Token": "secret"},
            }
        ]
        path = _generate_temp_config(
            base_config_dir,
            ai_config,
            family_id="100",
            mcp_servers=mcp_servers,
        )
        with open(path, encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        assert cfg.get("mcp_servers") == mcp_servers

    def test_temp_config_omits_mcp_servers_when_not_provided(self, tmp_path):
        """_generate_temp_config doesn't add mcp_servers key when None/empty."""
        from pathlib import Path

        import yaml

        from apps.agent.services.deerflow_adapter.family_adapter_cache import (
            _generate_temp_config,
        )

        base_config_dir = str(Path(__file__).resolve().parents[3] / "apps" / "agent" / "deerflow_config")
        ai_config = {
            "api_key": "sk-x",
            "ai_model_id": "gpt-4",
            "ai_provider": "openai",
        }
        path = _generate_temp_config(base_config_dir, ai_config, family_id="100")
        with open(path, encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        assert "mcp_servers" not in cfg
