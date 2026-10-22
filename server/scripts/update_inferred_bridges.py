"""Generate and persist inferred cross-subject bridge edges.

Usage::

    cd server
    uv run python scripts/update_inferred_bridges.py [--taxonomy os-taxonomy]

Deletes all previously inferred edges (``source_type='inferred'``) and
regenerates them from the current topic data.  Explicit edges are
never touched.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure the server workspace is importable.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from packages.db.session import SessionLocal
from packages.db.models.learning.topic import LearningDependency


def update_inferred_bridges(
    source_taxonomy: str = "os-taxonomy",
    dry_run: bool = False,
) -> dict:
    """Remove old inferred edges, generate new ones, and persist.

    Returns a summary dict with counts.
    """
    from apps.backend.app.services.learning.bridge_inference import (
        infer_cross_subject_bridges,
    )

    db = SessionLocal()
    try:
        # 1. Delete previously inferred edges
        deleted = (
            db.query(LearningDependency)
            .filter(LearningDependency.source_type == "inferred")
            .delete()
        )

        if dry_run:
            # Just report what would happen
            bridges = infer_cross_subject_bridges(db, source_taxonomy)
            print(f"Would delete {deleted} inferred edges")
            print(f"Would insert {len(bridges)} new inferred edges")
            # Show distribution
            from packages.db.models.learning.topic import LearningTopic

            id_to_topic = {
                t.id: t
                for t in db.query(LearningTopic).filter(
                    LearningTopic.source_taxonomy == source_taxonomy,
                    LearningTopic.deprecated.is_(False),
                )
            }
            domain_pairs: dict[tuple[str, str, str, str], int] = {}
            for b in bridges:
                ft = id_to_topic.get(b.topic_id)
                pt = id_to_topic.get(b.prerequisite_id)
                if ft and pt:
                    key = (ft.domain or "", ft.subject, pt.domain or "", pt.subject)
                    domain_pairs[key] = domain_pairs.get(key, 0) + 1
            print("\nDomain-pair distribution:")
            for (fd, fs, td, ts), cnt in sorted(
                domain_pairs.items(), key=lambda x: -x[1]
            ):
                print(f"  {fs}/{fd} -> {ts}/{td}: {cnt} edges")
            return {"deleted": deleted, "inserted": len(bridges), "dry_run": True}

        db.commit()
        print(f"Deleted {deleted} inferred edges")

        # 2. Generate new inferred bridges
        bridges = infer_cross_subject_bridges(db, source_taxonomy)
        print(f"Generated {len(bridges)} inferred bridge edges")

        # 3. Insert
        for b in bridges:
            db.add(
                LearningDependency(
                    topic_id=b.topic_id,
                    prerequisite_id=b.prerequisite_id,
                    strength=b.strength,
                    reason=b.reason,
                    source_type="inferred",
                    confidence=b.confidence,
                )
            )
        db.commit()
        print(f"Inserted {len(bridges)} inferred edges")

        return {"deleted": deleted, "inserted": len(bridges)}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Regenerate inferred cross-subject bridge edges"
    )
    parser.add_argument(
        "--taxonomy",
        default="os-taxonomy",
        help="Source taxonomy to generate bridges for (default: os-taxonomy)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be generated without writing",
    )
    args = parser.parse_args()

    result = update_inferred_bridges(
        source_taxonomy=args.taxonomy, dry_run=args.dry_run
    )
    print(f"\nSummary: {result}")


if __name__ == "__main__":
    main()
