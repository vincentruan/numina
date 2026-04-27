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
variables (`$AI_API_KEY`, `$AI_MODEL`) defined in that config — they are never hardcoded.

**Important:** DeerFlow config loader expects simple `$VAR` syntax (not bash-style `${VAR:-default}`).
If the env var is not set, it resolves to an empty string. Always ensure AI_MODEL and AI_API_KEY
are set before initializing DeerFlow.

## OD-2: 家庭级 DeerFlow 配置（动态注入）

Numina 支持按家庭配置 AI 模型（每个家庭有不同的 `ai_provider`, `ai_api_key`, `ai_model_id`）。
DeerFlow 的全局配置机制不支持并发多配置，因此采用 **方案 B：按家庭缓存实例**：

### 架构

```
orchestrator.dispatch(family_id, ai_config)
    ↓
create_family_adapter(family_id, ai_config)
    ↓
family_adapter_cache.get_family_adapter(family_id, ai_config)
    ↓
┌─ 缓存命中 → 返回已有的 DeerFlowClient
│
└─ 缓存未命中 →
    1. 生成临时 config.yaml（注入家庭的 api_key/model_id）
    2. 初始化 DeerFlowClient(config_path=temp_config)
    3. 缓存实例（LRU，最多 100 个家庭）
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

`_generate_temp_config()` 基于 `deerflow_config/base/config.yaml` 模板：
- 替换 `$AI_MODEL` → 家庭的 `ai_model_id`
- 替换 `$AI_API_KEY` → 家庭的 `api_key`（解密后）
- 如有 `ai_base_url`，注入到 llm 配置

生成的临时配置文件存放在 `/tmp/deerflow_config_xxx/`，缓存清理时自动删除。

## OD-2: SQLite checkpointer concurrency

The harness uses `SqliteSaver` (langgraph-checkpoint-sqlite) which does not
handle concurrent writes internally. The adapter uses a separate
`asyncio.Lock` (`_CHECKPOINTER_LOCK`) to serialize checkpointer writes,
independent of the `asyncio.Semaphore(4)` that bounds concurrent DeerFlow
dispatch calls.

**Decision: use `asyncio.Lock` for checkpointer writes** (not WAL mode),
because the harness creates the SQLite connection internally and we cannot
configure WAL mode from outside.
