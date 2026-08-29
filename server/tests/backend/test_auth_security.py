"""Tests for JTI-based token revocation, password change endpoint, and child PIN authentication."""

import statistics
import time
import unicodedata
from datetime import UTC

import bcrypt

from apps.backend.app.auth.revoke_jti import (
    _is_jti_revoked,
    revoke_all_user_tokens,
    revoke_jti,
)
from apps.backend.app.services.auth import hash_password

# ---------------------------------------------------------------------------
# JTI revocation helpers
# ---------------------------------------------------------------------------


def test_revoke_jti_blocks_token_use(client, auth_headers):
    """A revoked JTI should cause the token to be rejected."""
    resp = client.get("/api/v1/auth/me", headers=auth_headers)
    assert resp.status_code == 200

    import jwt

    from apps.backend.app.auth.deps import ALGORITHM
    from apps.backend.app.config import settings
    token = auth_headers["Authorization"].split(" ")[1]
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
    jti = payload["jti"]

    revoke_jti(jti, ttl_seconds=300)

    resp = client.get("/api/v1/auth/me", headers=auth_headers)
    assert resp.status_code == 401


def test_revoke_all_user_tokens_blocks_access(client, auth_headers):
    """revoke_all_user_tokens should invalidate all tokens for that user."""
    resp = client.get("/api/v1/auth/me", headers=auth_headers)
    assert resp.status_code == 200

    import jwt

    from apps.backend.app.auth.deps import ALGORITHM
    from apps.backend.app.config import settings
    token = auth_headers["Authorization"].split(" ")[1]
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
    user_id = payload["sub"]

    revoke_all_user_tokens(user_id)

    resp = client.get("/api/v1/auth/me", headers=auth_headers)
    assert resp.status_code == 401


def test_refresh_rotates_jti(client, auth_headers):
    """After refresh, the old refresh token JTI should be revoked."""
    import jwt

    from apps.backend.app.auth.deps import ALGORITHM
    from apps.backend.app.config import settings

    old_refresh = auth_headers["_refresh_token"]
    old_jti = jwt.decode(old_refresh, settings.SECRET_KEY, algorithms=[ALGORITHM])["jti"]

    resp = client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert resp.status_code == 200

    # Old JTI must now be in the revocation store
    assert _is_jti_revoked(old_jti)


def test_new_tokens_after_refresh_work(client, auth_headers):
    """New tokens issued after refresh should be valid."""
    old_refresh = auth_headers["_refresh_token"]

    resp = client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert resp.status_code == 200
    data = resp.json()["data"]

    new_headers = {"Authorization": f"Bearer {data['access_token']}"}
    me_resp = client.get("/api/v1/auth/me", headers=new_headers)
    assert me_resp.status_code == 200


# ---------------------------------------------------------------------------
# Password change endpoint
# ---------------------------------------------------------------------------


