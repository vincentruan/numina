"""Tests for family_adapter_cache module."""

import os
import tempfile
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from apps.agent.services.deerflow_adapter.family_adapter_cache import (
    _generate_temp_config,
    _get_shared_checkpointer,
    get_family_adapter,
    invalidate_family_adapter,
    clear_cache,
    close_shared_checkpointer,
    get_cache_stats,
    _adapter_cache,
)


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

        original_client_cls = None
        try:
            import deerflow.client as df_client_mod
            original_client_cls = df_client_mod.DeerFlowClient
        except ImportError:
            pytest.skip("deerflow not available")

        mock_checkpointer = MagicMock(name="shared_checkpointer")

        def _fake_client(config_path, checkpointer=None, **kwargs):
            captured_kwargs["checkpointer"] = checkpointer
            return MagicMock(name="DeerFlowClient")

        with (
            patch("apps.agent.services.deerflow_adapter.family_adapter_cache._get_shared_checkpointer", return_value=mock_checkpointer),
            patch("apps.agent.services.deerflow_adapter.family_adapter_cache.DeerFlowClient", side_effect=_fake_client),
            patch("apps.agent.services.deerflow_adapter.family_adapter_cache.reload_app_config"),
        ):
            get_family_adapter("family_cp_test", ai_config, base_config_dir)

        assert captured_kwargs.get("checkpointer") is mock_checkpointer, (
            "DeerFlowClient must receive the shared checkpointer — "
            "without it each dispatch is stateless and multi-turn reasoning is impossible"
        )

        clear_cache()

    def test_close_shared_checkpointer_resets_singleton(self, base_config_dir):
        """close_shared_checkpointer must allow a fresh checkpointer to be created."""
        import apps.agent.services.deerflow_adapter.family_adapter_cache as cache_mod

        orig = cache_mod._shared_checkpointer
        orig_ctx = cache_mod._checkpointer_ctx
        cache_mod._shared_checkpointer = None
        cache_mod._checkpointer_ctx = None

        try:
            cp1 = _get_shared_checkpointer(base_config_dir)
            close_shared_checkpointer()
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

        # Fill cache beyond limit (100)
        for i in range(105):
            get_family_adapter(
                family_id=f"family_{i}",
                ai_config=ai_config,
                base_config_dir=base_config_dir,
            )

        stats = get_cache_stats()
        assert stats["cached_families"] == 100
        # First family should be evicted
        assert "family_0" not in _adapter_cache
        assert "family_100" in _adapter_cache

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
        assert "family_1" not in _adapter_cache

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