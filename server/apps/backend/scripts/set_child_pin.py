#!/usr/bin/env python3
"""Set emoji PIN for child accounts.

Usage:
    uv run python scripts/set_child_pin.py --username xiaobao --pin "🐰🥕🌈⭐"
    uv run python scripts/set_child_pin.py --username dabao --pin "🌟🎁🎈🎊"
"""

import argparse
import sys

import bcrypt

from packages.db.models.user import User
from packages.db.session import SessionLocal


def set_child_pin(username: str, pin: str) -> bool:
    """Set emoji PIN for a child user.

    Args:
        username: Child's username
        pin: 4-emoji PIN string

    Returns:
        True if successful, False otherwise
    """
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        if not user:
            print(f"✗ User '{username}' not found")
            return False

        if user.role != "child":
            print(f"✗ User '{username}' is not a child account (role: {user.role})")
            return False

        # Generate bcrypt hash
        pin_hash = bcrypt.hashpw(pin.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        user.pin_hash = pin_hash
        db.commit()

        print(f"✓ Set PIN for {username} (display_name: {user.display_name})")
        print(f"  PIN: {pin}")
        print(f"  Hash: {pin_hash[:50]}...")
        return True

    except Exception as e:
        print(f"✗ Error setting PIN: {e}")
        db.rollback()
        return False
    finally:
        db.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Set emoji PIN for child accounts")
    parser.add_argument("--username", required=True, help="Child's username")
    parser.add_argument("--pin", required=True, help="4-emoji PIN string")
    args = parser.parse_args()

    # Validate PIN length (should be 4 emojis)
    if len(args.pin) != 4:
        print(f"⚠️  Warning: PIN length is {len(args.pin)} characters (expected 4 emojis)")

    success = set_child_pin(args.username, args.pin)
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())