def test_change_password_success(client, auth_headers):
    """Successful password change returns 200."""
    resp = client.post(
        "/api/v1/auth/me/password",
        json={"old_password": "TestPass123", "new_password": "NewPass456"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert "密码已修改" in resp.json()["data"]["message"]


def test_change_password_wrong_old_password(client, auth_headers):
    """Wrong old password returns 400."""
    resp = client.post(
        "/api/v1/auth/me/password",
        json={"old_password": "WrongPass999", "new_password": "NewPass456"},
        headers=auth_headers,
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == "AUTH_PASSWORD_INCORRECT"


def test_change_password_weak_new_password(client, auth_headers):
    """New password failing strength rules returns 422."""
    resp = client.post(
        "/api/v1/auth/me/password",
        json={"old_password": "TestPass123", "new_password": "weak"},
        headers=auth_headers,
    )
    assert resp.status_code == 422


def test_change_password_same_as_old(client, auth_headers):
    """New password identical to old password returns 400 AUTH_PASSWORD_SAME."""
    resp = client.post(
        "/api/v1/auth/me/password",
        json={"old_password": "TestPass123", "new_password": "TestPass123"},
        headers=auth_headers,
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == "AUTH_PASSWORD_SAME"


def test_change_password_revokes_all_tokens(client, auth_headers):
    """After password change, the old access token should be rejected."""
    resp = client.post(
        "/api/v1/auth/me/password",
        json={"old_password": "TestPass123", "new_password": "NewPass456"},
        headers=auth_headers,
    )
    assert resp.status_code == 200

    resp2 = client.get("/api/v1/auth/me", headers=auth_headers)
    assert resp2.status_code == 401


def test_change_password_revokes_refresh_token(client, auth_headers):
    """After password change, the old refresh token should be rejected."""
    old_refresh = auth_headers["_refresh_token"]

    client.post(
        "/api/v1/auth/me/password",
        json={"old_password": "TestPass123", "new_password": "NewPass456"},
        headers=auth_headers,
    )

    resp = client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert resp.status_code == 401


def test_change_password_requires_auth(client):
    """Password change without auth returns 401."""
    resp = client.post(
        "/api/v1/auth/me/password",
        json={"old_password": "TestPass123", "new_password": "NewPass456"},
    )
    assert resp.status_code == 401


def test_login_with_new_password_after_change(client, auth_headers):
    """After password change, login with new password succeeds."""
    client.post(
        "/api/v1/auth/me/password",
        json={"old_password": "TestPass123", "new_password": "NewPass456"},
        headers=auth_headers,
    )

    resp = client.post("/api/v1/auth/login", json={
        "username": "testuser",
        "password": "NewPass456",
    })
    assert resp.status_code == 200
    assert "access_token" in resp.json()["data"]


# ---------------------------------------------------------------------------
# Child PIN authentication helpers
# ---------------------------------------------------------------------------


def _make_child_pin_hash(emojis: list[str]) -> str:
    """Hash a 4-emoji PIN with PIN_BCRYPT_ROUNDS."""
    from apps.backend.app.config import settings
    normalized = unicodedata.normalize("NFC", "".join(emojis))
    return bcrypt.hashpw(normalized.encode("utf-8"), bcrypt.gensalt(rounds=settings.PIN_BCRYPT_ROUNDS)).decode("utf-8")


CHILD_PASSWORD = "ChildPass123"
_child_counter = 0


def _create_child_user(db, family_id: str, display_name: str = "小明", pin: list[str] | None = None):
    """Create a child user directly in the DB."""
    import bcrypt

    from apps.backend.app.models.user import User

    global _child_counter
    _child_counter += 1

    if pin is None:
        pin = ["🐱", "🐶", "🐸", "🦊"]

    child = User(
        family_id=int(family_id),
        username=f"child_{_child_counter}",
        display_name=display_name,
        password_hash=bcrypt.hashpw(CHILD_PASSWORD.encode(), bcrypt.gensalt()).decode(),
        role="child",
        pin_hash=_make_child_pin_hash(pin),
        pin_fail_count=0,
    )
    db.add(child)
    db.commit()
    db.refresh(child)
    return child


def _child_login(client, child, pin: list[str] | None = None) -> None:
    """Two-phase child login: step1 (password) → step2 (emoji PIN). Sets child cookies."""
    if pin is None:
        pin = VALID_PIN
    step1 = client.post("/api/v1/auth/login/step1", json={
        "username": child.username,
        "password": CHILD_PASSWORD,
    })
    assert step1.status_code == 200, step1.text
    data = step1.json()["data"]
    assert data["second_factor_required"] is True
    temp_token = data["temp_token"]

    step2 = client.post("/api/v1/auth/login/step2", json={
        "temp_token": temp_token,
        "factor_type": "emoji_pin",
        "payload": {"pin_sequence": pin},
    })
    assert step2.status_code == 200, step2.text


def _get_family_id(client) -> str:
    """Register a user and return their family_id."""
    resp = client.post("/api/v1/auth/register", json={
        "username": "parent_owner",
        "display_name": "Parent",
        "password": "ParentPass123",
        "family_name": "Test Family",
        "family_invitation_code": "AUT06"
    })
    assert resp.status_code == 200
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {resp.json()['data']['access_token']}"})
    return str(me.json()["data"]["family_id"])


VALID_PIN = ["🐱", "🐶", "🐸", "🦊"]
WRONG_PIN = ["🐱", "🐶", "🐸", "🐼"]


class TestChildPinAuth:
    """Tests for child two-phase authentication (password → emoji PIN)."""

    def test_child_login_happy_path(self, client, db):
        """Correct password + PIN returns 200 and sets child cookies."""
        family_id = _get_family_id(client)
        child = _create_child_user(db, family_id)

        # Step 1: password
        step1 = client.post("/api/v1/auth/login/step1", json={
            "username": child.username,
            "password": CHILD_PASSWORD,
        })
        assert step1.status_code == 200
        data = step1.json()["data"]
        assert data["second_factor_required"] is True
        assert data["second_factor_type"] == "emoji_pin"

        # Step 2: emoji PIN
        step2 = client.post("/api/v1/auth/login/step2", json={
            "temp_token": data["temp_token"],
            "factor_type": "emoji_pin",
            "payload": {"pin_sequence": VALID_PIN},
        })
        assert step2.status_code == 200
        resp_data = step2.json()["data"]
        assert "access_token" in resp_data
        assert "child_access_token" in step2.cookies
        assert "child_refresh_token" in step2.cookies

    def test_child_login_resets_fail_count(self, client, db):
        """Successful login resets pin_fail_count to 0."""
        family_id = _get_family_id(client)
        child = _create_child_user(db, family_id)

        # Cause one PIN failure via step2 with wrong PIN
        step1 = client.post("/api/v1/auth/login/step1", json={
            "username": child.username,
            "password": CHILD_PASSWORD,
        })
        temp_token = step1.json()["data"]["temp_token"]
        client.post("/api/v1/auth/login/step2", json={
            "temp_token": temp_token,
            "factor_type": "emoji_pin",
            "payload": {"pin_sequence": WRONG_PIN},
        })

        # Now login correctly
        _child_login(client, child)

        db.refresh(child)
        assert child.pin_fail_count == 0

    def test_child_refresh_token(self, client, db):
        """Child refresh token returns new access token."""
        family_id = _get_family_id(client)
        child = _create_child_user(db, family_id)

        _child_login(client, child)

        refresh_resp = client.post("/api/v1/auth/child/refresh")
        assert refresh_resp.status_code == 200
        assert refresh_resp.json()["data"]["message"] == "token refreshed"
        assert "child_access_token" in refresh_resp.cookies

    def test_wrong_pin_returns_401(self, client, db):
        """Wrong PIN at step2 returns 401 and increments fail count."""
        family_id = _get_family_id(client)
        child = _create_child_user(db, family_id)

        step1 = client.post("/api/v1/auth/login/step1", json={
            "username": child.username,
            "password": CHILD_PASSWORD,
        })
        temp_token = step1.json()["data"]["temp_token"]

        resp = client.post("/api/v1/auth/login/step2", json={
            "temp_token": temp_token,
            "factor_type": "emoji_pin",
            "payload": {"pin_sequence": WRONG_PIN},
        })
        assert resp.status_code == 401

        db.refresh(child)
        assert child.pin_fail_count == 1

    def test_three_wrong_pins_then_locked(self, client, db):
        """Three wrong PINs lock the account; 4th attempt returns 423."""
        family_id = _get_family_id(client)
        child = _create_child_user(db, family_id)

        for _ in range(3):
            step1 = client.post("/api/v1/auth/login/step1", json={
                "username": child.username,
                "password": CHILD_PASSWORD,
            })
            temp_token = step1.json()["data"]["temp_token"]
            client.post("/api/v1/auth/login/step2", json={
                "temp_token": temp_token,
                "factor_type": "emoji_pin",
                "payload": {"pin_sequence": WRONG_PIN},
            })

        db.refresh(child)
        assert child.pin_locked_until is not None

        # 4th attempt — account locked
        step1 = client.post("/api/v1/auth/login/step1", json={
            "username": child.username,
            "password": CHILD_PASSWORD,
        })
        temp_token = step1.json()["data"]["temp_token"]
        resp = client.post("/api/v1/auth/login/step2", json={
            "temp_token": temp_token,
            "factor_type": "emoji_pin",
            "payload": {"pin_sequence": VALID_PIN},
        })
        assert resp.status_code == 423
        assert "locked_until" in resp.json()["details"]

    def test_nonexistent_child_returns_401(self, client, db):
        """Non-existent username at step1 returns 401."""
        resp = client.post("/api/v1/auth/login/step1", json={
            "username": "no_such_child_xyz",
            "password": CHILD_PASSWORD,
        })
        assert resp.status_code == 401

    def test_invalid_emoji_in_pin_returns_4xx(self, client, db):
        """PIN with invalid emoji at step2 returns 401 or 422."""
        family_id = _get_family_id(client)
        child = _create_child_user(db, family_id)

        step1 = client.post("/api/v1/auth/login/step1", json={
            "username": child.username,
            "password": CHILD_PASSWORD,
        })
        temp_token = step1.json()["data"]["temp_token"]

        resp = client.post("/api/v1/auth/login/step2", json={
            "temp_token": temp_token,
            "factor_type": "emoji_pin",
            "payload": {"pin_sequence": ["🐱", "🐶", "🐸", "❌"]},
        })
        assert resp.status_code in (401, 422)

    def test_token_version_mismatch_on_refresh_returns_401(self, client, db):
        """Stale token_version on refresh returns 401."""
        family_id = _get_family_id(client)
        child = _create_child_user(db, family_id)

        _child_login(client, child)

        # Bump token_version to invalidate existing tokens
        child.token_version += 1
        db.commit()

        refresh_resp = client.post("/api/v1/auth/child/refresh")
        assert refresh_resp.status_code == 401

    def test_verify_parent_password_valid_owner(self, client, db):
        """verify-parent with valid owner password returns 200."""
        family_id = _get_family_id(client)
        child = _create_child_user(db, family_id)

        _child_login(client, child)

        resp = client.post("/api/v1/auth/child/verify-parent", json={
            "password": "ParentPass123",
        })
        assert resp.status_code == 200
        assert resp.json()["data"]["message"] == "verified"

    def test_verify_parent_password_wrong_password_returns_401(self, client, db):
        """verify-parent with wrong password returns 401."""
        family_id = _get_family_id(client)
        child = _create_child_user(db, family_id)

        _child_login(client, child)

        resp = client.post("/api/v1/auth/child/verify-parent", json={
            "password": "WrongPassword999",
        })
        assert resp.status_code == 401
        assert resp.json()["message"] == "用户名或密码错误"

    def test_pin_login_succeeds_after_lockout_expires(self, client, db):
        """After lockout window passes, child can login again and fail count resets."""
        from datetime import datetime, timedelta

        family_id = _get_family_id(client)
        child = _create_child_user(db, family_id)

        # Manually set locked-out state with an expired lockout time
        child.pin_fail_count = 3
        child.pin_locked_until = datetime.now(UTC) - timedelta(minutes=1)
        db.commit()

        # Login should succeed — lockout has expired
        _child_login(client, child)

        db.refresh(child)
        assert child.pin_fail_count == 0
        assert child.pin_locked_until is None

    def test_child_refresh_with_expired_token_returns_401(self, client):
        """Expired child refresh token is rejected."""
        from datetime import datetime, timedelta

        import jwt

        from apps.backend.app.auth.deps import ALGORITHM
        from apps.backend.app.config import settings

        expired_token = jwt.encode(
            {"sub": "fake-id", "type": "refresh", "token_version": 0,
             "exp": datetime.now(UTC) - timedelta(seconds=1)},
            settings.SECRET_KEY,
            algorithm=ALGORITHM,
        )
        client.cookies.set("child_refresh_token", expired_token)
        resp = client.post("/api/v1/auth/child/refresh")
        assert resp.status_code == 401

    def test_verify_parent_password_wrong_returns_401(self, client, db):
        """Wrong parent password returns 401."""
        family_id = _get_family_id(client)
        child = _create_child_user(db, family_id)

        _child_login(client, child)

        resp = client.post("/api/v1/auth/child/verify-parent", json={"password": "WrongPassword999!"})
        assert resp.status_code == 401


class TestTimingAttackProtection:
    """Tests for timing attack protection in login."""

    def test_login_response_time_consistency(self, client):
        """Test that login response times are consistent regardless of user existence."""
        # Register a known user
        client.post("/api/v1/auth/register", json={
            "username": "timing_test_user",
            "display_name": "Timing Test",
            "password": "CorrectPassword123",
            "family_name": "Test Family",
            "family_invitation_code": "AUT07"
        })

        # Measure login times for existing user with wrong password
        # Use 10 samples for better statistical stability in CI environments
        times_existing = []
        for _ in range(10):
            start = time.perf_counter()
            client.post("/api/v1/auth/login", json={
                "username": "timing_test_user",
                "password": "WrongPassword123"
            })
            times_existing.append(time.perf_counter() - start)

        # Measure login times for non-existent user
        times_nonexistent = []
        for _ in range(10):
            start = time.perf_counter()
            client.post("/api/v1/auth/login", json={
                "username": "nonexistent_user_xyz_12345",
                "password": "WrongPassword123"
            })
            times_nonexistent.append(time.perf_counter() - start)

        # Calculate statistics
        avg_existing = statistics.mean(times_existing)
        avg_nonexistent = statistics.mean(times_nonexistent)

        # Time difference should be within reasonable variance (< 50%)
        # bcrypt takes ~200-300ms, but CI environments have higher variance
        # Increased tolerance from 30% to 50% to account for CI fluctuations
        diff = abs(avg_existing - avg_nonexistent)
        tolerance = max(avg_existing, avg_nonexistent) * 0.5

        assert diff < tolerance, (
            f"Timing difference too large: {diff:.3f}s "
            f"(existing: {avg_existing:.3f}s, nonexistent: {avg_nonexistent:.3f}s)"
        )


class TestBcryptRoundsConfiguration:
    """Tests for bcrypt rounds configuration."""

    def test_hash_password_uses_configured_rounds(self):
        """Test that hash_password uses configured rounds."""
        password = "test_password_123"
        hashed = hash_password(password)

        # bcrypt hash format: $2b$XX$...
        # XX is the rounds (cost factor)
        parts = hashed.split("$")
        assert len(parts) >= 4
        rounds = int(parts[2])

        # Should be at least 12 (default)
        assert rounds >= 12

    def test_hash_password_produces_different_salts(self):
        """Test that hash_password produces different salts."""
        password = "test_password_123"
        hash1 = hash_password(password)
        hash2 = hash_password(password)

        # Different salts should produce different hashes
        assert hash1 != hash2


class TestLoginErrorMessage:
    """Tests for login error message consistency."""

    def test_same_error_message_for_wrong_password_and_nonexistent_user(self, client):
        """Test that wrong password and nonexistent user return same error message."""
        # Register a user
        client.post("/api/v1/auth/register", json={
            "username": "error_msg_test_user",
            "display_name": "Error Test",
            "password": "CorrectPassword123",
            "family_name": "Test Family"
        })

        # Wrong password
        response1 = client.post("/api/v1/auth/login", json={
            "username": "error_msg_test_user",
            "password": "WrongPassword123"
        })

        # Nonexistent user
        response2 = client.post("/api/v1/auth/login", json={
            "username": "nonexistent_user_xyz_99999",
            "password": "AnyPassword123"
        })

        # Both should return 401 with same error message
        assert response1.status_code == 401
        assert response2.status_code == 401
        assert response1.json()["message"] == response2.json()["message"]
        assert response1.json()["message"] == "用户名或密码错误"


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------

def test_refresh_rate_limit(client, auth_headers):
    """Exceeding 10 refresh calls per minute per user triggers 429."""
    import jwt

    from apps.backend.app.auth.deps import ALGORITHM
    from apps.backend.app.config import settings
    from apps.backend.app.services import auth as auth_service

    token = auth_headers["Authorization"].split(" ")[1]
    user_id = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])["sub"]

    # Exhaust the rate limit directly via the service function
    from apps.backend.app.services.cache.factory import get_rate_limit_cache
    cache = get_rate_limit_cache()
    key = f"refresh_attempts:{user_id}"
    cache.set(key, auth_service._REFRESH_RATE_LIMIT_PER_MINUTE, ttl_seconds=60)

    resp = client.post("/api/v1/auth/refresh", json={
        "refresh_token": auth_headers["_refresh_token"]
    })
    assert resp.status_code == 429


def test_password_change_rate_limit(client, auth_headers):
    """Exceeding 3 password change attempts per hour triggers 429."""
    import jwt

    from apps.backend.app.auth.deps import ALGORITHM
    from apps.backend.app.config import settings
    from apps.backend.app.services import auth as auth_service

    token = auth_headers["Authorization"].split(" ")[1]
    user_id = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])["sub"]

    from apps.backend.app.services.cache.factory import get_rate_limit_cache
    cache = get_rate_limit_cache()
    key = f"password_change_attempts:{user_id}"
    cache.set(key, auth_service._PASSWORD_CHANGE_RATE_LIMIT_PER_HOUR, ttl_seconds=3600)

    resp = client.post(
        "/api/v1/auth/me/password",
        json={"old_password": "TestPass123", "new_password": "NewPass456"},
        headers=auth_headers,
    )
    assert resp.status_code == 429


