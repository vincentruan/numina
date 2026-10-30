"""Tests for validating and restoring a backup payload.

Restore is destructive: it replaces everything the family owns. These tests
pin the guarantees that make that safe to offer — a backup that fails
validation writes nothing, a partial failure leaves the existing data
untouched, and the restore points its foreign keys at the rows it actually
inserted rather than at rows the delete removed.
"""

from __future__ import annotations

import pytest

from packages.db.models.asset import Asset
from packages.db.models.category import Category
from packages.db.models.family import Family
from packages.db.models.tag import Tag
from packages.db.models.user import User
from packages.db.models.wish import Wish
from packages.domain.backup.service import (
    VALID_EXPORT_VERSIONS,
    export_family_data,
    import_family_data,
    preview_restore,
    validate_backup_data,
)

FAMILY_ID = 800001
USER_ID = 800002


@pytest.fixture()
def family(packages_db):
    fam = Family(id=FAMILY_ID, name="测试家庭", created_by=USER_ID)
    packages_db.add(fam)
    packages_db.flush()
    return fam


@pytest.fixture()
def member(packages_db, family):
    user = User(
        id=USER_ID,
        family_id=FAMILY_ID,
        username="owner1",
        display_name="家长",
        password_hash="x",
        role="owner",
    )
    packages_db.add(user)
    packages_db.flush()
    return user


@pytest.fixture()
def category(packages_db, family):
    cat = Category(
        id=810001, family_id=FAMILY_ID, name="家电", icon="📦", asset_type="physical"
    )
    packages_db.add(cat)
    packages_db.flush()
    return cat


class TestValidateBackupData:
    def test_accepts_v2_payload(self, packages_db, family):
        payload = export_family_data(packages_db, FAMILY_ID)

        assert validate_backup_data(payload) == []

    def test_accepts_v1_payload(self):
        v1 = {
            "export_version": "1.0",
            "assets": [],
            "liabilities": [],
            "categories": [],
            "tags": [],
        }

        assert validate_backup_data(v1) == []

    def test_rejects_unknown_version(self):
        errors = validate_backup_data({"export_version": "3.0", "assets": []})

        assert errors
        assert "3.0" in errors[0]
        assert "1.0" in errors[0] and "2.0" in errors[0]

    def test_rejects_missing_version(self):
        assert validate_backup_data({"assets": []})

    def test_rejects_non_dict(self):
        assert validate_backup_data(["not", "a", "dict"])

    def test_rejects_orphan_category_reference(self):
        payload = {
            "export_version": "2.0",
            "categories": [],
            "assets": [{"id": "1", "name": "x", "category_id": "999"}],
        }

        errors = validate_backup_data(payload)

        assert errors
        assert "999" in errors[0]

    def test_accepts_reference_to_system_category(self, packages_db, family):
        packages_db.add(
            Category(
                id=820001, family_id=None, name="系统", icon="📦", asset_type="physical"
            )
        )
        packages_db.flush()
        payload = {
            "export_version": "2.0",
            "categories": [],
            "assets": [{"id": "1", "name": "x", "category_id": "820001"}],
        }

        from packages.domain.backup.service import validate_backup_data_with_session

        assert validate_backup_data_with_session(packages_db, payload) == []

    def test_known_versions_are_exposed(self):
        assert VALID_EXPORT_VERSIONS == ("1.0", "2.0")


