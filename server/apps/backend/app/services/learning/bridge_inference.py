"""Cross-subject bridge inference via keyword overlap.

Generates candidate bridge edges between topics of different subjects
based on shared keywords in their names.  Bridges are *inferred*, not
human-reviewed, so they carry a ``source_type="inferred"`` marker and
a ``confidence`` score.

The algorithm:

1. Build an inverted keyword index across all non-deprecated topics.
2. For each keyword, find topic pairs that share it and belong to
   different subjects.
3. Compute the *overlap coefficient* (shared keywords / min of both
   keyword sets) weighted by inverse document frequency to down-weight
   generic terms like "how" or "life".
4. Aggregate topic-level candidates to the domain-pair level.
5. Keep only domain pairs with at least ``min_topic_links`` supporting
   topic edges and an average confidence above ``min_confidence``.
"""

from __future__ import annotations

import math
import re
from collections import defaultdict
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from packages.db.models.learning.topic import LearningDependency, LearningTopic

# Words too common to carry semantic signal across subjects.
_STOP_WORDS: frozenset[str] = frozenset({
    "a", "an", "and", "are", "as", "at", "be", "between", "build", "builds",
    "built", "by", "can", "compare", "create", "creates", "data", "describe",
    "describes", "did", "do", "does", "doing", "done", "draw", "each", "early",
    "every", "for", "from", "get", "give", "gives", "gave", "given", "go",
    "going", "had", "has", "have", "how", "i", "if", "in", "into", "is", "it",
    "its", "know", "knew", "known", "late", "learn", "learning", "like", "look",
    "looked", "looking", "make", "makes", "making", "many", "me", "more", "most",
    "my", "new", "not", "of", "on", "one", "or", "our", "out", "over", "own",
    "past", "read", "reads", "same", "see", "she", "show", "showed", "shown",
    "simple", "so", "some", "step", "still", "steps", "such", "take", "tell",
    "than", "that", "the", "their", "them", "then", "there", "these", "they",
    "this", "to", "try", "two", "understanding", "up", "use", "used", "using",
    "very", "walk", "walks", "we", "what", "when", "which", "who", "why",
    "will", "with", "work", "working", "world", "you", "your",
})

#: Age-group ordering for adjacency check.
_AGE_ORDER = {"low": 0, "mid": 1, "high": 2}


@dataclass
class _TopicInfo:
    id: int
    subject: str
    domain: str
    name: str
    age_group: str
    keywords: set[str] = field(default_factory=set)


@dataclass
class InferredBridge:
    """A candidate cross-subject dependency edge."""

    topic_id: int
    prerequisite_id: int
    strength: str
    reason: str
    confidence: float


def _extract_keywords(name: str | None) -> set[str]:
    if not name:
        return set()
    words = re.findall(r"[a-zA-Z]+", name.lower())
    return {w for w in words if w not in _STOP_WORDS and len(w) > 1}


def _age_compatible(a: str, b: str) -> bool:
    """Same or adjacent age groups."""
    return abs(_AGE_ORDER.get(a, 1) - _AGE_ORDER.get(b, 1)) <= 1


def _tfidf_weighted_overlap(
    kw_a: set[str],
    kw_b: set[str],
    idf: dict[str, float],
) -> float:
    """Weighted overlap coefficient using IDF to down-weight generic terms."""
    shared = kw_a & kw_b
    if not shared:
        return 0.0
    shared_weight = sum(idf.get(w, 1.0) for w in shared)
    min_weight = min(
        sum(idf.get(w, 1.0) for w in kw_a),
        sum(idf.get(w, 1.0) for w in kw_b),
    )
    if min_weight == 0:
        return 0.0
    return shared_weight / min_weight


