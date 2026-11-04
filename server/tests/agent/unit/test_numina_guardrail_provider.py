"""Unit tests for NuminaGuardrailProvider — sandbox policy gate.

Tests cover the GuardrailProvider protocol (evaluate / aevaluate):
- Non-file tools bypass sandbox validation
- Valid file operation within policy → allow
- Path outside allowed prefixes → deny
- Write to read-only path → deny
- File size over limit → deny
- Quota exceeded → deny
- Missing family_id → fail-closed deny
- Malformed sandbox_policy → sandbox ops denied (config injection fails closed)
- Fail-open mode allows on evaluation error
- Protocol compliance (name / policy_id / release_policy_parameters)
"""

from pathlib import Path

import pytest
from deerflow.guardrails.provider import (
    GuardrailDecision,
    GuardrailProvider,
    GuardrailRequest,
)

from apps.agent.services.deerflow_adapter.numina_guardrail_provider import (
    NuminaGuardrailProvider,
)
from apps.agent.services.runtime.sandbox_provider import (
    reset_family_sandbox_context,
    set_family_sandbox_context,
)


@pytest.fixture
def user_data_root(tmp_path: Path) -> Path:
    """Host user-data root for a test family/thread, with mounts created."""
    root = tmp_path / "users" / "family-A" / "threads" / "t1" / "user-data"
    (root / "workspace").mkdir(parents=True)
    (root / "uploads").mkdir()
    (root / "outputs").mkdir()
    return root


@pytest.fixture(autouse=True)
def family_context():
    """Set the family sandbox ContextVar for every test, then reset."""
    set_family_sandbox_context("family-A", caller_user_id="user-1")
    try:
        yield
    finally:
        reset_family_sandbox_context()


@pytest.fixture(autouse=True)
def sandbox_root_patch(user_data_root: Path, monkeypatch: pytest.MonkeyPatch):
    """Point host_sandbox_user_data_dir at the tmp family tree."""

    def _fake_root(thread_id: str, *, user_id: str | None = None) -> str:
        assert user_id == "family-A"
        return str(user_data_root)

    monkeypatch.setattr(
        "apps.agent.services.deerflow_adapter.numina_guardrail_provider.get_paths",
        lambda: type("P", (), {"host_sandbox_user_data_dir": staticmethod(_fake_root)})(),
    )
    return user_data_root


def _request(tool_name: str, tool_input: dict, thread_id: str | None = "t1") -> GuardrailRequest:
    return GuardrailRequest(
        tool_name=tool_name, tool_input=tool_input, thread_id=thread_id
    )


class TestProtocolCompliance:
    """The provider must satisfy DeerFlow's runtime-checkable protocol."""

    def test_satisfies_guardrail_provider_protocol(self) -> None:
        provider = NuminaGuardrailProvider()
        assert isinstance(provider, GuardrailProvider)

    def test_declares_name_and_policy_id(self) -> None:
        provider = NuminaGuardrailProvider()
        assert provider.name == "numina-sandbox-gate"
        assert provider.policy_id == "numina-sandbox-gate"

    def test_release_policy_parameters_declares_knobs(self) -> None:
        provider = NuminaGuardrailProvider()
        params = provider.release_policy_parameters()
        assert params["max_file_size_bytes"] == 50 * 1024
        assert params["max_total_quota_bytes"] == 1024 * 1024 * 1024

    def test_previous_check_tool_call_method_is_gone(self) -> None:
        """The old, never-invoked entry point has been removed."""
        assert not hasattr(NuminaGuardrailProvider(), "check_tool_call")


class TestNonFileTools:
    """Tools that are not sandbox file operations pass through."""

    @pytest.mark.parametrize("tool_name", ["get_assets", "bash", "web_search", "task"])
    def test_non_file_tool_allowed(self, tool_name: str) -> None:
        provider = NuminaGuardrailProvider()
        decision = provider.evaluate(_request(tool_name, {"anything": 1}))
        assert decision.allow is True


class TestAllowedOperations:
    """File operations within policy are allowed."""

    def test_write_within_policy_allowed(self) -> None:
        provider = NuminaGuardrailProvider()
        decision = provider.evaluate(
            _request("write_file", {"path": "/mnt/user-data/workspace/report.txt", "content": "hi"})
        )
        assert decision.allow is True
        assert decision.reasons == []

    def test_read_within_policy_allowed(self) -> None:
        provider = NuminaGuardrailProvider()
        decision = provider.evaluate(
            _request("read_file", {"path": "/mnt/user-data/workspace/report.txt"})
        )
        assert decision.allow is True

    def test_str_replace_within_policy_allowed(self) -> None:
        provider = NuminaGuardrailProvider()
        decision = provider.evaluate(
            _request(
                "str_replace",
                {"path": "/mnt/user-data/workspace/report.txt", "old_str": "a", "new_str": "b"},
            )
        )
        assert decision.allow is True


