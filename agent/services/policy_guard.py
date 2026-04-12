"""PolicyGuard — enforces family admin capability switches before dispatch."""

from schemas.policy import CapabilityPolicy, PolicyDecision


class PolicyGuard:
    """Pure in-memory policy check. Never calls backend or LLM."""

    def check(self, policy: CapabilityPolicy, capability: str) -> PolicyDecision:
        if not policy.ai_enabled:
            return PolicyDecision(allowed=False, reason="AI功能未启用")

        if policy.allowed_capabilities and capability not in policy.allowed_capabilities:
            return PolicyDecision(allowed=False, reason="该功能不可用")

        if capability in policy.admin_only_capabilities and policy.member_role != "admin":
            return PolicyDecision(allowed=False, reason="仅管理员可使用")

        return PolicyDecision(allowed=True, reason="")


policy_guard = PolicyGuard()
