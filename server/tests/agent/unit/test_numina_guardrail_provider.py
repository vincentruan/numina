"""Unit tests for NuminaGuardrailProvider — tool execution safety guardrails.

Tests cover:
- Allowlist: only listed tools execute
- Denylist: explicitly denied tools never execute (overrides allowlist)
- Fail-closed: provider errors deny tool calls by default
- Fail-open: provider errors allow tool calls when configured
- Default allow: no lists = all tools allowed
- Integration with _inject_guardrail config injection
"""

from apps.agent.services.deerflow_adapter.numina_guardrail_provider import (
    GuardrailDecision,
    NuminaGuardrailProvider,
    create_provider_from_config,
)


class TestNuminaGuardrailProvider:
    """Tests for the core provider logic."""

    def test_default_allow_all(self) -> None:
        """No lists configured → all tools allowed."""
        provider = NuminaGuardrailProvider()
        result = provider.check_tool_call("get_assets")
        assert result.allowed is True
        assert result.reason == ""

    def test_allowlist_permits_listed_tool(self) -> None:
        """Allowlist configured → listed tool is allowed."""
        provider = NuminaGuardrailProvider(allowlist=["get_assets", "get_liabilities"])
        result = provider.check_tool_call("get_assets")
        assert result.allowed is True

    def test_allowlist_denies_unlisted_tool(self) -> None:
        """Allowlist configured → unlisted tool is denied."""
        provider = NuminaGuardrailProvider(allowlist=["get_assets"])
        result = provider.check_tool_call("bash")
        assert result.allowed is False
        assert "not in the allowed list" in result.reason

    def test_denylist_denies_listed_tool(self) -> None:
        """Denylist → listed tool is denied."""
        provider = NuminaGuardrailProvider(denylist=["bash", "execute_code"])
        result = provider.check_tool_call("bash")
        assert result.allowed is False
        assert "explicitly denied" in result.reason

    def test_denylist_allows_unlisted_tool(self) -> None:
        """Denylist → unlisted tool is allowed."""
        provider = NuminaGuardrailProvider(denylist=["bash"])
        result = provider.check_tool_call("get_assets")
        assert result.allowed is True

    def test_denylist_overrides_allowlist(self) -> None:
        """Denylist takes precedence over allowlist for same tool."""
        provider = NuminaGuardrailProvider(
            allowlist=["bash", "get_assets"],
            denylist=["bash"],
        )
        # bash is in both lists — deny wins
        result = provider.check_tool_call("bash")
        assert result.allowed is False
        assert "explicitly denied" in result.reason

        # get_assets is only in allowlist → allowed
        result = provider.check_tool_call("get_assets")
        assert result.allowed is True

    def test_empty_allowlist_means_all_allowed(self) -> None:
        """Empty allowlist (not None) means all tools allowed (subject to denylist)."""
        provider = NuminaGuardrailProvider(allowlist=[], denylist=["bash"])
        result = provider.check_tool_call("get_assets")
        assert result.allowed is True

        result = provider.check_tool_call("bash")
        assert result.allowed is False


class TestFailClosedBehavior:
    """Tests for fail-closed/fail-open error handling."""

    def test_fail_closed_denies_on_error(self) -> None:
        """Fail-closed (default) → errors deny tool calls."""
        provider = NuminaGuardrailProvider(fail_closed=True)

        # Simulate an error by patching _check_internal to raise
        def raise_error(tool_name: str) -> GuardrailDecision:
            raise RuntimeError("Simulated error")

        provider._check_internal = raise_error  # type: ignore[method-assign]

        result = provider.check_tool_call("get_assets")
        assert result.allowed is False
        assert "Guardrail check failed" in result.reason

    def test_fail_open_allows_on_error(self) -> None:
        """Fail-open → errors allow tool calls."""
        provider = NuminaGuardrailProvider(fail_closed=False)

        # Simulate an error by patching _check_internal to raise
        def raise_error(tool_name: str) -> GuardrailDecision:
            raise RuntimeError("Simulated error")

        provider._check_internal = raise_error  # type: ignore[method-assign]

        result = provider.check_tool_call("get_assets")
        assert result.allowed is True