class TestPathViolations:
    """Path-pattern and containment violations are denied."""

    def test_path_outside_allowed_prefixes_denied(self, user_data_root: Path) -> None:
        public_dir = user_data_root / "workspace" / "public"
        public_dir.mkdir()
        provider = NuminaGuardrailProvider(
            sandbox_policy={"allowed_paths": [str(public_dir)]}
        )

        decision = provider.evaluate(
            _request("write_file", {"path": "/mnt/user-data/workspace/report.txt", "content": "x"})
        )

        assert decision.allow is False
        assert decision.reasons[0].code == "path_not_allowed"
        assert decision.reasons[0].message == "Path outside allowed directories"

    def test_cross_family_path_denied(self, user_data_root: Path) -> None:
        provider = NuminaGuardrailProvider()

        decision = provider.evaluate(
            _request("read_file", {"path": "/mnt/user-data/../../other-family/x"})
        )

        assert decision.allow is False

    def test_missing_path_argument_denied(self) -> None:
        provider = NuminaGuardrailProvider()
        decision = provider.evaluate(_request("write_file", {"content": "x"}))
        assert decision.allow is False
        assert decision.reasons[0].code == "invalid_tool_input"


class TestPermissionViolations:
    """Writes to read-only prefixes are denied; reads are not."""

    def test_write_to_read_only_path_denied(self, user_data_root: Path) -> None:
        config_dir = user_data_root / "workspace" / "config"
        config_dir.mkdir()
        provider = NuminaGuardrailProvider(
            sandbox_policy={"read_only_paths": [str(config_dir)]}
        )

        decision = provider.evaluate(
            _request(
                "write_file",
                {"path": "/mnt/user-data/workspace/config/settings.json", "content": "{}"},
            )
        )

        assert decision.allow is False
        assert decision.reasons[0].code == "read_only_path"

    def test_read_from_read_only_path_allowed(self, user_data_root: Path) -> None:
        config_dir = user_data_root / "workspace" / "config"
        config_dir.mkdir()
        provider = NuminaGuardrailProvider(
            sandbox_policy={"read_only_paths": [str(config_dir)]}
        )

        decision = provider.evaluate(
            _request("read_file", {"path": "/mnt/user-data/workspace/config/settings.json"})
        )

        assert decision.allow is True

    def test_write_to_writable_path_allowed(self, user_data_root: Path) -> None:
        config_dir = user_data_root / "workspace" / "config"
        config_dir.mkdir()
        provider = NuminaGuardrailProvider(
            sandbox_policy={"read_only_paths": [str(config_dir)]}
        )

        decision = provider.evaluate(
            _request("write_file", {"path": "/mnt/user-data/workspace/report.txt", "content": "ok"})
        )

        assert decision.allow is True


class TestResourceViolations:
    """File size and cumulative quota limits are enforced."""

    def test_file_too_large_denied(self) -> None:
        provider = NuminaGuardrailProvider(
            sandbox_policy={"max_file_size_bytes": 10}
        )

        decision = provider.evaluate(
            _request(
                "write_file",
                {"path": "/mnt/user-data/workspace/big.txt", "content": "x" * 50},
            )
        )

        assert decision.allow is False
        assert decision.reasons[0].code == "file_too_large"
        assert "exceeds policy limit" in decision.reasons[0].message

    def test_quota_exceeded_denied(self, user_data_root: Path) -> None:
        (user_data_root / "workspace" / "existing.bin").write_bytes(b"x" * 4096)
        provider = NuminaGuardrailProvider(
            sandbox_policy={"max_total_quota_bytes": 1024}
        )

        decision = provider.evaluate(
            _request("write_file", {"path": "/mnt/user-data/workspace/more.txt", "content": "x"})
        )

        assert decision.allow is False
        assert decision.reasons[0].code == "quota_exceeded"

    def test_quota_within_limit_allowed(self, user_data_root: Path) -> None:
        (user_data_root / "workspace" / "small.bin").write_bytes(b"x" * 10)
        provider = NuminaGuardrailProvider(
            sandbox_policy={"max_total_quota_bytes": 1024}
        )

        decision = provider.evaluate(
            _request("write_file", {"path": "/mnt/user-data/workspace/ok.txt", "content": "x"})
        )

        assert decision.allow is True


