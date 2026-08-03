"""Tests for DraftImport model — U1 verification."""

from apps.backend.app.models.draft_import import DraftImport
from apps.backend.app.models.liability import Liability


class TestDraftImportModel:
    """DraftImport ORM model tests."""

    def test_instantiation_with_all_fields(self, db):
        """Model instantiation with all fields produces valid ORM object."""
        draft = DraftImport(
            family_id=1001,
            user_id=2001,
            source_filename="statement.pdf",
            source_format="pdf",
            file_hash="a" * 64,
            status="pending",
        )
        draft.set_parsed_items([
            {"name": "Test Asset", "target_model": "asset", "confidence": 0.9},
        ])
        db.add(draft)
        db.flush()

        assert draft.id is not None
        assert draft.family_id == 1001
        assert draft.source_filename == "statement.pdf"
        assert draft.status == "pending"
        assert draft.created_at is not None

    def test_parsed_items_json_roundtrip(self, db):
        """parsed_items JSON serialization round-trips correctly."""
        items = [
            {
                "name": "招商银行信用卡",
                "target_model": "liability",
                "original_amount": 50000.00,
                "remaining_amount": 32150.50,
                "confidence": 0.85,
            },
            {
                "name": "iPhone 16 Pro",
                "target_model": "asset",
                "current_value": 8999.00,
                "confidence": 0.92,
            },
        ]
        draft = DraftImport(
            family_id=1001,
            user_id=2001,
            source_filename="test.xlsx",
            source_format="xlsx",
        )
        draft.set_parsed_items(items)
        db.add(draft)
        db.flush()

        # Round-trip: read back from DB
        loaded = db.query(DraftImport).filter_by(id=draft.id).first()
        assert loaded is not None
        result = loaded.get_parsed_items()
        assert len(result) == 2
        assert result[0]["name"] == "招商银行信用卡"
        assert result[0]["target_model"] == "liability"
        assert result[1]["confidence"] == 0.92

    def test_committed_record_ids_json_roundtrip(self, db):
        """committed_record_ids JSON serialization round-trips correctly."""
        draft = DraftImport(
            family_id=1001,
            user_id=2001,
            source_filename="test.pdf",
            source_format="pdf",
        )
        draft.set_parsed_items([])
        draft.set_committed_record_ids(["123456789012345", "987654321098765"])
        db.add(draft)
        db.flush()

        loaded = db.query(DraftImport).filter_by(id=draft.id).first()
        assert loaded is not None
        ids = loaded.get_committed_record_ids()
        assert ids == ["123456789012345", "987654321098765"]

    def test_committed_record_ids_empty_default(self, db):
        """get_committed_record_ids returns [] when None."""
        draft = DraftImport(
            family_id=1001,
            user_id=2001,
            source_filename="test.csv",
            source_format="csv",
        )
        draft.set_parsed_items([])
        db.add(draft)
        db.flush()

        loaded = db.query(DraftImport).filter_by(id=draft.id).first()
        assert loaded.get_committed_record_ids() == []

    def test_default_status_is_pending(self, db):
        """status defaults to 'pending'."""
        draft = DraftImport(
            family_id=1001,
            user_id=2001,
            source_filename="img.png",
            source_format="png",
        )
        draft.set_parsed_items([])
        db.add(draft)
        db.flush()

        loaded = db.query(DraftImport).filter_by(id=draft.id).first()
        assert loaded.status == "pending"


class TestLiabilityIsArchived:
    """Liability.is_archived field tests (added for import rollback)."""

    def test_liability_has_is_archived_default_false(self, db):
        """Liability.is_archived defaults to False."""
        liability = Liability(
            user_id=2001,
            family_id=1001,
            category="credit_card",
            name="Test Card",
            original_amount=10000,
            remaining_amount=5000,
        )
        db.add(liability)
        db.flush()

        loaded = db.query(Liability).filter_by(id=liability.id).first()
        assert loaded.is_archived is False

    def test_liability_is_archived_can_be_set_true(self, db):
        """Liability.is_archived can be set to True (for rollback)."""
        liability = Liability(
            user_id=2001,
            family_id=1001,
            category="mortgage",
            name="Home Loan",
            original_amount=500000,
            remaining_amount=350000,
        )
        db.add(liability)
        db.flush()

        liability.is_archived = True
        db.flush()

        loaded = db.query(Liability).filter_by(id=liability.id).first()
        assert loaded.is_archived is True
