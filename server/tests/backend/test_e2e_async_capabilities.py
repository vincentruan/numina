"""E2E integration tests for async capability flow (U12).

Tests the full chain:
  POST /refresh/events → NDJSON stream → parse → write → GET results non-empty + audit

Uses monkeypatched httpx to simulate the agent NDJSON stream without a real agent.
"""

import json
from datetime import datetime

from apps.backend.app.models.ai_asset_alert import AIAssetAlert
from apps.backend.app.models.ai_disposal_suggestion import AIDisposalSuggestion
from apps.backend.app.models.ai_extraction_audit import AIExtractionAudit
from apps.backend.app.models.ai_provider_config import AIProviderConfig
from apps.backend.app.models.ai_spending_leak import AISpendingLeak
from apps.backend.app.models.user import User
from apps.backend.app.utils.snowflake import next_id


def _enable_ai(db, family_id: int):
    cfg = AIProviderConfig(
        id=next_id(),
        family_id=family_id,
        name="test",
        provider="openai",
        api_key_encrypted="dummy",
        model_id="gpt-4o-mini",
        is_active=True,
        display_order=1,
    )
    db.add(cfg)
    db.commit()


def _make_ndjson_with_structured_data(capability: str) -> list[str]:
    """Build a realistic NDJSON stream with STRUCTURED_DATA block."""
    if capability == "alerts":
        data = [
            {"asset_name": "MacBook Pro", "alert_type": "aging", "severity": "high",
             "suggestion": "Consider replacement", "remaining_life_days": 30, "daily_cost": 5.0}
        ]
    elif capability == "disposal":
        data = [
            {"asset_name": "Old Printer", "inefficiency_score": 85,
             "suggested_channel": "二手平台", "estimated_value": 200}
        ]
    elif capability == "spending_leak":
        data = [
            {"asset_name": "Gym Membership", "leak_type": "high_idle_cost",
             "severity": "medium", "estimated_annual_waste": 3588.0,
             "suggestion": "考虑降级或取消"}
        ]
    else:
        data = []

    answer = f"分析完成。\n\n<!-- STRUCTURED_DATA\n{json.dumps(data, ensure_ascii=False)}\n-->"

    lines = [
        json.dumps({"type": "phase.thinking"}),
        json.dumps({"type": "token.stream", "is_thinking": True, "token": "让我分析..."}),
        json.dumps({"type": "phase.answering"}),
        json.dumps({"type": "token.stream", "is_thinking": False, "token": answer}),
        json.dumps({"type": "capability.end", "result": {"summary": ""}}),
    ]
    return lines


def _make_ndjson_no_structured_data() -> list[str]:
    """Build a stream that has no STRUCTURED_DATA — triggers fallback → failure."""
    answer = "这是一段纯文本分析，没有结构化数据块。"
    lines = [
        json.dumps({"type": "phase.answering"}),
        json.dumps({"type": "token.stream", "is_thinking": False, "token": answer}),
        json.dumps({"type": "capability.end", "result": {"summary": ""}}),
    ]
    return lines


class FakeStreamResponse:
    def __init__(self, lines: list[str]):
        self._lines = lines

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def aiter_lines(self):
        for line in self._lines:
            yield line


class FakeAsyncClient:
    def __init__(self, lines: list[str]):
        self._lines = lines

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    def stream(self, *args, **kwargs):
        return FakeStreamResponse(self._lines)


class TestAlertsE2EHappyPath:
    def test_full_flow_regex_html(self, client, auth_headers, db, monkeypatch):
        """POST /refresh/events → stream with STRUCTURED_DATA → GET alerts non-empty."""
        from apps.backend.app.routers import _ai_events_helper

        user = db.query(User).filter_by(username="testuser").first()
        family_id = user.family_id
        _enable_ai(db, family_id)

        lines = _make_ndjson_with_structured_data("alerts")
        monkeypatch.setattr(
            _ai_events_helper, "AgentClient",
            lambda *a, **k: FakeAsyncClient(lines),
        )

        resp = client.post(
            "/api/v1/ai/asset-alerts/refresh/events",
            headers={"Authorization": auth_headers["Authorization"]},
        )
        assert resp.status_code == 200
        body = resp.text
        assert "capability.error" not in body
        assert "phase.answering" in body

        # Verify structured data was written
        alerts = db.query(AIAssetAlert).filter_by(family_id=family_id).all()
        assert len(alerts) >= 1
        assert alerts[0].asset_name == "MacBook Pro"
        assert alerts[0].alert_type == "aging"

        # Verify audit record
        audit = db.query(AIExtractionAudit).filter_by(
            family_id=family_id, capability="alerts"
        ).first()
        assert audit is not None
        assert audit.method == "regex_html"
        assert audit.error_msg is None


