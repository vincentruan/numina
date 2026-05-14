"""Unit tests for services/policy_guard.py and schemas/policy.py."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from apps.agent.schemas.policy import CapabilityPolicy, PolicyDecision
from apps.agent.services.policy_guard import PolicyGuard


class TestPolicyGuard:
    def setup_method(self):
        self.guard = PolicyGuard()

    def _policy(self, **kwargs) -> CapabilityPolicy:
        return CapabilityPolicy(**kwargs)

    def test_ai_enabled_capability_allowed(self):
        policy = self._policy(ai_enabled=True)
        result = self.guard.check(policy, "report")
        assert result.allowed is True

    def test_ai_disabled_blocks_all(self):
        policy = self._policy(ai_enabled=False)
        result = self.guard.check(policy, "report")
        assert result.allowed is False
        assert "未启用" in result.reason

    def test_capability_not_in_allowed_list_blocked(self):
        policy = self._policy(ai_enabled=True, allowed_capabilities=["report"])
        result = self.guard.check(policy, "chat")
        assert result.allowed is False
        assert "不可用" in result.reason

    def test_capability_in_allowed_list_passes(self):
        policy = self._policy(ai_enabled=True, allowed_capabilities=["report", "chat"])
        result = self.guard.check(policy, "chat")
        assert result.allowed is True

    def test_empty_allowed_list_means_all_allowed(self):
        policy = self._policy(ai_enabled=True, allowed_capabilities=[])
        result = self.guard.check(policy, "any_capability")
        assert result.allowed is True

    def test_admin_only_capability_blocked_for_member(self):
        policy = self._policy(
            ai_enabled=True,
            admin_only_capabilities=["deep_analysis"],
            member_role="member",
        )
        result = self.guard.check(policy, "deep_analysis")
        assert result.allowed is False
        assert "管理员" in result.reason

    def test_admin_only_capability_allowed_for_admin(self):
        policy = self._policy(
            ai_enabled=True,
            admin_only_capabilities=["deep_analysis"],
            member_role="admin",
        )
        result = self.guard.check(policy, "deep_analysis")
        assert result.allowed is True

    def test_ai_disabled_takes_priority_over_allowed_list(self):
        policy = self._policy(
            ai_enabled=False,
            allowed_capabilities=["report"],
        )
        result = self.guard.check(policy, "report")
        assert result.allowed is False

    def test_policy_decision_is_pydantic_model(self):
        policy = self._policy(ai_enabled=True)
        result = self.guard.check(policy, "report")
        assert isinstance(result, PolicyDecision)

    def test_allowed_result_has_empty_reason(self):
        policy = self._policy(ai_enabled=True)
        result = self.guard.check(policy, "report")
        assert result.reason == ""