class TestFailClosed:
    """Fail-closed behavior for missing context and errors."""

    def test_missing_family_id_denied(self) -> None:
        reset_family_sandbox_context()
        provider = NuminaGuardrailProvider()

        decision = provider.evaluate(
            _request("write_file", {"path": "/mnt/user-data/workspace/x.txt", "content": "x"})
        )

        assert decision.allow is False
        assert decision.reasons[0].code == "internal_error"

    def test_missing_thread_id_denied(self) -> None:
        provider = NuminaGuardrailProvider()

        decision = provider.evaluate(
            _request("write_file", {"path": "/mnt/user-data/workspace/x.txt", "content": "x"}, thread_id=None)
        )

        assert decision.allow is False
        assert decision.reasons[0].code == "internal_error"

    def test_fail_open_allows_on_error(self) -> None:
        reset_family_sandbox_context()
        provider = NuminaGuardrailProvider(fail_closed=False)

        decision = provider.evaluate(
            _request("write_file", {"path": "/mnt/user-data/workspace/x.txt", "content": "x"})
        )

        assert decision.allow is True

    def test_malformed_policy_denies_sandbox_operations(self) -> None:
        """A malformed policy blocks sandbox ops instead of passing permissively."""
        provider = NuminaGuardrailProvider(sandbox_policy={"max_file_size_bytes": -5})

        decision = provider.evaluate(
            _request("write_file", {"path": "/mnt/user-data/workspace/x.txt", "content": "x"})
        )

        assert decision.allow is False
        assert decision.reasons[0].code == "invalid_policy"

    def test_relative_policy_path_denies_sandbox_operations(self) -> None:
        provider = NuminaGuardrailProvider(
            sandbox_policy={"allowed_paths": ["relative/path"]}
        )

        decision = provider.evaluate(
            _request("read_file", {"path": "/mnt/user-data/workspace/x.txt"})
        )

        assert decision.allow is False
        assert decision.reasons[0].code == "invalid_policy"

    def test_malformed_policy_still_allows_non_file_tools(self) -> None:
        """A policy problem must not break unrelated tool calls."""
        provider = NuminaGuardrailProvider(sandbox_policy={"max_file_size_bytes": -5})

        decision = provider.evaluate(_request("get_assets", {}))

        assert decision.allow is True


class TestAsyncVariant:
    """aevaluate mirrors evaluate."""

    async def test_aevaluate_allows_valid_operation(self) -> None:
        provider = NuminaGuardrailProvider()
        decision = await provider.aevaluate(
            _request("write_file", {"path": "/mnt/user-data/workspace/a.txt", "content": "x"})
        )
        assert decision.allow is True

    async def test_aevaluate_denies_violation(self, user_data_root: Path) -> None:
        config_dir = user_data_root / "workspace" / "config"
        config_dir.mkdir()
        provider = NuminaGuardrailProvider(
            sandbox_policy={"read_only_paths": [str(config_dir)]}
        )

        decision = await provider.aevaluate(
            _request("write_file", {"path": "/mnt/user-data/workspace/config/s.json", "content": "x"})
        )
        assert decision.allow is False


class TestAuditLogging:
    """Violations are logged with family/tool/operation/path/reason."""

    def test_violation_logged_with_full_context(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        provider = NuminaGuardrailProvider(sandbox_policy={"max_file_size_bytes": 1})

        with caplog.at_level("WARNING"):
            provider.evaluate(
                _request("write_file", {"path": "/mnt/user-data/workspace/big.txt", "content": "xxxx"})
            )

        record = next(r for r in caplog.records if "sandbox_gate] violation" in r.message)
        assert "family_id=family-A" in record.message
        assert "tool=write_file" in record.message
        assert "operation=write" in record.message
        assert "path=/mnt/user-data/workspace/big.txt" in record.message
        assert "reason=" in record.message


class TestDecisionShape:
    """Returned decisions match DeerFlow's GuardrailDecision shape."""

    def test_allow_decision_shape(self) -> None:
        provider = NuminaGuardrailProvider()
        decision = provider.evaluate(_request("get_assets", {}))
        assert isinstance(decision, GuardrailDecision)
        assert decision.allow is True

    def test_deny_decision_carries_policy_id_and_reason(self) -> None:
        provider = NuminaGuardrailProvider(sandbox_policy={"max_file_size_bytes": 1})
        decision = provider.evaluate(
            _request("write_file", {"path": "/mnt/user-data/workspace/b.txt", "content": "xxxx"})
        )
        assert decision.allow is False
        assert decision.policy_id == "numina-sandbox-gate"
        assert len(decision.reasons) == 1
        assert decision.reasons[0].code and decision.reasons[0].message


class TestStrReplacePayload:
    """str_replace's payload key is new_str, not content."""

    def test_oversized_new_str_denied(self) -> None:
        provider = NuminaGuardrailProvider(
            sandbox_policy={"max_file_size_bytes": 10}
        )

        decision = provider.evaluate(
            _request(
                "str_replace",
                {
                    "path": "/mnt/user-data/workspace/a.txt",
                    "old_str": "x",
                    "new_str": "y" * 50,
                },
            )
        )

        assert decision.allow is False
        assert decision.reasons[0].code == "file_too_large"

    def test_shrinking_str_replace_allowed(self) -> None:
        """A str_replace that shrinks the file skips the size check."""
        provider = NuminaGuardrailProvider(
            sandbox_policy={"max_file_size_bytes": 10}
        )

        decision = provider.evaluate(
            _request(
                "str_replace",
                {
                    "path": "/mnt/user-data/workspace/a.txt",
                    "old_str": "long text here",
                    "new_str": "x",
                },
            )
        )

        assert decision.allow is True


class TestQuotaWriteOnly:
    """Cumulative quota is enforced only on writes."""

    def test_read_allowed_when_over_quota(self, user_data_root: Path) -> None:
        (user_data_root / "workspace" / "big.bin").write_bytes(b"x" * 4096)
        provider = NuminaGuardrailProvider(
            sandbox_policy={"max_total_quota_bytes": 1024}
        )

        decision = provider.evaluate(
            _request("read_file", {"path": "/mnt/user-data/workspace/big.bin"})
        )

        assert decision.allow is True
