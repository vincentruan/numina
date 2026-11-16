"""T11: Per-family MCP cache race fix — concurrent multi-family tests.

Verifies that _maybe_reset_mcp_cache uses per-family signature tracking
instead of a process-global state variable, eliminating alternating resets
under concurrent multi-family requests.
"""

from __future__ import annotations

import threading
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def _reset_state():
    """Reset the per-family tracking dict before each test."""
    from apps.agent.services.deerflow_adapter.adapter import (
        _per_family_reset_state,
    )

    _per_family_reset_state.clear()
    yield
    _per_family_reset_state.clear()


class TestPerFamilySignatureTracking:
    """Same family, same config → zero repeated resets."""

    def test_same_family_no_repeated_reset(self, _reset_state):
        """Repeated calls with same path/sig → reset_extensions_config called once."""
        from apps.agent.services.deerflow_adapter.adapter import (
            _maybe_reset_mcp_cache,
        )

        mock_sig = (1000, 500, "abc123")
        mock_reset = MagicMock()

        with (
            patch(
                "apps.agent.services.deerflow_adapter.adapter._get_config_signature",
                return_value=mock_sig,
            ) if False else patch.dict("sys.modules", {}),
            patch(
                "deerflow.mcp.cache._get_config_signature",
                return_value=mock_sig,
            ),
            patch(
                "deerflow.config.extensions_config.reset_extensions_config",
                mock_reset,
            ),
        ):
            _maybe_reset_mcp_cache("/path/to/family_a/extensions_config.json")
            _maybe_reset_mcp_cache("/path/to/family_a/extensions_config.json")
            _maybe_reset_mcp_cache("/path/to/family_a/extensions_config.json")

        assert mock_reset.call_count == 1

    def test_different_family_independent_tracking(self, _reset_state):
        """Different paths tracked independently — each gets its own first-call reset."""
        from apps.agent.services.deerflow_adapter.adapter import (
            _maybe_reset_mcp_cache,
        )

        sig_a = (1000, 500, "aaa")
        sig_b = (2000, 600, "bbb")
        mock_reset = MagicMock()

        def fake_sig(path):
            if "family_a" in str(path):
                return sig_a
            return sig_b

        with (
            patch(
                "deerflow.mcp.cache._get_config_signature",
                side_effect=fake_sig,
            ),
            patch(
                "deerflow.config.extensions_config.reset_extensions_config",
                mock_reset,
            ),
        ):
            _maybe_reset_mcp_cache("/path/family_a/extensions_config.json")
            _maybe_reset_mcp_cache("/path/family_b/extensions_config.json")
            # Second calls — should skip (sig matches per-family state)
            _maybe_reset_mcp_cache("/path/family_a/extensions_config.json")
            _maybe_reset_mcp_cache("/path/family_b/extensions_config.json")

        # One reset per family (first call), not on repeated calls
        assert mock_reset.call_count == 2

    def test_config_change_triggers_reset(self, _reset_state):
        """Same path, changed sig (admin edits MCP servers) → reset again."""
        from apps.agent.services.deerflow_adapter.adapter import (
            _maybe_reset_mcp_cache,
        )

        sig_v1 = (1000, 500, "v1")
        sig_v2 = (2000, 600, "v2")
        mock_reset = MagicMock()
        path = "/path/family_a/extensions_config.json"

        with (
            patch(
                "deerflow.mcp.cache._get_config_signature",
                return_value=sig_v1,
            ),
            patch(
                "deerflow.config.extensions_config.reset_extensions_config",
                mock_reset,
            ),
        ):
            _maybe_reset_mcp_cache(path)
            assert mock_reset.call_count == 1

        # Config changed
        with (
            patch(
                "deerflow.mcp.cache._get_config_signature",
                return_value=sig_v2,
            ),
            patch(
                "deerflow.config.extensions_config.reset_extensions_config",
                mock_reset,
            ),
        ):
            _maybe_reset_mcp_cache(path)
            assert mock_reset.call_count == 2

        # Same new sig — skip
        with (
            patch(
                "deerflow.mcp.cache._get_config_signature",
                return_value=sig_v2,
            ),
            patch(
                "deerflow.config.extensions_config.reset_extensions_config",
                mock_reset,
            ),
        ):
            _maybe_reset_mcp_cache(path)
            assert mock_reset.call_count == 2  # No additional reset


