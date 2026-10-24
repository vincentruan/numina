"""Taxonomy loader registry and factory.

Provides a get_loader() factory function to retrieve registered loaders by
source name. Raises ValueError for unknown sources.
"""

from __future__ import annotations

from packages.os_taxonomy.loaders.base import TaxonomyLoader
from packages.os_taxonomy.types import (
    NormalizedCluster,
    NormalizedDependency,
    NormalizedTopic,
)

__all__ = [
    "NormalizedCluster",
    "NormalizedDependency",
    "NormalizedTopic",
    "TaxonomyLoader",
    "get_loader",
]

# Registry mapping source names to loader classes/instances
_LOADER_REGISTRY: dict[str, TaxonomyLoader] = {}


def get_loader(source: str) -> TaxonomyLoader:
    """Retrieve a registered taxonomy loader by source name.

    Args:
        source: The taxonomy source identifier (e.g., "os-taxonomy", "os-taxonomy-beijing").

    Returns:
        A TaxonomyLoader instance for the requested source.

    Raises:
        ValueError: If the source is not registered.
    """
    if source not in _LOADER_REGISTRY:
        available = ", ".join(sorted(_LOADER_REGISTRY.keys())) if _LOADER_REGISTRY else "none"
        msg = f"Unknown taxonomy source: {source!r}. Available sources: {available}"
        raise ValueError(msg)
    return _LOADER_REGISTRY[source]
