"""Tests for ALTCHA captcha enhancements."""

import hashlib
import time

from apps.backend.app.services.cache import get_captcha_payload_cache, reset_captcha_payload_cache


class TestEndpointSpecificDifficulty:
    """Tests for endpoint-specific difficulty parameter."""

    def test_challenge_default_difficulty(self, client):
        """Test that missing endpoint parameter returns default difficulty."""
        response = client.get("/api/v1/captcha/challenge")
        assert response.status_code == 200
        # Captcha endpoint returns raw JSON (not envelope) for altcha browser library compatibility
        data = response.json()
        assert "challenge" in data
        assert "max_number" in data
        # Default difficulty is 50000
        assert data["max_number"] == 50000

    def test_challenge_login_difficulty(self, client):
        """Test that login endpoint returns lower difficulty (30000)."""
        response = client.get("/api/v1/captcha/challenge?endpoint=login")
        assert response.status_code == 200
        data = response.json()
        assert data["max_number"] == 30000

    def test_challenge_register_difficulty(self, client):
        """Test that register endpoint returns higher difficulty (100000)."""
        response = client.get("/api/v1/captcha/challenge?endpoint=register")
        assert response.status_code == 200
        data = response.json()
        assert data["max_number"] == 100000

    def test_challenge_join_family_difficulty(self, client):
        """Test that join-family endpoint returns higher difficulty (100000)."""
        response = client.get("/api/v1/captcha/challenge?endpoint=join-family")
        assert response.status_code == 200
        data = response.json()
        assert data["max_number"] == 100000

    def test_challenge_unknown_endpoint_uses_default(self, client):
        """Test that unknown endpoint returns default difficulty."""
        response = client.get("/api/v1/captcha/challenge?endpoint=unknown")
        assert response.status_code == 200
        data = response.json()
        assert data["max_number"] == 50000


class TestPayloadRegistry:
    """Tests for payload registry cache functionality."""

    def test_cache_factory_returns_instance(self):
        """Test that captcha payload cache factory returns a CacheBackend."""
        reset_captcha_payload_cache()
        cache = get_captcha_payload_cache()
        assert cache is not None
        # Should have the required methods
        assert hasattr(cache, 'get')
        assert hasattr(cache, 'set')
        assert hasattr(cache, 'delete')

    def test_cache_set_and_get(self):
        """Test that cache can store and retrieve values."""
        reset_captcha_payload_cache()
        cache = get_captcha_payload_cache()

        # Store a payload hash
        test_key = "altcha:used:test-hash-123"
        cache.set(test_key, "1", ttl_seconds=3600)

        # Retrieve it
        result = cache.get(test_key)
        assert result == "1"

    def test_cache_ttl_expiry(self):
        """Test that cache entries respect TTL (short TTL for testing)."""
        reset_captcha_payload_cache()
        cache = get_captcha_payload_cache()

        test_key = "altcha:used:test-hash-ttl"
        # Set with very short TTL (1 second)
        cache.set(test_key, "1", ttl_seconds=1)

        # Should exist immediately
        assert cache.get(test_key) == "1"

        # Wait for expiry (short sleep is acceptable for TTL tests)
        time.sleep(2)

        # Should be expired now
        assert cache.get(test_key) is None

    def test_payload_hash_key_format(self):
        """Test that payload hash is correctly formatted."""
        test_payload = "test-payload-string"
        expected_hash = hashlib.sha256(test_payload.encode()).hexdigest()
        expected_key = f"altcha:used:{expected_hash}"

        # Verify the hash is 64 characters (SHA-256 hex)
        assert len(expected_hash) == 64

        reset_captcha_payload_cache()
        cache = get_captcha_payload_cache()

        # Store using the expected key format
        cache.set(expected_key, "1", ttl_seconds=3600)
        assert cache.get(expected_key) == "1"


class TestSecurityEventType:
    """Tests for CAPTCHA_REPLAY_ATTACK security event type."""

    def test_replay_attack_event_exists(self):
        """Test that CAPTCHA_REPLAY_ATTACK event type is defined."""
        from apps.backend.app.services.security_log import SecurityEventType

        assert hasattr(SecurityEventType, "CAPTCHA_REPLAY_ATTACK")
        assert SecurityEventType.CAPTCHA_REPLAY_ATTACK == "captcha_replay_attack"

    def test_all_captcha_event_types_exist(self):
        """Test that all captcha-related event types are defined."""
        from apps.backend.app.services.security_log import SecurityEventType

        # Base captcha event type
        assert hasattr(SecurityEventType, "CAPTCHA_VERIFICATION_FAILED")
        assert SecurityEventType.CAPTCHA_VERIFICATION_FAILED == "captcha_verification_failed"

        # Replay attack event type
        assert hasattr(SecurityEventType, "CAPTCHA_REPLAY_ATTACK")
        assert SecurityEventType.CAPTCHA_REPLAY_ATTACK == "captcha_replay_attack"


class TestCaptchaCacheReset:
    """Tests for captcha cache reset functionality."""

    def test_reset_clears_cache(self):
        """Test that reset_captcha_payload_cache clears all entries."""
        reset_captcha_payload_cache()
        cache = get_captcha_payload_cache()

        # Add some entries
        cache.set("altcha:used:hash1", "1", ttl_seconds=3600)
        cache.set("altcha:used:hash2", "1", ttl_seconds=3600)

        # Verify they exist
        assert cache.get("altcha:used:hash1") == "1"
        assert cache.get("altcha:used:hash2") == "1"

        # Reset
        reset_captcha_payload_cache()

        # Get a new cache instance (should be empty)
        cache = get_captcha_payload_cache()
        assert cache.get("altcha:used:hash1") is None
        assert cache.get("altcha:used:hash2") is None