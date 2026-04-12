"""DeerFlowAdapter — async wrapper around DeerFlowClient.stream()."""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import AsyncGenerator

from schemas.context import RedactedContext
from services.deerflow_adapter.client_factory import get_deerflow_client
from services.deerflow_adapter.exceptions import DeerFlowError, DeerFlowSkillNotFoundError, DeerFlowTimeoutError

logger = logging.getLogger(__name__)

# Bounded thread pool — each stream() call holds a thread for its full duration
_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="deerflow")
# Semaphore bounds concurrent DeerFlow calls to match the executor pool size.
# NOTE: Semaphore(4) does NOT serialize SQLite writes — it allows up to 4 concurrent
# holders. The separate _CHECKPOINTER_LOCK (limit-1) serializes checkpointer writes.
_SEMAPHORE = asyncio.Semaphore(4)
# Separate lock for SQLite checkpointer writes — prevents SQLITE_BUSY under concurrency.
# The harness uses SqliteSaver (langgraph-checkpoint-sqlite) which does not handle
# concurrent writes internally; we serialize at the adapter layer instead.
_CHECKPOINTER_LOCK = asyncio.Lock()


class DeerFlowAdapter:
    """Async adapter for DeerFlowClient. Protocol translation only — no business logic."""

    def __init__(self, config_path: str, timeout_seconds: int = 120) -> None:
        self._client = get_deerflow_client(config_path)
        self._timeout = timeout_seconds

    async def dispatch(self, skill_name: str, context: RedactedContext, thread_id: str) -> str:
        """Dispatch a skill call and return the full response string."""
        async with _SEMAPHORE:
            try:
                loop = asyncio.get_running_loop()
                result = await asyncio.wait_for(
                    loop.run_in_executor(
                        _EXECUTOR,
                        self._sync_dispatch,
                        skill_name,
                        context,
                        thread_id,
                    ),
                    timeout=self._timeout,
                )
                return result
            except asyncio.TimeoutError:
                raise DeerFlowTimeoutError(
                    f"DeerFlow skill '{skill_name}' timed out after {self._timeout}s"
                )
            except DeerFlowSkillNotFoundError:
                raise
            except DeerFlowError:
                raise
            except Exception as e:
                raise DeerFlowError(f"DeerFlow error in skill '{skill_name}': {e}") from e

    async def stream_dispatch(
        self, skill_name: str, context: RedactedContext, thread_id: str
    ) -> AsyncGenerator[str, None]:
        """Yield text deltas for future streaming use."""
        result = await self.dispatch(skill_name, context, thread_id)
        yield result

    def _sync_dispatch(self, skill_name: str, context: RedactedContext, thread_id: str) -> str:
        """Synchronous DeerFlow call — runs in thread pool executor."""
        try:
            # Build prompt from redacted context
            prompt = self._build_prompt(skill_name, context)
            # stream() returns a sync generator of StreamEvent objects
            chunks = []
            for event in self._client.stream(
                message=prompt,
                thread_id=thread_id,
            ):
                # Collect AI text events
                if hasattr(event, "data") and isinstance(event.data, str):
                    chunks.append(event.data)
                elif isinstance(event, str):
                    chunks.append(event)
            return "".join(chunks)
        except Exception as e:
            err_msg = str(e).lower()
            if "skill" in err_msg and ("not found" in err_msg or "unknown" in err_msg):
                raise DeerFlowSkillNotFoundError(f"Skill not found: {skill_name}") from e
            raise DeerFlowError(str(e)) from e

    def _build_prompt(self, skill_name: str, context: RedactedContext) -> str:
        """Build a skill-dispatch prompt from the redacted context."""
        import json
        ctx_dict = context.model_dump(exclude={"redaction_log"})
        return f"[SKILL:{skill_name}]\n{json.dumps(ctx_dict, ensure_ascii=False, indent=2)}"