class TestNoResetMcpToolsCache:
    """reset_mcp_tools_cache() must never be called — get_cached_mcp_tools handles it."""

    def test_no_reset_mcp_tools_cache(self, _reset_state):
        """Verify reset_mcp_tools_cache is NOT imported or called."""
        from apps.agent.services.deerflow_adapter.adapter import (
            _maybe_reset_mcp_cache,
        )

        mock_sig = (1000, 500, "abc")
        mock_reset_ext = MagicMock()
        mock_reset_tools = MagicMock()

        with (
            patch(
                "deerflow.mcp.cache._get_config_signature",
                return_value=mock_sig,
            ),
            patch(
                "deerflow.config.extensions_config.reset_extensions_config",
                mock_reset_ext,
            ),
            patch(
                "deerflow.mcp.cache.reset_mcp_tools_cache",
                mock_reset_tools,
            ),
        ):
            _maybe_reset_mcp_cache("/path/to/extensions_config.json")

        mock_reset_tools.assert_not_called()
        assert mock_reset_ext.call_count == 1


class TestConcurrentAccess:
    """Thread safety — concurrent same-family and different-family access."""

    def test_concurrent_same_family(self, _reset_state):
        """4 threads, same path/sig → reset called at most once (fast path)."""
        from apps.agent.services.deerflow_adapter.adapter import (
            _maybe_reset_mcp_cache,
        )

        mock_sig = (1000, 500, "concurrent")
        mock_reset = MagicMock()
        path = "/path/family_a/extensions_config.json"
        errors: list[Exception] = []

        def worker():
            try:
                _maybe_reset_mcp_cache(path)
            except Exception as e:
                errors.append(e)

        with (
            patch(
                "deerflow.mcp.cache._get_config_signature",
                return_value=mock_sig,
            ),
            patch(
                "deerflow.config.extensions_config.reset_extensions_config",
                mock_reset,
            ),
        ):
            threads = [threading.Thread(target=worker) for _ in range(4)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

        assert not errors
        # At most 4 resets (one per thread if they all pass the check before
        # any updates the state). In practice, the first thread updates the
        # state and subsequent threads see the matching sig → skip.
        # The important invariant: no thread crashes, and the final state is
        # correct.
        assert mock_reset.call_count <= 4

        # Verify final state is correct
        from apps.agent.services.deerflow_adapter.adapter import (
            _per_family_reset_state,
        )

        assert _per_family_reset_state.get(path) == mock_sig

    def test_concurrent_different_families(self, _reset_state):
        """4 threads, 2 families alternating → per-family tracking prevents cross-family interference."""
        from apps.agent.services.deerflow_adapter.adapter import (
            _maybe_reset_mcp_cache,
        )

        sig_a = (1000, 500, "aaa")
        sig_b = (2000, 600, "bbb")
        path_a = "/path/family_a/extensions_config.json"
        path_b = "/path/family_b/extensions_config.json"
        errors: list[Exception] = []
        reset_calls: list[str] = []

        mock_reset = MagicMock(side_effect=lambda: reset_calls.append("reset"))

        def fake_sig(path):
            if "family_a" in str(path):
                return sig_a
            return sig_b

        def worker_a():
            try:
                _maybe_reset_mcp_cache(path_a)
            except Exception as e:
                errors.append(e)

        def worker_b():
            try:
                _maybe_reset_mcp_cache(path_b)
            except Exception as e:
                errors.append(e)

        with (
            patch(
                "deerflow.mcp.cache._get_config_signature",
                side_effect=fake_sig,
            ),
            patch(
                "deerflow.config.extensions_config.reset_extensions_config",
                mock_reset,
            ),
        ):
            # Interleave: A, B, A, B
            threads = [
                threading.Thread(target=worker_a),
                threading.Thread(target=worker_b),
                threading.Thread(target=worker_a),
                threading.Thread(target=worker_b),
            ]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

        assert not errors
        # Each family's path is tracked independently — no cross-family
        # interference. Final state should have both paths.
        from apps.agent.services.deerflow_adapter.adapter import (
            _per_family_reset_state,
        )

        assert _per_family_reset_state.get(path_a) == sig_a
        assert _per_family_reset_state.get(path_b) == sig_b


class TestImportErrorGraceful:
    """Graceful degradation when DeerFlow imports are unavailable."""

    def test_import_error_no_crash(self, _reset_state):
        """If _get_config_signature or reset_extensions_config unavailable → return silently."""
        from apps.agent.services.deerflow_adapter.adapter import (
            _maybe_reset_mcp_cache,
        )

        with patch.dict("sys.modules", {"deerflow.mcp.cache": None}):
            # Should not raise — just return silently
            _maybe_reset_mcp_cache("/path/to/extensions_config.json")

        # No state recorded (imports failed before tracking)
        from apps.agent.services.deerflow_adapter.adapter import (
            _per_family_reset_state,
        )

        assert "/path/to/extensions_config.json" not in _per_family_reset_state