class TestProperties:
    """Tests for read-only properties."""

    def test_allowlist_property(self) -> None:
        """Allowlist property returns frozenset."""
        provider = NuminaGuardrailProvider(allowlist=["get_assets", "get_liabilities"])
        assert provider.allowlist == frozenset({"get_assets", "get_liabilities"})

    def test_denylist_property(self) -> None:
        """Denylist property returns frozenset."""
        provider = NuminaGuardrailProvider(denylist=["bash"])
        assert provider.denylist == frozenset({"bash"})

    def test_fail_closed_property(self) -> None:
        """Fail-closed property returns bool."""
        provider = NuminaGuardrailProvider(fail_closed=True)
        assert provider.fail_closed is True

        provider = NuminaGuardrailProvider(fail_closed=False)
        assert provider.fail_closed is False


class TestTypeValidation:
    """Tests for type validation in __init__."""

    def test_allowlist_string_raises_typeerror(self) -> None:
        """String allowlist raises TypeError (would split into characters)."""
        try:
            NuminaGuardrailProvider(allowlist="bash")  # type: ignore[arg-type]
            raise AssertionError("Expected TypeError")
        except TypeError as e:
            assert "allowlist must be a list" in str(e)
            assert "str" in str(e)

    def test_denylist_string_raises_typeerror(self) -> None:
        """String denylist raises TypeError (would split into characters)."""
        try:
            NuminaGuardrailProvider(denylist="bash")  # type: ignore[arg-type]
            raise AssertionError("Expected TypeError")
        except TypeError as e:
            assert "denylist must be a list" in str(e)
            assert "str" in str(e)

    def test_allowlist_tuple_raises_typeerror(self) -> None:
        """Tuple allowlist raises TypeError (strict list check)."""
        try:
            NuminaGuardrailProvider(allowlist=("bash",))  # type: ignore[arg-type]
            raise AssertionError("Expected TypeError")
        except TypeError as e:
            assert "allowlist must be a list" in str(e)

    def test_none_and_empty_list_accepted(self) -> None:
        """None and empty list are both valid."""
        # None — default
        provider = NuminaGuardrailProvider()
        assert provider.allowlist == frozenset()

        # Empty list
        provider = NuminaGuardrailProvider(allowlist=[], denylist=[])
        assert provider.allowlist == frozenset()
        assert provider.denylist == frozenset()


class TestFactory:
    """Tests for create_provider_from_config factory."""

    def test_create_from_full_config(self) -> None:
        """Factory creates provider from complete config."""
        config = {
            "enabled": True,
            "fail_closed": False,
            "allowlist": ["get_assets"],
            "denylist": ["bash"],
        }
        provider = create_provider_from_config(config)
        assert provider.allowlist == frozenset({"get_assets"})
        assert provider.denylist == frozenset({"bash"})
        assert provider.fail_closed is False

    def test_create_from_minimal_config(self) -> None:
        """Factory creates provider with defaults for missing keys."""
        config = {"enabled": True}
        provider = create_provider_from_config(config)
        assert provider.allowlist == frozenset()
        assert provider.denylist == frozenset()
        assert provider.fail_closed is True  # default


