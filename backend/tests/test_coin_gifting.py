"""Tests for sibling coin gifting."""

import pytest


@pytest.fixture
def child_a(client, auth_headers):
    resp = client.post("/api/v1/family/children", headers=auth_headers, json={
        "username": "xiaoming",
        "display_name": "小明",
        "password": "ChildPass1",
        "avatar_color": "#FF5733",
        "pin": ["🐱", "🌟", "🎈", "🐶"],
    })
    assert resp.status_code == 201
    child = resp.json()["data"]
    login = client.post("/api/v1/auth/child/login", json={
        "child_id": child["id"],
        "pin_sequence": ["🐱", "🌟", "🎈", "🐶"],
    })
    token = login.json()["data"]["access_token"]
    client.cookies.delete("access_token")
    client.cookies.delete("child_access_token")
    return {"id": child["id"], "headers": {"Authorization": f"Bearer {token}"}}


@pytest.fixture
def child_b(client, auth_headers):
    resp = client.post("/api/v1/family/children", headers=auth_headers, json={
        "username": "xiaohong",
        "display_name": "小红",
        "password": "ChildPass1",
        "avatar_color": "#33AAFF",
        "pin": ["🌈", "🍎", "🐸", "🦁"],
    })
    assert resp.status_code == 201
    child = resp.json()["data"]
    login = client.post("/api/v1/auth/child/login", json={
        "child_id": child["id"],
        "pin_sequence": ["🌈", "🍎", "🐸", "🦁"],
    })
    token = login.json()["data"]["access_token"]
    client.cookies.delete("access_token")
    client.cookies.delete("child_access_token")
    return {"id": child["id"], "headers": {"Authorization": f"Bearer {token}"}}


def _grant(client, auth_headers, child_id, amount):
    resp = client.post("/api/v1/family/coins/grant", headers=auth_headers, json={
        "child_user_id": child_id,
        "amount": amount,
        "reason": "测试充值",
    })
    assert resp.status_code == 201


def test_list_siblings(client, auth_headers, child_a, child_b):
    resp = client.get("/api/v1/child/coins/siblings", headers=child_a["headers"])
    assert resp.status_code == 200
    siblings = resp.json()["data"]
    ids = [s["id"] for s in siblings]
    assert child_b["id"] in ids
    assert child_a["id"] not in ids


def test_gift_coins_success(client, auth_headers, child_a, child_b):
    _grant(client, auth_headers, child_a["id"], 50)

    resp = client.post("/api/v1/child/coins/gift", headers=child_a["headers"], json={
        "to_child_id": child_b["id"],
        "amount": 20,
        "emoji_reason": "🎁",
    })
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["sent_amount"] == 20
    assert data["to_display_name"] == "小红"

    # Verify balances
    bal_a = client.get("/api/v1/child/coins/balance", headers=child_a["headers"]).json()["data"]["balance"]
    bal_b = client.get("/api/v1/child/coins/balance", headers=child_b["headers"]).json()["data"]["balance"]
    assert bal_a == 30
    assert bal_b == 20


def test_gift_insufficient_balance(client, auth_headers, child_a, child_b):
    _grant(client, auth_headers, child_a["id"], 10)

    resp = client.post("/api/v1/child/coins/gift", headers=child_a["headers"], json={
        "to_child_id": child_b["id"],
        "amount": 50,
    })
    assert resp.status_code == 422


def test_gift_zero_amount(client, auth_headers, child_a, child_b):
    _grant(client, auth_headers, child_a["id"], 10)

    resp = client.post("/api/v1/child/coins/gift", headers=child_a["headers"], json={
        "to_child_id": child_b["id"],
        "amount": 0,
    })
    assert resp.status_code == 422


def test_gift_to_self_fails(client, auth_headers, child_a):
    _grant(client, auth_headers, child_a["id"], 10)

    resp = client.post("/api/v1/child/coins/gift", headers=child_a["headers"], json={
        "to_child_id": child_a["id"],
        "amount": 5,
    })
    assert resp.status_code == 404


