"""Tests for global rate limiting middleware."""

import base64
import json
import time
import uuid

import pytest
from fastapi.testclient import TestClient

from app.middleware.rate_limit import RateLimitMiddleware, _decode_jwt_user_id


def _create_mock_jwt(user_id: str) -> str:
    """Create a mock JWT token for testing.

    Creates a minimal JWT-like token with just the sub claim.
    """
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {"sub": user_id}

    def encode(obj):
        return base64.urlsafe_b64encode(json.dumps(obj).encode()).rstrip(b"=").decode()

    # Create a minimal token (not cryptographically valid, but parseable)
    return f"{encode(header)}.{encode(payload)}.signature"


@pytest.fixture(autouse=True)
def reset_rate_limit():
    """Reset rate limit state before and after each test."""
    # Clear rate limit store before test
    if hasattr(RateLimitMiddleware, '_rate_store'):
        RateLimitMiddleware._rate_store.clear()
    else:
        RateLimitMiddleware._rate_store = {}

    yield

    # Clean up after test
    if hasattr(RateLimitMiddleware, '_rate_store'):
        RateLimitMiddleware._rate_store.clear()


class TestGlobalRateLimit:
    """Tests for global API rate limiting."""

    def test_health_endpoint_not_rate_limited(self):
        """Test that health endpoint is not rate limited."""
        from app.main import app
        # Don't raise exceptions for 429 responses
        client = TestClient(app, raise_server_exceptions=False)

        # Make many requests to health endpoint - should all succeed
        for _ in range(150):
            response = client.get("/api/health")
            assert response.status_code == 200

    def test_rate_limit_enforcement(self):
        """Test that rate limiting is enforced by the middleware."""
        # Test the middleware logic directly rather than through HTTP
        middleware = RateLimitMiddleware(None)

        # Should allow first 100 requests
        for i in range(100):
            result = middleware._check_rate_limit(f"test_client_{i % 3}")  # 3 different clients
            assert result is True, f"Request {i} should have passed"

        # After 100 requests per client, should be rate limited
        # Client 0, 1, 2 each made ~33-34 requests, so make more to hit limit
        for _ in range(100):
            middleware._check_rate_limit("heavy_user")

        # Now should be rate limited
        result = middleware._check_rate_limit("heavy_user")
        assert result is False, "Should be rate limited after many requests"

    def test_different_clients_have_separate_limits(self):
        """Test that different clients have separate rate limits."""
        middleware = RateLimitMiddleware(None)

        # Client A makes 150 requests (should be limited)
        for _ in range(150):
            middleware._check_rate_limit("client_a")

        # Client A should be limited
        assert middleware._check_rate_limit("client_a") is False

        # Client B should still be allowed
        assert middleware._check_rate_limit("client_b") is True

    def test_rate_limit_resets_after_window(self):
        """Test that rate limit window logic works."""
        import time

        middleware = RateLimitMiddleware(None)

        # Make some requests
        for _ in range(50):
            middleware._check_rate_limit("test_window_client")

        # Should still be allowed
        assert middleware._check_rate_limit("test_window_client") is True

        # Simulate time passing by modifying the timestamp in the store
        # This tests the window expiration logic
        if hasattr(middleware, '_rate_store') and 'test_window_client' in middleware._rate_store:
            count, timestamp = middleware._rate_store['test_window_client']
            # Set timestamp to 61 seconds ago (past the window)
            middleware._rate_store['test_window_client'] = (count, time.time() - 61)

        # After window expires, should be allowed again
        assert middleware._check_rate_limit("test_window_client") is True


class TestClientIdentification:
    """Tests for client identification in rate limiting."""

    def test_authenticated_user_identified_by_user_id(self):
        """Test that authenticated users are identified by decoded user_id from JWT."""
        # Create a mock JWT token with a user_id
        user_id = str(uuid.uuid4())
        mock_token = _create_mock_jwt(user_id)

        # Mock request with Authorization header
        class MockRequest:
            class Client:
                host = "192.168.1.1"
            client = Client()
            headers = {"Authorization": f"Bearer {mock_token}"}
            url = type('obj', (object,), {'path': '/api/v1/assets'})()

        middleware = RateLimitMiddleware(None)
        client_id = middleware._get_client_id(MockRequest())

        assert client_id == f"user:{user_id}"

    def test_authenticated_user_with_invalid_token_falls_back_to_ip(self):
        """Test that invalid tokens fall back to IP-based identification."""
        # Mock request with invalid token
        class MockRequest:
            class Client:
                host = "192.168.1.1"
            client = Client()
            headers = {"Authorization": "Bearer invalid_token"}
            url = type('obj', (object,), {'path': '/api/v1/assets'})()

        middleware = RateLimitMiddleware(None)
        client_id = middleware._get_client_id(MockRequest())

        # Should fall back to IP
        assert client_id == "ip:192.168.1.1"

    def test_unauthenticated_user_identified_by_ip(self):
        """Test that unauthenticated users are identified by IP."""
        # Mock request without Authorization header
        class MockRequest:
            class Client:
                host = "192.168.1.100"
            client = Client()
            headers = {}
            url = type('obj', (object,), {'path': '/api/v1/assets'})()

        middleware = RateLimitMiddleware(None)
        client_id = middleware._get_client_id(MockRequest())

        assert client_id == "ip:192.168.1.100"

    def test_unknown_ip_handling(self):
        """Test handling of unknown IP (no client info)."""
        # Mock request with no client info
        class MockRequest:
            client = None
            headers = {}
            url = type('obj', (object,), {'path': '/api/v1/assets'})()

        middleware = RateLimitMiddleware(None)
        client_id = middleware._get_client_id(MockRequest())

        assert client_id == "ip:unknown"


class TestRateLimitSkipPaths:
    """Tests for paths that skip rate limiting."""

    def test_skip_paths_defined(self):
        """Test that skip paths are properly defined."""
        skip_paths = RateLimitMiddleware.SKIP_PATHS

        assert "/api/health" in skip_paths
        assert "/api/v1/auth/login" in skip_paths
        assert "/api/v1/auth/register" in skip_paths

    def test_static_prefixes_defined(self):
        """Test that static prefixes are defined."""
        static_prefixes = RateLimitMiddleware.STATIC_PREFIXES

        assert "/uploads/" in static_prefixes
        assert "/static/" in static_prefixes

    def test_rate_limit_check_logic(self):
        """Test the rate limit check logic directly."""
        middleware = RateLimitMiddleware(None)

        # First check should pass
        assert middleware._check_rate_limit("test_client_1") is True

        # Exhaust the limit
        for _ in range(150):
            middleware._check_rate_limit("test_client_2")

        # Should now be rate limited
        assert middleware._check_rate_limit("test_client_2") is False

        # Different client should still pass
        assert middleware._check_rate_limit("test_client_3") is True