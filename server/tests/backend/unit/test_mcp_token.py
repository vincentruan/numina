"""Tests for MCP external API token service and CRUD endpoints."""

import hashlib
from datetime import UTC, datetime, timedelta

import pytest

from apps.backend.app.models.family import Family
from apps.backend.app.models.family_mcp_token import FamilyMCPToken
from apps.backend.app.models.user import User
from apps.backend.app.services import mcp_token as token_svc
from apps.backend.app.utils.snowflake import next_id
from packages.core.roles import UserRole


# ── Service-level tests ───────────────────────────────────────────────────────


class TestGenerateToken:
    def test_generate_returns_plaintext_and_row(self, db):
        family = Family(id=next_id(), name="T", created_by=next_id())
        db.add(family)
        db.flush()

        plaintext, row = token_svc.generate_token(family.id, db)
        db.commit()

        assert plaintext.startswith("mcp_")
        assert len(plaintext) == 47  # mcp_ (4) + token_urlsafe(32) (43)
        assert row.token_hash == hashlib.sha256(plaintext.encode()).hexdigest()
        assert row.token_prefix == plaintext[:8]
        assert row.token_last4 == plaintext[-4:]
        assert row.is_active is True
        assert row.allow_external is False
        assert row.allow_write is False

    def test_generate_creates_synthetic_user(self, db):
        family = Family(id=next_id(), name="T", created_by=next_id())
        db.add(family)
        db.flush()

        token_svc.generate_token(family.id, db)
        db.commit()

        synthetic = (
            db.query(User)
            .filter(User.family_id == family.id, User.role == UserRole.EXTERNAL_TOKEN)
            .first()
        )
        assert synthetic is not None

    def test_rotation_deactivates_old_token(self, db):
        family = Family(id=next_id(), name="T", created_by=next_id())
        db.add(family)
        db.flush()

        plain1, row1 = token_svc.generate_token(family.id, db)
        db.commit()

        plain2, row2 = token_svc.generate_token(family.id, db)
        db.commit()

        assert plain1 != plain2
        assert row1.id != row2.id

        # Old token deactivated
        old = db.get(FamilyMCPToken, row1.id)
        assert old.is_active is False

        # New token active
        new = db.get(FamilyMCPToken, row2.id)
        assert new.is_active is True

    def test_rotation_reuses_synthetic_user(self, db):
        family = Family(id=next_id(), name="T", created_by=next_id())
        db.add(family)
        db.flush()

        token_svc.generate_token(family.id, db)
        db.commit()

        token_svc.generate_token(family.id, db)
        db.commit()

        synthetics = (
            db.query(User)
            .filter(User.family_id == family.id, User.role == UserRole.EXTERNAL_TOKEN)
            .all()
        )
        assert len(synthetics) == 1


class TestVerifyToken:
    def test_valid_token_returns_row(self, db):
        family = Family(id=next_id(), name="T", created_by=next_id())
        db.add(family)
        db.flush()

        plaintext, row = token_svc.generate_token(family.id, db)
        db.commit()

        result = token_svc.verify_token(family.id, plaintext, db)
        assert result is not None
        assert result.id == row.id

    def test_wrong_token_returns_none(self, db):
        family = Family(id=next_id(), name="T", created_by=next_id())
        db.add(family)
        db.flush()

        token_svc.generate_token(family.id, db)
        db.commit()

        result = token_svc.verify_token(family.id, "mcp_wrongtoken_value", db)
        assert result is None

    def test_expired_token_returns_none(self, db):
        family = Family(id=next_id(), name="T", created_by=next_id())
        db.add(family)
        db.flush()

        plaintext, row = token_svc.generate_token(family.id, db)
        row.expires_at = datetime.now(UTC) - timedelta(hours=1)
        db.commit()

        result = token_svc.verify_token(family.id, plaintext, db)
        assert result is None

    def test_inactive_token_returns_none(self, db):
        family = Family(id=next_id(), name="T", created_by=next_id())
        db.add(family)
        db.flush()

        plaintext, row = token_svc.generate_token(family.id, db)
        row.is_active = False
        db.commit()

        result = token_svc.verify_token(family.id, plaintext, db)
        assert result is None

    def test_verify_updates_last_used_at(self, db):
        family = Family(id=next_id(), name="T", created_by=next_id())
        db.add(family)
        db.flush()

        plaintext, row = token_svc.generate_token(family.id, db)
        db.commit()
        assert row.last_used_at is None

        token_svc.verify_token(family.id, plaintext, db)
        db.commit()

        updated = db.get(FamilyMCPToken, row.id)
        assert updated.last_used_at is not None


