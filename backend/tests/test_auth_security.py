"""Tests for authentication security enhancements."""

import statistics
import time

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.auth import hash_password


class TestTimingAttackProtection:
    """Tests for timing attack protection in login."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    def test_login_response_time_consistency(self, client):
        """Test that login response times are consistent regardless of user existence."""
        # Register a known user
        client.post("/api/v1/auth/register", json={
            "username": "timing_test_user",
            "display_name": "Timing Test",
            "password": "CorrectPassword123",
            "family_name": "Test Family"
        })

        # Measure login times for existing user with wrong password
        times_existing = []
        for _ in range(5):
            start = time.perf_counter()
            client.post("/api/v1/auth/login", json={
                "username": "timing_test_user",
                "password": "WrongPassword123"
            })
            times_existing.append(time.perf_counter() - start)

        # Measure login times for non-existent user
        times_nonexistent = []
        for _ in range(5):
            start = time.perf_counter()
            client.post("/api/v1/auth/login", json={
                "username": "nonexistent_user_xyz_12345",
                "password": "WrongPassword123"
            })
            times_nonexistent.append(time.perf_counter() - start)

        # Calculate statistics
        avg_existing = statistics.mean(times_existing)
        avg_nonexistent = statistics.mean(times_nonexistent)

        # Time difference should be within reasonable variance (< 30%)
        # bcrypt takes ~200-300ms, variance should be similar
        diff = abs(avg_existing - avg_nonexistent)
        tolerance = max(avg_existing, avg_nonexistent) * 0.3

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

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

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
        assert response1.json()["code"] == response2.json()["code"]
        assert response1.json()["code"] == "AUTH_INVALID_CREDENTIALS"