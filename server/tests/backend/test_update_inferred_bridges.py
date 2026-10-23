"""Tests for update_inferred_bridges script."""

from unittest.mock import MagicMock

import pytest

from scripts.update_inferred_bridges import update_inferred_bridges


@pytest.fixture
def mock_db():
    db = MagicMock()
    db.query.return_value.filter.return_value.delete.return_value = 3
    return db


@pytest.fixture
def mock_session(mock_db):
    session = MagicMock()
    session.__enter__ = MagicMock(return_value=session)
    session.__exit__ = MagicMock(return_value=False)
    return session


@pytest.fixture(autouse=True)
def _patch_session(monkeypatch, mock_session):
    """Replace SessionLocal in the script module with a test mock."""
    monkeypatch.setattr(
        "scripts.update_inferred_bridges.SessionLocal",
        lambda: mock_session,
    )


@pytest.fixture
def mock_inference(monkeypatch):
    """Patch infer_cross_subject_bridges to return a controllable list."""
    bridges: list = []

    def _set(new_bridges):
        bridges.clear()
        bridges.extend(new_bridges)

    def _infer(*args, **kwargs):
        return list(bridges)

    monkeypatch.setattr(
        "apps.backend.app.services.learning.bridge_inference.infer_cross_subject_bridges",
        _infer,
    )
    return _set


def _make_bridge(topic_id=1, prereq_id=2, confidence=0.5):
    from apps.backend.app.services.learning.bridge_inference import InferredBridge

    return InferredBridge(
        topic_id=topic_id,
        prerequisite_id=prereq_id,
        strength="soft",
        reason="Inferred cross-subject bridge via keyword overlap",
        confidence=confidence,
    )


class TestUpdateInferredBridges:
    def test_deletes_old_and_inserts_new(self, mock_db, mock_session, mock_inference):
        """Normal execution: delete old inferred edges, insert new ones."""
        mock_session.query.return_value.filter.return_value.delete.return_value = 2
        mock_inference([_make_bridge(1, 2, 0.7), _make_bridge(3, 4, 0.8)])

        result = update_inferred_bridges("os-taxonomy")

        assert result["deleted"] == 2
        assert result["inserted"] == 2
        # Commit should be called twice: once after delete, once after insert
        assert mock_session.commit.call_count == 2
        # add() called for each new bridge
        assert mock_session.add.call_count == 2

    def test_explicit_edges_untouched(self, mock_db, mock_session, mock_inference):
        """Only source_type='inferred' edges are deleted."""
        mock_inference([])

        update_inferred_bridges("os-taxonomy")

        # The delete call should filter by source_type='inferred'
        filter_call = mock_session.query.return_value.filter
        assert filter_call.called

    def test_dry_run_does_not_commit(self, mock_db, mock_session, mock_inference):
        """Dry-run mode must not persist any changes."""
        mock_session.query.return_value.filter.return_value.delete.return_value = 5
        mock_inference([_make_bridge(1, 2, 0.6)])

        result = update_inferred_bridges("os-taxonomy", dry_run=True)

        assert result["dry_run"] is True
        assert result["deleted"] == 5
        assert result["inserted"] == 1
        # No commit in dry-run mode
        mock_session.commit.assert_not_called()

    def test_empty_result(self, mock_db, mock_session, mock_inference):
        """No old edges to delete, no new bridges generated."""
        mock_session.query.return_value.filter.return_value.delete.return_value = 0
        mock_inference([])

        result = update_inferred_bridges("os-taxonomy")

        assert result["deleted"] == 0
        assert result["inserted"] == 0
        mock_session.add.assert_not_called()

    def test_rollback_on_error(self, mock_db, mock_session):
        """If inference fails, the session should be rolled back."""

        def _raise(*args, **kwargs):
            raise RuntimeError("inference failed")

        import apps.backend.app.services.learning.bridge_inference as bi_mod

        original = bi_mod.infer_cross_subject_bridges
        bi_mod.infer_cross_subject_bridges = _raise
        try:
            with pytest.raises(RuntimeError, match="inference failed"):
                update_inferred_bridges("os-taxonomy")
            mock_session.rollback.assert_called_once()
        finally:
            bi_mod.infer_cross_subject_bridges = original

    def test_inserted_bridges_have_inferred_source_type(
        self, mock_db, mock_session, mock_inference
    ):
        """Inserted LearningDependency rows should have source_type='inferred'."""
        mock_inference([_make_bridge(10, 20, 0.85)])

        update_inferred_bridges("os-taxonomy")

        # Inspect what was passed to db.add()
        added = [call.args[0] for call in mock_session.add.call_args_list]
        assert len(added) == 1
        dep = added[0]
        assert dep.source_type == "inferred"
        assert dep.confidence == pytest.approx(0.85)
        assert dep.topic_id == 10
        assert dep.prerequisite_id == 20