class TestPreviewRestore:
    def test_counts_existing_rows_and_payload_rows(
        self, packages_db, family, member, category
    ):
        packages_db.add_all(
            [
                Asset(
                    id=830001,
                    family_id=FAMILY_ID,
                    user_id=member.id,
                    category_id=category.id,
                    name="旧资产",
                    asset_type="physical",
                ),
                Wish(id=830002, family_id=FAMILY_ID, user_id=member.id, name="旧心愿"),
            ]
        )
        packages_db.flush()

        payload = {
            "export_version": "2.0",
            "export_date": "2026-10-28",
            "categories": [],
            "assets": [{"id": "1", "name": "新资产", "category_id": str(category.id)}],
            "wishes": [{}, {}],
        }

        preview = preview_restore(packages_db, FAMILY_ID, payload)

        assert preview["delete"]["assets"] == 1
        assert preview["delete"]["wishes"] == 1
        assert preview["insert"]["assets"] == 1
        assert preview["insert"]["wishes"] == 2
        assert preview["backup_date"] == "2026-10-28"
        assert preview["export_version"] == "2.0"

    def test_does_not_modify_data(self, packages_db, family, member, category):
        packages_db.add(
            Asset(
                id=830003,
                family_id=FAMILY_ID,
                user_id=member.id,
                category_id=category.id,
                name="保留",
                asset_type="physical",
            )
        )
        packages_db.flush()

        preview_restore(
            packages_db,
            FAMILY_ID,
            {"export_version": "2.0", "categories": [], "assets": []},
        )

        assert packages_db.query(Asset).filter_by(family_id=FAMILY_ID).count() == 1


class TestImportRoundTrip:
    def test_export_then_import_preserves_data(
        self, packages_db, family, member, category
    ):
        tag = Tag(id=840001, family_id=FAMILY_ID, name="贵重")
        asset = Asset(
            id=840002,
            family_id=FAMILY_ID,
            user_id=member.id,
            category_id=category.id,
            name="相机",
            asset_type="physical",
        )
        asset.tags = [tag]
        packages_db.add_all([tag, asset])
        packages_db.flush()

        payload = export_family_data(packages_db, FAMILY_ID)
        stats = import_family_data(packages_db, FAMILY_ID, USER_ID, payload)

        restored = packages_db.query(Asset).filter_by(family_id=FAMILY_ID).one()
        assert restored.name == "相机"
        assert restored.id == 840002
        assert [t.name for t in restored.tags] == ["贵重"]
        assert stats["assets"] == 1

    def test_full_replacement_removes_rows_not_in_backup(
        self, packages_db, family, member, category
    ):
        packages_db.add_all(
            [
                Asset(
                    id=850001,
                    family_id=FAMILY_ID,
                    user_id=member.id,
                    category_id=category.id,
                    name="会被删掉",
                    asset_type="physical",
                ),
                Asset(
                    id=850002,
                    family_id=FAMILY_ID,
                    user_id=member.id,
                    category_id=category.id,
                    name="保留",
                    asset_type="physical",
                ),
            ]
        )
        packages_db.flush()

        backup = {
            "export_version": "2.0",
            "categories": [
                {
                    "id": str(category.id),
                    "name": "家电",
                    "icon": "📦",
                    "asset_type": "physical",
                }
            ],
            "assets": [
                {
                    "id": "850002",
                    "user_id": str(USER_ID),
                    "family_id": str(FAMILY_ID),
                    "category_id": str(category.id),
                    "name": "保留",
                    "asset_type": "physical",
                }
            ],
        }

        import_family_data(packages_db, FAMILY_ID, USER_ID, backup)

        names = [
            a.name
            for a in packages_db.query(Asset).filter_by(family_id=FAMILY_ID).all()
        ]
        assert names == ["保留"]

    def test_other_families_are_untouched(self, packages_db, family, member, category):
        other = Family(id=890001, name="别人家", created_by=USER_ID)
        other_asset = Asset(
            id=860001,
            family_id=890001,
            user_id=member.id,
            category_id=category.id,
            name="别人的",
            asset_type="physical",
        )
        packages_db.add_all([other, other_asset])
        packages_db.flush()

        packages_db.query(Asset).filter_by(family_id=FAMILY_ID).delete()
        packages_db.flush()

        import_family_data(
            packages_db,
            FAMILY_ID,
            USER_ID,
            {"export_version": "2.0", "categories": [], "assets": []},
        )

        assert packages_db.query(Asset).filter_by(family_id=890001).count() == 1