class TestUpdateAccess:
    def test_patch_allow_external(self, db):
        family = Family(id=next_id(), name="T", created_by=next_id())
        db.add(family)
        db.flush()

        token_svc.generate_token(family.id, db)
        db.commit()

        row = token_svc.update_access(family.id, db, allow_external=True)
        db.commit()

        assert row.allow_external is True
        assert row.allow_write is False  # unchanged

    def test_patch_clears_expires_at_via_router(self, client, auth_headers):
        """PATCH {expires_at: null} clears expiration — explicit null ≠ field absent."""
        from datetime import UTC, datetime, timedelta

        client.post("/api/v1/ai/mcp-token", headers=auth_headers)

        # Set expiration
        resp = client.patch(
            "/api/v1/ai/mcp-token",
            json={"expires_at": (datetime.now(UTC) + timedelta(days=30)).isoformat()},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json().get("data", resp.json())
        assert data["expires_at"] is not None

        # Clear it with explicit null
        resp = client.patch(
            "/api/v1/ai/mcp-token",
            json={"expires_at": None},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json().get("data", resp.json())
        assert data["expires_at"] is None

    def test_patch_omitting_expires_at_leaves_it(self, client, auth_headers):
        """PATCH {allow_external: true} (no expires_at) leaves expiration untouched."""
        from datetime import UTC, datetime, timedelta

        client.post("/api/v1/ai/mcp-token", headers=auth_headers)
        future = (datetime.now(UTC) + timedelta(days=90)).isoformat()
        client.patch(
            "/api/v1/ai/mcp-token",
            json={"expires_at": future},
            headers=auth_headers,
        )

        # Toggle allow_external only — expires_at should remain
        resp = client.patch(
            "/api/v1/ai/mcp-token",
            json={"allow_external": True},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json().get("data", resp.json())
        assert data["expires_at"] is not None
        assert data["allow_external"] is True


class TestRevokeToken:
    def test_revoke_deactivates_token(self, db):
        family = Family(id=next_id(), name="T", created_by=next_id())
        db.add(family)
        db.flush()

        plaintext, row = token_svc.generate_token(family.id, db)
        db.commit()

        token_svc.revoke_token(family.id, db)
        db.commit()

        updated = db.get(FamilyMCPToken, row.id)
        assert updated.is_active is False

        # Verify also fails
        result = token_svc.verify_token(family.id, plaintext, db)
        assert result is None


# ── API endpoint tests ────────────────────────────────────────────────────────


class TestMCPTokenEndpoints:
    def test_get_returns_404_when_no_token(self, client, auth_headers):
        resp = client.get("/api/v1/ai/mcp-token", headers=auth_headers)
        assert resp.status_code == 404

    def test_generate_returns_plaintext(self, client, auth_headers):
        resp = client.post("/api/v1/ai/mcp-token", headers=auth_headers)
        assert resp.status_code == 201
        data = resp.json().get("data", resp.json())
        assert "token" in data
        assert data["token"].startswith("mcp_")
        assert "token_prefix" in data
        assert "token_last4" in data

    def test_get_returns_metadata_after_generate(self, client, auth_headers):
        client.post("/api/v1/ai/mcp-token", headers=auth_headers)

        resp = client.get("/api/v1/ai/mcp-token", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json().get("data", resp.json())
        assert "token" not in data  # plaintext NOT in GET response
        assert data["allow_external"] is False
        assert data["is_active"] is True

    def test_patch_updates_flags(self, client, auth_headers):
        client.post("/api/v1/ai/mcp-token", headers=auth_headers)

        resp = client.patch(
            "/api/v1/ai/mcp-token",
            json={"allow_external": True},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json().get("data", resp.json())
        assert data["allow_external"] is True

    def test_delete_deactivates_token(self, client, auth_headers):
        client.post("/api/v1/ai/mcp-token", headers=auth_headers)

        resp = client.delete("/api/v1/ai/mcp-token", headers=auth_headers)
        assert resp.status_code == 204

        # GET returns 404 after delete
        resp = client.get("/api/v1/ai/mcp-token", headers=auth_headers)
        assert resp.status_code == 404

    def test_non_owner_gets_403(self, client, db):
        # Register owner
        owner_resp = client.post("/api/v1/auth/register", json={
            "username": "owner_test",
            "display_name": "Owner",
            "password": "TestPass123",
            "family_name": "Test Family",
            "family_invitation_code": "AUT03",
        })
        assert owner_resp.status_code == 200

        # Join as member using the family's invite code
        owner_user = (
            db.query(User).filter(User.username == "owner_test").first()
        )
        family = (
            db.query(Family).filter(Family.id == owner_user.family_id).first()
        )
        member_resp = client.post("/api/v1/auth/family/join", json={
            "username": "member_test",
            "display_name": "Member",
            "password": "TestPass456",
            "invite_code": family.invite_code,
        })
        assert member_resp.status_code == 200, member_resp.text
        member_headers = {
            "Authorization": f"Bearer {member_resp.json()['data']['access_token']}"
        }

        resp = client.get("/api/v1/ai/mcp-token", headers=member_headers)
        assert resp.status_code == 403


# ── Member list exclusion (AE6) ──────────────────────────────────────────────


class TestSyntheticUserExclusion:
    def test_family_members_excludes_external_token(self, db):
        from apps.backend.app.services.family import get_family_members

        family = Family(id=next_id(), name="T", created_by=next_id())
        db.add(family)
        db.flush()

        owner = User(
            id=next_id(), family_id=family.id, username="owner",
            display_name="Owner", password_hash="x", role="owner",
        )
        db.add(owner)
        db.flush()

        # Create synthetic user
        synthetic = User(
            id=next_id(), family_id=family.id, username="__mcp_service",
            display_name="MCP Service", password_hash="",
            role=UserRole.EXTERNAL_TOKEN,
        )
        db.add(synthetic)
        db.flush()

        members = get_family_members(db, owner)
        member_ids = [m.id for m in members]

        assert owner.id in member_ids
        assert synthetic.id not in member_ids
        assert len(members) == 1
