"""Deduplication pipeline for semantic overlap between mt_ and mtc_ topics.

Standalone CLI that analyzes semantic overlap between translated mt_ topics
and China-specific mtc_ topics from a taxonomy source, producing a
dedup_mapping.json file.

Usage:
    python -m os_taxonomy.dedup --source beijing [--output PATH] [--fallback] [--threshold 0.8]

Modes:
    fallback — rule-based similarity using difflib.SequenceMatcher on
        name_zh pairs (no external dependencies, default when --fallback).
    llm      — LLM-based semantic classification via the OpenAI API.
        Currently a stub: prints a note about needing API credentials and
        falls back to the rule-based behavior. Real LLM integration will
        be added manually.
"""

from __future__ import annotations

import argparse
import difflib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from packages.os_taxonomy.loaders import get_loader
from packages.os_taxonomy.types import NormalizedTopic

MT_PREFIX = "mt_"
MTC_PREFIX = "mtc_"

# Minimum similarity ratio for a "subset" classification (fallback mode)
_RATIO_SUBSET = 0.5

_DATA_DIR = Path(__file__).parent

__all__ = [
    "DedupStats",
    "main",
    "run_dedup",
]


@dataclass
class DedupStats:
    """Summary statistics for a deduplication run."""

    subjects_analyzed: int = 0
    pairs_compared: int = 0
    merges: int = 0
    hides: int = 0
    keeps: int = 0

    def print_summary(self) -> None:
        """Print a human-readable summary of the run."""
        print("=== Deduplication summary ===")
        print(f"Subjects analyzed : {self.subjects_analyzed}")
        print(f"Pairs compared    : {self.pairs_compared}")
        print(f"Merge suggested   : {self.merges}")
        print(f"Hide mtc suggested: {self.hides}")
        print(f"Keep both         : {self.keeps}")


# ---------------------------------------------------------------------------
# Core dedup logic
# ---------------------------------------------------------------------------


def _similarity(name_a: str | None, name_b: str | None) -> float:
    """Compute name similarity via difflib.SequenceMatcher.

    Empty/None names yield 0.0; identical names yield 1.0.
    """
    a = (name_a or "").strip()
    b = (name_b or "").strip()
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    return difflib.SequenceMatcher(None, a, b).ratio()


def _best_mt_match(
    mtc_topic: NormalizedTopic,
    mt_topics: list[NormalizedTopic],
    threshold: float,
) -> tuple[str, str, float] | None:
    """Pick the best matching mt_ topic for an mtc_ topic.

    Returns (mt_topic_key, overlap_type, ratio) for the highest-similarity
    pair, or None if there is no mt_ candidate.
    """
    best_key: str | None = None
    best_ratio = 0.0
    for mt_topic in mt_topics:
        ratio = _similarity(mtc_topic.name_zh, mt_topic.name_zh)
        if ratio > best_ratio:
            best_key = mt_topic.topic_key
            best_ratio = ratio
    if best_key is None:
        return None
    if best_ratio >= threshold:
        return best_key, "equivalent", best_ratio
    if best_ratio >= _RATIO_SUBSET:
        return best_key, "subset", best_ratio
    return best_key, "none", best_ratio


