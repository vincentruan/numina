"""Tests for summarization absolute-value triggers (U4).

Verifies _inject_summarization produces the correct config structure
with messages/tokens triggers (not fraction) and keep=12.
"""

from apps.agent.services.deerflow_adapter.family_adapter_cache import (
    _inject_summarization,
)


def test_inject_summarization_memory_enabled():
    """memory_enabled=True → absolute-value triggers (messages + tokens)."""
    config: dict = {}
    _inject_summarization(config, memory_enabled=True)

    assert "summarization" in config
    summ = config["summarization"]
    assert summ["enabled"] is True

    # Trigger is a list with messages + tokens (OR relationship)
    triggers = summ["trigger"]
    assert isinstance(triggers, list), "trigger should be a list of trigger clauses"
    assert len(triggers) == 2

    types = {t["type"] for t in triggers}
    assert types == {"messages", "tokens"}

    messages_trigger = next(t for t in triggers if t["type"] == "messages")
    tokens_trigger = next(t for t in triggers if t["type"] == "tokens")
    assert messages_trigger["value"] == 40
    assert tokens_trigger["value"] == 12000

    # Keep: 12 messages (aligned with base/config.yaml)
    assert summ["keep"] == {"type": "messages", "value": 12}


def test_inject_summarization_memory_disabled():
    """memory_enabled=False → config unchanged (early return)."""
    config: dict = {"existing": "data"}
    _inject_summarization(config, memory_enabled=False)

    assert "summarization" not in config
    assert config == {"existing": "data"}


def test_no_fraction_trigger():
    """Verify no fraction-based trigger is injected (would cause 'Dropped' warning)."""
    config: dict = {}
    _inject_summarization(config, memory_enabled=True)

    triggers = config["summarization"]["trigger"]
    for t in triggers:
        assert t["type"] != "fraction", "fraction triggers cause 'Dropped' warnings"
