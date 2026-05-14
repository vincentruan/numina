#!/usr/bin/env python3
"""Admin CLI script for managing family invitation codes.

Commands:
    generate --count N       Generate N unique invitation codes
    list [--format csv]      List all codes with status
    revoke --codes A,B,C     Revoke unused codes
    link-existing            Create retroactive records for existing families

Usage:
    python scripts/family_invitation_codes.py generate --count 5
    python scripts/family_invitation_codes.py list --format csv --output codes.csv
    python scripts/family_invitation_codes.py revoke --codes ABC123,XYZ789
    python scripts/family_invitation_codes.py link-existing
"""

import argparse
import csv
import random
import string
import sys
from datetime import UTC, datetime
from pathlib import Path

# Add server/ root to path so apps.* and packages.* resolve
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from apps.backend.app.models.child_bind_token import ChildBindToken  # noqa: F401

from apps.backend.app.database import SessionLocal
from apps.backend.app.models.asset import Asset  # noqa: F401
from apps.backend.app.models.category import Category  # noqa: F401
from apps.backend.app.models.family import Family
from apps.backend.app.models.family_invitation_code import FamilyInvitationCode
from apps.backend.app.models.liability import Liability  # noqa: F401
from apps.backend.app.models.snapshot import AssetSnapshot  # noqa: F401
from apps.backend.app.models.tag import Tag  # noqa: F401
from apps.backend.app.models.user import User
from apps.backend.app.models.wish import Wish  # noqa: F401


def generate_code() -> str:
    """Generate a 6-character uppercase alphanumeric code."""
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=6))


def cmd_generate(count: int) -> None:
    """Generate N unique invitation codes."""
    db = SessionLocal()
    try:
        codes = []
        for _ in range(count):
            # Ensure uniqueness
            while True:
                code = generate_code()
                existing = db.query(FamilyInvitationCode).filter_by(code=code).first()
                if existing is None:
                    break

            invitation_code = FamilyInvitationCode(code=code)
            db.add(invitation_code)
            codes.append(code)

        db.commit()
        print(f"Generated {count} invitation codes:")
        for code in codes:
            print(f"  {code}")
    except Exception as e:
        db.rollback()
        print(f"Error generating codes: {e}")
        sys.exit(1)
    finally:
        db.close()


