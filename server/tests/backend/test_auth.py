def test_register_success(client):
    """Test successful user registration"""
    response = client.post("/api/v1/auth/register", json={
        "username": "newuser",
        "display_name": "New User",
        "password": "Password123",
        "family_name": "New Family",
        "family_invitation_code": "AUT04"
    })
    assert response.status_code == 200
    data = response.json()["data"]
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


def test_register_duplicate_username(client, auth_headers):
    """Test registration with duplicate username fails"""
    response = client.post("/api/v1/auth/register", json={
        "username": "testuser",  # Already exists from auth_headers fixture
        "display_name": "Another User",
        "password": "Password123",
        "family_name": "Another Family",
        "family_invitation_code": "AUT05"
    })
    assert response.status_code == 400
    assert response.json()["code"] == "AUTH_USERNAME_EXISTS"


def test_login_success(client, auth_headers):
    """Test successful login"""
    response = client.post("/api/v1/auth/login", json={
        "username": "testuser",
        "password": "TestPass123"
    })
    assert response.status_code == 200
    data = response.json()["data"]
    assert "access_token" in data
    assert "refresh_token" in data


def test_login_wrong_password(client, auth_headers):
    """Test login with wrong password fails"""
    response = client.post("/api/v1/auth/login", json={
        "username": "testuser",
        "password": "wrongpassword"
    })
    assert response.status_code == 401
    assert response.json()["code"] == "AUTH_INVALID_CREDENTIALS"


def test_login_nonexistent_user(client):
    """Test login with nonexistent user fails"""
    response = client.post("/api/v1/auth/login", json={
        "username": "nonexistent",
        "password": "password123"
    })
    assert response.status_code == 401
    assert response.json()["code"] == "AUTH_INVALID_CREDENTIALS"


def test_refresh_token(client, auth_headers):
    """Test token refresh"""
    refresh_token = auth_headers["_refresh_token"]
    response = client.post("/api/v1/auth/refresh", json={
        "refresh_token": refresh_token
    })
    assert response.status_code == 200
    data = response.json()["data"]
    assert "access_token" in data
    assert "refresh_token" in data


def test_get_me(client, auth_headers):
    """Test getting current user info"""
    response = client.get("/api/v1/auth/me", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["username"] == "testuser"
    assert data["display_name"] == "Test User"
    assert "password_hash" not in data  # Should not expose password


def test_get_me_unauthorized(client):
    """Test getting user info without auth fails"""
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401


def test_join_family_success(client, auth_headers):
    """Test joining a family with valid invite code"""
    # Get the invite code from the first user's family
    family_response = client.get("/api/v1/family", headers=auth_headers)
    invite_code = family_response.json()["data"]["invite_code"]

    # Create a new user and join the family
    response = client.post("/api/v1/auth/family/join", json={
        "username": "joiner",
        "display_name": "Joiner User",
        "password": "Password123",
        "invite_code": invite_code
    })
    assert response.status_code == 200
    data = response.json()["data"]
    assert "access_token" in data

    # Verify the new user is in the same family
    new_user_headers = {"Authorization": f"Bearer {data['access_token']}"}
    me_response = client.get("/api/v1/auth/me", headers=new_user_headers)
    assert me_response.json()["data"]["family_id"] == str(family_response.json()["data"]["id"])


def test_join_family_invalid_code(client):
    """Test joining family with invalid invite code fails"""
    response = client.post("/api/v1/auth/family/join", json={
        "username": "joiner",
        "display_name": "Joiner User",
        "password": "Password123",
        "invite_code": "INVALID"
    })
    assert response.status_code == 404


def test_register_short_password(client):
    """Registration with a password shorter than 8 characters returns 422."""
    response = client.post("/api/v1/auth/register", json={
        "username": "shortpwuser",
        "display_name": "Short PW",
        "password": "Ab1",
        "family_name": "Test Family",
        "family_invitation_code": "AUT16"
    })
    assert response.status_code == 422


def test_join_family_member_limit_exceeded(client, auth_headers, db_session):
    """Test joining family fails when member limit (50) is reached."""
    from apps.backend.app.models.user import User
    from apps.backend.app.services.auth import hash_password

    # Get the invite code from the first user's family
    family_response = client.get("/api/v1/family", headers=auth_headers)
    family_id = int(family_response.json()["data"]["id"])
    invite_code = family_response.json()["data"]["invite_code"]

    # Add 48 more members to reach the limit (1 already exists from auth_headers + 48 = 49)
    for i in range(48):
        user = User(
            family_id=family_id,
            username=f"member{i}",
            display_name=f"Member {i}",
            password_hash=hash_password("Password123"),
            role="member",
        )
        db_session.add(user)
    db_session.commit()

    # Now try to add the 50th member (should succeed)
    response = client.post("/api/v1/auth/family/join", json={
        "username": "member49",
        "display_name": "Member 49",
        "password": "Password123",
        "invite_code": invite_code
    })
    assert response.status_code == 200

    # Try to add the 51st member (should fail with FAMILY_MEMBER_LIMIT_EXCEEDED)
    response = client.post("/api/v1/auth/family/join", json={
        "username": "member50",
        "display_name": "Member 50",
        "password": "Password123",
        "invite_code": invite_code
    })
    assert response.status_code == 400
    assert response.json()["code"] == "FAMILY_MEMBER_LIMIT_EXCEEDED"
