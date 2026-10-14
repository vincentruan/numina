"""Coverage report CLI tool.

Usage:
    cd server
    uv run python -m apps.backend.scripts.coverage_report --subject mathematics --format table
    uv run python -m apps.backend.scripts.coverage_report --gap-only --output gaps.json
"""
from __future__ import annotations

import argparse
import json

from packages.db.session import SessionLocal
from apps.backend.app.services.learning.coverage_service import (
    compute_subject_coverage,
    get_gap_report,
)


def _print_table(rows: list[dict], columns: list[str]) -> None:
    """Print rows as a simple text table."""
    if not rows:
        print("(no data)")
        return
    widths = {c: max(len(c), max(len(str(r.get(c, ""))) for r in rows)) for c in columns}
    header = "  ".join(c.ljust(widths[c]) for c in columns)
    print(header)
    print("-" * len(header))
    for row in rows:
        print("  ".join(str(row.get(c, "")).ljust(widths[c]) for c in columns))


def main() -> None:
    parser = argparse.ArgumentParser(description="Coverage report")
    parser.add_argument("--subject", type=str, help="Filter by subject")
    parser.add_argument("--gap-only", action="store_true", help="Show only gaps")
    parser.add_argument("--threshold", type=float, default=0.5)
    parser.add_argument("--format", choices=["table", "json"], default="table")
    parser.add_argument("--output", type=str, help="Output file path")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        if args.gap_only:
            gaps = get_gap_report(db, subject=args.subject, threshold=args.threshold)
            if args.format == "json" or args.output:
                data = json.dumps(gaps, indent=2, ensure_ascii=False)
                if args.output:
                    with open(args.output, "w") as f:
                        f.write(data)
                    print(f"Gap report written to {args.output} ({len(gaps)} gaps)")
                else:
                    print(data)
            else:
                _print_table(gaps, ["topic_key", "name", "subject", "domain",
                                    "coverage_score", "prerequisite_value"])
        else:
            from packages.db.models.learning.topic import LearningTopic
            subjects = (
                db.query(LearningTopic.subject)
                .filter(LearningTopic.subject.isnot(None), LearningTopic.deprecated == False)
                .distinct().all()
            )
            results = []
            for (subj,) in subjects:
                if args.subject and subj != args.subject:
                    continue
                s = compute_subject_coverage(db, subj)
                results.append(s)

            if args.format == "json":
                print(json.dumps(results, indent=2))
            else:
                _print_table(results, ["subject", "total_topics", "covered_topics",
                                       "coverage_rate", "avg_prerequisite_value"])
    finally:
        db.close()


if __name__ == "__main__":
    main()
