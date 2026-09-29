"""DeerFlowClient factory — singleton per process."""


from apps.agent.services.deerflow_adapter.numina_deerflow_client import (
    NuminaDeerFlowClient,
)
from packages.core.logging import get_logger

logger = get_logger(__name__)

_client = None


def get_deerflow_client(config_path: str):
    """Return the singleton NuminaDeerFlowClient, creating it if needed."""
    global _client
    if _client is not None:
        return _client

    try:
        _client = NuminaDeerFlowClient(config_path=config_path)
        logger.info("NuminaDeerFlowClient initialized with config: %s", config_path)
        return _client
    except Exception as e:
        raise RuntimeError(
            f"Failed to initialize NuminaDeerFlowClient from config '{config_path}': {e}"
        ) from e


def reset_client() -> None:
    """Reset the singleton (for testing only)."""
    global _client
    _client = None
