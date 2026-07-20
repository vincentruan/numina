"""W1 savings endpoints + ignore-debt-warning (Plan B T3)."""


def _create_wish(client, auth_headers, name="T3 wish"):
    resp = client.post(
        "/api/v1/wishes",
        headers=auth_headers,
        json={"name": name, "expected_price": "10000.00"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["id"]


def test_post_savings_201(client, auth_headers):
    wish_id = _create_wish(client, auth_headers)
    resp = client.post(
        f"/api/v1/wishes/{wish_id}/savings",
        json={"amount": "100.00", "note": "first"},
        headers=auth_headers,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()["data"]
    assert body["amount"] == "100.00"
    assert body["wish_id"] == str(wish_id)


def test_get_savings_list(client, auth_headers):
    wish_id = _create_wish(client, auth_headers)
    client.post(
        f"/api/v1/wishes/{wish_id}/savings",
        json={"amount": "100.00"},
        headers=auth_headers,
    )
    resp = client.get(f"/api/v1/wishes/{wish_id}/savings", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()["data"]
    assert isinstance(body, list)
    assert len(body) >= 1
    assert body[0]["amount"] == "100.00"


def test_delete_savings_owner_ok(client, auth_headers):
    wish_id = _create_wish(client, auth_headers)
    create = client.post(
        f"/api/v1/wishes/{wish_id}/savings",
        json={"amount": "50.00"},
        headers=auth_headers,
    )
    log_id = create.json()["data"]["id"]
    resp = client.delete(
        f"/api/v1/wishes/{wish_id}/savings/{log_id}", headers=auth_headers
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"] == {"detail": "已删除"}


def test_delete_savings_other_family_404(client, auth_headers, second_user_headers):
    """A different family's user cannot even see this wish → 404."""
    wish_id = _create_wish(client, auth_headers)
    create = client.post(
        f"/api/v1/wishes/{wish_id}/savings",
        json={"amount": "50.00"},
        headers=auth_headers,
    )
    log_id = create.json()["data"]["id"]
    resp = client.delete(
        f"/api/v1/wishes/{wish_id}/savings/{log_id}", headers=second_user_headers
    )
    assert resp.status_code == 404, resp.text


def test_patch_ignore_debt_warning(client, auth_headers):
    wish_id = _create_wish(client, auth_headers)
    resp = client.patch(
        f"/api/v1/wishes/{wish_id}/ignore-debt-warning",
        json={"ignore": True},
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["ignore_debt_warning"] is True


def test_wish_response_includes_savings_fields(client, auth_headers):
    """WishResponse serializes saved_amount/monthly_saving as str (2 decimals)."""
    wish_id = _create_wish(client, auth_headers)
    resp = client.get(f"/api/v1/wishes/{wish_id}", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()["data"]
    assert "saved_amount" in body and isinstance(body["saved_amount"], str)
    assert "monthly_saving" in body and isinstance(body["monthly_saving"], str)
    assert "target_date" in body
    assert "savings_count" in body
    assert "ignore_debt_warning" in body


def test_savings_count_reflects_logs(client, auth_headers):
    """savings_count is the number of savings logs for the wish."""
    wish_id = _create_wish(client, auth_headers)
    for amt in ("100.00", "200.00", "50.00"):
        r = client.post(
            f"/api/v1/wishes/{wish_id}/savings",
            json={"amount": amt},
            headers=auth_headers,
        )
        assert r.status_code == 201, r.text
    resp = client.get(f"/api/v1/wishes/{wish_id}", headers=auth_headers)
    assert resp.json()["data"]["savings_count"] == 3
    assert resp.json()["data"]["saved_amount"] == "350.00"


def test_saved_amount_updates_after_delete(client, auth_headers):
    """Deleting a log reverses its amount from saved_amount (invariant via router)."""
    wish_id = _create_wish(client, auth_headers)
    a = client.post(
        f"/api/v1/wishes/{wish_id}/savings", json={"amount": "100.00"}, headers=auth_headers
    ).json()["data"]
    client.post(
        f"/api/v1/wishes/{wish_id}/savings", json={"amount": "200.00"}, headers=auth_headers
    )
    client.delete(f"/api/v1/wishes/{wish_id}/savings/{a['id']}", headers=auth_headers)
    resp = client.get(f"/api/v1/wishes/{wish_id}", headers=auth_headers)
    assert resp.json()["data"]["saved_amount"] == "200.00"
    assert resp.json()["data"]["savings_count"] == 1
