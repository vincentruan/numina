"""Unit tests for Numina StreamBridge implementation.

Tests the factory, config, and Numina-specific Redis bridge wrapper.
"""

from __future__ import annotations

import pytest

from apps.agent.services.runtime.stream_bridge import (
    MemoryStreamBridge,
    NuminaRedisStreamBridge,
    StreamBridge,
    StreamBridgeConfig,
    make_stream_bridge,
)


class TestStreamBridgeConfig:
    """Test StreamBridgeConfig pydantic model."""

    def test_default_config(self):
        """Default config should be memory bridge."""
        config = StreamBridgeConfig()
        assert config.type == "memory"
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

    def test_make_memory_bridge(self):
        """Factory should create MemoryStreamBridge for type='memory'."""
        config = StreamBridgeConfig(type="memory", queue_maxsize=128)
        bridge = make_stream_bridge(config)
        assert isinstance(bridge, MemoryStreamBridge)
        assert isinstance(bridge, StreamBridge)

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
        """Factory with no config should create MemoryStreamBridge."""
        bridge = make_stream_bridge()
        assert isinstance(bridge, MemoryStreamBridge)

    def test_make_invalid_type_raises(self):
        """Factory should raise ValueError for unknown type."""
        config = StreamBridgeConfig(type="invalid")
        with pytest.raises(ValueError, match="Unknown stream_bridge.type"):
            make_stream_bridge(config)


class TestNuminaRedisStreamBridge:
    """Test Numina-specific Redis bridge wrapper."""

    def test_inherits_from_deerflow(self):
        """NuminaRedisStreamBridge should inherit from DeerFlow's RedisStreamBridge."""
        from deerflow.runtime.stream_bridge.redis import RedisStreamBridge

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
