"""Seed production database with test users and families.

This creates the demouser family and other test accounts referenced in tests.
Run from backend/ directory: uv run python scripts/seed_test_data.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

import apps.backend.app.models  # noqa: F401 — registers all ORM models
from apps.backend.app.database import SessionLocal
from apps.backend.app.models.family import Family
from apps.backend.app.models.family_invitation_code import FamilyInvitationCode
from apps.backend.app.models.user import User
from apps.backend.app.models.ai_provider_config import AIProviderConfig
from apps.backend.app.services.auth import hash_password
from apps.backend.app.services.ai_crypto import encrypt_api_key
from packages.core.snowflake import next_id
from datetime import datetime


def seed_test_users(db):
    """Create test families and users."""
    # Create invitation codes
    codes_data = [
        ("AUTO-TEST", "testuser family"),
        ("AUTO-TEST-2", "testuser2 family"),
        ("DEMO-CODE", "demouser family"),
        ("DEMO-SPOUSE", "demouser spouse"),
    ]

    for code, description in codes_data:
        existing = db.query(FamilyInvitationCode).filter_by(code=code).first()
        if not existing:
            db.add(FamilyInvitationCode(code=code))
            print(f"Created invitation code: {code}")

    db.commit()

    # Create families and users
    users_data = [
        {
            "username": "testuser",
            "display_name": "Test User",
            "password": "TestPass123",
            "family_name": "Test Family",
            "role": "owner",
            "invitation_code": "AUTO-TEST",
        },
        {
            "username": "testuser2",
            "display_name": "Test User 2",
            "password": "TestPass456",
            "family_name": "Test Family 2",
            "role": "owner",
            "invitation_code": "AUTO-TEST-2",
        },
        {
            "username": "demouser",
            "display_name": "Demo User",
            "password": "DemoPass123",
            "family_name": "Demo Family",
            "role": "owner",
            "invitation_code": "DEMO-CODE",
        },
    ]

    for user_data in users_data:
        # Check if user exists
        existing_user = db.query(User).filter_by(username=user_data["username"]).first()
        if existing_user:
            print(f"User {user_data['username']} already exists (family_id={existing_user.family_id})")
            continue

        # Create family
        family_id = next_id()
        family = Family(
            id=family_id,
            name=user_data["family_name"],
            created_by=family_id,  # Will be updated after user creation
        )
        db.add(family)
        db.flush()  # Flush to get family.id

        # Create user
        user_id = next_id()
        password_hash = hash_password(user_data["password"])
        user = User(
            id=user_id,
            username=user_data["username"],
            display_name=user_data["display_name"],
            password_hash=password_hash,
            family_id=family.id,
            role=user_data["role"],
            is_active=True,
        )
        db.add(user)
        db.flush()

        # Update family.created_by
        family.created_by = user.id

        print(f"Created user: {user_data['username']} (id={user.id}, family_id={family.id})")

    db.commit()


def seed_ai_configs(db):
    """Create AI provider configs for test families."""
    # Find demouser family
    demouser = db.query(User).filter_by(username="demouser").first()
    if not demouser:
        print("ERROR: demouser not found, cannot create AI config")
        return

    # Check if config already exists
    existing_config = db.query(AIProviderConfig).filter_by(family_id=demouser.family_id).first()
    if existing_config:
        print(f"AI config already exists for family {demouser.family_id}: provider={existing_config.provider}, model={existing_config.model_id}")
        return

    # Create Claude Sonnet 4.6 config
    # IMPORTANT: You need to set ANTHROPIC_API_KEY in your environment
    import os
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not set in environment")
        print("Please set it before running this script:")
        print("  export ANTHROPIC_API_KEY='your-key-here'")
        return

    encrypted_key = encrypt_api_key(api_key)
    config_id = next_id()
    config = AIProviderConfig(
        id=config_id,
        family_id=demouser.family_id,
        name="Claude Sonnet 4.6",
        provider="anthropic",
        api_key_encrypted=encrypted_key,
        model_id="claude-sonnet-4-6",  # Supports extended thinking
        vision_model_id="claude-sonnet-4-6",
        timeout_seconds=120,
        is_active=True,
    )
    db.add(config)
    db.commit()

    print(f"Created AI config for demouser family (family_id={demouser.family_id})")
    print(f"  Provider: {config.provider}")
    print(f"  Model: {config.model_id}")
    print(f"  Active: {config.is_active}")


def main():
    """Run seeding."""
    print("Seeding test users and AI configs...")
    print("=" * 60)

    db = SessionLocal()
    try:
        seed_test_users(db)
        print()
        print("=" * 60)
        seed_ai_configs(db)
        print()
        print("=" * 60)
        print("Seeding complete!")
    finally:
        db.close()


if __name__ == "__main__":
    main()