"""os-taxonomy — Learning OS knowledge graph data with Chinese translations.

This package contains the os-taxonomy knowledge graph data (topics, dependencies,
clusters) with Chinese translations merged in. The English source comes from the
os-taxonomy project; Chinese translations are generated via LLM and exported
from the database.

Files:
    topics.json       — 1,590 learning topics with *_zh translation fields
    clusters.json     — 183 topic clusters with summary_zh
    dependencies.json — 3,221 prerequisite relationships (no translation needed)

Usage:
    from packages.os_taxonomy import get_topics, get_clusters

    topics = get_topics()        # list of topic dicts with nameZh, descriptionZh, etc.
    clusters = get_clusters()    # list of cluster dicts with summaryZh
"""

import json
from pathlib import Path

_DATA_DIR = Path(__file__).parent


def get_topics() -> list[dict]:
    """Load topics with Chinese translations."""
    with open(_DATA_DIR / "topics.json", encoding="utf-8") as f:
        return json.load(f)["topics"]


def get_clusters() -> list[dict]:
    """Load clusters with Chinese translations."""
    with open(_DATA_DIR / "clusters.json", encoding="utf-8") as f:
        return json.load(f)["clusters"]


def get_dependencies() -> list[dict]:
    """Load topic dependencies (prerequisite relationships)."""
    with open(_DATA_DIR / "dependencies.json", encoding="utf-8") as f:
        return json.load(f).get("dependencies", [])
