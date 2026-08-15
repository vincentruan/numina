"""Factory for creating StreamBridge instances.

Reads configuration and returns the appropriate StreamBridge implementation
(MemoryStreamBridge for dev, NuminaRedisStreamBridge for production).
"""

from __future__ import annotations

import logging

from deerflow.runtime.stream_bridge import MemoryStreamBridge, StreamBridge

from .config import StreamBridgeConfig
from .redis import NuminaRedisStreamBridge

logger = logging.getLogger(__name__)


def make_stream_bridge(config: StreamBridgeConfig | None = None) -> StreamBridge:
    """Create a StreamBridge instance based on configuration.

    Args:
        config: Stream bridge configuration. If None, uses memory bridge.

    Returns:
        StreamBridge instance (MemoryStreamBridge or NuminaRedisStreamBridge).

    Raises:
        ValueError: If config.type is not "memory" or "redis".
    """
    if config is None:
        logger.info("Creating in-memory StreamBridge (default)")
        return MemoryStreamBridge()

    if config.type == "memory":
        logger.info("Creating in-memory StreamBridge (config)")
        return MemoryStreamBridge(
            queue_maxsize=config.queue_maxsize,
        )

    if config.type == "redis":
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

    raise ValueError(
        f"Unknown stream_bridge.type: {config.type!r}. "
        f"Expected 'memory' or 'redis'."
    )
