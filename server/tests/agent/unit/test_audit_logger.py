"""Unit tests for services/audit_logger.py."""

import json
import os
import sys
import tempfile
import uuid
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from apps.agent.services.audit_logger import AuditEntry, AuditLogger, setup_audit_logger


class TestAuditEntry:
    def test_audit_id_is_uuid4(self):
        entry = AuditEntry(family_id="f1", capability="report", success=True)
        parsed = uuid.UUID(entry.audit_id, version=4)
        assert str(parsed) == entry.audit_id

    def test_timestamp_is_iso(self):
        from datetime import datetime
        entry = AuditEntry(family_id="f1", capability="report", success=True)
        # Should parse without error
        datetime.fromisoformat(entry.timestamp)

    def test_output_summary_truncated_to_200(self):
        long_text = "x" * 500
        entry = AuditEntry(family_id="f1", capability="report", success=True, output_summary=long_text)
        assert len(entry.output_summary) == 200

    def test_output_summary_short_not_truncated(self):
        entry = AuditEntry(family_id="f1", capability="report", success=True, output_summary="short")
        assert entry.output_summary == "short"

    def test_all_required_fields_present(self):
        entry = AuditEntry(
            family_id="f1",
            capability="chat",
            success=False,
            user_id="u1",
            skill_triggered="family-asset-checkup",
            fallback_used=True,
            deerflow_attempted=True,
            duration_ms=1234,
            error_type="DeerFlowTimeoutError",
            output_summary="partial result",
        )
        assert entry.family_id == "f1"
        assert entry.user_id == "u1"
        assert entry.skill_triggered == "family-asset-checkup"
        assert entry.fallback_used is True
        assert entry.deerflow_attempted is True
        assert entry.duration_ms == 1234
        assert entry.error_type == "DeerFlowTimeoutError"


class TestAuditLogger:
    def test_log_call_writes_entry(self, tmp_path):
        import apps.agent.services.audit_logger as al
        messages = []

        class CapturingHandler:
            level = 0
            def setFormatter(self, f): pass
            def handle(self, record): messages.append(record.getMessage())
            def emit(self, record): messages.append(record.getMessage())

        # Initialize audit logger first (required before accessing handlers)
        setup_audit_logger()

        # Clear existing handlers and add test handler
        for h in al._audit_logger.handlers[:]:
            al._audit_logger.removeHandler(h)
        al._audit_logger.addHandler(CapturingHandler())

        entry = AuditEntry(family_id="f1", capability="report", success=True)
        al.AuditLogger().log_call(entry)
        assert len(messages) > 0
        assert al._audit_logger is not None

    def test_log_call_does_not_raise_on_failure(self):
        """Audit failure must never propagate."""
        import apps.agent.services.audit_logger as al

        # Initialize audit logger first
        setup_audit_logger()

        # Clear existing handlers
        for h in al._audit_logger.handlers[:]:
            al._audit_logger.removeHandler(h)

        class BrokenHandler:
            level = 0
            def handle(self, record): raise RuntimeError("disk full")
            def emit(self, record): raise RuntimeError("disk full")

        al._audit_logger.addHandler(BrokenHandler())

        entry = AuditEntry(family_id="f1", capability="report", success=True)
        # Must not raise
        al.AuditLogger().log_call(entry)

    def test_success_entry_contains_family_id(self, tmp_path, capsys):
        import apps.agent.services.audit_logger as al
        messages = []

        class CapturingHandler:
            level = 0
            terminator = "\n"
            def handle(self, record): messages.append(record.getMessage())
            def emit(self, record): messages.append(record.getMessage())

        # Initialize audit logger first
        setup_audit_logger()

        for h in al._audit_logger.handlers[:]:
            al._audit_logger.removeHandler(h)
        al._audit_logger.addHandler(CapturingHandler())

        entry = AuditEntry(family_id="fam-123", capability="report", success=True)
        al.AuditLogger().log_call(entry)
        assert any("fam-123" in m for m in messages)

    def test_user_id_included_in_log(self, tmp_path):
        import apps.agent.services.audit_logger as al
        messages = []

        class CapturingHandler:
            level = 0
            def handle(self, record): messages.append(record.getMessage())
            def emit(self, record): messages.append(record.getMessage())

        # Initialize audit logger first
        setup_audit_logger()

        for h in al._audit_logger.handlers[:]:
            al._audit_logger.removeHandler(h)
        al._audit_logger.addHandler(CapturingHandler())

        entry = AuditEntry(family_id="f1", capability="chat", success=True, user_id="user-42")
        al.AuditLogger().log_call(entry)
        assert any("user-42" in m for m in messages)


class TestDeerflowAuditFields:
    def test_deerflow_attempted_defaults_false(self):
        entry = AuditEntry(family_id="f1", capability="report", success=True)
        assert entry.deerflow_attempted is False

    def test_deerflow_attempted_true_when_set(self):
        entry = AuditEntry(family_id="f1", capability="report", success=True, deerflow_attempted=True)
        assert entry.deerflow_attempted is True
