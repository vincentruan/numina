"""Tests for the family export payload.

The payload is the whole disaster-recovery story: it must carry every
family-scoped table, keep IDs precise, and never decrypt a secret on the way
out. Anything missing here is unrecoverable, and anything decrypted here
leaks into remote storage.
"""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal

import pytest

from packages.db.models.asset import Asset
from packages.db.models.category import Category
from packages.db.models.family import Family
from packages.db.models.tag import Tag
from packages.db.models.user import User
from packages.db.models.wish import Wish
from packages.domain.backup.service import export_family_data

FAMILY_ID = 900001


@pytest.fixture()
def family(packages_db):
    fam = Family(id=FAMILY_ID, name="测试家庭", created_by=900002)
    packages_db.add(fam)
    packages_db.flush()
    return fam


@pytest.fixture()
def member(packages_db, family):
    user = User(
        id=900002,
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
        id=910002, family_id=FAMILY_ID, name="自定义", icon="📦", asset_type="physical"
    )
    packages_db.add(cat)
    packages_db.flush()
    return cat


class TestPayloadEnvelope:
    def test_reports_version_and_family(self, packages_db, family):
        payload = export_family_data(packages_db, FAMILY_ID)

        assert payload["export_version"] == "2.0"
        assert payload["family_id"] == str(FAMILY_ID)
        assert payload["export_date"] == date.today().isoformat()

    def test_every_section_is_present_even_when_empty(self, packages_db, family):
        payload = export_family_data(packages_db, FAMILY_ID)

        for section in (
            "users",
            "assets",
            "liabilities",
            "categories",
            "tags",
            "wishes",
            "chores",
            "coin_transactions",
            "milestones",
            "rental_contracts",
            "asset_snapshots",
            "trips",
            "itinerary_items",
            "expense_entries",
            "expense_categories",
            "cached_files",
            "file_remote_locations",
            "storage_backends",
            "learning_progress",
            "learning_stats",
            "learning_sessions",
            "notification_channels",
            "notification_configs",
            "reminders",
            "reminder_notifications",
            "ai_provider_configs",
        ):
            assert section in payload, f"missing section: {section}"
            assert payload[section] == [], f"{section} should be empty"

    def test_payload_is_json_serializable(self, packages_db, family, member, category):
        packages_db.add(
            Asset(
                family_id=FAMILY_ID,
                user_id=member.id,
                name="沙发",
                asset_type="physical",
                category_id=category.id,
                purchase_price=Decimal("1200.50"),
                purchase_date=date(2026, 1, 2),
            )
        )
        packages_db.flush()

        payload = export_family_data(packages_db, FAMILY_ID)

        # Must round-trip without custom encoders — this is what gets uploaded.
        assert (
            json.loads(json.dumps(payload, ensure_ascii=False))["assets"][0]["name"]
            == "沙发"
        )


class TestIdPrecision:
    def test_ids_are_strings(self, packages_db, family, member, category):
        asset = Asset(
            family_id=FAMILY_ID,
            user_id=member.id,
            name="车",
            asset_type="physical",
            category_id=category.id,
        )
        packages_db.add(asset)
        packages_db.flush()

        payload = export_family_data(packages_db, FAMILY_ID)

        exported = payload["assets"][0]
        assert isinstance(exported["id"], str)
        assert isinstance(exported["family_id"], str)
        assert exported["id"] == str(asset.id)

    def test_money_is_serialized_as_string(self, packages_db, family, member, category):
        packages_db.add(
            Asset(
                family_id=FAMILY_ID,
                user_id=member.id,
                name="表",
                asset_type="physical",
                category_id=category.id,
                purchase_price=Decimal("88.87"),
            )
        )
        packages_db.flush()

        payload = export_family_data(packages_db, FAMILY_ID)

        assert payload["assets"][0]["purchase_price"] == "88.87"


class TestSectionContents:
    def test_system_categories_are_excluded(self, packages_db, family):
        packages_db.add_all(
            [
                Category(
                    id=910001,
                    family_id=None,
                    name="系统分类",
                    icon="📦",
                    asset_type="physical",
                ),
                Category(
                    id=910002,
                    family_id=FAMILY_ID,
                    name="自定义",
                    icon="📦",
                    asset_type="physical",
                ),
            ]
        )
        packages_db.flush()

        payload = export_family_data(packages_db, FAMILY_ID)

        names = [c["name"] for c in payload["categories"]]
        assert names == ["自定义"]

    def test_asset_carries_tag_names(self, packages_db, family, member, category):
        tag = Tag(family_id=FAMILY_ID, name="贵重")
        asset = Asset(
            family_id=FAMILY_ID,
            user_id=member.id,
            name="相机",
            asset_type="physical",
            category_id=category.id,
        )
        asset.tags = [tag]
        packages_db.add_all([tag, asset])
        packages_db.flush()

        payload = export_family_data(packages_db, FAMILY_ID)

        assert payload["assets"][0]["tag_names"] == ["贵重"]

    def test_wishes_are_exported(self, packages_db, family, member):
        packages_db.add(
            Wish(
                family_id=FAMILY_ID,
                user_id=member.id,
                name="旅行",
                expected_price=Decimal("5000"),
            )
        )
        packages_db.flush()

        payload = export_family_data(packages_db, FAMILY_ID)

        assert payload["wishes"][0]["name"] == "旅行"

    def test_other_families_are_not_leaked(self, packages_db, family, member, category):
        packages_db.add_all(
            [
                Family(id=990001, name="别人家", created_by=900002),
                Asset(
                    id=920001,
                    family_id=990001,
                    user_id=member.id,
                    name="别人的",
                    asset_type="physical",
                    category_id=category.id,
                ),
            ]
        )
        packages_db.flush()

        payload = export_family_data(packages_db, FAMILY_ID)

        assert payload["assets"] == []


class TestSecretHandling:
    def test_encrypted_blobs_are_copied_verbatim(self, packages_db, family):
        from packages.db.models.storage_backend import (
            StorageBackend as StorageBackendModel,
        )

        packages_db.add(
            StorageBackendModel(
                family_id=FAMILY_ID,
                backend_type="github",
                config="ENCRYPTED-BLOB-VALUE",
                is_active=True,
            )
        )
        packages_db.flush()

        payload = export_family_data(packages_db, FAMILY_ID)

        assert payload["storage_backends"][0]["config"] == "ENCRYPTED-BLOB-VALUE"

    def test_ai_provider_api_key_is_not_decrypted(self, packages_db, family):
        from apps.backend.app.models.ai_provider_config import AIProviderConfig

        packages_db.add(
            AIProviderConfig(
                family_id=FAMILY_ID,
                name="dashscope",
                provider="dashscope",
                api_key_encrypted="ENCRYPTED-KEY",
            )
        )
        packages_db.flush()

        payload = export_family_data(packages_db, FAMILY_ID)

        assert payload["ai_provider_configs"][0]["api_key_encrypted"] == "ENCRYPTED-KEY"
