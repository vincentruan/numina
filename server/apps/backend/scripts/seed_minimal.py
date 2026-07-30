"""Minimal seed script using raw SQL to avoid SQLAlchemy RETURNING issues."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

import os
from datetime import UTC, datetime, timezone

from sqlalchemy import text

from apps.backend.app.models.family_mcp_server import FamilyMCPServer
from packages.db.session import SessionLocal


def _next_snowflake_id():
    """Generate a new Snowflake ID via the shared package."""
    from packages.core.snowflake import next_id

    return next_id()


def _ensure_demouser_family(db):
    """Find or create the demouser and its family.

    Uses real Snowflake IDs so the created records match the actual database
    sequence used by the application. Hard-coding IDs caused provider configs
    to be inserted for non-existent families in the past.
    """
    result = db.execute(text("SELECT id, family_id FROM users WHERE username = 'demouser'"))
    user_row = result.fetchone()

    if user_row:
        user_id, family_id = user_row
        print(f"demouser already exists: user_id={user_id}, family_id={family_id}")
        return user_id, family_id

    # Create family and user with Snowflake IDs
    family_id = _next_snowflake_id()
    invite_code = "DEMO01"
    now = datetime.now(UTC).replace(tzinfo=None)
    db.execute(
        text("""
            INSERT INTO families (id, name, invite_code, created_by, created_at, updated_at)
            VALUES (:fid, 'Demo Family', :code, :fid, :now, :now)
        """),
        {"fid": family_id, "code": invite_code, "now": now},
    )

    user_id = _next_snowflake_id()
    # bcrypt hash for "DemoPass123" (rounds=12)
    password_hash = "$2b$12$Mv4RrX/3j/3URnofmYiNs.2Usj596itM3yQN7cGHEnOhtHxp.Tfoy"
    db.execute(
        text("""
            INSERT INTO users (id, username, display_name, password_hash, family_id, role, is_active, created_at, updated_at)
            VALUES (:uid, 'demouser', 'Demo User', :hash, :fid, 'owner', 1, :now, :now)
        """),
        {"uid": user_id, "hash": password_hash, "fid": family_id, "now": now},
    )

    print(f"Created demouser: user_id={user_id}, family_id={family_id}")
    return user_id, family_id


def _ensure_invitation_code(db, family_id):
    """Ensure the demo invitation code points at the demouser family."""
    now = datetime.now(UTC).replace(tzinfo=None)
    result = db.execute(text("SELECT code FROM family_invitation_codes WHERE code = 'DEMO-CODE'"))
    if not result.fetchone():
        db.execute(
            text("""
                INSERT INTO family_invitation_codes (id, code, is_used, used_at, used_by_family_id, used_by_username)
                VALUES (:cid, 'DEMO-CODE', 1, :now, :fid, 'demouser')
            """),
            {"cid": _next_snowflake_id(), "now": now, "fid": family_id},
        )
        print("Created invitation code: DEMO-CODE")
    else:
        db.execute(
            text("""
                UPDATE family_invitation_codes
                SET is_used = 1, used_at = :now, used_by_family_id = :fid, used_by_username = 'demouser'
                WHERE code = 'DEMO-CODE'
            """),
            {"now": now, "fid": family_id},
        )


def _ensure_mcp_server(db, family_id):
    """Ensure the 'Numina Backend MCP' server entry exists for the family.

    This is the per-family MCP server record that tells the agent where to
    find the backend's internal MCP SSE endpoint for querying family data.
    Normally created by auth.py during register(), but seed_minimal bypasses
    the registration flow, so we must create it explicitly.
    """
    existing = (
        db.query(FamilyMCPServer)
        .filter_by(family_id=family_id, name="Numina Backend MCP")
        .first()
    )
    if existing:
        print(f"MCP server already exists for family {family_id}: url={existing.url}")
        return existing

    backend_url = os.environ.get("BACKEND_BASE_URL", "http://localhost:8000")
    mcp_url = f"{backend_url}/api/v1/internal/mcp/{family_id}/sse"

    server = FamilyMCPServer(
        id=_next_snowflake_id(),
        family_id=family_id,
        name="Numina Backend MCP",
        url=mcp_url,
        transport="sse",
        is_enabled=True,
        mcp_type="backend",
    )
    db.add(server)
    db.commit()
    print(f"Created MCP server for family {family_id}: url={mcp_url}")
    return server


def seed_minimal():
    """Create minimal test data using raw SQL."""
    db = SessionLocal()

    try:
        user_id, family_id = _ensure_demouser_family(db)
        _ensure_invitation_code(db, family_id)
        _ensure_mcp_server(db, family_id)
        db.commit()

        # Now create AI config for demouser family
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            print("\nERROR: ANTHROPIC_API_KEY not set")
            print("Set it: export ANTHROPIC_API_KEY='your-key-here'")
            return

        # Check existing AI config
        result = db.execute(
            text("SELECT id, provider, model_id FROM ai_providers WHERE family_id = :fid"),
            {"fid": family_id},
        )
        config_row = result.fetchone()

        if config_row:
            config_id, provider, model_id = config_row
            print(f"\nAI config already exists: provider={provider}, model={model_id}")
            return

        from apps.backend.app.models.ai_provider_config import AIProviderConfig
        from apps.backend.app.services.ai_crypto import encrypt_api_key

        encrypted_key = encrypt_api_key(api_key)

        config = AIProviderConfig(
            id=_next_snowflake_id(),
            family_id=family_id,
            name="Claude Sonnet 4.6",
            provider="anthropic",
            api_key_encrypted=encrypted_key,
            base_url=None,
            model_id="claude-sonnet-4-6",
            vision_model_id="claude-sonnet-4-6",
            timeout_seconds=120,
            thinking_supported=True,
            is_active=True,
            provider_name="Anthropic",
            display_order=0,
            model_1_capabilities='["text_generation", "deep_thinking"]',
        )
        db.add(config)
        db.commit()

        print("\nCreated AI config for demouser family:")
        print(f"  family_id: {family_id}")
        print(f"  Provider: {config.provider}")
        print(f"  Model: {config.model_id} (supports extended thinking)")
        print(f"  Active: {config.is_active}")

    finally:
        db.close()


if __name__ == "__main__":
    print("=" * 60)
    print("Minimal seed for AI testing")
    print("=" * 60)
    seed_minimal()
    print("=" * 60)
    print("Done!")
