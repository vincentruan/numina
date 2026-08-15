"""StreamBridge configuration for Numina agent.

Pydantic model for stream bridge settings, loaded from agent config or env vars.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class StreamBridgeConfig(BaseModel):
    """Configuration for the StreamBridge implementation.

    Attributes:
        type: Bridge type — "memory" for single-process dev, "redis" for
            multi-worker Docker deployment.
        redis_url: Redis connection URL (only used when type="redis").
        queue_maxsize: Max events retained per stream (default 256).
        stream_ttl_seconds: Stream TTL in seconds (default 86400 = 24h).
    """

    type: str = Field(
        default="memory",
        description="Bridge type: 'memory' or 'redis'",
    )
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis URL (used when type='redis')",
    )
    queue_maxsize: int = Field(
        default=256,
        description="Max events retained per stream",
    )
    stream_ttl_seconds: int = Field(
        default=86400,
        description="Stream TTL in seconds (default 24h)",
    )