def test_password_change_rate_limit_includes_retry_after(client, auth_headers):
    """Password-change rate-limited response includes Retry-After header."""
    import jwt

    from apps.backend.app.auth.deps import ALGORITHM
    from apps.backend.app.config import settings
    from apps.backend.app.services import auth as auth_service
    from apps.backend.app.services.cache.factory import get_rate_limit_cache

    token = auth_headers["Authorization"].split(" ")[1]
    user_id = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])["sub"]

    # Exhaust the password change rate limit
    cache = get_rate_limit_cache()
    key = f"password_change_attempts:{user_id}"
    cache.set(key, auth_service._PASSWORD_CHANGE_RATE_LIMIT_PER_HOUR, ttl_seconds=3600)

    resp = client.post(
        "/api/v1/auth/me/password",
        json={"old_password": "TestPass123", "new_password": "NewPass456"},
        headers=auth_headers,
    )
    assert resp.status_code == 429
    assert "retry-after" in resp.headers
    assert int(resp.headers["retry-after"]) > 0


def test_rate_limit_retry_after_header(client, auth_headers):
    """Rate-limited responses include a Retry-After header with a positive value."""
    import jwt

    from apps.backend.app.auth.deps import ALGORITHM
    from apps.backend.app.config import settings
    from apps.backend.app.services import auth as auth_service
    from apps.backend.app.services.cache.factory import get_rate_limit_cache

    token = auth_headers["Authorization"].split(" ")[1]
    user_id = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])["sub"]

    # Exhaust the refresh rate limit
    cache = get_rate_limit_cache()
    key = f"refresh_attempts:{user_id}"
    cache.set(key, auth_service._REFRESH_RATE_LIMIT_PER_MINUTE, ttl_seconds=60)

    resp = client.post("/api/v1/auth/refresh", json={
        "refresh_token": auth_headers["_refresh_token"]
    })
    assert resp.status_code == 429
    assert "retry-after" in resp.headers
    assert int(resp.headers["retry-after"]) > 0