class TestDisposalE2EHappyPath:
    def test_full_flow_regex_html(self, client, auth_headers, db, monkeypatch):
        from apps.backend.app.routers import _ai_events_helper

        user = db.query(User).filter_by(username="testuser").first()
        family_id = user.family_id
        _enable_ai(db, family_id)

        lines = _make_ndjson_with_structured_data("disposal")
        monkeypatch.setattr(
            _ai_events_helper, "AgentClient",
            lambda *a, **k: FakeAsyncClient(lines),
        )

        resp = client.post(
            "/api/v1/ai/disposal-suggestions/refresh/events",
            headers={"Authorization": auth_headers["Authorization"]},
        )
        assert resp.status_code == 200
        assert "capability.error" not in resp.text

        suggestions = db.query(AIDisposalSuggestion).filter_by(family_id=family_id).all()
        assert len(suggestions) >= 1
        assert suggestions[0].asset_name == "Old Printer"

        audit = db.query(AIExtractionAudit).filter_by(
            family_id=family_id, capability="disposal"
        ).first()
        assert audit is not None
        assert audit.method == "regex_html"


class TestSpendingLeakE2EHappyPath:
    def test_full_flow_regex_html(self, client, auth_headers, db, monkeypatch):
        from apps.backend.app.routers import _ai_events_helper

        user = db.query(User).filter_by(username="testuser").first()
        family_id = user.family_id
        _enable_ai(db, family_id)

        lines = _make_ndjson_with_structured_data("spending_leak")
        monkeypatch.setattr(
            _ai_events_helper, "AgentClient",
            lambda *a, **k: FakeAsyncClient(lines),
        )

        resp = client.post(
            "/api/v1/ai/spending-leaks/refresh/events",
            headers={"Authorization": auth_headers["Authorization"]},
        )
        assert resp.status_code == 200
        assert "capability.error" not in resp.text

        leaks = db.query(AISpendingLeak).filter_by(family_id=family_id).all()
        assert len(leaks) >= 1
        assert leaks[0].asset_name == "Gym Membership"

        audit = db.query(AIExtractionAudit).filter_by(
            family_id=family_id, capability="spending_leak"
        ).first()
        assert audit is not None
        assert audit.method == "regex_html"


class TestFallbackAndFailure:
    def test_no_structured_data_no_provider_fails(self, client, auth_headers, db, monkeypatch):
        """No STRUCTURED_DATA + no provider → status=failed + capability.error + audit method=failed."""
        from apps.backend.app.routers import _ai_events_helper

        user = db.query(User).filter_by(username="testuser").first()
        family_id = user.family_id
        _enable_ai(db, family_id)

        lines = _make_ndjson_no_structured_data()
        monkeypatch.setattr(
            _ai_events_helper, "AgentClient",
            lambda *a, **k: FakeAsyncClient(lines),
        )

        resp = client.post(
            "/api/v1/ai/asset-alerts/refresh/events",
            headers={"Authorization": auth_headers["Authorization"]},
        )
        assert resp.status_code == 200
        body = resp.text
        assert "capability.error" in body
        assert "api_key_error" in body

        # GET alerts should be empty (no data written)
        alerts = db.query(AIAssetAlert).filter_by(family_id=family_id).all()
        assert len(alerts) == 0

        # Audit shows method=failed
        audit = db.query(AIExtractionAudit).filter_by(
            family_id=family_id, capability="alerts"
        ).first()
        assert audit is not None
        assert audit.method == "failed"
        assert audit.error_msg == "api_key_error"

    def test_fallback_hit_with_mocked_llm(self, client, auth_headers, db, monkeypatch):
        """No STRUCTURED_DATA but LLM fallback succeeds → data written + audit method=llm_fallback_hit."""
        from apps.backend.app.routers import _ai_events_helper
        from apps.backend.app.services import ai_result_parser

        user = db.query(User).filter_by(username="testuser").first()
        family_id = user.family_id
        _enable_ai(db, family_id)

        lines = _make_ndjson_no_structured_data()
        monkeypatch.setattr(
            _ai_events_helper, "AgentClient",
            lambda *a, **k: FakeAsyncClient(lines),
        )

        # Mock the LLM call to return valid structured data
        monkeypatch.setattr(ai_result_parser, "decrypt_api_key", lambda _: "sk-fake")

        async def fake_call(*args, **kwargs):
            return json.dumps([
                {"asset_name": "FromLLM", "alert_type": "aging", "severity": "medium",
                 "suggestion": "Check it", "remaining_life_days": 60}
            ])

        monkeypatch.setattr(ai_result_parser, "_call_llm", fake_call)

        resp = client.post(
            "/api/v1/ai/asset-alerts/refresh/events",
            headers={"Authorization": auth_headers["Authorization"]},
        )
        assert resp.status_code == 200
        assert "capability.error" not in resp.text

        alerts = db.query(AIAssetAlert).filter_by(family_id=family_id).all()
        assert len(alerts) >= 1
        assert alerts[0].asset_name == "FromLLM"

        audit = db.query(AIExtractionAudit).filter_by(
            family_id=family_id, capability="alerts"
        ).first()
        assert audit is not None
        assert audit.method == "llm_fallback_hit"