def run_dedup(
    topics: list[NormalizedTopic],
    mode: str = "fallback",
    threshold: float = 0.8,
) -> list[dict[str, Any]]:
    """Run the deduplication pipeline over a flat topic list.

    Splits topics into mt_ (translated) and mtc_ (China-specific) sets,
    groups both by subject, and for each subject that has topics in both
    sets, pairs each mtc_ topic against the best-matching mt_ topic.

    Args:
        topics: Normalized topics from a single taxonomy source.
        mode: "fallback" for rule-based similarity, "llm" for LLM-based
            classification (currently a stub that behaves like fallback).
        threshold: Similarity ratio threshold for the "equivalent" class.

    Returns:
        A list of mapping dicts, one per mtc_ topic, each with keys
        mtc_topic_key, mt_topic_key, overlap_type, and action.
        Subjects with only mtc_ topics get action "keep_both" and
        mt_topic_key None.
    """
    if mode not in ("fallback", "llm"):
        raise ValueError(f"Unknown dedup mode: {mode!r}")

    if mode == "llm":
        print(
            "Note: LLM mode requires OpenAI API credentials (OPENAI_API_KEY). "
            "No credentials configured — defaulting to fallback rule-based behavior."
        )

    mt_topics = [t for t in topics if t.topic_key.startswith(MT_PREFIX)]
    mtc_topics = [t for t in topics if t.topic_key.startswith(MTC_PREFIX)]

    mt_by_subject: dict[str, list[NormalizedTopic]] = {}
    mtc_by_subject: dict[str, list[NormalizedTopic]] = {}
    for topic in mt_topics:
        mt_by_subject.setdefault(topic.subject, []).append(topic)
    for topic in mtc_topics:
        mtc_by_subject.setdefault(topic.subject, []).append(topic)

    mappings: list[dict[str, Any]] = []
    stats = DedupStats()
    subjects = sorted(set(mt_by_subject) | set(mtc_by_subject))
    subjects_with_both = [
        s for s in subjects if s in mt_by_subject and s in mtc_by_subject
    ]
    stats.subjects_analyzed = len(subjects_with_both)

    for subject in subjects:
        subject_mtc = mtc_by_subject.get(subject, [])
        subject_mt = mt_by_subject.get(subject, [])

        if not subject_mt:
            # Only mtc_ topics in this subject — nothing to compare against.
            for mtc_topic in subject_mtc:
                mappings.append(
                    {
                        "mtc_topic_key": mtc_topic.topic_key,
                        "mt_topic_key": None,
                        "overlap_type": "none",
                        "action": "keep_both",
                    }
                )
                stats.keeps += 1
            continue

        for mtc_topic in subject_mtc:
            match = _best_mt_match(mtc_topic, subject_mt, threshold)
            if match is None:
                continue
            mt_key, _overlap_type, ratio = match
            stats.pairs_compared += 1
            # Action derives from the best-match ratio: >= threshold -> merge,
            # >= _RATIO_SUBSET -> hide_mtc, otherwise keep_both.
            if ratio >= threshold:
                action = "merge"
            elif ratio >= _RATIO_SUBSET:
                action = "hide_mtc"
            else:
                action = "keep_both"
            if action == "merge":
                stats.merges += 1
            elif action == "hide_mtc":
                stats.hides += 1
            else:
                stats.keeps += 1
            mappings.append(
                {
                    "mtc_topic_key": mtc_topic.topic_key,
                    "mt_topic_key": mt_key,
                    "overlap_type": _overlap_type,
                    "action": action,
                }
            )

    return mappings


def summarize(mappings: list[dict[str, Any]], subjects_analyzed: int = 0) -> DedupStats:
    """Compute summary statistics from a list of mappings."""
    stats = DedupStats(subjects_analyzed=subjects_analyzed)
    stats.pairs_compared = sum(1 for m in mappings if m.get("mt_topic_key") is not None)
    for m in mappings:
        action = m.get("action")
        if action == "merge":
            stats.merges += 1
        elif action == "hide_mtc":
            stats.hides += 1
        elif action == "keep_both":
            stats.keeps += 1
    return stats


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def _default_output_path() -> Path:
    """Default output path: dedup_mapping.json in the Beijing data directory.

    Writes to ``server/data/os-taxonomy-beijing/data/dedup_mapping.json``
    (matching where the seed script's ``load_dedup_mapping()`` searches).
    Falls back to the package directory if the Beijing data dir is absent.
    """
    # Match BeijingLoader's default data dir resolution
    beijing_data_dir = (
        Path(__file__).resolve().parent.parent.parent.parent
        / "data"
        / "os-taxonomy-beijing"
        / "data"
    )
    if beijing_data_dir.is_dir():
        return beijing_data_dir / "dedup_mapping.json"
    return _DATA_DIR / "dedup_mapping.json"


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns a process exit code."""
    parser = argparse.ArgumentParser(
        prog="python -m os_taxonomy.dedup",
        description=(
            "Analyze semantic overlap between translated mt_ topics and "
            "China-specific mtc_ topics, producing dedup_mapping.json."
        ),
    )
    parser.add_argument(
        "--source",
        default="beijing",
        help="Taxonomy data source (default: beijing)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output file path (default: dedup_mapping.json in the data dir)",
    )
    parser.add_argument(
        "--fallback",
        action="store_true",
        help="Use rule-based similarity instead of LLM",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.8,
        help="Similarity threshold for fallback mode (default: 0.8)",
    )
    args = parser.parse_args(argv)

    mode = "fallback" if args.fallback else "llm"

    try:
        loader = get_loader(args.source)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    topics = loader.load_topics()
    mappings = run_dedup(topics, mode=mode, threshold=args.threshold)

    mt_subjects = {t.subject for t in topics if t.topic_key.startswith(MT_PREFIX)}
    subjects_analyzed = len(
        {
            t.subject
            for t in topics
            if t.topic_key.startswith(MTC_PREFIX) and t.subject in mt_subjects
        }
    )
    stats = summarize(mappings, subjects_analyzed)
    stats.print_summary()

    output_path = Path(args.output) if args.output else _default_output_path()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(mappings, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(f"Wrote {len(mappings)} mappings to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
