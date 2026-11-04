"""Integration tests for the T18 sandbox gate across the real middleware chain.

These exercise the full path a file tool takes: a DeerFlow ``GuardrailRequest``
built the way ``GuardrailMiddleware._build_request`` builds it, through the
provider's policy checks, against real filesystem state. No mocks stand in for
the validators or the filesystem.
"""

from pathlib import Path

import pytest
from deerflow.guardrails.provider import GuardrailProvider, GuardrailRequest

from apps.agent.services.deerflow_adapter.numina_guardrail_provider import (
    NuminaGuardrailProvider,
)
from apps.agent.services.runtime.sandbox_provider import (
    reset_family_sandbox_context,
    set_family_sandbox_context,
)

FAMILY = "family-A"
THREAD = "thread-t1"


@pytest.fixture
def family_tree(tmp_path: Path) -> Path:
    """Real family user-data tree with workspace/uploads/outputs mounts."""
    root = tmp_path / "users" / FAMILY / "threads" / THREAD / "user-data"
    for sub in ("workspace", "uploads", "outputs"):
        (root / sub).mkdir(parents=True)
    return root


@pytest.fixture(autouse=True)
def sandbox_paths(family_tree: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Route DeerFlow's path lookup at the real tmp family tree."""
    fake = type(
        "FakePaths",
        (),
        {
            "host_sandbox_user_data_dir": staticmethod(
                lambda thread_id, *, user_id=None: str(family_tree)
            )
        },
    )
    monkeypatch.setattr(
        "apps.agent.services.deerflow_adapter.numina_guardrail_provider.get_paths",
        lambda: fake(),
    )
    return family_tree


@pytest.fixture(autouse=True)
def family_context():
    set_family_sandbox_context(FAMILY, caller_user_id="user-1")
    try:
        yield
    finally:
        reset_family_sandbox_context()


def _file_call(tool: str, path: str, **extra) -> GuardrailRequest:
    """Build a request the way GuardrailMiddleware would for a file tool."""
    return GuardrailRequest(
        tool_name=tool,
        tool_input={"path": path, **extra},
        thread_id=THREAD,
        user_id="user-1",
        run_id="run-1",
    )


class TestFullChain:
    """Evaluate → path → permission → size → quota, against real files."""

    def test_all_checks_pass_and_file_is_writable(self, family_tree: Path) -> None:
        provider = NuminaGuardrailProvider()
        target = family_tree / "workspace" / "report.txt"

        decision = provider.evaluate(
            _file_call("write_file", "/mnt/user-data/workspace/report.txt", content="hello")
        )
        assert decision.allow is True

        # The gate permitted a path that really accepts the write.
        target.write_text("hello", encoding="utf-8")
        assert target.read_text(encoding="utf-8") == "hello"

    def test_path_violation_blocks_before_write(self, family_tree: Path) -> None:
        public = family_tree / "workspace" / "public"
        public.mkdir()
        provider = NuminaGuardrailProvider(
            sandbox_policy={"allowed_paths": [str(public)]}
        )

        decision = provider.evaluate(
            _file_call("write_file", "/mnt/user-data/workspace/report.txt", content="x")
        )

        assert decision.allow is False
        assert decision.reasons[0].message == "Path outside allowed directories"

    def test_resource_violation_blocks(self, family_tree: Path) -> None:
        provider = NuminaGuardrailProvider(
            sandbox_policy={"max_file_size_bytes": 8}
        )

        decision = provider.evaluate(
            _file_call("write_file", "/mnt/user-data/workspace/big.txt", content="x" * 100)
        )

        assert decision.allow is False
        assert decision.reasons[0].code == "file_too_large"

    def test_permission_violation_blocks(self, family_tree: Path) -> None:
        config_dir = family_tree / "workspace" / "config"
        config_dir.mkdir()
        provider = NuminaGuardrailProvider(
            sandbox_policy={"read_only_paths": [str(config_dir)]}
        )

        decision = provider.evaluate(
            _file_call(
                "write_file", "/mnt/user-data/workspace/config/settings.json", content="{}"
            )
        )

        assert decision.allow is False
        assert decision.reasons[0].code == "read_only_path"

    def test_quota_violation_blocks_after_real_files_exist(self, family_tree: Path) -> None:
        # Real usage on disk drives the check — no counter involved.
        (family_tree / "workspace" / "a.bin").write_bytes(b"x" * 4096)
        (family_tree / "outputs" / "b.bin").write_bytes(b"x" * 4096)
        provider = NuminaGuardrailProvider(
            sandbox_policy={"max_total_quota_bytes": 4096}
        )

        decision = provider.evaluate(
            _file_call("write_file", "/mnt/user-data/workspace/c.txt", content="x")
        )

        assert decision.allow is False
        assert decision.reasons[0].code == "quota_exceeded"

    def test_quota_frees_up_after_deletion(self, family_tree: Path) -> None:
        """Quota reflects deletions because usage is measured, not counted."""
        big = family_tree / "workspace" / "big.bin"
        big.write_bytes(b"x" * 8192)
        policy = {"max_total_quota_bytes": 4096}
        provider = NuminaGuardrailProvider(sandbox_policy=policy)

        blocked = provider.evaluate(
            _file_call("write_file", "/mnt/user-data/workspace/n.txt", content="x")
        )
        assert blocked.allow is False

        big.unlink()

        allowed = provider.evaluate(
            _file_call("write_file", "/mnt/user-data/workspace/n.txt", content="x")
        )
        assert allowed.allow is True


class TestFailClosedIntegration:
    """Missing tenant context denies rather than skipping checks."""

    def test_missing_family_id_fails_closed(self) -> None:
        reset_family_sandbox_context()
        provider = NuminaGuardrailProvider()

        decision = provider.evaluate(
            _file_call("write_file", "/mnt/user-data/workspace/x.txt", content="x")
        )

        assert decision.allow is False
        assert decision.reasons[0].code == "internal_error"

    def test_non_file_tool_bypasses_sandbox_validation(self) -> None:
        reset_family_sandbox_context()
        provider = NuminaGuardrailProvider()

        decision = provider.evaluate(
            GuardrailRequest(tool_name="get_assets", tool_input={}, thread_id=THREAD)
        )

        assert decision.allow is True


class TestAuditTrail:
    """Violations carry the fields a security review needs."""

    def test_violation_records_family_tool_operation_path_reason(
        self, family_tree: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        provider = NuminaGuardrailProvider(sandbox_policy={"max_file_size_bytes": 4})

        with caplog.at_level("WARNING"):
            provider.evaluate(
                _file_call(
                    "write_file", "/mnt/user-data/workspace/too-big.txt", content="xxxxxx"
                )
            )

        record = next(
            r for r in caplog.records if "sandbox_gate] violation" in r.message
        )
        message = record.message
        assert f"family_id={FAMILY}" in message
        assert "tool=write_file" in message
        assert "operation=write" in message
        assert "path=/mnt/user-data/workspace/too-big.txt" in message
        assert "reason=" in message

    def test_read_violation_records_read_operation(
        self, family_tree: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        public = family_tree / "workspace" / "public"
        public.mkdir()
        provider = NuminaGuardrailProvider(
            sandbox_policy={"allowed_paths": [str(public)]}
        )

        with caplog.at_level("WARNING"):
            provider.evaluate(
                _file_call("read_file", "/mnt/user-data/workspace/secret.txt")
            )

        record = next(
            r for r in caplog.records if "sandbox_gate] violation" in r.message
        )
        assert "operation=read" in record.message


class TestProtocolIntegration:
    """The provider is what DeerFlow's middleware will resolve and call."""

    def test_provider_satisfies_runtime_protocol(self) -> None:
        assert isinstance(NuminaGuardrailProvider(), GuardrailProvider)

    def test_config_declares_a_loadable_provider_path(self) -> None:
        """The injected class path must resolve to the provider class."""
        from deerflow.reflection import resolve_variable

        from apps.agent.services.deerflow_adapter.family_adapter_cache import (
            _inject_sandbox_gate,
        )

        config: dict = {}
        _inject_sandbox_gate(config, {})

        use_path = config["guardrails"]["provider"]["use"]
        assert resolve_variable(use_path) is NuminaGuardrailProvider

    def test_injected_config_constructs_a_working_provider(self, family_tree: Path) -> None:
        """End-to-end: injected kwargs → provider → decision."""
        from apps.agent.services.deerflow_adapter.family_adapter_cache import (
            _inject_sandbox_gate,
        )

        config: dict = {}
        _inject_sandbox_gate(
            config, {"sandbox_policy": {"max_file_size_bytes": 4}}
        )

        provider_cfg = config["guardrails"]["provider"]["config"]
        provider = NuminaGuardrailProvider(**provider_cfg)

        decision = provider.evaluate(
            _file_call("write_file", "/mnt/user-data/workspace/x.txt", content="toolong")
        )
        assert decision.allow is False
        assert decision.reasons[0].code == "file_too_large"
