"""Initialize test data for development environment."""
import requests
import os

# Disable proxy
os.environ['NO_PROXY'] = 'localhost,127.0.0.1'
session = requests.Session()
session.trust_env = False

BASE_URL = "http://localhost:8000/api/v1"

# CI invitation codes
CI_CODES = ["CI0001", "CI0002", "CI0003", "CI0004", "CI0005", "CI0006", "CI0007", "CI0008"]
code_idx = 0


def register_or_login(username: str, password: str, display_name: str, family_name: str) -> str:
    """Register or login and return access token."""
    # Try login first
    login_resp = session.post(
        f"{BASE_URL}/auth/login",
        json={"username": username, "password": password}
    )
    if login_resp.status_code == 200:
        print(f"[INFO] {username} already exists, logging in")
        return login_resp.json()["data"]["access_token"]

    # Register
    global code_idx
    invite_code = CI_CODES[code_idx]
    code_idx += 1
    reg_resp = session.post(
        f"{BASE_URL}/auth/register",
        json={
            "username": username,
            "display_name": display_name,
            "password": password,
            "family_name": family_name,
            "family_invitation_code": invite_code
        }
    )
    if reg_resp.status_code in (200, 201):
        print(f"[OK] {username} registered")
        return reg_resp.json()["data"]["access_token"]
    raise Exception(f"Failed to register {username}: {reg_resp.text}")


def get_category_id(token: str, name: str, asset_type: str) -> str:
    """Get category ID by name."""
    resp = session.get(
        f"{BASE_URL}/categories?asset_type={asset_type}",
        headers={"Authorization": f"Bearer {token}"}
    )
    cats = resp.json()["data"]
    cat = next(c for c in cats if c["name"] == name)
    return cat["id"]


def create_asset(token: str, asset_data: dict) -> str:
    """Create an asset."""
    resp = session.post(
        f"{BASE_URL}/assets/",
        headers={"Authorization": f"Bearer {token}"},
        json=asset_data
    )
    if resp.status_code == 201:
        return resp.json()["data"]["id"]
    print(f"[WARN] Failed to create asset: {resp.status_code} - {resp.text}")
    return None


def create_liability(token: str, liability_data: dict) -> str:
    """Create a liability."""
    resp = session.post(
        f"{BASE_URL}/liabilities/",
        headers={"Authorization": f"Bearer {token}"},
        json=liability_data
    )
    if resp.status_code in (200, 201):
        return resp.json()["data"]["id"]
    print(f"[WARN] Failed to create liability: {resp.status_code} - {resp.text}")
    return None


def create_wish(token: str, wish_data: dict) -> str:
    """Create a wish."""
    resp = session.post(
        f"{BASE_URL}/wishes/",
        headers={"Authorization": f"Bearer {token}"},
        json=wish_data
    )
    if resp.status_code in (200, 201):
        return resp.json()["data"]["id"]
    print(f"[WARN] Failed to create wish: {resp.status_code} - {resp.text}")
    return None