def test_gift_appears_in_ledger(client, auth_headers, child_a, child_b):
    _grant(client, auth_headers, child_a["id"], 30)
    client.post("/api/v1/child/coins/gift", headers=child_a["headers"], json={
        "to_child_id": child_b["id"],
        "amount": 10,
    })

    ledger_a = client.get("/api/v1/child/coins/ledger", headers=child_a["headers"]).json()["data"]
    ledger_b = client.get("/api/v1/child/coins/ledger", headers=child_b["headers"]).json()["data"]

    types_a = [tx["transaction_type"] for tx in ledger_a]
    types_b = [tx["transaction_type"] for tx in ledger_b]
    assert "gift_sent" in types_a
    assert "gift_received" in types_b


def test_gift_cross_family_fails(client, auth_headers, second_user_headers, child_a):
    """Child cannot gift to a child in a different family."""
    # Create a child in the second family
    resp = client.post("/api/v1/family/children", headers=second_user_headers, json={
        "username": "otherchild",
        "display_name": "外家孩子",
        "password": "ChildPass1",
        "avatar_color": "#AABBCC",
        "pin": ["🐸", "🦊", "🐼", "🐨"],
    })
    assert resp.status_code == 201
    other_child_id = resp.json()["data"]["id"]

    _grant(client, auth_headers, child_a["id"], 20)

    resp = client.post("/api/v1/child/coins/gift", headers=child_a["headers"], json={
        "to_child_id": other_child_id,
        "amount": 5,
    })
    assert resp.status_code == 404


def test_bearer_priority_over_cookie(client, auth_headers, child_a, child_b):
    """Bearer token identity takes precedence over child_access_token cookie."""
    # child_b logs in — sets child_access_token cookie on client
    login_b = client.post("/api/v1/auth/child/login", json={
        "child_id": child_b["id"],
        "pin_sequence": ["🌈", "🍎", "🐸", "🦁"],
    })
    assert login_b.status_code == 200
    # Now client has child_b's cookie set

    # But we use child_a's Bearer token — should get child_a's balance
    _grant(client, auth_headers, child_a["id"], 50)
    resp = client.get("/api/v1/child/coins/balance", headers=child_a["headers"])
    assert resp.status_code == 200
    # child_a has 50, child_b has 0 — if Bearer takes precedence, balance=50
    assert resp.json()["data"]["balance"] == 50

    # Clean up cookie
    client.cookies.delete("child_access_token")


# ---------------------------------------------------------------------------
# Additional tests: balance query, over-balance gifting, concurrent gifting
# ---------------------------------------------------------------------------

def test_balance_endpoint(client, auth_headers, child_a):
    """GET /child/coins/balance returns correct balance after grant."""
    _grant(client, auth_headers, child_a["id"], 75)

    resp = client.get("/api/v1/child/coins/balance", headers=child_a["headers"])
    assert resp.status_code == 200
    assert resp.json()["data"]["balance"] == 75


def test_gift_exceeds_balance_returns_422(client, auth_headers, child_a, child_b):
    """Gifting more than current balance returns 422."""
    _grant(client, auth_headers, child_a["id"], 10)

    resp = client.post("/api/v1/child/coins/gift", headers=child_a["headers"], json={
        "to_child_id": child_b["id"],
        "amount": 11,
        "emoji_reason": "🎁",
    })
    assert resp.status_code == 422


def test_concurrent_gift_balance_not_negative(client, auth_headers, child_a, child_b):
    """Two concurrent gift requests cannot drive balance below zero."""
    import threading

    _grant(client, auth_headers, child_a["id"], 10)

    results = []

    def do_gift():
        r = client.post("/api/v1/child/coins/gift", headers=child_a["headers"], json={
            "to_child_id": child_b["id"],
            "amount": 8,
            "emoji_reason": "🎁",
        })
        results.append(r.status_code)

    t1 = threading.Thread(target=do_gift)
    t2 = threading.Thread(target=do_gift)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    # At most one should succeed; balance must never go negative
    final_balance = client.get("/api/v1/child/coins/balance", headers=child_a["headers"]).json()["data"]["balance"]
    assert final_balance >= 0
    # At least one request must have been rejected (422) or only one succeeded (201)
    assert results.count(201) <= 1
