"""Write-progress emitter ContextVar for ``write_file`` tool calls.

``write_file`` is the one sandbox tool long enough that users wait on it while
an agent report is generated.  ``tool.progress`` is a tool-level status event
(``writing`` → ``done``) rather than byte-level progress, because DeerFlow
writes the file atomically (temp file + rename) — there are no intermediate
bytes to report.

The emitter is a ContextVar rather than a middleware hook so that no bridge
reference has to be threaded through the middleware chain: the run pipeline
installs a publisher for the duration of one run, and the tool wrapper reads
it.  ContextVars are copied by ``asyncio.to_thread`` and by DeerFlow's tool
executor, so the emitter set in the pipeline's context is visible where the
write actually happens.

When no emitter is installed (non-pipeline callers, tests, direct tool use),
:func:`emit_write_progress` is a no-op.
"""

from __future__ import annotations

import contextvars
from collections.abc import Callable

from packages.core.logging import get_logger

logger = get_logger(__name__)

# (status, path, size_bytes, tool_call_id) -> None
WriteProgressEmitter = Callable[[str, str, "int | None", str], None]

_write_progress_emitter: contextvars.ContextVar[WriteProgressEmitter | None] = (
    contextvars.ContextVar("numina_write_progress_emitter", default=None)
)


def set_write_progress_emitter(
    emitter: WriteProgressEmitter | None,
) -> contextvars.Token[WriteProgressEmitter | None]:
    """Install the emitter for the current context. Returns a reset token."""
    return _write_progress_emitter.set(emitter)


def reset_write_progress_emitter(
    token: contextvars.Token[WriteProgressEmitter | None],
) -> None:
    """Restore the emitter that was active before the matching ``set``."""
    _write_progress_emitter.reset(token)


def get_write_progress_emitter() -> WriteProgressEmitter | None:
    """Return the active emitter, or ``None`` when none is installed."""
    return _write_progress_emitter.get()


# Module-level flag: log a missing emitter at most once per process so a
# wiring break (patches applied but emitter not installed) is visible in
# logs without flooding them on every write_file call.
_missing_emitter_logged = False


def emit_write_progress(
    status: str,
    path: str,
    size_bytes: int | None,
    tool_call_id: str,
) -> None:
    """Publish one progress event, if an emitter is installed.

    Emission is best-effort: a publisher failure (closed bridge, full queue)
    must never fail a file write that already succeeded, so the error is
    swallowed.  The emitter is itself responsible for logging.

    When no emitter is installed (non-pipeline path such as direct tool use,
    a custom runner, or a lifespan ordering gap), a single debug-level log
    is emitted so a wiring break is not entirely silent.
    """
    global _missing_emitter_logged  # noqa: PLW0603
    emitter = _write_progress_emitter.get()
    if emitter is None:
        if not _missing_emitter_logged:
            _missing_emitter_logged = True
            logger.debug(
                "write progress: no emitter installed; "
                "tool.progress events will not be emitted"
            )
        return
    try:
        emitter(status, path, size_bytes, tool_call_id)
    except Exception:  # noqa: BLE001 — a progress event must not break the write
        logger.debug(
            "write progress emit failed (non-fatal): status=%s", status, exc_info=True
        )