def main():
    print("=" * 50)
    print("Numina Test Data Initialization")
    print("=" * 50)

    # 1. test_empty - empty family
    print("\n[INFO] Initializing test_empty...")
    token_empty = register_or_login("test_empty", "TestEmpty123!", "Empty Test User", "Empty Test Family")
    print("[OK] test_empty ready (no assets)")

    # 2. test_asset - single physical asset
    print("\n[INFO] Initializing test_asset...")
    token_asset = register_or_login("test_asset", "TestAsset123!", "Asset Test User", "Asset Test Family")
    cat_house = get_category_id(token_asset, "房产", "physical")

    create_asset(token_asset, {
        "name": "测试房产",
        "asset_type": "physical",
        "category_id": cat_house,
        "purchase_price": 1000000,
        "current_value": 1000000,
        "currency": "CNY",
        "purchase_date": "2024-01-01",
        "status": "in_use",
        "location": "测试城市",
    })
    print("[OK] test_asset ready (1 asset)")

    # 3. test_rich - complete data
    print("\n[INFO] Initializing test_rich...")
    token_rich = register_or_login("test_rich", "TestRich123!", "Rich Test User", "Rich Test Family")

    cat_house_r = get_category_id(token_rich, "房产", "physical")
    cat_car_r = get_category_id(token_rich, "车辆", "physical")
    cat_digital_r = get_category_id(token_rich, "数码", "physical")
    cat_stock_r = get_category_id(token_rich, "股票", "financial")
    cat_fund_r = get_category_id(token_rich, "基金", "financial")
    cat_deposit_r = get_category_id(token_rich, "存款", "financial")

    # Physical assets
    create_asset(token_rich, {
        "name": "测试房产",
        "asset_type": "physical",
        "category_id": cat_house_r,
        "purchase_price": 5000000,
        "current_value": 5500000,
        "currency": "CNY",
        "purchase_date": "2020-01-01",
        "status": "in_use",
        "location": "测试城市",
    })

    car_id = create_asset(token_rich, {
        "name": "测试车辆",
        "asset_type": "physical",
        "category_id": cat_car_r,
        "purchase_price": 300000,
        "current_value": 250000,
        "currency": "CNY",
        "purchase_date": "2022-06-01",
        "status": "in_use",
    })

    create_asset(token_rich, {
        "name": "测试电脑",
        "asset_type": "physical",
        "category_id": cat_digital_r,
        "purchase_price": 15000,
        "current_value": 10000,
        "currency": "CNY",
        "purchase_date": "2023-01-01",
        "status": "in_use",
    })

    # Financial assets
    create_asset(token_rich, {
        "name": "测试股票",
        "asset_type": "financial",
        "category_id": cat_stock_r,
        "purchase_price": 100000,
        "current_value": 120000,
        "currency": "CNY",
        "purchase_date": "2023-01-01",
    })

    create_asset(token_rich, {
        "name": "测试基金",
        "asset_type": "financial",
        "category_id": cat_fund_r,
        "purchase_price": 50000,
        "current_value": 55000,
        "currency": "CNY",
        "purchase_date": "2023-06-01",
    })

    create_asset(token_rich, {
        "name": "测试存款",
        "asset_type": "financial",
        "category_id": cat_deposit_r,
        "purchase_price": 200000,
        "current_value": 200000,
        "currency": "CNY",
        "purchase_date": "2024-01-01",
    })

    # Liabilities
    create_liability(token_rich, {
        "name": "测试房贷",
        "category": "mortgage",
        "original_amount": 3000000,
        "remaining_amount": 2800000,
        "currency": "CNY",
        "interest_rate": 4.2,
        "monthly_payment": 15000,
        "start_date": "2020-01-01",
        "end_date": "2050-01-01",
    })

    create_liability(token_rich, {
        "name": "测试车贷",
        "category": "car_loan",
        "original_amount": 200000,
        "remaining_amount": 100000,
        "currency": "CNY",
        "interest_rate": 5.0,
        "monthly_payment": 4000,
        "start_date": "2022-06-01",
        "end_date": "2026-06-01",
        "linked_asset_id": car_id,
    })

    # Wishes
    create_wish(token_rich, {
        "name": "测试心愿1",
        "expected_price": 50000,
        "currency": "CNY",
        "priority": "high",
    })

    create_wish(token_rich, {
        "name": "测试心愿2",
        "expected_price": 10000,
        "currency": "CNY",
        "priority": "medium",
    })

    print("[OK] test_rich ready (6 assets + 2 liabilities + 2 wishes)")

    print("\n" + "=" * 50)
    print("Test data initialization complete!")
    print("=" * 50)

    # Summary
    print("\nTest accounts:")
    print("  - test_empty / TestEmpty123! (empty family)")
    print("  - test_asset / TestAsset123! (1 asset)")
    print("  - test_rich  / TestRich123!  (6 assets + 2 liabilities + 2 wishes)")


if __name__ == "__main__":
    main()