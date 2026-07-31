"""Family manifesto models: FamilyManifesto, ManifestoVersion, ManifestoSignature, ManifestoFeedback."""
import pytest
from sqlalchemy.exc import IntegrityError

from apps.backend.app.models.manifesto import (
    FamilyManifesto,
    ManifestoFeedback,
    ManifestoSignature,
    ManifestoVersion,
)


def test_create_family_manifesto(db_session):
    m = FamilyManifesto(family_id=100, created_by=1)
    db_session.add(m)
    db_session.commit()
    db_session.refresh(m)
    assert m.id is not None
    assert m.status == "active"
    assert m.family_id == 100
    assert m.created_by == 1
    assert m.created_at is not None
    assert m.updated_at is not None


def test_create_manifesto_version(db_session):
    m = FamilyManifesto(family_id=100, created_by=1)
    db_session.add(m)
    db_session.commit()

    v = ManifestoVersion(
        manifesto_id=m.id,
        version_number=1,
        template_id="default_v1",
        title="Our Family Promise",
        body="We promise to support each other.",
        created_by=1,
    )
    db_session.add(v)
    db_session.commit()
    db_session.refresh(v)
    assert v.id is not None
    assert v.change_type == "initial"
    assert v.trackable_clause_indices is None


def test_create_manifesto_version_with_clause_indices(db_session):
    v = ManifestoVersion(
        manifesto_id=1,
        version_number=2,
        template_id="default_v1",
        title="Updated",
        body="Updated body.",
        change_type="minor",
        trackable_clause_indices=[0, 2, 5],
        created_by=1,
    )
    db_session.add(v)
    db_session.commit()
    db_session.refresh(v)
    assert v.trackable_clause_indices == [0, 2, 5]
    assert v.change_type == "minor"


def test_manifesto_signature_null_signature_data(db_session):
    """Tap-to-consent: signature_data is NULL."""
    sig = ManifestoSignature(version_id=1, user_id=10)
    db_session.add(sig)
    db_session.commit()
    db_session.refresh(sig)
    assert sig.id is not None
    assert sig.signature_data is None
    assert sig.signed_at is not None


def test_manifesto_signature_base64_data(db_session):
    """Parent handwritten signature: base64 PNG."""
    sig = ManifestoSignature(
        version_id=1,
        user_id=11,
        signature_data="iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg==",
    )
    db_session.add(sig)
    db_session.commit()
    db_session.refresh(sig)
    assert sig.signature_data is not None
    assert sig.signature_data.startswith("iVBORw0KGgo")


def test_manifesto_signature_unique_constraint(db_session):
    sig1 = ManifestoSignature(version_id=1, user_id=20)
    sig2 = ManifestoSignature(version_id=1, user_id=20)
    db_session.add(sig1)
    db_session.commit()
    db_session.add(sig2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_manifesto_feedback(db_session):
    fb = ManifestoFeedback(
        manifesto_id=1,
        user_id=10,
        family_id=100,
        content="Great manifesto!",
    )
    db_session.add(fb)
    db_session.commit()
    db_session.refresh(fb)
    assert fb.id is not None
    assert fb.is_read is False
    assert fb.created_at is not None


def test_family_id_indexed(db_session):
    """Verify family_id columns are indexed via table inspection."""
    from apps.backend.app.database import Base

    for table_name in ("family_manifesto", "manifesto_feedback"):
        table = Base.metadata.tables[table_name]
        index_cols = {c.name for idx in table.indexes for c in idx.columns}
        assert "family_id" in index_cols, f"{table_name}.family_id should be indexed"


def test_snowflake_id_generation(db_session):
    m = FamilyManifesto(family_id=100, created_by=1)
    db_session.add(m)
    db_session.commit()
    db_session.refresh(m)
    # Snowflake IDs are large integers (not None, > 0)
    assert isinstance(m.id, int)
    assert m.id > 0
