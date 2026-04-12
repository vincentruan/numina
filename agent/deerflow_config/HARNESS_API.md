# DeerFlow Harness Public API

Pinned commit: see `HARNESS_VERSION`

## OD-1: Harness interface verification

`client.stream()` is a **synchronous generator** — it yields `StreamEvent` objects
one at a time. The `run_in_executor` wrapping in `DeerFlowAdapter._sync_dispatch()`
is therefore **correct and necessary** to avoid blocking the asyncio event loop.

### DeerFlowClient

```python
class DeerFlowClient:
    def stream(self, message: str, thread_id: str = ...) -> Generator[StreamEvent, None, None]:
        ...
    def chat(self, message: str, thread_id: str = ...) -> str:
        ...
```

### StreamEvent

```python
@dataclass
class StreamEvent:
    type: Literal["values", "messages-tuple", "custom", "end"]
    data: dict[str, Any]
```

Text content is extracted from `event.data` when it is a `str`, or from
`event.data` dict keys depending on event type. The adapter collects all
string chunks and joins them.

### RunnableConfig

`RunnableConfig` is available from `langchain_core.runnables` and is used
to inject the API key into the model call without embedding it in the prompt
or context string:

```python
from langchain_core.runnables import RunnableConfig
config = RunnableConfig(configurable={"model_api_key": api_key})
```

The `DeerFlowClient` constructor accepts a `config_path` pointing to
`deerflow_config/base/config.yaml`. Model API keys are read from environment
variables (`$AI_API_KEY`) defined in that config — they are never hardcoded.

## OD-2: SQLite checkpointer concurrency

The harness uses `SqliteSaver` (langgraph-checkpoint-sqlite) which does not
handle concurrent writes internally. The adapter uses a separate
`asyncio.Lock` (`_CHECKPOINTER_LOCK`) to serialize checkpointer writes,
independent of the `asyncio.Semaphore(4)` that bounds concurrent DeerFlow
dispatch calls.

**Decision: use `asyncio.Lock` for checkpointer writes** (not WAL mode),
because the harness creates the SQLite connection internally and we cannot
configure WAL mode from outside.
