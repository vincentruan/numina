import json
def test_export_json_with_liability(client, auth_headers):
    r = client.post("/api/v1/liabilities", headers=auth_headers, json={
        "name": "车贷", "category": "car_loan",
        "original_amount": 80000, "remaining_amount": 55000, "monthly_payment": 2500,
    })
    assert r.status_code == 201, r.text
    r = client.get("/api/v1/export/all/json", headers=auth_headers)
    assert r.status_code == 200, f"FAIL: status={r.status_code} body={r.text[:300]}"
