"""ArchivableMixin tests.

Verifies the is_archived column provided by the mixin, including default
value, server_default on Liability, and query filter compatibility.
"""
from packages.db.mixins.archivable import ArchivableMixin
from packages.db.models.asset import Asset
from packages.db.models.liability import Liability


def test_archivable_mixin_provides_is_archived():
    """ArchivableMixin defines is_archived as a mapped column."""
    assert hasattr(ArchivableMixin, "is_archived")


def test_asset_inherits_archivable_mixin():
    """Asset uses ArchivableMixin and has is_archived column."""
    assert issubclass(Asset, ArchivableMixin)
    asset = Asset(
        user_id=1, family_id=1, category_id=1,
        name="Test", asset_type="physical",
    )
    # default=False fires on DB insert; Python-side is None before flush
    assert hasattr(asset, "is_archived")


def test_asset_is_archived_default_on_flush(packages_db):
    """Asset.is_archived defaults to False after DB flush."""
    asset = Asset(
        user_id=1, family_id=1, category_id=1,
        name="Test", asset_type="physical",
    )
    packages_db.add(asset)
    packages_db.flush()
    assert asset.is_archived is False


def test_asset_is_archived_settable():
    """Asset.is_archived can be set to True."""
    asset = Asset(
        user_id=1, family_id=1, category_id=1,
        name="Test", asset_type="physical",
    )
    asset.is_archived = True
    assert asset.is_archived is True


def test_liability_has_is_archived_with_server_default(packages_db):
    """Liability defines is_archived inline with server_default=text('false')."""
    liability = Liability(
        user_id=1, family_id=1, category="other",
        repayment_method="equal_payment", name="Test",
        original_amount=1000, remaining_amount=1000,
    )
    packages_db.add(liability)
    packages_db.flush()
    assert liability.is_archived is False


def test_liability_is_archived_settable():
    """Liability.is_archived can be toggled."""
    liability = Liability(
        user_id=1, family_id=1, category="other",
        repayment_method="equal_payment", name="Test",
        original_amount=1000, remaining_amount=1000,
    )
    liability.is_archived = True
    assert liability.is_archived is True


def test_liability_status_active(packages_db):
    """Liability.status returns 'active' when is_active=True."""
    liability = Liability(
        user_id=1, family_id=1, category="other",
        repayment_method="equal_payment", name="Test",
        original_amount=1000, remaining_amount=500,
        is_active=True, is_archived=False,
    )
    packages_db.add(liability)
    packages_db.flush()
    assert liability.status == "active"


def test_liability_status_paid_off(packages_db):
    """Liability.status returns 'paid_off' when is_active=False, is_archived=False."""
    liability = Liability(
        user_id=1, family_id=1, category="other",
        repayment_method="equal_payment", name="Test",
        original_amount=1000, remaining_amount=0,
        is_active=False, is_archived=False,
    )
    packages_db.add(liability)
    packages_db.flush()
    assert liability.status == "paid_off"


def test_liability_status_archived(packages_db):
    """Liability.status returns 'archived' when is_active=False, is_archived=True."""
    liability = Liability(
        user_id=1, family_id=1, category="other",
        repayment_method="equal_payment", name="Test",
        original_amount=1000, remaining_amount=0,
        is_active=False, is_archived=True,
    )
    packages_db.add(liability)
    packages_db.flush()
    assert liability.status == "archived"
