"""Tests for Liability.status hybrid property.

Liability exposes a computed `status` property (no DB column) that derives
from the boolean `is_active` column:

  - is_active=True  → "active"
  - is_active=False → "paid_off"
"""

from __future__ import annotations

from packages.db.models.liability import Liability


class TestLiabilityStatus:
    """Liability.status 派生值测试。"""

    def test_active_liability_status(self):
        is_obj = Liability(is_active=True)
        assert is_obj.status == "active"

    def test_paid_off_liability_status(self):
        is_obj = Liability(is_active=False)
        assert is_obj.status == "paid_off"
