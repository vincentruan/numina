"""DeerFlowClient factory — singleton per process."""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

_client = None


def get_deerflow_client(config_path: str):
    """Return the singleton DeerFlowClient, creating it if needed."""
    global _client
    if _client is not None:
        return _client

    try:
        from deerflow.client import DeerFlowClient
        _client = DeerFlowClient(config_path=config_path)
        logger.info(f"DeerFlowClient initialized with config: {config_path}")
        return _client
    except Exception as e:
        raise RuntimeError(
            f"Failed to initialize DeerFlowClient from config '{config_path}': {e}"
        ) from e


def reset_client() -> None:
    """Reset the singleton (for testing only)."""
    global _client
    _client = None
