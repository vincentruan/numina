"""Unit tests for Numina StreamBridge implementation.

Tests the factory, config, NuminaRedisStreamBridge wrapper, and the
test-only MemoryStreamBridge (lives under tests/agent/helpers/).
"""

from __future__ import annotations

import pytest

from packages.stream_bridge import (
    NuminaRedisStreamBridge,
    StreamBridge,
    StreamBridgeConfig,
    make_stream_bridge,
)
from tests.agent.helpers.memory_bridge import MemoryStreamBridge


class TestStreamBridgeConfig:
    """Test StreamBridgeConfig pydantic model."""

    def test_default_config(self):
        """Default config should be redis bridge."""
        config = StreamBridgeConfig()
        assert config.type == "redis"
        assert config.redis_url == "redis://localhost:6379/0"
        assert config.queue_maxsize == 256
        assert config.stream_ttl_seconds == 86400

    def test_redis_config(self):
        """Redis config should set type and redis_url."""
        config = StreamBridgeConfig(
            type="redis",
            redis_url="redis://redis:6379/0",
            queue_maxsize=512,
            stream_ttl_seconds=43200,
        )
        assert config.type == "redis"
        assert config.redis_url == "redis://redis:6379/0"
        assert config.queue_maxsize == 512
        assert config.stream_ttl_seconds == 43200


class TestMakeStreamBridge:
    """Test make_stream_bridge factory function."""

    def test_make_redis_bridge(self):
        """Factory should create NuminaRedisStreamBridge for type='redis'."""
        config = StreamBridgeConfig(
            type="redis",
            redis_url="redis://localhost:6379/0",
            queue_maxsize=256,
            stream_ttl_seconds=86400,
        )
        bridge = make_stream_bridge(config)
        assert isinstance(bridge, NuminaRedisStreamBridge)
        assert isinstance(bridge, StreamBridge)

    def test_make_default_bridge(self):
        """Factory with no config should create NuminaRedisStreamBridge."""
        bridge = make_stream_bridge()
        assert isinstance(bridge, NuminaRedisStreamBridge)

    def test_make_invalid_type_raises(self):
        """Factory should raise ValueError for unknown type."""
        config = StreamBridgeConfig(type="invalid")
        with pytest.raises(ValueError, match="Unknown stream_bridge.type"):
            make_stream_bridge(config)


class TestNuminaRedisStreamBridge:
    """Test Numina-specific Redis bridge wrapper."""

    def test_inherits_from_shared_redis_bridge(self):
        """NuminaRedisStreamBridge should inherit from the shared package's RedisStreamBridge."""
        from packages.stream_bridge.redis import RedisStreamBridge

        assert issubclass(NuminaRedisStreamBridge, RedisStreamBridge)

    def test_key_prefix(self):
        """NuminaRedisStreamBridge should use 'numina:stream' key prefix."""
        bridge = NuminaRedisStreamBridge(
            redis_url="redis://localhost:6379/0",
            queue_maxsize=256,
            stream_ttl_seconds=86400,
        )
        # Check that the key prefix is set correctly
        assert bridge._key_prefix == "numina:stream"

    def test_supports_cross_process(self):
        """NuminaRedisStreamBridge should support cross-process operation."""
        bridge = NuminaRedisStreamBridge(
            redis_url="redis://localhost:6379/0",
        )
        assert bridge.supports_cross_process is True


class TestMemoryStreamBridge:
    """Test the test-only MemoryStreamBridge protocol implementation.

    These tests verify the StreamBridge contract (publish/subscribe/reconnect)
    without requiring a running Redis instance.
    """

    async def test_publish_and_subscribe(self):
        """Subscriber should receive published events in order."""
        bridge = MemoryStreamBridge()
        run_id = "test-run-1"

        await bridge.publish(run_id, "update", {"msg": "hello"})
        await bridge.publish(run_id, "update", {"msg": "world"})
        await bridge.publish_end(run_id)

        events = []
        async for item in bridge.subscribe(run_id, heartbeat_interval=0.1):
            events.append(item)
            if item is not None and hasattr(item, "event") and item.event == "__end__":
                break

        assert len(events) == 3
        assert events[0].event == "update"
        assert events[0].data == {"msg": "hello"}
        assert events[1].data == {"msg": "world"}
        assert events[2].event == "__end__"

        await bridge.close()

    async def test_last_event_id_replay(self):
        """Subscriber with last_event_id should skip already-seen events."""
        bridge = MemoryStreamBridge()
        run_id = "test-run-2"

        await bridge.publish(run_id, "update", {"n": 1})
        await bridge.publish(run_id, "update", {"n": 2})
        await bridge.publish(run_id, "update", {"n": 3})
        await bridge.publish_end(run_id)

        # First subscriber gets all events
        first_event_id = None
        async for item in bridge.subscribe(run_id, heartbeat_interval=0.1):
            if first_event_id is None:
                first_event_id = item.id
            if item is not None and hasattr(item, "event") and item.event == "__end__":
                break

        # Second subscriber replays from after first event
        replayed = []
        async for item in bridge.subscribe(
            run_id, last_event_id=first_event_id, heartbeat_interval=0.1
        ):
            replayed.append(item)
            if item is not None and hasattr(item, "event") and item.event == "__end__":
                break

        # Should get events 2 and 3 (not event 1)
        data_events = [e for e in replayed if hasattr(e, "event") and e.event == "update"]
        assert len(data_events) == 2
        assert data_events[0].data == {"n": 2}
        assert data_events[1].data == {"n": 3}

        await bridge.close()

    async def test_cleanup_removes_stream(self):
        """Cleanup should remove the stream for a run_id."""
        bridge = MemoryStreamBridge()
        run_id = "test-run-3"

        await bridge.publish(run_id, "update", {"x": 1})
        assert await bridge.stream_exists(run_id) is True

        await bridge.cleanup(run_id)
        assert await bridge.stream_exists(run_id) is False

        await bridge.close()

    async def test_queue_overflow(self):
        """When queue overflows, oldest events are dropped."""
        bridge = MemoryStreamBridge(queue_maxsize=3)
        run_id = "test-run-4"

        for i in range(5):
            await bridge.publish(run_id, "update", {"i": i})
        await bridge.publish_end(run_id)

        events = []
        async for item in bridge.subscribe(run_id, heartbeat_interval=0.1):
            events.append(item)
            if item is not None and hasattr(item, "event") and item.event == "__end__":
                break

        # Only last 3 events + end sentinel
        data_events = [e for e in events if hasattr(e, "event") and e.event == "update"]
        assert len(data_events) == 3
        assert data_events[0].data == {"i": 2}

        await bridge.close()

    async def test_stream_exists(self):
        """stream_exists should reflect publish/cleanup state."""
        bridge = MemoryStreamBridge()
        assert await bridge.stream_exists("nonexistent") is False

        await bridge.publish("r1", "evt", {})
        assert await bridge.stream_exists("r1") is True

        await bridge.cleanup("r1")
        assert await bridge.stream_exists("r1") is False

        await bridge.close()
