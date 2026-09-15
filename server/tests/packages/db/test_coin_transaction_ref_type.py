"""Tests for CoinTransaction.ref_type property.

CoinTransaction exposes a computed `ref_type` property (no DB column) that
maps `transaction_type` to the referenced entity type string:

  - chore_earn      → "chore_instance"
  - wish_spend      → "child_wish"
  - parent_grant    → None
  - gift_sent       → None
  - gift_received   → None
"""

from __future__ import annotations

from apps.backend.app.models.coin_transaction import CoinTransaction


class TestCoinTransactionRefType:
    """CoinTransaction.ref_type 映射测试。"""

    def test_chore_earn_maps_to_chore_instance(self):
        tx = CoinTransaction(transaction_type="chore_earn")
        assert tx.ref_type == "chore_instance"

    def test_wish_spend_maps_to_child_wish(self):
        tx = CoinTransaction(transaction_type="wish_spend")
        assert tx.ref_type == "child_wish"

    def test_parent_grant_returns_none(self):
        tx = CoinTransaction(transaction_type="parent_grant")
        assert tx.ref_type is None

    def test_gift_sent_returns_none(self):
        tx = CoinTransaction(transaction_type="gift_sent")
        assert tx.ref_type is None

    def test_gift_received_returns_none(self):
        tx = CoinTransaction(transaction_type="gift_received")
        assert tx.ref_type is None
