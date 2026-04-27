# backend/tests/test_notification_rules.py
from datetime import date, timedelta

import pytest

from app.services.notification.rules import (
    check_allocation_drift,
    check_expiring_soon,
    check_large_purchase,
    check_maturity,
)


def test_check_large_purchase_fixed_threshold():
    result = check_large_purchase(
        db=None,
        family_id=1,
        asset_id=99,
        asset_name="豪华沙发",
        purchase_price=10000.0,
        threshold_fixed=5000.0,
        threshold_multiplier=None,
        avg_monthly_spend=None,
    )
    assert result is not None
    assert result["reminder_type"] == "large_purchase"
    assert result["severity"] == "warning"


def test_check_large_purchase_below_threshold():
    result = check_large_purchase(
        db=None,
        family_id=1,
        asset_id=99,
        asset_name="普通水杯",
        purchase_price=50.0,
        threshold_fixed=5000.0,
        threshold_multiplier=None,
        avg_monthly_spend=None,
    )
    assert result is None


def test_check_large_purchase_multiplier_threshold():
    result = check_large_purchase(
        db=None,
        family_id=1,
        asset_id=99,
        asset_name="电视",
        purchase_price=6000.0,
        threshold_fixed=None,
        threshold_multiplier=2.0,
        avg_monthly_spend=2000.0,
    )
    assert result is not None  # 6000 >= 2000 * 2 = 4000


def test_check_expiring_soon_within_30_days():
    expiry = date.today() + timedelta(days=20)
    result = check_expiring_soon(
        family_id=1,
        asset_id=1,
        asset_name="iPhone保修",
        expiry_date=expiry,
    )
    assert result is not None
    assert result["reminder_type"] == "expiring_soon"
    assert result["severity"] == "warning"


def test_check_expiring_soon_within_7_days():
    expiry = date.today() + timedelta(days=5)
    result = check_expiring_soon(
        family_id=1,
        asset_id=1,
        asset_name="iPhone保修",
        expiry_date=expiry,
    )
    assert result is not None
    assert result["severity"] == "critical"


def test_check_expiring_soon_far_future():
    expiry = date.today() + timedelta(days=60)
    result = check_expiring_soon(
        family_id=1,
        asset_id=1,
        asset_name="iPhone保修",
        expiry_date=expiry,
    )
    assert result is None


def test_check_expiring_soon_already_expired():
    expiry = date.today() - timedelta(days=1)
    result = check_expiring_soon(
        family_id=1,
        asset_id=1,
        asset_name="iPhone保修",
        expiry_date=expiry,
    )
    assert result is None


def test_check_maturity_within_30_days():
    mat = date.today() + timedelta(days=25)
    result = check_maturity(
        family_id=1,
        asset_id=2,
        asset_name="招行理财",
        maturity_date=mat,
        amount=100000.0,
    )
    assert result is not None
    assert result["reminder_type"] == "maturity"
    assert result["severity"] == "warning"


def test_check_maturity_within_7_days():
    mat = date.today() + timedelta(days=3)
    result = check_maturity(
        family_id=1,
        asset_id=2,
        asset_name="招行理财",
        maturity_date=mat,
        amount=100000.0,
    )
    assert result is not None
    assert result["severity"] == "critical"


def test_check_allocation_drift_triggered():
    result = check_allocation_drift(
        family_id=1,
        category="financial",
        current_pct=68.0,
        target_pct=50.0,
        drift_threshold=10.0,
    )
    assert result is not None
    assert result["reminder_type"] == "allocation_drift"


def test_check_allocation_drift_within_threshold():
    result = check_allocation_drift(
        family_id=1,
        category="financial",
        current_pct=55.0,
        target_pct=50.0,
        drift_threshold=10.0,
    )
    assert result is None
