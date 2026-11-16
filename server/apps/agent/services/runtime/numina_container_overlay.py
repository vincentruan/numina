"""Numina container-sandbox overlay for DeerFlow's AioSandboxProvider.

T22 upgrades the software gate to OS-level isolation: each family gets a Docker
container whose filesystem view is that family's own sandbox tree, so
cross-family access is impossible at the mount-namespace level.

Numina does not re-implement container lifecycle. DeerFlow's
``AioSandboxProvider`` + ``LocalContainerBackend`` already handle per-thread
mount computation, warm pooling, idle timeout, ownership leases, and network
policy. This module supplies the provider switch plus the container-local
settings Numina needs; it deliberately does not re-specify mounts, because
``AioSandboxProvider._get_thread_mounts`` already bind-mounts exactly the
family's ``workspace``/``uploads``/``outputs`` at ``/mnt/user-data/...`` using
``user_id`` (Numina's family_id) from the acquire call. Adding a second mount
would duplicate that tree at a different path and desynchronize the virtual
paths the file tools use.

What varies per family vs. what stays agent-wide
------------------------------------------------
Per family: the mounted tree (via the provider's thread mounts, keyed on
family_id + thread_id).
Agent-wide: memory/CPU/pids limits. ``SandboxConfig`` has no such fields;
``LocalContainerBackend._start_container`` reads ``DEER_FLOW_SANDBOX_MEMORY``,
``DEER_FLOW_SANDBOX_CPUS``, and ``DEER_FLOW_SANDBOX_PIDS_LIMIT`` from the
process environment. Per-family limits would need a ``LocalContainerBackend``
subclass overriding ``_start_container``.

Image selection
---------------
The container must run DeerFlow's all-in-one sandbox server, so this overlay
does not impose an image: ``sandbox["image"]`` stays whatever the operator
configured, and ``AioSandboxProvider`` falls back to its own default when it is
absent. Pinning a plain Python runtime here would produce a container the
provider cannot drive.

Hardening already applied by ``LocalContainerBackend``
-----------------------------------------------------
``--cap-drop=ALL``, ``no-new-privileges``, memory/CPU/pids limits, plus the
``DEER_FLOW_SANDBOX_CONTAINER_USER`` / ``DEER_FLOW_SANDBOX_SECCOMP_*`` knobs.
This overlay does not duplicate those; it adds the container-local environment
that keeps a bytecode-writing Python image working on a hardened filesystem.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from apps.agent.services.runtime.sandbox_policy import SandboxPolicy
from packages.core.logging import get_logger

logger = get_logger(__name__)

# Class path of DeerFlow's container provider, wired via config["sandbox"]["use"].
AIO_SANDBOX_PROVIDER_PATH = (
    "deerflow.community.aio_sandbox.aio_sandbox_provider:AioSandboxProvider"
)

DEFAULT_TIMEOUT_SECONDS = 600

# DeerFlow's agent-wide container defaults. A policy asking for anything else
# cannot be honoured per family in this pass (see the module docstring).
_AGENT_DEFAULT_MEMORY_MB = 512
_AGENT_DEFAULT_CPU_COUNT = 1


def numina_container_sandbox_config(
    policy: SandboxPolicy,
    family_id: str,
    sandbox_root: Path | str,
) -> dict[str, Any]:
    """Build the Numina-specific ``config["sandbox"]`` overlay.

    The returned dict carries only settings DeerFlow's container provider needs
    from Numina — the container-local environment and the idle timeout. Mounts
    are left to the provider, which derives them per family and thread.

    Args:
        policy: The family's policy. Its resource limits cannot be applied
            per-family here; the argument keeps the policy as the single source
            of truth and lets the overlay report when a policy asks for limits
            this pass cannot honour.
        family_id: Family identifier, used for logging.
        sandbox_root: Host-absolute family user-data root. Recorded for logging
            and validation only — the provider's own thread mounts are the
            authority for what the container can see.

    Returns:
        Dict of provider config keys (``environment``, ``idle_timeout``).
    """
    root = Path(sandbox_root)

    overlay: dict[str, Any] = {
        "environment": {
            # python:3.12-slim writes __pycache__ on import. On a hardened
            # filesystem that raises OSError: Read-only file system, and the
            # obvious operator fix is to disable the hardening entirely.
            "PYTHONDONTWRITEBYTECODE": "1",
        },
        "idle_timeout": DEFAULT_TIMEOUT_SECONDS,
    }

    logger.debug(
        "[container_overlay] family_id=%s root=%s (mounts derived by provider)",
        family_id,
        root,
    )

    # Per-family memory/CPU cannot be expressed through SandboxConfig, so a
    # policy asking for non-default limits would otherwise silently do nothing.
    if (
        policy.max_memory_mb != _AGENT_DEFAULT_MEMORY_MB
        or policy.max_cpu_count != _AGENT_DEFAULT_CPU_COUNT
    ):
        logger.warning(
            "[container_overlay] family_id=%s policy requests %sMB/%s CPU, but "
            "container resource limits are agent-wide in this pass "
            "(DEER_FLOW_SANDBOX_MEMORY/DEER_FLOW_SANDBOX_CPUS); per-family "
            "limits need a LocalContainerBackend._start_container override",
            family_id,
            policy.max_memory_mb,
            policy.max_cpu_count,
        )

    return overlay


def container_enabled(ai_config: dict[str, Any]) -> bool:
    """Read the opt-in flag from ``ai_config['sandbox']['container_enabled']``.

    The flag lives under ``sandbox`` because that is the section DeerFlow
    validates; a top-level key would be dropped as an unknown field.
    """
    sandbox_cfg = ai_config.get("sandbox")
    if not isinstance(sandbox_cfg, dict):
        return False
    return sandbox_cfg.get("container_enabled") is True


def override_sandbox_provider(
    config: dict[str, Any],
    ai_config: dict[str, Any],
    family_id: str,
    sandbox_root: Path | str,
) -> None:
    """Point ``config["sandbox"]`` at the container provider when opted in.

    Mutates ``config`` in place. No-op when the family has not opted into
    container isolation, so merging T22 changes no family's isolation until an
    operator enables it explicitly.
    """
    if not container_enabled(ai_config):
        return

    policy = _resolve_policy(ai_config)
    overlay = numina_container_sandbox_config(policy, family_id, sandbox_root)

    sandbox = config.setdefault("sandbox", {})
    sandbox["use"] = AIO_SANDBOX_PROVIDER_PATH
    # Deliberately leave ``image`` unset when the operator has not chosen one:
    # AioSandboxProvider runs its own all-in-one sandbox server image, and
    # substituting a plain runtime image yields a container with nothing to
    # talk to. DeerFlow's DEFAULT_IMAGE applies when the key is absent.
    sandbox["environment"] = {
        **sandbox.get("environment", {}),
        **overlay["environment"],
    }
    sandbox["idle_timeout"] = overlay["idle_timeout"]

    logger.info(
        "[container_overlay] family_id=%s using AioSandboxProvider image=%s",
        family_id,
        sandbox.get("image", "<provider default>"),
    )


def _resolve_policy(ai_config: dict[str, Any]) -> SandboxPolicy:
    """Resolve the family policy, falling back to defaults on a bad config.

    Container configuration only consults the policy for logging and for the
    limits-availability warning; the software gate is where a malformed policy
    fails closed, so this path degrades quietly instead of blocking startup.
    """
    raw = ai_config.get("sandbox_policy")
    if isinstance(raw, dict):
        try:
            return SandboxPolicy.from_config(raw)
        except Exception as e:
            logger.warning(
                "[container_overlay] invalid sandbox_policy, using defaults: %s",
                e,
                exc_info=True,
            )
    return SandboxPolicy.default_policy()
