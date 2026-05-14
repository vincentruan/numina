"""Golden case fixtures — realistic redacted context inputs for all 7 capabilities.

These fixtures represent what the orchestrator receives AFTER PII redaction.
They are used by both golden case tests and integration tests.
"""

from apps.agent.schemas.context import RedactedContext
from apps.agent.schemas.response import AgentResponse


# ── Shared redacted context ────────────────────────────────────────────────────

REDACTED_CONTEXT = RedactedContext(
    family_id="fam-golden-001",
    assets=[
        {
            "id": "a1",
            "category": "车辆",
            "asset_type": "physical",
            "current_value": 180000,
            "purchase_price": 220000,
            "usage_frequency": "daily",
            "expected_lifespan_days": 3650,
            "annual_maintenance_cost": 8000,
            "purchase_date": "2020-03",
        },
        {
            "id": "a2",
            "category": "数码",
            "asset_type": "physical",
            "current_value": 3000,
            "purchase_price": 8000,
            "usage_frequency": "idle",
            "expected_lifespan_days": 1825,
            "annual_maintenance_cost": 0,
            "purchase_date": "2021-06",
        },
        {
            "id": "a3",
            "category": "存款",
            "asset_type": "financial",
            "current_value": 150000,
            "purchase_price": 150000,
            "usage_frequency": None,
        },
        {
            "id": "a4",
            "category": "基金",
            "asset_type": "financial",
            "current_value": 85000,
            "purchase_price": 100000,
            "usage_frequency": None,
        },
    ],
    liabilities=[
        {
            "id": "l1",
            "liability_type": "mortgage",
            "amount_range": "50万-100万",
            "amount_midpoint": 750000.0,
            "interest_rate": 4.2,
            "monthly_payment_range": "3000-5000",
            "remaining_months": 240,
            "due_year_month": "2044-03",
        },
        {
            "id": "l2",
            "liability_type": "car_loan",
            "amount_range": "5万-10万",
            "amount_midpoint": 75000.0,
            "interest_rate": 5.8,
            "monthly_payment_range": "1000-3000",
            "remaining_months": 36,
            "due_year_month": "2027-04",
        },
    ],
    members=[
        {"label": "成员A", "role": "admin"},
        {"label": "成员B", "role": "member"},
    ],
    dashboard_overview={
        "total_assets": 418000,
        "total_liabilities": 825000,
        "net_worth": -407000,
        "asset_count": 4,
        "liability_count": 2,
    },
    dashboard_allocation={
        "items": [
            {"category": "车辆", "value": 180000, "percentage": 43.1},
            {"category": "存款", "value": 150000, "percentage": 35.9},
            {"category": "基金", "value": 85000, "percentage": 20.3},
            {"category": "数码", "value": 3000, "percentage": 0.7},
        ],
        "total": 418000,
    },
    dashboard_trend={
        "points": [
            {"date": "2025-10", "net_worth": -450000},
            {"date": "2025-11", "net_worth": -430000},
            {"date": "2025-12", "net_worth": -415000},
            {"date": "2026-01", "net_worth": -407000},
        ]
    },
    low_usage_assets=[
        {
            "id": "a2",
            "category": "数码",
            "usage_frequency": "idle",
            "daily_cost": 4.38,
        }
    ],
    redaction_log=["assets:name", "liabilities:name,institution,exact_amounts", "members:name"],
)


# ── Expected response shapes (structural assertions only) ─────────────────────

def assert_valid_agent_response(response: AgentResponse, capability: str) -> None:
    """Assert that an AgentResponse has the required structural properties."""
    assert response.capability == capability, f"Expected capability={capability}, got {response.capability}"
    assert isinstance(response.summary, str), "summary must be a string"
    assert len(response.summary) > 0, "summary must not be empty"
    assert isinstance(response.disclaimers, list), "disclaimers must be a list"
    assert len(response.disclaimers) > 0, "disclaimers must not be empty"
    assert isinstance(response.fallback_used, bool), "fallback_used must be bool"
    assert isinstance(response.audit_id, str) and len(response.audit_id) > 0


def assert_has_risk_flags(response: AgentResponse) -> None:
    assert isinstance(response.risk_flags, list)


def assert_has_recommendations(response: AgentResponse) -> None:
    assert isinstance(response.recommendations, list)


def assert_distinguishes_rule_vs_ai(response: AgentResponse) -> None:
    """Verify rule_based_findings and ai_inferences are separate lists."""
    assert isinstance(response.rule_based_findings, list)
    assert isinstance(response.ai_inferences, list)
    for f in response.ai_inferences:
        assert 0.0 <= f.confidence <= 0.75, (
            f"AI inference confidence {f.confidence} exceeds 0.75 cap"
        )
