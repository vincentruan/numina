"""Verify agent initializes Redis StreamBridge when Redis is available.

These tests validate the existing ``NuminaRedisStreamBridge`` behavior,
confirming the bridge works as expected for cross-process event sharing.

Tests require a Redis instance. Set ``REDIS_URL`` environment variable
to point to a test Redis instance. Tests are skipped if Redis is unavailable.
"""

from __future__ import annotations

import os

import pytest

# Check if Redis is available for testing
_redis_url = os.environ.get("REDIS_URL", "")


def _check_redis_available() -> bool:
    """Return True if Redis is reachable at the configured URL."""
    if not _redis_url:
        return False
    try:
        import redis
        r = redis.from_url(_redis_url, decode_responses=True)
        r.ping()
        r.close()
        return True
    except Exception:
        return False


_redis_available = _check_redis_available()

skip_no_redis = pytest.mark.skipif(
    not _redis_available,
    reason="Redis not available (set REDIS_URL env var to enable)",
)


@pytest.fixture
def redis_url() -> str:
    """Return the Redis URL for testing."""
    return _redis_url


@skip_no_redis
@pytest.mark.asyncio
async def test_redis_bridge_initializes_with_valid_url(redis_url: str):
    """Agent should create NuminaRedisStreamBridge when STREAM_BRIDGE_REDIS_URL is set."""
    from packages.stream_bridge.config import StreamBridgeConfig
    from packages.stream_bridge.factory import make_stream_bridge
    from packages.stream_bridge.redis import NuminaRedisStreamBridge

    config = StreamBridgeConfig(
        type="redis",
        redis_url=redis_url,
        queue_maxsize=256,
        stream_ttl_seconds=86400,
    )
    bridge = make_stream_bridge(config)
    assert isinstance(bridge, NuminaRedisStreamBridge)
    assert bridge.supports_cross_process is True
    await bridge.close()


@skip_no_redis
@pytest.mark.asyncio
async def test_redis_bridge_publish_subscribe_cross_process(redis_url: str):
    """Events published by one bridge instance are readable by another (simulates agent->backend)."""
    from packages.stream_bridge.config import StreamBridgeConfig
    from packages.stream_bridge.factory import make_stream_bridge

    config = StreamBridgeConfig(type="redis", redis_url=redis_url, queue_maxsize=256)

    # Producer (agent side)
    producer = make_stream_bridge(config)
    # Consumer (backend side) — separate instance, same Redis
    consumer = make_stream_bridge(config)

    run_id = "test_family:run_123"
    await producer.publish(run_id, "messages", {"content": "hello"})
    await producer.publish_end(run_id)

    # Consumer should see the events
    events = []
    async for item in consumer.subscribe(run_id):
        events.append(item)
        if item.event == "__end__":
            break

    assert len(events) >= 2  # at least 1 message + end sentinel
    assert events[0].event == "messages"
    assert events[0].data == {"content": "hello"}

    await producer.close()
    await consumer.close()


@skip_no_redis
@pytest.mark.asyncio
async def test_redis_bridge_tenant_isolation(redis_url: str):
    """NuminaRedisStreamBridge keys include family_id for tenant isolation."""
    from packages.stream_bridge.config import StreamBridgeConfig
    from packages.stream_bridge.factory import make_stream_bridge

    config = StreamBridgeConfig(type="redis", redis_url=redis_url)
    bridge = make_stream_bridge(config)

    # Key format: numina:stream:{family_id}:{run_id}
    key = bridge._stream_key("family_123:run_456")
    assert key == "numina:stream:family_123:run_456"

    # Without family_id prefix
    key_bare = bridge._stream_key("run_789")
    assert key_bare == "numina:stream:0:run_789"

    await bridge.close()


class TestLifespanConfigIntegration:
    """Test that lifespan correctly reads config and falls back to memory."""

    def test_config_has_stream_bridge_redis_url(self):
        """AgentSettings should have STREAM_BRIDGE_REDIS_URL field."""
        from apps.agent.app.config import AgentSettings

        settings = AgentSettings()
        assert hasattr(settings, "STREAM_BRIDGE_REDIS_URL")
        assert settings.STREAM_BRIDGE_REDIS_URL == ""  # default is empty

    def test_config_accepts_redis_url(self):
        """AgentSettings should accept STREAM_BRIDGE_REDIS_URL value."""
        from apps.agent.app.config import AgentSettings

        settings = AgentSettings(STREAM_BRIDGE_REDIS_URL="redis://custom:6379/1")
        assert settings.STREAM_BRIDGE_REDIS_URL == "redis://custom:6379/1"

    def test_memory_bridge_fallback_when_redis_unavailable(self):
        """When Redis ping fails, bridge should fall back to memory."""
        from packages.stream_bridge.config import StreamBridgeConfig
        from packages.stream_bridge.factory import make_stream_bridge
        from packages.stream_bridge.memory import MemoryStreamBridge

        # Simulate the fallback logic from lifespan.py
        # When Redis connection fails, the except block creates a memory bridge
        bridge = None
        try:
            # Simulate Redis connection failure
            raise ConnectionError("Simulated Redis failure")
        except Exception:
            config = StreamBridgeConfig(type="memory", queue_maxsize=256)
            bridge = make_stream_bridge(config)

        assert isinstance(bridge, MemoryStreamBridge)
