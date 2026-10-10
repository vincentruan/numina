"""TaxonomyLoader protocol and base types.

Defines the interface that all taxonomy source loaders must implement.
"""

from __future__ import annotations

from typing import Protocol

from packages.os_taxonomy.types import (
    NormalizedCluster,
    NormalizedDependency,
    NormalizedTopic,
)


class TaxonomyLoader(Protocol):
    """Protocol for taxonomy data source loaders.

    Implementations load topics, dependencies, and clusters from a specific
    source (e.g., os-taxonomy, os-taxonomy-beijing) and return normalized
    data structures.
    """

    def load_topics(self) -> list[NormalizedTopic]:
        """Load all topics from this source."""
        ...

    def load_dependencies(self) -> list[NormalizedDependency]:
        """Load all dependency relationships from this source."""
        ...

    def load_clusters(self) -> list[NormalizedCluster]:
        """Load all topic clusters from this source."""
        ...
