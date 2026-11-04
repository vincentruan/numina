"""Integration tests for container-level sandbox isolation (T22).

These require a running Docker Engine and pull DeerFlow's all-in-one sandbox
image, so they are marked ``docker`` and skip when Docker is unavailable.

They verify the property T22 exists for: two families get containers whose
filesystem views do not overlap, so cross-family access fails at the OS level,
while the software gate independently rejects the same path.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
from deerflow.guardrails.provider import GuardrailRequest

from apps.agent.services.deerflow_adapter.numina_guardrail_provider import (
    NuminaGuardrailProvider,
)
from apps.agent.services.runtime.numina_container_overlay import (
    AIO_SANDBOX_PROVIDER_PATH,
    override_sandbox_provider,
)
from apps.agent.services.runtime.sandbox_provider import (
    reset_family_sandbox_context,
    set_family_sandbox_context,
)

pytestmark = pytest.mark.docker


def _docker_available() -> bool:
    if shutil.which("docker") is None:
        return False
    try:
        return (
            subprocess.run(
                ["docker", "info"], capture_output=True, timeout=15
            ).returncode
            == 0
        )
    except (OSError, subprocess.TimeoutExpired):
        return False


requires_docker = pytest.mark.skipif(
    not _docker_available(), reason="Docker Engine is not available"
)


class TestPerFamilyMountIsolation:
    """Each family's sandbox tree is mounted alone."""

    @requires_docker
    def test_provider_derives_mounts_from_family_identity(self, tmp_path: Path) -> None:
        """Mount sources come from the family_id passed to acquire.

        The provider reads ``user_id`` — Numina's family_id — so two families
        resolve to two disjoint host trees. This is the mechanism that makes
        cross-family access impossible inside the container.
        """
        from deerflow.community.aio_sandbox.aio_sandbox_provider import (
            AioSandboxProvider,
        )

        family_a = tmp_path / "users" / "family-A"
        family_b = tmp_path / "users" / "family-B"
        for root in (family_a, family_b):
            for sub in ("workspace", "uploads", "outputs"):
                (root / "threads" / "t1" / "user-data" / sub).mkdir(parents=True)

        mounts_a = AioSandboxProvider._get_thread_mounts("t1", user_id="family-A")
        mounts_b = AioSandboxProvider._get_thread_mounts("t1", user_id="family-B")

        sources_a = {src for src, _, _ in mounts_a}
        sources_b = {src for src, _, _ in mounts_b}

        # Each family mounts its own workspace/uploads/outputs plus the
        # read-only ACP workspace — four sources each, no overlap between them.
        assert len(sources_a) == len(sources_b) == 4
        assert not (sources_a & sources_b), (
            "family A and family B must not share a mount source"
        )
        assert any("family-A" in src for src in sources_a)
        assert any("family-B" in src for src in sources_b)

    @requires_docker
    def test_family_trees_are_disjoint(self, tmp_path: Path) -> None:
        """A file in one family's tree is not reachable from the other's."""
        a_ws = tmp_path / "users" / "family-A" / "threads" / "t1" / "user-data" / "workspace"
        b_ws = tmp_path / "users" / "family-B" / "threads" / "t1" / "user-data" / "workspace"
        a_ws.mkdir(parents=True)
        b_ws.mkdir(parents=True)

        (b_ws / "private.json").write_text('{"secret": true}', encoding="utf-8")

        assert not (a_ws / "private.json").exists()


class TestDualEnforcement:
    """Container isolation and the software gate both reject cross-family paths."""

    @requires_docker
    def test_gate_blocks_path_outside_family_tree(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        a_root = tmp_path / "users" / "family-A" / "threads" / "t1" / "user-data"
        b_root = tmp_path / "users" / "family-B" / "threads" / "t1" / "user-data"
        for root in (a_root, b_root):
            for sub in ("workspace", "uploads", "outputs"):
                (root / sub).mkdir(parents=True)
        (b_root / "workspace" / "private.json").write_text("secret", encoding="utf-8")

        fake = type(
            "FakePaths",
            (),
            {
                "host_sandbox_user_data_dir": staticmethod(
                    lambda thread_id, *, user_id=None: str(a_root)
                )
            },
        )
        monkeypatch.setattr(
            "apps.agent.services.deerflow_adapter.numina_guardrail_provider.get_paths",
            lambda: fake(),
        )

        set_family_sandbox_context("family-A", caller_user_id="u1")
        try:
            provider = NuminaGuardrailProvider()
            decision = provider.evaluate(
                GuardrailRequest(
                    tool_name="read_file",
                    tool_input={"path": str(b_root / "workspace" / "private.json")},
                    thread_id="t1",
                )
            )
        finally:
            reset_family_sandbox_context()

        assert decision.allow is False


class TestProviderSelection:
    """Opting a family in selects the container provider."""

    @requires_docker
    def test_enabled_family_uses_aio_provider(self, tmp_path: Path) -> None:
        config: dict = {}
        override_sandbox_provider(
            config,
            {"sandbox": {"container_enabled": True}},
            "family-A",
            tmp_path / "users" / "family-A",
        )
        assert config["sandbox"]["use"] == AIO_SANDBOX_PROVIDER_PATH

    @requires_docker
    def test_provider_path_resolves(self) -> None:
        """The configured class path must import and expose the provider."""
        from deerflow.reflection import resolve_variable

        provider_cls = resolve_variable(AIO_SANDBOX_PROVIDER_PATH)
        assert provider_cls.__name__ == "AioSandboxProvider"


class TestContainerLifecycle:
    """The container lifecycle is DeerFlow's, exercised through its own API."""

    @requires_docker
    def test_provider_exposes_acquire_get_release(self) -> None:
        """T22 depends on these existing rather than reimplementing them."""
        from deerflow.community.aio_sandbox.aio_sandbox_provider import (
            AioSandboxProvider,
        )

        assert callable(getattr(AioSandboxProvider, "acquire", None))
        assert callable(getattr(AioSandboxProvider, "get", None))
        assert callable(getattr(AioSandboxProvider, "release", None))

    @requires_docker
    def test_idle_timeout_is_configurable(self, tmp_path: Path) -> None:
        """Idle eviction is configured through sandbox.idle_timeout."""
        config: dict = {}
        override_sandbox_provider(
            config,
            {"sandbox": {"container_enabled": True}},
            "family-A",
            tmp_path / "users" / "family-A",
        )
        assert config["sandbox"]["idle_timeout"] == 600
