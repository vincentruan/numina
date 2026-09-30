"""Factory for creating StreamBridge instances.

Reads configuration and returns the appropriate StreamBridge implementation.
Production always uses ``type="redis"`` (NuminaRedisStreamBridge).
The ``type="memory"`` branch and ``config=None`` default exist for unit tests
only — a memory bridge in the agent process is invisible to the backend's
bridge_consumer, so it cannot work in production.
"""

from __future__ import annotations

from packages.core.logging import get_logger

from .base import StreamBridge
from .config import StreamBridgeConfig
from .memory import MemoryStreamBridge
from .redis import NuminaRedisStreamBridge

logger = get_logger(__name__)


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
