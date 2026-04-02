def test_register_success(client):
    """Test successful user registration"""
    response = client.post("/api/v1/auth/register", json={
        "username": "newuser",
        "display_name": "New User",
        "password": "Password123",
        "family_name": "New Family"
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


def test_register_duplicate_username(client, auth_headers):
    """Test registration with duplicate username fails"""
    response = client.post("/api/v1/auth/register", json={
        "username": "testuser",  # Already exists from auth_headers fixture
        "display_name": "Another User",
        "password": "Password123",
        "family_name": "Another Family"
    })
    assert response.status_code == 400
    assert "用户名已存在" in response.json()["detail"]


def test_login_success(client, auth_headers):
    """Test successful login"""
    response = client.post("/api/v1/auth/login", json={
        "username": "testuser",
        "password": "TestPass123"
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data


def test_login_wrong_password(client, auth_headers):
    """Test login with wrong password fails"""
    response = client.post("/api/v1/auth/login", json={
        "username": "testuser",
        "password": "wrongpassword"
    })
    assert response.status_code == 401
    assert "用户名或密码错误" in response.json()["detail"]


def test_login_nonexistent_user(client):
    """Test login with nonexistent user fails"""
    response = client.post("/api/v1/auth/login", json={
        "username": "nonexistent",
        "password": "password123"
    })
    assert response.status_code == 401
    assert "用户名或密码错误" in response.json()["detail"]


def test_refresh_token(client, auth_headers):
    """Test token refresh"""
    refresh_token = auth_headers["_refresh_token"]
    response = client.post("/api/v1/auth/refresh", json={
        "refresh_token": refresh_token
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data


def test_get_me(client, auth_headers):
    """Test getting current user info"""
    response = client.get("/api/v1/auth/me", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
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
    invite_code = family_response.json()["invite_code"]

    # Create a new user and join the family
    response = client.post("/api/v1/auth/family/join", json={
        "username": "joiner",
        "display_name": "Joiner User",
        "password": "Password123",
        "invite_code": invite_code
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data

    # Verify the new user is in the same family
    new_user_headers = {"Authorization": f"Bearer {data['access_token']}"}
    me_response = client.get("/api/v1/auth/me", headers=new_user_headers)
    assert me_response.json()["family_id"] == family_response.json()["id"]


def test_join_family_invalid_code(client):
    """Test joining family with invalid invite code fails"""
    response = client.post("/api/v1/auth/family/join", json={
        "username": "joiner",
        "display_name": "Joiner User",
        "password": "Password123",
        "invite_code": "INVALID"
    })
    assert response.status_code == 404
