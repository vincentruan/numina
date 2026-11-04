"""Unit tests for the Numina container-sandbox overlay (T22).

Tests cover:
- The overlay carries the container-local environment and idle timeout
- Mounts are NOT specified by the overlay (the provider derives them)
- A policy requesting per-family resource limits logs a warning
- The provider switch is a no-op unless the family opted in
- The opt-in flag is read from ai_config["sandbox"]
- Injection merges environment rather than replacing unrelated keys
"""

from pathlib import Path

import pytest

from apps.agent.services.runtime.numina_container_overlay import (
    AIO_SANDBOX_PROVIDER_PATH,
    DEFAULT_CONTAINER_IMAGE,
    container_enabled,
    numina_container_sandbox_config,
    override_sandbox_provider,
)
from apps.agent.services.runtime.sandbox_policy import SandboxPolicy


@pytest.fixture
def family_root(tmp_path: Path) -> Path:
    root = tmp_path / "users" / "family-A"
    root.mkdir(parents=True)
    return root


class TestOverlayContents:
    """The overlay carries what Numina adds; the provider owns mounts."""

    def test_sets_python_bytecode_env(self, family_root: Path) -> None:
        """Bytecode writing is disabled so a hardened filesystem still works."""
        overlay = numina_container_sandbox_config(
            SandboxPolicy.default_policy(), "family-A", family_root
        )
        assert overlay["environment"]["PYTHONDONTWRITEBYTECODE"] == "1"

    def test_sets_idle_timeout(self, family_root: Path) -> None:
        overlay = numina_container_sandbox_config(
            SandboxPolicy.default_policy(), "family-A", family_root
        )
        assert overlay["idle_timeout"] == 600

    def test_does_not_specify_mounts(self, family_root: Path) -> None:
        """Mounts belong to AioSandboxProvider's per-thread computation.

        Re-specifying them here would duplicate the family tree at a second
        container path and break the /mnt/user-data virtual path contract.
        """
        overlay = numina_container_sandbox_config(
            SandboxPolicy.default_policy(), "family-A", family_root
        )
        assert "mounts" not in overlay


class TestResourceLimitWarning:
    """A policy asking for un-honourable limits must not fail silently."""

    def test_warns_when_policy_requests_custom_memory(
        self, family_root: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        policy = SandboxPolicy(max_memory_mb=4096)

        with caplog.at_level("WARNING"):
            numina_container_sandbox_config(policy, "family-A", family_root)

        assert any("agent-wide" in r.message for r in caplog.records)

    def test_warns_when_policy_requests_custom_cpu(
        self, family_root: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        policy = SandboxPolicy(max_cpu_count=4)

        with caplog.at_level("WARNING"):
            numina_container_sandbox_config(policy, "family-A", family_root)

        assert any("agent-wide" in r.message for r in caplog.records)

    def test_no_warning_for_default_policy(
        self, family_root: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level("WARNING"):
            numina_container_sandbox_config(
                SandboxPolicy.default_policy(), "family-A", family_root
            )

        assert not any("agent-wide" in r.message for r in caplog.records)


class TestContainerEnabled:
    """The opt-in flag is read from the sandbox section."""

    def test_flag_true(self) -> None:
        assert container_enabled({"sandbox": {"container_enabled": True}}) is True

    def test_flag_false(self) -> None:
        assert container_enabled({"sandbox": {"container_enabled": False}}) is False

    def test_flag_absent(self) -> None:
        assert container_enabled({"sandbox": {}}) is False

    def test_sandbox_section_absent(self) -> None:
        assert container_enabled({}) is False

    def test_sandbox_section_not_a_dict(self) -> None:
        assert container_enabled({"sandbox": "nonsense"}) is False

    def test_truthy_non_bool_is_not_opt_in(self) -> None:
        """Only an explicit boolean True opts in."""
        assert container_enabled({"sandbox": {"container_enabled": "yes"}}) is False


class TestOverrideSandboxProvider:
    """Wiring the container provider into config["sandbox"]."""

    def test_noop_when_disabled(self, family_root: Path) -> None:
        config: dict = {"sandbox": {"use": "original:Provider"}}

        override_sandbox_provider(config, {}, "family-A", family_root)

        assert config["sandbox"]["use"] == "original:Provider"

    def test_switches_provider_when_enabled(self, family_root: Path) -> None:
        config: dict = {}
        ai_config = {"sandbox": {"container_enabled": True}}

        override_sandbox_provider(config, ai_config, "family-A", family_root)

        assert config["sandbox"]["use"] == AIO_SANDBOX_PROVIDER_PATH

    def test_sets_pinned_image(self, family_root: Path) -> None:
        config: dict = {}
        ai_config = {"sandbox": {"container_enabled": True}}

        override_sandbox_provider(config, ai_config, "family-A", family_root)

        assert config["sandbox"]["image"] == DEFAULT_CONTAINER_IMAGE

    def test_preserves_operator_image(self, family_root: Path) -> None:
        """An explicitly configured image is not replaced by the default."""
        config: dict = {"sandbox": {"image": "custom:1.0"}}
        ai_config = {"sandbox": {"container_enabled": True}}

        override_sandbox_provider(config, ai_config, "family-A", family_root)

        assert config["sandbox"]["image"] == "custom:1.0"

    def test_merges_environment(self, family_root: Path) -> None:
        """Existing environment entries survive the overlay merge."""
        config: dict = {"sandbox": {"environment": {"EXISTING": "1"}}}
        ai_config = {"sandbox": {"container_enabled": True}}

        override_sandbox_provider(config, ai_config, "family-A", family_root)

        env = config["sandbox"]["environment"]
        assert env["EXISTING"] == "1"
        assert env["PYTHONDONTWRITEBYTECODE"] == "1"

    def test_does_not_add_mounts(self, family_root: Path) -> None:
        config: dict = {}
        ai_config = {"sandbox": {"container_enabled": True}}

        override_sandbox_provider(config, ai_config, "family-A", family_root)

        assert "mounts" not in config["sandbox"]

    def test_tolerates_malformed_policy(self, family_root: Path) -> None:
        """A bad policy must not block enabling container isolation."""
        config: dict = {}
        ai_config = {
            "sandbox": {"container_enabled": True},
            "sandbox_policy": {"max_file_size_bytes": -1},
        }

        override_sandbox_provider(config, ai_config, "family-A", family_root)

        assert config["sandbox"]["use"] == AIO_SANDBOX_PROVIDER_PATH


class TestConfigBuilderWiring:
    """The overlay is reachable from the real config builder."""

    def test_inject_container_sandbox_switches_provider(self, tmp_path, monkeypatch):
        from apps.agent.services.deerflow_adapter.family_adapter_cache import (
            _inject_container_sandbox,
        )

        config: dict = {}
        _inject_container_sandbox(
            config, {"sandbox": {"container_enabled": True}}, "family-A"
        )

        assert config["sandbox"]["use"] == AIO_SANDBOX_PROVIDER_PATH

    def test_inject_container_sandbox_noop_by_default(self):
        from apps.agent.services.deerflow_adapter.family_adapter_cache import (
            _inject_container_sandbox,
        )

        config: dict = {"sandbox": {"use": "original:Provider"}}
        _inject_container_sandbox(config, {}, "family-A")

        assert config["sandbox"]["use"] == "original:Provider"
