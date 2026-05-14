from apps.backend.app.seed.currencies import seed_currencies


def test_list_currencies(client, auth_headers, db):
    seed_currencies(db)
    response = client.get("/api/v1/currencies", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) >= 13

    codes = [c["code"] for c in data]
    assert "CNY" in codes
    assert "USD" in codes
    assert "EUR" in codes


def test_currencies_favorites_first(client, auth_headers, db):
    seed_currencies(db)
    response = client.get("/api/v1/currencies", headers=auth_headers)
    data = response.json()["data"]
    favorites = [c for c in data if c["is_favorite"]]
    non_favorites = [c for c in data if not c["is_favorite"]]
    # All favorites should appear before non-favorites
    if favorites and non_favorites:
        last_fav_idx = max(data.index(c) for c in favorites)
        first_non_fav_idx = min(data.index(c) for c in non_favorites)
        assert last_fav_idx < first_non_fav_idx


def test_list_rates_empty(client, auth_headers):
    """Returns empty dict when no exchange rate data exists."""
    response = client.get("/api/v1/currencies/rates", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["data"] == {}


def test_get_cny_rate(client, auth_headers):
    """CNY always returns rate=1.0 without DB data."""
    response = client.get("/api/v1/currencies/rates/CNY", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["rate"] == 1.0


def test_get_rate_not_found(client, auth_headers):
    """Returns 404 when no rate data exists for a currency."""
    response = client.get("/api/v1/currencies/rates/USD", headers=auth_headers)
    assert response.status_code == 404


def test_currencies_public_endpoint(client):
    """Currencies are reference data, not user-specific, so endpoint is public."""
    response = client.get("/api/v1/currencies")
    assert response.status_code == 200
