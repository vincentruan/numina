# backend/tests/test_notification_i18n.py
"""Tests for notification template i18n (locale-aware rendering)."""
from unittest.mock import patch

from apps.backend.app.services.notification.sender import (
    _normalize_locale,
    render_template,
)


# ── _normalize_locale ────────────────────────────────────────────────────────────


def test_normalize_locale_zh_cn():
    assert _normalize_locale("zh-CN") == "zh-CN"


def test_normalize_locale_zh_tw():
    assert _normalize_locale("zh-TW") == "zh-CN"


def test_normalize_locale_en_us():
    assert _normalize_locale("en-US") == "en-US"


def test_normalize_locale_en_gb():
    assert _normalize_locale("en-GB") == "en-US"


def test_normalize_locale_ja():
    assert _normalize_locale("ja-JP") == "en-US"


def test_normalize_locale_empty():
    assert _normalize_locale("") == "en-US"


# ── render_template locale ───────────────────────────────────────────────────────


_VARS = {"asset_name": "Test", "amount": "1000", "threshold": "5000"}


def test_render_template_default_locale_is_chinese():
    result = render_template("large_purchase", "feishu", _VARS)
    assert "大额消费" in result


def test_render_template_en_us():
    result = render_template("large_purchase", "feishu", _VARS, locale="en-US")
    assert "Large Purchase" in result


def test_render_template_zh_tw_resolves_to_chinese():
    result = render_template("large_purchase", "feishu", _VARS, locale="zh-TW")
    assert "大额消费" in result


def test_render_template_ja_resolves_to_english():
    result = render_template("large_purchase", "feishu", _VARS, locale="ja-JP")
    assert "Large Purchase" in result


def test_render_template_all_channels_en():
    """Verify all channel types render in English."""
    for channel_type in ["telegram", "feishu", "email_subject", "email_body", "webpush_title", "webpush_body"]:
        result = render_template("large_purchase", channel_type, _VARS, locale="en-US")
        assert isinstance(result, str)
        assert len(result) > 0


def test_render_template_all_templates_have_en():
    """Verify all 11 template types render in English without error."""
    types = [
        "large_purchase", "expiring_soon", "maturity", "allocation_drift",
        "chore_completed", "treasure_redeemed", "wish_redeemed",
        "ai_report_complete", "ai_finance_coach_complete",
        "ai_wish_advice_complete", "ai_literacy_report_complete",
    ]
    vars_all = {
        "asset_name": "Test", "amount": "1000", "expiry_date": "2026-01-01",
        "days_left": "30", "maturity_date": "2026-06-01", "threshold": "5000",
        "category": "Stocks", "current_pct": "40", "target_pct": "30",
        "drift_pct": "10", "child_name": "Kid", "chore_title": "Dishes",
        "treasure_title": "Toy", "wish_title": "Bike", "task_title": "Report",
    }
    for rtype in types:
        result = render_template(rtype, "feishu", vars_all, locale="en-US")
        assert isinstance(result, str)
        assert len(result) > 0


# ── _env_prefix locale ──────────────────────────────────────────────────────────


def test_env_prefix_zh_cn_dev():
    from apps.backend.app.services.notification.dispatcher import _env_prefix

    with patch(
        "apps.backend.app.services.notification.dispatcher.settings"
    ) as mock_settings:
        mock_settings.ENVIRONMENT = "development"
        assert _env_prefix("zh-CN") == "【测试】"


def test_env_prefix_en_us_dev():
    from apps.backend.app.services.notification.dispatcher import _env_prefix

    with patch(
        "apps.backend.app.services.notification.dispatcher.settings"
    ) as mock_settings:
        mock_settings.ENVIRONMENT = "development"
        assert _env_prefix("en-US") == "[Test]"


def test_env_prefix_production_no_prefix():
    from apps.backend.app.services.notification.dispatcher import _env_prefix

    with patch(
        "apps.backend.app.services.notification.dispatcher.settings"
    ) as mock_settings:
        mock_settings.ENVIRONMENT = "production"
        assert _env_prefix("zh-CN") == ""
        assert _env_prefix("en-US") == ""


# ── _resolve_locale ─────────────────────────────────────────────────────────────


def test_resolve_locale_owner_found(db_session):
    from apps.backend.app.models.family import Family
    from apps.backend.app.models.user import User
    from apps.backend.app.services.notification.dispatcher import _resolve_locale
    from apps.backend.app.utils.snowflake import next_id

    fam = Family(id=next_id(), name="Test Family", created_by=next_id())
    db_session.add(fam)
    db_session.flush()

    owner = User(
        id=next_id(),
        family_id=fam.id,
        username="owner",
        display_name="Owner",
        password_hash="fake",
        role="owner",
        language="en-US",
    )
    db_session.add(owner)
    db_session.commit()

    assert _resolve_locale(db_session, fam.id) == "en-US"


def test_resolve_locale_no_owner_fallback(db_session):
    from apps.backend.app.models.family import Family
    from apps.backend.app.services.notification.dispatcher import _resolve_locale
    from apps.backend.app.utils.snowflake import next_id

    fam = Family(id=next_id(), name="No Owner Family", created_by=next_id())
    db_session.add(fam)
    db_session.commit()

    assert _resolve_locale(db_session, fam.id) == "zh-CN"
