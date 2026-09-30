"""Factory for creating StreamBridge instances.

Production always uses ``NuminaRedisStreamBridge`` (Redis Streams).
A test-only ``MemoryStreamBridge`` lives under ``tests/agent/helpers/``.
"""

from __future__ import annotations

from packages.core.logging import get_logger

from .base import StreamBridge
from .config import StreamBridgeConfig
from .redis import NuminaRedisStreamBridge

logger = get_logger(__name__)


def make_stream_bridge(config: StreamBridgeConfig | None = None) -> StreamBridge:
    """Create a NuminaRedisStreamBridge from configuration.

    Args:
        config: Stream bridge configuration. If None, uses defaults
            (redis://localhost:6379/0).

    Returns:
        NuminaRedisStreamBridge instance.

    Raises:
        ValueError: If config.type is not "redis".
    """
    if config is None:
        config = StreamBridgeConfig()

    if config.type != "redis":
        raise ValueError(
            f"Unknown stream_bridge.type: {config.type!r}. "
            f"Only 'redis' is supported in production."
        )

    logger.info(
        "Creating Redis StreamBridge (url=%s, ttl=%ds)",
        config.redis_url,
        config.stream_ttl_seconds,
    )
    return NuminaRedisStreamBridge(
        redis_url=config.redis_url,
        queue_maxsize=config.queue_maxsize,
        stream_ttl_seconds=config.stream_ttl_seconds,
    )
