"""Minimal seed script using raw SQL to avoid SQLAlchemy RETURNING issues."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from packages.db.session import SessionLocal, engine
from sqlalchemy import text
from datetime import datetime
import os

def seed_minimal():
    """Create minimal test data using raw SQL."""
    db = SessionLocal()

    try:
        # Check for existing user
        result = db.execute(text("SELECT id, family_id FROM users WHERE username = 'demouser'"))
        user_row = result.fetchone()

        if user_row:
            user_id, family_id = user_row
            print(f"demouser already exists: user_id={user_id}, family_id={family_id}")
        else:
            # Create family using raw SQL (bypasses RETURNING clause)
            family_id = 123456789012345
            invite_code = "DEMO01"
            db.execute(text("""
                INSERT INTO families (id, name, invite_code, created_by, created_at, updated_at)
                VALUES (:fid, 'Demo Family', :code, :fid, :now, :now)
            """), {"fid": family_id, "code": invite_code, "now": datetime.utcnow()})

            # Create user
            user_id = 123456789012346
            # Use bcrypt hash for "DemoPass123" (rounds=12)
            password_hash = "$2b$12$Mv4RrX/3j/3URnofmYiNs.2Usj596itM3yQN7cGHEnOhtHxp.Tfoy"
            db.execute(text("""
                INSERT INTO users (id, username, display_name, password_hash, family_id, role, is_active, created_at, updated_at)
                VALUES (:uid, 'demouser', 'Demo User', :hash, :fid, 'owner', 1, :now, :now)
            """), {"uid": user_id, "hash": password_hash, "fid": family_id, "now": datetime.utcnow()})

            print(f"Created demouser: user_id={user_id}, family_id={family_id}")

        # Check for invitation code and link it to the family
        result = db.execute(text("SELECT code FROM family_invitation_codes WHERE code = 'DEMO-CODE'"))
        if not result.fetchone():
            from packages.core.snowflake import next_id as _next_id
            db.execute(text("""
                INSERT INTO family_invitation_codes (id, code, is_used, used_at, used_by_family_id, used_by_username)
                VALUES (:cid, 'DEMO-CODE', 1, :now, :fid, 'demouser')
            """), {"cid": _next_id(), "now": datetime.utcnow(), "fid": family_id})
            print("Created invitation code: DEMO-CODE")
        else:
            db.execute(text("""
                UPDATE family_invitation_codes
                SET is_used = 1, used_at = :now, used_by_family_id = :fid, used_by_username = 'demouser'
                WHERE code = 'DEMO-CODE'
            """), {"now": datetime.utcnow(), "fid": family_id})

        db.commit()

        # Now create AI config for demouser family
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            print("\nERROR: ANTHROPIC_API_KEY not set")
            print("Set it: export ANTHROPIC_API_KEY='your-key-here'")
            return

        # Check existing AI config
        result = db.execute(text("SELECT id, provider, model_id FROM ai_providers WHERE family_id = :fid"), {"fid": family_id})
        config_row = result.fetchone()

        if config_row:
            config_id, provider, model_id = config_row
            print(f"\nAI config already exists: provider={provider}, model={model_id}")
        else:
            # Import encryption function
            from apps.backend.app.services.ai_crypto import encrypt_api_key
            encrypted_key = encrypt_api_key(api_key)

            config_id = 123456789012347
            db.execute(text("""
                INSERT INTO ai_providers
                (id, family_id, name, provider, api_key_encrypted, model_id, vision_model_id, timeout_seconds, is_active, created_at, updated_at)
                VALUES
                (:cid, :fid, 'Claude Sonnet 4.6', 'anthropic', :key, 'claude-sonnet-4-6', 'claude-sonnet-4-6', 120, 1, :now, :now)
            """), {
                "cid": config_id,
                "fid": family_id,
                "key": encrypted_key,
                "now": datetime.utcnow()
            })
            db.commit()

            print(f"\nCreated AI config for demouser family:")
            print(f"  Provider: anthropic")
            print(f"  Model: claude-sonnet-4-6 (supports extended thinking)")
            print(f"  Active: True")

    finally:
        db.close()

if __name__ == "__main__":
    print("=" * 60)
    print("Minimal seed for AI testing")
    print("=" * 60)
    seed_minimal()
    print("=" * 60)
    print("Done!")