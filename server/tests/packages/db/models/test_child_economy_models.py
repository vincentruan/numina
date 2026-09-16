"""Tests for packages.db.models.child_economy — ChoreTemplate, ChoreInstance, CoinTransaction."""

from __future__ import annotations

from packages.db.models.child_economy.chore import ChoreInstance, ChoreTemplate
from packages.db.models.child_economy.coin_transaction import CoinTransaction


class TestChoreImports:
    """Verify ChoreTemplate and ChoreInstance are importable from both paths."""

    def test_import_from_db_package(self):
        from packages.db.models.child_economy.chore import ChoreInstance as CI
        from packages.db.models.child_economy.chore import ChoreTemplate as CT

        assert CT.__name__ == "ChoreTemplate"
        assert CI.__name__ == "ChoreInstance"
        assert CT.__tablename__ == "chore_templates"
        assert CI.__tablename__ == "chore_instances"

    def test_backward_compat_import(self):
        """Backend re-export shim still works."""
        from apps.backend.app.models.chore import ChoreInstance as CI2
        from apps.backend.app.models.chore import ChoreTemplate as CT2

        assert CI2 is ChoreInstance
        assert CT2 is ChoreTemplate

    def test_models_registered_on_base(self):
        from packages.db.session import Base
        assert "chore_templates" in Base.metadata.tables
        assert "chore_instances" in Base.metadata.tables


class TestCoinTransactionImports:
    """Verify CoinTransaction is importable from both paths."""

    def test_import_from_db_package(self):
        from packages.db.models.child_economy.coin_transaction import (
            CoinTransaction as CTx,
        )
        assert CTx.__name__ == "CoinTransaction"
        assert CTx.__tablename__ == "coin_transactions"

    def test_backward_compat_import(self):
        from apps.backend.app.models.coin_transaction import CoinTransaction as CTx2
        assert CTx2 is CoinTransaction

    def test_model_registered_on_base(self):
        from packages.db.session import Base
        assert "coin_transactions" in Base.metadata.tables


class TestDomainImportFix:
    """Verify the domain service no longer imports from apps backend."""

    def test_domain_service_imports_db_models(self):
        """The literacy service should import from packages.db, not apps.backend."""
        import inspect

        import packages.domain.literacy.service as svc
        source = inspect.getsource(svc._aggregate_signals)
        assert "apps.backend.app.models.chore" not in source
        assert "apps.backend.app.models.coin_transaction" not in source
        assert "packages.db.models.child_economy.chore" in source
        assert "packages.db.models.child_economy.coin_transaction" in source