def infer_cross_subject_bridges(
    db: Session,
    source_taxonomy: str,
    *,
    min_confidence: float = 0.35,
    min_topic_links: int = 2,
) -> list[InferredBridge]:
    """Generate inferred cross-subject bridge edges.

    Returns a list of :class:`InferredBridge` objects ready to be inserted
    into ``learning_dependencies`` with ``source_type="inferred"``.

    Parameters
    ----------
    db:
        Active database session.
    source_taxonomy:
        Which taxonomy's topics to consider (e.g. ``"os-taxonomy"``).
    min_confidence:
        Minimum aggregated confidence for a domain-pair bridge.
    min_topic_links:
        Minimum number of topic-level edges supporting a domain-pair bridge.
    """
    topics = (
        db.query(LearningTopic)
        .filter(
            LearningTopic.source_taxonomy == source_taxonomy,
            LearningTopic.deprecated.is_(False),
        )
        .all()
    )

    if not topics:
        return []

    # Build topic info objects with keywords
    infos: list[_TopicInfo] = []
    for t in topics:
        kws = _extract_keywords(t.name)
        if kws:
            infos.append(
                _TopicInfo(
                    id=t.id,
                    subject=t.subject,
                    domain=t.domain or "",
                    name=t.name or "",
                    age_group=t.age_group,
                    keywords=kws,
                )
            )

    if not infos:
        return []

    # Compute IDF from the topic corpus (smoothed to avoid negative values
    # when a keyword is very common).
    n_docs = len(infos)
    df: dict[str, int] = defaultdict(int)
    for info in infos:
        for w in info.keywords:
            df[w] += 1
    idf: dict[str, float] = {
        w: math.log((n_docs + 1) / (freq + 1)) + 1.0 for w, freq in df.items()
    }

    # Build inverted index: keyword -> list of topic indices
    kw_index: dict[str, list[int]] = defaultdict(list)
    for idx, info in enumerate(infos):
        for w in info.keywords:
            kw_index[w].append(idx)

    # Existing explicit edge set (avoid duplicates)
    existing_edges: set[tuple[int, int]] = set()
    for dep in db.query(
        LearningDependency.topic_id, LearningDependency.prerequisite_id
    ).all():
        existing_edges.add((dep.topic_id, dep.prerequisite_id))

    # Find candidate topic pairs via shared keywords
    # topic_pair -> list of shared keywords
    pair_shared: dict[tuple[int, int], set[str]] = defaultdict(set)
    for _kw, indices in kw_index.items():
        for i, idx_a in enumerate(indices):
            for idx_b in indices[i + 1 :]:
                a, b = infos[idx_a], infos[idx_b]
                # Different subjects only
                if a.subject == b.subject:
                    continue
                # Age-compatible
                if not _age_compatible(a.age_group, b.age_group):
                    continue
                pair_shared[(idx_a, idx_b)].add(_kw)

    # Score each pair
    # Aggregate by domain pair: (from_domain, from_subject, to_domain, to_subject)
    # -> list of (confidence, topic_id, prereq_id)
    domain_pair_scores: dict[
        tuple[str, str, str, str], list[tuple[float, int, int]]
    ] = defaultdict(list)

    for (idx_a, idx_b) in pair_shared:
        a, b = infos[idx_a], infos[idx_b]
        overlap = _tfidf_weighted_overlap(a.keywords, b.keywords, idf)
        if overlap < 0.2:
            continue

        # Direction: lower centrality → higher centrality (prerequisite)
        # Without centrality data, use alphabetical subject as tiebreaker
        # to ensure stable direction.
        topic_id = a.id
        prereq_id = b.id
        # We want the edge to point from the "dependent" topic to its
        # "prerequisite".  Without semantic direction, we use the existing
        # bridge directionality convention: the edge goes from the topic
        # whose subject comes later alphabetically to the one that comes
        # earlier.  This is arbitrary but stable.
        if a.subject > b.subject:
            topic_id, prereq_id = a.id, b.id
        else:
            topic_id, prereq_id = b.id, a.id

        if (topic_id, prereq_id) in existing_edges:
            continue

        confidence = min(overlap, 1.0)
        domain_key = (
            a.domain if a.id == topic_id else b.domain,
            a.subject if a.id == topic_id else b.subject,
            b.domain if b.id == prereq_id else a.domain,
            b.subject if b.id == prereq_id else a.subject,
        )
        domain_pair_scores[domain_key].append((confidence, topic_id, prereq_id))

    # Filter domain pairs by min_topic_links and min_confidence
    bridges: list[InferredBridge] = []
    seen_edges: set[tuple[int, int]] = set()

    for scores in domain_pair_scores.values():
        if len(scores) < min_topic_links:
            continue
        avg_conf = sum(c for c, _, _ in scores) / len(scores)
        if avg_conf < min_confidence:
            continue

        # Create individual topic-level edges
        for _, tid, pid in scores:
            if (tid, pid) in seen_edges:
                continue
            seen_edges.add((tid, pid))
            bridges.append(
                InferredBridge(
                    topic_id=tid,
                    prerequisite_id=pid,
                    strength="soft",
                    reason="Inferred cross-subject bridge via keyword overlap",
                    confidence=round(avg_conf, 3),
                )
            )

    return bridges