class TestCategoryResolution:
    def test_composite_key_match_reuses_category(
        self, packages_db, family, member, category
    ):
        backup = {
            "export_version": "2.0",
            "categories": [
                {
                    "id": str(category.id),
                    "name": "家电",
                    "icon": "📦",
                    "asset_type": "physical",
                }
            ],
            "assets": [
                {
                    "id": "870001",
                    "user_id": str(USER_ID),
                    "family_id": str(FAMILY_ID),
                    "category_id": str(category.id),
                    "name": "冰箱",
                    "asset_type": "physical",
                }
            ],
        }

        import_family_data(packages_db, FAMILY_ID, USER_ID, backup)

        names = {
            c.name for c in packages_db.query(Category).filter_by(family_id=FAMILY_ID)
        }
        assert names == {"家电"}

    def test_same_name_different_asset_type_creates_new_category(
        self, packages_db, family, member, category
    ):
        # The pre-existing "家电/physical" category is itself in the payload, so
        # full replacement re-inserts it; the financial one is a distinct key and
        # must not silently reuse it.
        backup = {
            "export_version": "2.0",
            "categories": [
                {
                    "id": str(category.id),
                    "name": "家电",
                    "icon": "📦",
                    "asset_type": "physical",
                },
                {
                    "id": "820002",
                    "name": "家电",
                    "icon": "💰",
                    "asset_type": "financial",
                },
            ],
            "assets": [],
        }

        import_family_data(packages_db, FAMILY_ID, USER_ID, backup)

        types = {
            c.asset_type
            for c in packages_db.query(Category).filter_by(family_id=FAMILY_ID)
            if c.name == "家电"
        }
        assert types == {"physical", "financial"}


class TestVersionHandling:
    def test_v1_payload_imports_only_its_sections(
        self, packages_db, family, member, category
    ):
        v1 = {
            "export_version": "1.0",
            "assets": [
                {
                    "id": "880001",
                    "user_id": str(USER_ID),
                    "family_id": str(FAMILY_ID),
                    "category_id": str(category.id),
                    "name": "老资产",
                    "asset_type": "physical",
                }
            ],
            "categories": [
                {
                    "id": str(category.id),
                    "name": category.name,
                    "icon": "📦",
                    "asset_type": category.asset_type,
                }
            ],
            "tags": [],
            "liabilities": [],
        }

        stats = import_family_data(packages_db, FAMILY_ID, USER_ID, v1)

        assert stats["assets"] == 1
        assert packages_db.query(Wish).filter_by(family_id=FAMILY_ID).count() == 0

    def test_unknown_version_is_rejected_before_any_write(
        self, packages_db, family, member, category
    ):
        packages_db.add(
            Asset(
                id=880002,
                family_id=FAMILY_ID,
                user_id=member.id,
                category_id=category.id,
                name="原样保留",
                asset_type="physical",
            )
        )
        packages_db.flush()

        with pytest.raises(ValueError, match="不支持的备份版本"):
            import_family_data(
                packages_db, FAMILY_ID, USER_ID, {"export_version": "9.9", "assets": []}
            )

        assert packages_db.query(Asset).filter_by(family_id=FAMILY_ID).count() == 1

    def test_validation_failure_writes_nothing(
        self, packages_db, family, member, category
    ):
        packages_db.add(
            Asset(
                id=880003,
                family_id=FAMILY_ID,
                user_id=member.id,
                category_id=category.id,
                name="原样保留",
                asset_type="physical",
            )
        )
        packages_db.flush()

        orphan = {
            "export_version": "2.0",
            "categories": [],
            "assets": [{"id": "1", "name": "x", "category_id": "999999"}],
        }

        with pytest.raises(ValueError):
            import_family_data(packages_db, FAMILY_ID, USER_ID, orphan)

        assert packages_db.query(Asset).filter_by(family_id=FAMILY_ID).count() == 1