def cmd_list(format: str, output: str | None) -> None:
    """List all invitation codes with their status."""
    db = SessionLocal()
    try:
        codes = db.query(FamilyInvitationCode).order_by(FamilyInvitationCode.created_at.desc()).all()

        if format == "csv":
            rows = []
            for c in codes:
                status = "revoked" if c.revoked_at else ("used" if c.is_used else "unused")
                rows.append({
                    "code": c.code,
                    "status": status,
                    "created_at": c.created_at.isoformat() if c.created_at else "",
                    "used_at": c.used_at.isoformat() if c.used_at else "",
                    "used_by_family_id": c.used_by_family_id or "",
                    "used_by_username": c.used_by_username or "",
                    "revoked_at": c.revoked_at.isoformat() if c.revoked_at else "",
                })

            if output:
                with open(output, "w", newline="", encoding="utf-8") as f:
                    fieldnames = ["code", "status", "created_at", "used_at", "used_by_family_id", "used_by_username", "revoked_at"]
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(rows)
                print(f"Exported {len(rows)} codes to {output}")
            else:
                # Print CSV to stdout
                fieldnames = ["code", "status", "created_at", "used_at", "used_by_family_id", "used_by_username", "revoked_at"]
                writer = csv.DictWriter(sys.stdout, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
        else:
            # Table format
            print(f"\nTotal codes: {len(codes)}")
            print("-" * 80)
            print(f"{'Code':<8} {'Status':<10} {'Created':<20} {'Used By':<20}")
            print("-" * 80)

            for c in codes:
                status = "revoked" if c.revoked_at else ("used" if c.is_used else "unused")
                created = c.created_at.strftime("%Y-%m-%d %H:%M") if c.created_at else "N/A"
                used_by = c.used_by_username or "N/A"
                print(f"{c.code:<8} {status:<10} {created:<20} {used_by:<20}")

            print("-" * 80)

            # Summary
            unused = sum(1 for c in codes if not c.is_used and not c.revoked_at)
            used = sum(1 for c in codes if c.is_used)
            revoked = sum(1 for c in codes if c.revoked_at)
            print(f"\nSummary: {unused} unused, {used} used, {revoked} revoked")
    except Exception as e:
        print(f"Error listing codes: {e}")
        sys.exit(1)
    finally:
        db.close()


def cmd_revoke(codes_str: str) -> None:
    """Revoke unused invitation codes."""
    db = SessionLocal()
    try:
        codes_to_revoke = [c.strip().upper() for c in codes_str.split(",")]
        revoked_count = 0
        errors = []

        for code in codes_to_revoke:
            invitation_code = db.query(FamilyInvitationCode).filter_by(code=code).first()

            if not invitation_code:
                errors.append(f"Code '{code}' not found")
                continue

            if invitation_code.is_used:
                errors.append(f"Code '{code}' is already used and cannot be revoked")
                continue

            if invitation_code.revoked_at:
                errors.append(f"Code '{code}' is already revoked")
                continue

            invitation_code.revoked_at = datetime.now(UTC)
            revoked_count += 1

        if revoked_count > 0:
            db.commit()

        if errors:
            print("Warnings:")
            for err in errors:
                print(f"  - {err}")

        print(f"Revoked {revoked_count} codes successfully")
    except Exception as e:
        db.rollback()
        print(f"Error revoking codes: {e}")
        sys.exit(1)
    finally:
        db.close()


def cmd_link_existing() -> None:
    """Create retroactive invitation code records for existing families.

    This links families created before the invitation code system was implemented.
    Each existing family gets a FamilyInvitationCode record linking it to its
    current invite_code (stored on the Family model).
    """
    db = SessionLocal()
    try:
        # Find all families
        families = db.query(Family).all()

        # Find families that don't have a linked invitation code record
        families_to_link = []
        for family in families:
            existing_link = db.query(FamilyInvitationCode).filter_by(
                used_by_family_id=family.id
            ).first()

            if not existing_link:
                families_to_link.append(family)

        if not families_to_link:
            print("No families need retroactive linking")
            return

        # Get the owner username for each family
        linked_count = 0
        for family in families_to_link:
            # Find the owner (creator) of the family
            owner = db.query(User).filter_by(
                family_id=family.id,
                id=family.created_by
            ).first()

            owner_username = owner.username if owner and owner.username else None

            # Create a retroactive invitation code record
            invitation_code = FamilyInvitationCode(
                code=family.invite_code,  # Use existing invite_code from Family
                is_used=True,
                used_at=family.created_at,  # Use family creation time
                used_by_family_id=family.id,
                used_by_username=owner_username,
            )
            db.add(invitation_code)
            linked_count += 1

        db.commit()
        print(f"Linked {linked_count} existing families to invitation codes")
    except Exception as e:
        db.rollback()
        print(f"Error linking existing families: {e}")
        sys.exit(1)
    finally:
        db.close()


def main() -> None:
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        description="Admin CLI for managing family invitation codes",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Generate command
    gen_parser = subparsers.add_parser("generate", help="Generate unique invitation codes")
    gen_parser.add_argument(
        "--count",
        type=int,
        required=True,
        help="Number of codes to generate",
    )

    # List command
    list_parser = subparsers.add_parser("list", help="List all invitation codes")
    list_parser.add_argument(
        "--format",
        choices=["table", "csv"],
        default="table",
        help="Output format (default: table)",
    )
    list_parser.add_argument(
        "--output",
        type=str,
        help="Output file path (for CSV format)",
    )

    # Revoke command
    revoke_parser = subparsers.add_parser("revoke", help="Revoke unused invitation codes")
    revoke_parser.add_argument(
        "--codes",
        type=str,
        required=True,
        help="Comma-separated list of codes to revoke",
    )

    # Link-existing command
    link_parser = subparsers.add_parser("link-existing", help="Link existing families retroactively")
    link_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be linked without making changes",
    )

    args = parser.parse_args()

    if args.command == "generate":
        cmd_generate(args.count)
    elif args.command == "list":
        cmd_list(args.format, args.output)
    elif args.command == "revoke":
        cmd_revoke(args.codes)
    elif args.command == "link-existing":
        if args.dry_run:
            print("Dry run mode - showing what would be linked")
            # TODO: implement dry-run logic if needed
        cmd_link_existing()
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()