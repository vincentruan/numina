"""Tests for _select_stream_run_provider — circuit-state aware selection."""

from __future__ import annotations

from apps.agent.services.orchestrator import _select_stream_run_provider


def _make_provider(
    config_id: str, circuit_state: str = "closed"
) -> dict:
    return {
        "config_id": config_id,
        "ai_provider": "openai",
        "ai_model_id": "gpt-4o",
        "circuit_state": circuit_state,
    }


def test_returns_first_closed_provider():
    providers = [
        _make_provider("cfg-1", "closed"),
        _make_provider("cfg-2", "closed"),
    ]
    result = _select_stream_run_provider(providers)
    assert result is not None
    assert result["config_id"] == "cfg-1"


def test_skips_open_provider():
    """When provider-1 is open, provider-2 (closed) must be selected."""
    providers = [
        _make_provider("cfg-1", "open"),
        _make_provider("cfg-2", "closed"),
    ]
    result = _select_stream_run_provider(providers)
    assert result is not None
    assert result["config_id"] == "cfg-2"


def test_returns_none_when_all_open():
    """No usable provider → return None so caller surfaces the failure."""
    providers = [
        _make_provider("cfg-1", "open"),
        _make_provider("cfg-2", "open"),
    ]
    assert _select_stream_run_provider(providers) is None


def test_returns_none_for_empty_list():
    assert _select_stream_run_provider([]) is None


def test_prefers_closed_over_half_open():
    """When both closed and half_open providers exist, prefer closed."""
    providers = [
        _make_provider("cfg-ho", "half_open"),
        _make_provider("cfg-closed", "closed"),
    ]
    # 10% probe chance means 90% of the time we pick closed; run many
    # iterations and verify closed is overwhelmingly preferred.
    counts: dict[str, int] = {}
    for _ in range(200):
        result = _select_stream_run_provider(providers)
        assert result is not None
        counts[result["config_id"]] = counts.get(result["config_id"], 0) + 1
    assert counts.get("cfg-closed", 0) > 150  # ~90% of 200
    assert counts.get("cfg-ho", 0) > 0  # at least some probes hit half_open


def test_half_open_only_always_returned():
    """When only half_open providers remain, return the first one."""
    providers = [_make_provider("cfg-ho", "half_open")]
    result = _select_stream_run_provider(providers)
    assert result is not None
    assert result["config_id"] == "cfg-ho"


def test_default_circuit_state_is_closed():
    """Providers without circuit_state default to closed (defensive)."""
    providers = [
        {"config_id": "cfg-no-state", "ai_provider": "openai", "ai_model_id": "gpt-4o"},
    ]
    result = _select_stream_run_provider(providers)
    assert result is not None
    assert result["config_id"] == "cfg-no-state"
