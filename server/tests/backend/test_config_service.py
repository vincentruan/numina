"""Tests for config_service: read/write with fallback and validation."""
import pytest

from apps.backend.app.errors.exceptions import AppError
from apps.backend.app.models.family_setting import FamilySetting
from apps.backend.app.models.user_setting import UserSetting
from apps.backend.app.services.config_service import (
    get_all_family_settings,
    get_all_user_settings,
    get_family_setting,
    get_user_setting,
    update_family_settings,
    update_user_settings,
)

FAMILY_ID = 12345
USER_ID = 67890


class TestFamilySettings:
    def test_get_returns_defaults_when_empty(self, db):
        result = get_all_family_settings(db, FAMILY_ID)
        assert result["ai_cache_ttl_report"] == 60
        assert result["ai_cache_ttl_finance_coach"] == 480
        assert result["dashboard_min_asset_count"] == 5
        assert result["scheduled_monthly_report_day"] == 1

    def test_update_and_read_back(self, db):
        update_family_settings(db, FAMILY_ID, {"ai_cache_ttl_report": 120})
        assert get_family_setting(db, FAMILY_ID, "ai_cache_ttl_report") == 120
        # Other keys still return defaults
        assert get_family_setting(db, FAMILY_ID, "ai_cache_ttl_finance_coach") == 480

    def test_update_multiple_keys(self, db):
        update_family_settings(
            db, FAMILY_ID,
            {"ai_cache_ttl_report": 30, "dashboard_min_asset_count": 10},
        )
        result = get_all_family_settings(db, FAMILY_ID)
        assert result["ai_cache_ttl_report"] == 30
        assert result["dashboard_min_asset_count"] == 10

    def test_update_unknown_key_raises(self, db):
        with pytest.raises(AppError):
            update_family_settings(db, FAMILY_ID, {"bogus_key": 42})

    def test_update_out_of_range_raises(self, db):
        with pytest.raises(AppError):
            update_family_settings(db, FAMILY_ID, {"ai_cache_ttl_report": 9999})

    def test_update_overwrites_existing(self, db):
        update_family_settings(db, FAMILY_ID, {"ai_cache_ttl_report": 120})
        update_family_settings(db, FAMILY_ID, {"ai_cache_ttl_report": 240})
        assert get_family_setting(db, FAMILY_ID, "ai_cache_ttl_report") == 240
        # Verify only one row exists (upsert, not duplicate)
        rows = (
            db.query(FamilySetting)
            .filter_by(family_id=FAMILY_ID, key="ai_cache_ttl_report")
            .all()
        )
        assert len(rows) == 1

    def test_get_single_key_default(self, db):
        assert get_family_setting(db, FAMILY_ID, "ai_cache_ttl_report") == 60


class TestUserSettings:
    def test_get_returns_defaults_when_empty(self, db):
        result = get_all_user_settings(db, USER_ID)
        assert result["dashboard_trend_period"] == "month"
        assert result["activity_feed_page_size"] == 20

    def test_update_and_read_back(self, db):
        update_user_settings(db, USER_ID, {"dashboard_trend_period": "year"})
        assert get_user_setting(db, USER_ID, "dashboard_trend_period") == "year"

    def test_update_invalid_allowed_value(self, db):
        with pytest.raises(AppError):
            update_user_settings(db, USER_ID, {"dashboard_trend_period": "decade"})

    def test_update_out_of_range(self, db):
        with pytest.raises(AppError):
            update_user_settings(db, USER_ID, {"activity_feed_page_size": 999})

    def test_update_unknown_key_raises(self, db):
        with pytest.raises(AppError):
            update_user_settings(db, USER_ID, {"bogus_key": "value"})

    def test_get_single_key_default(self, db):
        assert get_user_setting(db, USER_ID, "dashboard_trend_period") == "month"
