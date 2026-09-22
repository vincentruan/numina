"""Tests for bootstrap_categories incremental backfill logic."""

from apps.backend.app.bootstrap.categories import (
    SYSTEM_CATEGORIES,
    bootstrap_categories,
)
from apps.backend.app.models.category import Category


class TestBootstrapCategoriesBackfill:
    """Verify the incremental backfill logic for system categories."""

    def test_fresh_bootstrap_creates_all_categories(self, db):
        """Fresh DB bootstrap creates all system categories including new ones."""
        bootstrap_categories(db)

        categories = db.query(Category).filter(Category.is_system).all()
        names = {c.name for c in categories}

        # Verify all system categories exist
        expected_names = {cat["name"] for cat in SYSTEM_CATEGORIES}
        assert names == expected_names

        # Verify new categories are present
        assert "租房" in names
        assert "旅游" in names
        assert len(categories) == len(SYSTEM_CATEGORIES)

    def test_backfill_adds_missing_categories(self, db):
        """Re-running bootstrap after deleting a category re-adds it."""
        # Initial bootstrap
        bootstrap_categories(db)
        initial_count = db.query(Category).filter(Category.is_system).count()

        # Delete one category
        db.query(Category).filter(Category.name == "旅游", Category.is_system).delete()
        db.commit()

        after_delete = db.query(Category).filter(Category.is_system).count()
        assert after_delete == initial_count - 1

        # Re-run bootstrap — should re-add the missing category
        bootstrap_categories(db)

        final_count = db.query(Category).filter(Category.is_system).count()
        assert final_count == initial_count

        # Verify the deleted category is back
        restored = db.query(Category).filter(
            Category.name == "旅游", Category.is_system
        ).first()
        assert restored is not None

    def test_bootstrap_idempotent_no_duplicates(self, db):
        """Running bootstrap twice does not create duplicates."""
        bootstrap_categories(db)
        count_after_first = db.query(Category).filter(Category.is_system).count()

        bootstrap_categories(db)
        count_after_second = db.query(Category).filter(Category.is_system).count()

        assert count_after_first == count_after_second
