# DeerFlow Harness Public API

Pinned commit: see `HARNESS_VERSION`

## OD-1: Harness interface verification

`client.stream()` is a **synchronous generator** — it yields `StreamEvent` objects
one at a time. The `run_in_executor` wrapping in `DeerFlowAdapter._sync_dispatch()`
is therefore **correct and necessary** to avoid blocking the asyncio event loop.

### DeerFlowClient

```python
class DeerFlowClient:
    def __init__(
        self,
        config_path: str | None = None,
        model_name: str | None = None,       # init-time: override default model
        thinking_enabled: bool = False,       # init-time: enable extended thinking
        subagent_enabled: bool = False,       # init-time: enable subagent delegation
        plan_mode: bool = False,              # init-time: enable TodoList middleware
        agent_name: str | None = None,
        checkpointer=None,
    ): ...
    def stream(self, message: str, thread_id: str = ...) -> Generator[StreamEvent, None, None]:
        # NOTE: stream() only accepts message and thread_id.
        # subagent_enabled, plan_mode, thinking_enabled are init-time only — NOT stream() kwargs.
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
variables (`$AI_API_KEY`, `$AI_MODEL`) defined in that config — they are never hardcoded.

**Important:** DeerFlow config loader expects simple `$VAR` syntax (not bash-style `${VAR:-default}`).
If the env var is not set, it resolves to an empty string. Always ensure AI_MODEL and AI_API_KEY
are set before initializing DeerFlow.

## OD-2: 家庭级 DeerFlow 配置（动态注入）

Numina 支持按家庭配置 AI 模型（每个家庭有不同的 `ai_provider`, `ai_api_key`, `ai_model_id`）。
DeerFlow 的全局配置机制不支持并发多配置，因此采用 **方案 B：按家庭缓存实例**：

### 架构

```
orchestrator.dispatch(family_id, ai_config, skill_config)
    ↓
create_family_adapter(family_id, ai_config, subagent_enabled, plan_mode)
    ↓
family_adapter_cache.get_family_adapter(family_id, ai_config, subagent_enabled, plan_mode)
    ↓
┌─ 缓存命中 (family_id, config_id, subagent_enabled, plan_mode) → 返回已有的 DeerFlowClient
│
└─ 缓存未命中 →
    1. 生成临时 config.yaml（注入家庭的 api_key/model_id/memory_path）
    2. 初始化 DeerFlowClient(config_path=temp_config, model_name=...,
                              subagent_enabled=..., plan_mode=...)
    3. 缓存实例（LRU，最多 100 个家庭，key 为 4-tuple）
    4. 返回实例
```

### 使用方式

```python
# Orchestrator 内部调用
from services.deerflow_adapter.adapter import create_family_adapter

family_adapter = create_family_adapter(family_id, ai_config)
raw_output = await family_adapter.dispatch(skill_name, context, thread_id)

# 家庭禁用 AI 或配置变更时清理缓存
from services.deerflow_adapter.adapter import invalidate_family_adapter_cache
invalidate_family_adapter_cache(family_id)
```

### 配置生成逻辑

`_generate_temp_config(base_config_dir, ai_config, family_id)` 基于 `deerflow_config/base/config.yaml` 模板：
- 替换 `$AI_MODEL` → 家庭的 `ai_model_id`
- 替换 `$AI_API_KEY` → 家庭的 `api_key`（解密后）
- 如有 `ai_base_url`，注入到 models 配置
- 注入 `memory.storage_path: {AGENT_DATA_DIR}/{family_id}/memory.json`（家庭级内存隔离）
  - `AGENT_DATA_DIR` 默认为 `data/workspace`，可通过环境变量覆盖
  - 目录在写入前自动创建（`mkdir -p`）
  - Context7 确认 DeerFlow memory 配置键为 `storage_path`（非 `path`）；Postgres namespace 不支持

### 缓存键

缓存键为 4-tuple `(family_id, config_id, subagent_enabled, plan_mode)`：
- 同一家庭的大多数 skill 使用 `(False, False)`，命中同一缓存实例
- `report` 和 `time_machine` 使用 `(True, True)`，创建独立实例
- 最多 4 个变体/家庭（2 flags × 2 values），LRU 上限 100 条目

生成的临时配置文件存放在 `/tmp/deerflow_config_xxx/`，缓存清理时自动删除。

## OD-3: Session memory injection — multi-turn reasoning

Each `DeerFlowClient` must receive an explicit `checkpointer` to support multi-turn
conversations. Without one, `DeerFlowClient` falls back to `get_checkpointer()` which
may return `InMemorySaver` (lost on restart) or a stale singleton after
`reload_app_config()` resets the global config for a different family.

### Architecture

```
family_adapter_cache.get_family_adapter(family_id, ai_config)
    ↓
_get_shared_checkpointer()          ← created once, shared by all families
    ↓ SqliteSaver(/app/data/deerflow-checkpoints.db)
DeerFlowClient(config_path=..., checkpointer=shared_checkpointer)
    ↓
client.stream(message, thread_id=thread_id)
    ↓ DeerFlow namespaces state by thread_id — family isolation maintained
```

### Why a shared checkpointer

- `SqliteSaver` holds a connection to a single SQLite file. Creating one per family
  would open 100 connections (LRU cache size) to 100 different files — wasteful and
  unnecessary.
- DeerFlow namespaces all checkpoint state by `thread_id`. Two families using the
  same checkpointer instance cannot see each other's conversation history as long as
  their `thread_id` values are distinct (which they are — each session gets a UUID).
- The shared instance is created once in `_get_shared_checkpointer()` and reused for
  the lifetime of the process. It is closed in `close_shared_checkpointer()` at
  shutdown.

### Checkpointer DB path

Read from `deerflow_config/base/config.yaml` → `checkpointer.path`.
Default: `/app/data/deerflow-checkpoints.db`.

### Fallback behaviour

If `langgraph-checkpoint-sqlite` is not installed, falls back to `InMemorySaver`
with a WARNING log. Multi-turn memory will not survive restarts in this case.


The harness uses `SqliteSaver` (langgraph-checkpoint-sqlite) which does not
handle concurrent writes internally. The adapter uses a separate
`asyncio.Lock` (`_CHECKPOINTER_LOCK`) to serialize checkpointer writes,
independent of the `asyncio.Semaphore(4)` that bounds concurrent DeerFlow
dispatch calls.

**Decision: use `asyncio.Lock` for checkpointer writes** (not WAL mode),
because the harness creates the SQLite connection internally and we cannot
configure WAL mode from outside.