class TestInjectGuardrail:
    """Tests for _inject_guardrail config injection."""

    def test_inject_when_enabled(self) -> None:
        """Inject guardrail config when ai_config has guardrails.enabled=True."""
        from apps.agent.services.deerflow_adapter.family_adapter_cache import (
            _inject_guardrail,
        )

        config: dict = {}
        ai_config = {
            "guardrails": {
                "enabled": True,
                "fail_closed": False,
                "allowlist": ["get_assets"],
                "denylist": ["bash"],
            }
        }

        _inject_guardrail(config, ai_config)

        assert config["guardrails"]["enabled"] is True
        assert config["guardrails"]["fail_closed"] is False
        assert config["guardrails"]["allowlist"] == ["get_assets"]
        assert config["guardrails"]["denylist"] == ["bash"]
        assert "numina_guardrail_provider" in config["guardrails"]["provider"]["use"]

    def test_inject_when_disabled(self) -> None:
        """No injection when guardrails.enabled=False."""
        from apps.agent.services.deerflow_adapter.family_adapter_cache import (
            _inject_guardrail,
        )

        config: dict = {}
        ai_config = {"guardrails": {"enabled": False}}

        _inject_guardrail(config, ai_config)

        assert "guardrails" not in config

    def test_inject_when_missing(self) -> None:
        """No injection when ai_config has no guardrails key."""
        from apps.agent.services.deerflow_adapter.family_adapter_cache import (
            _inject_guardrail,
        )

        config: dict = {}
        ai_config: dict = {}

        _inject_guardrail(config, ai_config)

        assert "guardrails" not in config

    def test_inject_defaults(self) -> None:
        """Injection uses defaults for missing optional keys."""
        from apps.agent.services.deerflow_adapter.family_adapter_cache import (
            _inject_guardrail,
        )

        config: dict = {}
        ai_config = {"guardrails": {"enabled": True}}

        _inject_guardrail(config, ai_config)

        assert config["guardrails"]["fail_closed"] is True  # default
        assert config["guardrails"]["allowlist"] == []  # default
        assert config["guardrails"]["denylist"] == []  # default


class TestPolicyGuardNoConflict:
    """Verify NuminaGuardrailProvider does not conflict with PolicyGuard.

    PolicyGuard is a pre-dispatch gate (checks skill/capability before LLM call).
    NuminaGuardrailProvider is a tool execution gate (during LLM run, per-tool).
    They operate at different layers and should not interfere.
    """

    def test_different_responsibilities(self) -> None:
        """PolicyGuard and NuminaGuardrailProvider have distinct responsibilities."""
        from apps.agent.schemas.policy import CapabilityPolicy
        from apps.agent.services.policy_guard import PolicyGuard

        # PolicyGuard: pre-dispatch, checks capability access
        policy_guard = PolicyGuard()
        policy = CapabilityPolicy(ai_enabled=True, allowed_capabilities=["chat"])

        # PolicyGuard allows/disallows entire capabilities (skills)
        decision = policy_guard.check(policy, "chat")
        assert decision.allowed is True

        decision = policy_guard.check(policy, "asset-report")
        assert decision.allowed is False

        # NuminaGuardrailProvider: tool execution, checks individual tools
        guardrail = NuminaGuardrailProvider(allowlist=["get_assets"])

        # Provider allows/denies specific tool calls
        result = guardrail.check_tool_call("get_assets")
        assert result.allowed is True

        result = guardrail.check_tool_call("bash")
        assert result.allowed is False

    def test_both_can_be_active(self) -> None:
        """Both gates can be active simultaneously without conflict."""
        from apps.agent.schemas.policy import CapabilityPolicy
        from apps.agent.services.policy_guard import PolicyGuard

        # Setup: AI enabled, chat allowed, guardrail allows get_assets
        policy_guard = PolicyGuard()
        policy = CapabilityPolicy(ai_enabled=True, allowed_capabilities=["chat"])
        guardrail = NuminaGuardrailProvider(allowlist=["get_assets"])

        # PolicyGuard allows dispatch
        assert policy_guard.check(policy, "chat").allowed is True

        # Guardrail allows get_assets tool
        assert guardrail.check_tool_call("get_assets").allowed is True

        # Guardrail denies bash tool (not in allowlist)
        assert guardrail.check_tool_call("bash").allowed is False

        # They don't interfere — each does its job at its layer
