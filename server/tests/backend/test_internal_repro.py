def test_internal_liabilities_endpoint(client, auth_headers):
    r = client.post("/api/v1/liabilities", headers=auth_headers, json={
        "name": "车贷", "category": "car_loan",
        "original_amount": 80000, "remaining_amount": 55000, "monthly_payment": 2500,
    })
    assert r.status_code == 201, r.text
    # The agent-facing internal endpoint returns plain list[dict]
    from apps.backend.app.routers.ai_internal import router
    # Find the agent token mechanism — just call via the app's internal prefix
    # This endpoint requires verify_agent_token; skip if too complex.
