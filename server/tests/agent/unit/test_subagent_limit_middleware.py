"""Tests for SubagentLimitMiddleware."""

from __future__ import annotations

from unittest.mock import patch

from apps.agent.services.runtime.subagent_limit_middleware import (
    SubagentDecision,
    SubagentLimitMiddleware,
)


_REGISTRY = "apps.agent.services.runtime.subagent_registry.FamilySubagentRegistry"
_SANDBOX_CTX = "apps.agent.services.runtime.sandbox_provider.get_family_sandbox_context"


class TestSubagentLimitMiddleware:
    """Unit tests for the subagent concurrency limiter."""

    def test_allow_when_under_limit(self) -> None:
        """Active count < max_concurrent → allowed."""
        mw = SubagentLimitMiddleware(max_concurrent=3, family_id="fam_1")
        mock_tasks = ["task_a", "task_b"]  # 2 active < 3 max

        with patch(_REGISTRY) as mock_reg:
            mock_reg.list_for_family.return_value = mock_tasks
            result = mw.check_subagent_spawn()

        assert result.allowed is True
        assert result.reason == ""

    def test_deny_when_at_limit(self) -> None:
        """Active count >= max_concurrent → denied."""
        mw = SubagentLimitMiddleware(max_concurrent=3, family_id="fam_1")
        mock_tasks = ["task_a", "task_b", "task_c"]  # 3 active == 3 max

        with patch(_REGISTRY) as mock_reg:
            mock_reg.list_for_family.return_value = mock_tasks
            result = mw.check_subagent_spawn()

        assert result.allowed is False
        assert "limit reached" in result.reason.lower() or "3/3" in result.reason

    def test_deny_when_over_limit(self) -> None:
        """Active count > max_concurrent → denied."""
        mw = SubagentLimitMiddleware(max_concurrent=2, family_id="fam_1")
        mock_tasks = ["a", "b", "c"]  # 3 active > 2 max

        with patch(_REGISTRY) as mock_reg:
            mock_reg.list_for_family.return_value = mock_tasks
            result = mw.check_subagent_spawn()

        assert result.allowed is False

    def test_allow_when_empty_registry(self) -> None:
        """Zero active tasks → allowed."""
        mw = SubagentLimitMiddleware(max_concurrent=3, family_id="fam_1")

        with patch(_REGISTRY) as mock_reg:
            mock_reg.list_for_family.return_value = []
            result = mw.check_subagent_spawn()

        assert result.allowed is True

    def test_family_isolation(self) -> None:
        """Different family_id → queries its own task count."""
        mw = SubagentLimitMiddleware(max_concurrent=3, family_id="fam_A")

        with patch(_REGISTRY) as mock_reg:
            mock_reg.list_for_family.return_value = ["t1", "t2", "t3"]
            # fam_A has 3 tasks → denied
            result_a = mw.check_subagent_spawn()
            assert result_a.allowed is False
            mock_reg.list_for_family.assert_called_with("fam_A")

            # Override: fam_B has 0 tasks → allowed
            mock_reg.list_for_family.return_value = []
            result_b = mw.check_subagent_spawn(family_id="fam_B")
            assert result_b.allowed is True
            mock_reg.list_for_family.assert_called_with("fam_B")

    def test_deny_on_registry_error(self) -> None:
        """Registry read failure → fail-closed (deny)."""
        mw = SubagentLimitMiddleware(max_concurrent=3, family_id="fam_1")

        with patch(_REGISTRY) as mock_reg:
            mock_reg.list_for_family.side_effect = RuntimeError("boom")
            result = mw.check_subagent_spawn()

        assert result.allowed is False
        assert "failed" in result.reason.lower()

    def test_deny_when_no_family_context(self) -> None:
        """No family_id available → deny."""
        mw = SubagentLimitMiddleware(max_concurrent=3)  # no init family_id

        with patch(_SANDBOX_CTX, return_value=None):
            result = mw.check_subagent_spawn()

        assert result.allowed is False
        assert "no family_id" in result.reason.lower()

    def test_properties(self) -> None:
        """max_concurrent and family_id are readable."""
        mw = SubagentLimitMiddleware(max_concurrent=5, family_id="fam_x")
        assert mw.max_concurrent == 5
        assert mw.family_id == "fam_x"

    def test_subagent_decision_dataclass(self) -> None:
        """SubagentDecision is a proper dataclass."""
        d = SubagentDecision(allowed=True, reason="")
        assert d.allowed is True
        assert d.reason == ""

        d2 = SubagentDecision(allowed=False, reason="limit")
        assert d2.allowed is False
        assert d2.reason == "limit"