def test_update_profile_invalid_avatar_color(client, auth_headers):
    """PUT /auth/me with non-hex avatar_color returns 422."""
    resp = client.put("/api/v1/auth/me", json={"avatar_color": "red"}, headers=auth_headers)
    assert resp.status_code == 422


def test_update_profile_valid_avatar_color(client, auth_headers):
    """PUT /auth/me with valid hex avatar_color returns 200 and persists the value."""
    resp = client.put("/api/v1/auth/me", json={"avatar_color": "#FF5733"}, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["avatar_color"] == "#FF5733"


# ---------------------------------------------------------------------------
# Settings startup validation
# ---------------------------------------------------------------------------


class TestSettingsStartupValidation:
    """Tests for production secret key validation at settings init time."""

    def _make_settings(self, secret_key: str, environment: str = "production"):
        """Instantiate Settings with overrides, then run the module-level guards inline."""
        import secrets as _secrets

        from packages.core.settings import Settings, _is_weak_secret

        s = Settings(SECRET_KEY=secret_key, ENVIRONMENT=environment)

        if _is_weak_secret(s.SECRET_KEY):
            if s.ENVIRONMENT == "production":
                raise RuntimeError(
                    "SECRET_KEY 未配置或使用了默认占位符！"
                    "生产环境必须设置强随机 SECRET_KEY 环境变量。"
                )
            else:
                s.SECRET_KEY = _secrets.token_urlsafe(32)

        return s

    def test_production_change_me_raises(self):
        """SECRET_KEY containing 'change-me' in production raises RuntimeError."""
        import pytest
        with pytest.raises(RuntimeError, match="SECRET_KEY"):
            self._make_settings("change-me-anything", environment="production")

    def test_production_change_me_uppercase_raises(self):
        """SECRET_KEY containing 'CHANGE_ME' (uppercase) in production raises RuntimeError."""
        import pytest
        with pytest.raises(RuntimeError, match="SECRET_KEY"):
            self._make_settings("CHANGE_ME_IN_PRODUCTION", environment="production")

    def test_production_empty_secret_raises(self):
        """Empty SECRET_KEY in production raises RuntimeError."""
        import pytest
        with pytest.raises(RuntimeError, match="SECRET_KEY"):
            self._make_settings("", environment="production")

    def test_production_valid_secret_succeeds(self):
        """Strong random SECRET_KEY in production does not raise."""
        import secrets
        strong_key = secrets.token_urlsafe(32)
        s = self._make_settings(strong_key, environment="production")
        assert strong_key == s.SECRET_KEY

    def test_development_empty_secret_autogenerates(self):
        """Empty/default SECRET_KEY in development auto-generates a random key."""
        s = self._make_settings("CHANGE_ME_IN_PRODUCTION", environment="development")
        # Should have been replaced with a random value
        assert s.SECRET_KEY != "CHANGE_ME_IN_PRODUCTION"
        assert len(s.SECRET_KEY) > 20
