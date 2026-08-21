"""NuminaDeerFlowClient — DeerFlowClient subclass with checkpoint_id support.

This subclass extends DeerFlowClient to support checkpoint_id in the
configurable, enabling retry checkpoint forking without modifying vendored
DeerFlow code.

When checkpoint_id is passed via kwargs (e.g., stream(message, checkpoint_id=...)),
it is included in the RunnableConfig's configurable dict, so the checkpointer
loads from that checkpoint instead of the head.

Usage:
    client = NuminaDeerFlowClient(config_path=...)
    for event in client.stream(message, thread_id=..., checkpoint_id=...):
        ...
"""

from __future__ import annotations

import logging
from typing import Any

from deerflow.client import DeerFlowClient

logger = logging.getLogger(__name__)


class NuminaDeerFlowClient(DeerFlowClient):
    """DeerFlowClient subclass with checkpoint_id support for retry forking.

    Extends _get_runnable_config to extract checkpoint_id from kwargs and
    include it in the configurable dict. This enables the checkpointer to
    load from a specific checkpoint (e.g., pre-failure state) instead of
    always reading from the head.

    Example:
        client = NuminaDeerFlowClient(config_path=...)
        # Fork from checkpoint_id instead of head
        for event in client.stream(message, thread_id=..., checkpoint_id="..."):
            ...
    """

    def _get_runnable_config(self, thread_id: str, **overrides: Any) -> Any:
        """Build RunnableConfig, extracting checkpoint_id from overrides.

        Extends the parent implementation to include checkpoint_id in the
        configurable dict when present. This is used for retry checkpoint
        forking — the frontend passes checkpoint_id from retryPrepare, and
        the checkpointer loads from that checkpoint (before the failed
        message) instead of the head.

        Args:
            thread_id: Thread ID for conversation context.
            **overrides: Per-call kwargs (model_name, thinking_enabled, etc.).
                When checkpoint_id is present, it is included in configurable.

        Returns:
            RunnableConfig with checkpoint_id in configurable (if provided).
        """
        # Call parent to get the base config
        config = super()._get_runnable_config(thread_id, **overrides)

        # Inject checkpoint_id into configurable if present in overrides
        checkpoint_id = overrides.get("checkpoint_id")
        if checkpoint_id is not None:
            # config is a RunnableConfig with .configurable dict
            if hasattr(config, "configurable") and isinstance(config.configurable, dict):
                config.configurable["checkpoint_id"] = checkpoint_id
            elif isinstance(config, dict) and "configurable" in config and isinstance(config["configurable"], dict):
                # Fallback: if config is a plain dict (shouldn't happen, but defensive)
                config["configurable"]["checkpoint_id"] = checkpoint_id

        return config
