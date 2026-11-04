"""NuminaGuardrailProvider — sandbox policy gate for DeerFlow tool calls.

Implements DeerFlow's ``GuardrailProvider`` protocol
(``deerflow.guardrails.provider``), which ``GuardrailMiddleware`` invokes as
``evaluate(request) -> GuardrailDecision`` / ``aevaluate`` before each tool call.

What this provider enforces, per family:
- Path patterns: the tool's virtual path must land inside the family's sandbox
  tree and inside ``allowed_paths`` prefixes.
- Write permission: writes under ``read_only_paths`` prefixes are denied.
- File size: a single write's content must fit ``max_file_size_bytes``.
- Cumulative quota: the family sandbox tree's total size must fit
  ``max_total_quota_bytes`` (measured at check time; see caveat below).

What it deliberately does NOT enforce:
- Raw path traversal. DeerFlow validates that upstream via
  ``validate_local_tool_path`` and ``LocalSandbox._resolve_path_with_mapping``.
- Execution time and execute-path denials. The protocol has no post-execution
  hook to time a call, and ``allow_host_bash: false`` means no tool triggers
  the execute axis.

Quota caveat: the usage walk and the tool's own write are not atomic, so
concurrent requests can overshoot by up to one file's worth. That is accepted
here; hard enforcement belongs to the container tier's OS-level quota.

Relationship to PolicyGuard:
- PolicyGuard: pre-dispatch gate (checks skill/capability before the LLM call)
- NuminaGuardrailProvider: tool execution gate (per tool call during the run)
Both are active simultaneously — different layers, no overlap.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from deerflow.config.paths import get_paths
from deerflow.guardrails.provider import (
    GuardrailDecision,
    GuardrailReason,
    GuardrailRequest,
)

from apps.agent.services.runtime.sandbox_path_validator import (
    validate_path_against_policy,
)
from apps.agent.services.runtime.sandbox_permission_check import (
    check_write_permission,
)
from apps.agent.services.runtime.sandbox_policy import SandboxPolicy
from apps.agent.services.runtime.sandbox_resource_check import (
    check_cumulative_quota,
    check_file_size,
)
from packages.core.logging import get_logger

logger = get_logger(__name__)

# Tools whose paths and payloads this gate inspects. Everything else is not a
# sandbox file operation and passes through untouched.
_FILE_PATH_TOOLS = frozenset({"write_file", "read_file", "str_replace"})

# Tools that mutate file content, and therefore need the write-permission check.
_WRITE_TOOLS = frozenset({"write_file", "str_replace"})

_POLICY_ID = "numina-sandbox-gate"


class NuminaGuardrailProvider:
    """Per-family sandbox policy gate for DeerFlow tool calls.

    Configuration (injected via ``family_adapter_cache._inject_sandbox_gate``)::

        guardrails:
          enabled: true
          provider:
            use: "...:NuminaGuardrailProvider"
            config:
              sandbox_policy: {max_file_size_bytes: 51200, ...}
              fail_closed: true

    Thread safety: the policy is immutable after init and no per-call state is
    stored, so one instance is safe for concurrent use.
    """

    name = "numina-sandbox-gate"
    policy_id = _POLICY_ID

    def __init__(
        self,
        sandbox_policy: dict[str, Any] | None = None,
        fail_closed: bool = True,
    ) -> None:
        """Initialize the provider.

        A malformed ``sandbox_policy`` does not raise: the provider stays
        loadable but enters a fail-closed state that denies every sandbox file
        operation, so a misconfiguration blocks sandbox work instead of
        silently degrading to the permissive default or crashing the run.

        Args:
            sandbox_policy: Policy dict from config, or ``None`` for defaults.
            fail_closed: When True (default), any evaluation error denies the
                call. When False, errors allow the call through with a warning.
        """
        self._fail_closed = fail_closed
        self._policy_error: str | None = None
        try:
            self._policy = SandboxPolicy.from_config(sandbox_policy)
        except Exception as e:
            self._policy = SandboxPolicy.default_policy()
            self._policy_error = str(e)
            logger.error(
                "[sandbox_gate] invalid sandbox_policy; denying all sandbox "
                "operations until the configuration is fixed: %s",
                e,
            )

        logger.debug(
            "[sandbox_gate] initialized: max_file_size=%s quota=%s "
            "allowed_paths=%d read_only_paths=%d fail_closed=%s",
            self._policy.max_file_size_bytes,
            self._policy.max_total_quota_bytes,
            len(self._policy.allowed_paths),
            len(self._policy.read_only_paths),
            self._fail_closed,
        )

    # -- GuardrailProvider protocol -----------------------------------------

    def evaluate(self, request: GuardrailRequest) -> GuardrailDecision:
        """Evaluate a tool call against the family's sandbox policy."""
        try:
            return self._evaluate_internal(request)
        except Exception as e:
            return self._handle_error(e, request)

    async def aevaluate(self, request: GuardrailRequest) -> GuardrailDecision:
        """Async variant. The checks are filesystem-bound and stay synchronous."""
        return self.evaluate(request)

    def release_policy_parameters(self) -> dict[str, object]:
        """Declare the policy knobs active for this provider (audit visibility)."""
        return {
            "max_file_size_bytes": self._policy.max_file_size_bytes,
            "max_total_quota_bytes": self._policy.max_total_quota_bytes,
            "allowed_paths": list(self._policy.allowed_paths),
            "read_only_paths": list(self._policy.read_only_paths),
        }

    # -- Internals ----------------------------------------------------------

    def _evaluate_internal(self, request: GuardrailRequest) -> GuardrailDecision:
        """Run the policy checks. Exceptions propagate to :meth:`evaluate`."""
        if request.tool_name not in _FILE_PATH_TOOLS:
            return _allow()

        if self._policy_error is not None:
            return _deny(
                "invalid_policy",
                f"Sandbox policy configuration is invalid: {self._policy_error}",
            )

        family_id = self._require_family_id()

        virtual_path = request.tool_input.get("path")
        if not isinstance(virtual_path, str) or not virtual_path:
            return _deny(
                "invalid_tool_input",
                f"Tool '{request.tool_name}' was called without a usable 'path' argument",
            )

        sandbox_root = self._sandbox_root(request.thread_id, family_id)
        is_write = request.tool_name in _WRITE_TOOLS

        # 1. Path patterns + sandbox-root containment
        path_result = validate_path_against_policy(
            virtual_path, sandbox_root, self._policy
        )
        if not path_result.allowed:
            return self._violation(
                request,
                family_id=family_id,
                operation="write" if is_write else "read",
                path=virtual_path,
                code="path_not_allowed",
                message=path_result.reason,
            )

        # 2. Write permission against read-only prefixes
        if is_write:
            permission = check_write_permission(path_result.resolved_path, self._policy)
            if not permission.allowed:
                return self._violation(
                    request,
                    family_id=family_id,
                    operation="write",
                    path=virtual_path,
                    code="read_only_path",
                    message=permission.reason,
                )

        # 3. Single-file size limit (write payloads only)
        if is_write:
            size = check_file_size(request.tool_input.get("content"), self._policy)
            if not size.allowed:
                return self._violation(
                    request,
                    family_id=family_id,
                    operation="write",
                    path=virtual_path,
                    code="file_too_large",
                    message=size.reason,
                )

        # 4. Cumulative quota for the family tree
        quota = check_cumulative_quota(sandbox_root, self._policy)
        if not quota.allowed:
            return self._violation(
                request,
                family_id=family_id,
                operation="write" if is_write else "read",
                path=virtual_path,
                code="quota_exceeded",
                message=quota.reason,
            )

        return _allow()

    def _require_family_id(self) -> str:
        """Read family_id, raising when the run context is incomplete."""
        from apps.agent.services.runtime.run_context import assert_run_context_complete
        from apps.agent.services.runtime.sandbox_provider import (
            get_family_sandbox_context,
        )

        assert_run_context_complete("SandboxGate")
        family_id = get_family_sandbox_context()
        if not family_id:
            raise RuntimeError("SandboxGate: family_id ContextVar is not set")
        return family_id

    @staticmethod
    def _sandbox_root(thread_id: str | None, family_id: str) -> Path:
        """Resolve the family's host user-data root for this thread.

        DeerFlow's ``get_paths()`` returns host paths as strings; normalize to
        ``Path`` here so every downstream check works on one type.
        """
        if not thread_id:
            raise RuntimeError("SandboxGate: tool call arrived without a thread_id")
        return Path(get_paths().host_sandbox_user_data_dir(thread_id, user_id=family_id))

    def _violation(
        self,
        request: GuardrailRequest,
        *,
        family_id: str,
        operation: str,
        path: str,
        code: str,
        message: str,
    ) -> GuardrailDecision:
        """Log a policy violation and return the deny decision."""
        logger.warning(
            "[sandbox_gate] violation: family_id=%s tool=%s operation=%s path=%s reason=%s",
            family_id,
            request.tool_name,
            operation,
            path,
            message,
        )
        return _deny(code, message)

    def _handle_error(self, error: Exception, request: GuardrailRequest) -> GuardrailDecision:
        """Apply the configured fail mode after an evaluation error."""
        mode = "fail-closed" if self._fail_closed else "fail-open"
        logger.warning(
            "[sandbox_gate] evaluation failed (%s): family_id=%s tool=%s error=%s",
            mode,
            _best_effort_family_id(),
            request.tool_name,
            error,
            exc_info=True,
        )
        if self._fail_closed:
            return _deny("internal_error", f"Sandbox gate evaluation failed: {error}")
        return _allow()


def _allow() -> GuardrailDecision:
    return GuardrailDecision(allow=True)


def _deny(code: str, message: str) -> GuardrailDecision:
    return GuardrailDecision(
        allow=False,
        policy_id=_POLICY_ID,
        reasons=[GuardrailReason(code=code, message=message)],
    )


def _best_effort_family_id() -> str | None:
    """Read family_id without raising — used only for error-path logging."""
    try:
        from apps.agent.services.runtime.sandbox_provider import (
            get_family_sandbox_context,
        )

        return get_family_sandbox_context()
    except Exception:
        return None
