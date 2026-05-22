# 统一文件路径管理 + 多租户 Agent/Skill/MCP 资源管理 设计文档

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 为 Numina 的 server 层（backend + agent + scheduler_worker）实现统一文件路径管理（PathManager）和多租户资源隔离方案，复用 DeerFlow2 原生 Agent/Skill/MCP 链路，DB 作为元数据唯一 source of truth。

**Architecture:** App 层负责 family_id 解析 → DB 策略查询 → PathManager 路径映射 → AppConfig 对象构造 → 通过 `make_lead_agent(config)` 的 `RunnableConfig["configurable"]["app_config"]` 单点注入 DeerFlow2，复用其原生 middleware/model/subagent 全链路。

**Tech Stack:** Python 3.12+, FastAPI, SQLAlchemy, DeerFlow2 Harness (LangGraph), Pydantic v2

---

## 1. 核心设计决策

### 1.1 多租户隔离机制：Gateway 路径 + 显式参数注入

**选型**：不使用 `DeerFlowClient` wrapper，不使用 ContextVar，不使用 `reload_app_config()` 全局单例覆盖。

**方案**：每个请求构造独立的 `AppConfig` 对象，通过 `RunnableConfig["configurable"]["app_config"]` 注入 `make_lead_agent()`。DeerFlow2 内部从此单一注入点提取 config，自动透传到全链路（middleware → model → subagent）。

**隔离保证**：
- `AppConfig` 对象是请求级实例，不共享、不缓存
- `create_chat_model(app_config=...)` 每次创建新 LLM 实例，api_key 在构造函数中绑定
- Subagent 通过 `SubagentExecutor` 的 context 注入递归透传
- 不触碰全局状态，不需要 `_init_lock`

**已验证**：DeerFlow2 源码审计确认 `make_lead_agent()` 路径下所有 12 个 middleware、model 创建、tools 加载、subagent 路径均通过显式参数接收 `app_config`，全局 fallback 是死代码。

### 1.2 DB 与文件系统职责边界

| 职责 | 所有者 | 说明 |
|------|--------|------|
| 元数据（启用/禁用/版本/排序/权限/可见性/模型选择/安全策略/配额） | DB | `ai_providers`, `ai_agents`, `ai_skills`, `ai_mcp_servers` |
| 实体文件（SOUL.md, config.yaml, SKILL.md, extensions_config 模板） | 文件系统 | `workspaces/builtin/` 和 `workspaces/tenants/{family_id}/` |
| 会话产物（events.jsonl, artifacts, memory.json, uploads） | 文件系统 | `workspaces/tenants/{family_id}/` |
| 运行态配置（effective config）| 文件系统（生成物） | `runtime/effective/{family_id}/` 可删除重建 |

**不存在 `registry.json`。** DB 是唯一 source of truth。

### 1.3 DeerFlow2 复用原则

| DeerFlow2 能力 | 复用方式 |
|---------------|----------|
| `make_lead_agent()` | 直接调用，注入 `AppConfig` |
| `ThreadState` | 原生使用（messages, artifacts, todos, uploaded_files, sandbox, thread_data） |
| `create_chat_model()` | 通过 `AppConfig.models` 配置，不直接调用 |
| Skills | SKILL.md 格式不变，通过 `skills.path` 指向 effective 目录 |
| MCP | 生成 `extensions_config.json`，通过 `AppConfig` 指定路径 |
| Subagent | 原生 `task_tool` 链路，`app_config` 自动递归透传 |
| Memory | 原生 memory middleware，通过 `AppConfig.memory.storage_path` 配置 |
| Checkpointer | 共享 `SqliteSaver`（按 thread_id 天然隔离） |

---

## 2. 目录结构

```
${DATA_ROOT}/                          # 默认 ~/.numina/data/
├── db/
│   └── numina.db                      # SQLite（开发/单机）
├── workspaces/
│   ├── builtin/                       # 系统内置资源（只读）
│   │   ├── agents/
│   │   │   └── {agent_name}/          # agent_name: [a-z][a-z0-9-]*
│   │   │       ├── SOUL.md
│   │   │       └── config.yaml
│   │   ├── skills/
│   │   │   └── {skill_name}/
│   │   │       └── SKILL.md
│   │   ├── mcp/
│   │   │   └── extensions_config.template.json
│   │   └── llm/
│   │       └── provider_templates.yaml
│   └── tenants/
│       └── {family_id}/               # 租户强隔离边界
│           ├── uploads/
│           │   └── {user_id}/
│           │       └── ...
│           ├── agents/
│           │   └── {agent_name}/
│           │       ├── sessions/
│           │       │   └── {thread_id}/
│           │       │       ├── events.jsonl
│           │       │       ├── uploaded_files.json
│           │       │       ├── todos.json
│           │       │       └── artifacts/
│           │       ├── memory/
│           │       │   └── memory.json
│           │       └── config.overlay.yaml
│           ├── skills/
│           │   └── {skill_name}/
│           │       └── SKILL.md
│           ├── mcp/
│           │   └── extensions_config.overlay.json
│           └── tmp/
│               └── {user_id}/
│                   └── {request_id}/
├── runtime/
│   └── effective/
│       └── {family_id}/               # 生成物（可删除重建）
│           ├── agents/
│           │   └── {agent_name}/
│           │       ├── SOUL.md
│           │       └── config.yaml
│           ├── skills/
│           │   ├── public/
│           │   │   └── {skill_name}/SKILL.md
│           │   └── custom/
│           │       └── {skill_name}/SKILL.md
│           └── extensions_config.json
├── logs/
└── backups/
```

### 目录说明

1. **`workspaces/builtin/`** — 只读。系统管理员维护，普通用户/租户不可写。内置资源的启用/禁用/版本等由 DB 管理。
2. **`workspaces/tenants/{family_id}/`** — 强隔离。所有租户自定义内容、会话产物在此。
3. **`runtime/effective/{family_id}/`** — 生成物。由 DB 策略 + builtin + tenant overlay 合并生成，供 DeerFlow2 运行消费。可删除后重建。
4. **`db/`** — 可选。SQLite 仅建议开发/单机。生产多实例用 Postgres。

### agent 会话目录设计

DeerFlow2 原生路径格式为 `{base_dir}/users/{user_id}/agents/{agent_name}/`。我们将 `base_dir` 设为 `workspaces/tenants/{family_id}/agents/{agent_name}/`，配合 `user_id` 映射为 Numina 的 `user_id`，使 DeerFlow2 原生的 thread/memory 路径自动落入正确的租户目录：

```
DeerFlow2 解析路径:
  {base_dir}/users/{user_id}/memory.json
  → workspaces/tenants/{family_id}/agents/{agent_name}/sessions/{thread_id}/...

Numina PathManager 路径:
  tenant_session_dir(family_id, agent_name, thread_id)
  → ${DATA_ROOT}/workspaces/tenants/{family_id}/agents/{agent_name}/sessions/{thread_id}/
```

---

## 3. PathManager 设计

### 3.1 位置

`server/packages/core/path_manager.py` — 所有 app 共享。

### 3.2 接口

```python
class PathManager:
    """统一文件路径管理。所有本地文件路径必须通过此类获取。"""

    def __init__(self, data_root: str | Path | None = None):
        """
        Args:
            data_root: 覆盖 DATA_ROOT 环境变量。None 时读 env，默认 ~/.numina/data
        """

    # === 根目录 ===
    @property
    def data_root(self) -> Path: ...
    @property
    def db_dir(self) -> Path: ...
    @property
    def logs_dir(self) -> Path: ...
    @property
    def backups_dir(self) -> Path: ...

    # === Builtin 资源（只读）===
    @property
    def builtin_root(self) -> Path: ...
    @property
    def builtin_agents_dir(self) -> Path: ...
    @property
    def builtin_skills_dir(self) -> Path: ...
    @property
    def builtin_mcp_dir(self) -> Path: ...

    def builtin_agent_dir(self, agent_name: str) -> Path: ...
    def builtin_skill_dir(self, skill_name: str) -> Path: ...

    # === 租户目录 ===
    def tenant_root(self, family_id: int) -> Path: ...
    def tenant_uploads_dir(self, family_id: int, user_id: int) -> Path: ...
    def tenant_agents_dir(self, family_id: int) -> Path: ...
    def tenant_agent_dir(self, family_id: int, agent_name: str) -> Path: ...
    def tenant_session_dir(self, family_id: int, agent_name: str, thread_id: str) -> Path: ...
    def tenant_session_events_file(self, family_id: int, agent_name: str, thread_id: str) -> Path: ...
    def tenant_session_artifacts_dir(self, family_id: int, agent_name: str, thread_id: str) -> Path: ...
    def tenant_memory_dir(self, family_id: int, agent_name: str) -> Path: ...
    def tenant_skills_dir(self, family_id: int) -> Path: ...
    def tenant_skill_dir(self, family_id: int, skill_name: str) -> Path: ...
    def tenant_mcp_dir(self, family_id: int) -> Path: ...
    def tenant_tmp_dir(self, family_id: int, user_id: int, request_id: str) -> Path: ...

    # === Runtime effective（生成物）===
    def effective_dir(self, family_id: int) -> Path: ...
    def effective_agents_dir(self, family_id: int) -> Path: ...
    def effective_agent_dir(self, family_id: int, agent_name: str) -> Path: ...
    def effective_skills_dir(self, family_id: int) -> Path: ...
    def effective_extensions_file(self, family_id: int) -> Path: ...

    # === 安全 ===
    def assert_under_root(self, path: Path) -> Path: ...
    def assert_tenant_access(self, path: Path, family_id: int) -> Path: ...
```

### 3.3 安全策略

```python
# 所有 slug 参数验证
SLUG_PATTERN = re.compile(r"^[a-z][a-z0-9-]*$")
THREAD_ID_PATTERN = re.compile(r"^[a-f0-9-]{36}$")  # UUID

def _validate_slug(self, value: str, field_name: str) -> str:
    if not SLUG_PATTERN.match(value):
        raise PathSecurityError(f"Invalid {field_name}: {value!r}")
    return value

def _validate_thread_id(self, value: str) -> str:
    if not THREAD_ID_PATTERN.match(value):
        raise PathSecurityError(f"Invalid thread_id: {value!r}")
    return value

def assert_under_root(self, path: Path) -> Path:
    resolved = path.resolve()
    if not resolved.is_relative_to(self._data_root):
        raise PathSecurityError(f"Path escapes data root: {path}")
    return resolved

def assert_tenant_access(self, path: Path, family_id: int) -> Path:
    resolved = self.assert_under_root(path)
    tenant_root = self.tenant_root(family_id).resolve()
    if not resolved.is_relative_to(tenant_root):
        raise PathSecurityError(f"Path escapes tenant boundary: {path}")
    return resolved
```

防护措施：
- `family_id` 转 str 后验证为纯数字
- `agent_name`、`skill_name` 必须匹配 `[a-z][a-z0-9-]*`（与 DeerFlow2 的 `[A-Za-z0-9-]+` 兼容的小写子集，不含下划线）
- `thread_id` 必须是 UUID 格式
- `user_id` 转 str 后验证为纯数字（Snowflake ID）
- `request_id` 必须是 UUID 格式
- 所有最终路径 `resolve()` 后 `is_relative_to(data_root)` 检查
- 禁止 `..`、绝对路径注入、软链逃逸（resolve 会解析软链到真实路径）

### 3.4 初始化

```python
def __init__(self, data_root: str | Path | None = None):
    raw = data_root or os.environ.get("DATA_ROOT", "~/.numina/data")
    self._data_root = Path(raw).expanduser().resolve()
    self._ensure_base_dirs()
    self._check_writable()
```

启动时：
1. 展开 `~`
2. 转绝对路径（`resolve()`）
3. 创建必要子目录（`db/`, `workspaces/builtin/`, `workspaces/tenants/`, `runtime/effective/`, `logs/`, `backups/`）
4. 写入测试文件验证可读写
5. 校验 `builtin/` 目录存在（若不存在则从项目源码 seed）

### 3.5 单例管理

```python
# server/packages/core/__init__.py
from .path_manager import PathManager
from .settings import Settings

_path_manager: PathManager | None = None

def get_path_manager() -> PathManager:
    global _path_manager
    if _path_manager is None:
        _path_manager = PathManager()
    return _path_manager
```

---

## 4. Effective Config 生成（资源合并策略）

### 4.1 EffectiveConfigBuilder

位置：`server/packages/core/effective_config.py`

每次 Agent run 前，App 层调用 `EffectiveConfigBuilder` 生成当前请求的运行态配置：

```python
class EffectiveConfigBuilder:
    """
    合并 DB 策略 + builtin 文件 + tenant overlay → DeerFlow2 AppConfig 对象。
    """

    def __init__(self, path_manager: PathManager):
        self._pm = path_manager

    async def build(
        self,
        family_id: int,
        agent_name: str,
        ai_provider: dict,       # 从 DB 查询的 provider config
        agent_config: dict,      # 从 DB 查询的 agent config
        enabled_skills: list[dict],  # 从 DB 查询的启用 skills
        mcp_servers: list[dict],     # 从 DB 查询的启用 MCP servers
    ) -> "EffectiveConfig":
        """
        Returns:
            EffectiveConfig 包含:
            - app_config: DeerFlow2 AppConfig 对象（内存中，不写文件）
            - skills_dir: effective skills 目录路径
            - memory_path: 当前 agent 的 memory 路径
            - thread_data: ThreadState 需要的 workspace/uploads/outputs 路径
        """
```

### 4.2 合并流程

```
1. 鉴权（由 router 层完成）
   确认 user_id 属于 family_id

2. 查询 DB（由 service 层完成，传入 builder）
   - ai_provider: 已选定的 provider（经过 _select_model() 多 slot 选择）
   - agent_config: agent 元数据（soul_md, skills, tool_groups, model, subagent_enabled）
   - enabled_skills: 当前租户启用的 skill 列表（含 builtin + custom）
   - mcp_servers: 当前租户启用的 MCP servers

3. 解析实体文件
   对每个 enabled skill:
     if is_builtin: 读 builtin_skill_dir(skill_name)/SKILL.md
     else: 读 tenant_skill_dir(family_id, skill_name)/SKILL.md
   对 agent SOUL.md:
     if is_builtin: 读 builtin_agent_dir(agent_name)/SOUL.md
     else: 读 tenant_agent_dir(family_id, agent_name)/config.overlay.yaml
     合并: base SOUL.md + overlay (如有)

4. 生成 effective 目录
   effective_skills_dir(family_id)/ 下:
     public/{skill_name}/SKILL.md  (builtin skills 硬链接或 copy)
     custom/{skill_name}/SKILL.md  (tenant skills 硬链接或 copy)
   effective_agent_dir(family_id, agent_name)/:
     SOUL.md (合并后)
     config.yaml

5. 生成 extensions_config.json
   合并: builtin/mcp/extensions_config.template.json
       + tenant/mcp/extensions_config.overlay.json
       + DB 中各 mcp_server 的配置
   写入: effective_extensions_file(family_id)
   env 变量: $VAR 保留占位符（运行时由 DeerFlow2 解析）

6. 构造 AppConfig 对象
   - models: [{name:"main", use:<class>, model:<id>, api_key, base_url, ...}]
   - skills.path: effective_skills_dir(family_id)
   - extensions_config_path: effective_extensions_file(family_id)
   - memory.storage_path: tenant_memory_dir(family_id, agent_name)/memory.json
   - checkpointer: 共享 SqliteSaver 实例
```

### 4.3 AppConfig 构造（核心隔离点）

```python
from deerflow.config.app_config import AppConfig

def _build_app_config(
    self,
    ai_provider: dict,
    family_id: int,
    agent_name: str,
    effective_skills_dir: Path,
    effective_extensions_file: Path,
) -> AppConfig:
    """构造请求级 AppConfig 对象。不触碰全局单例。"""

    model_entry = self._build_model_entry(ai_provider)

    config_dict = {
        "models": [model_entry],
        "skills": {
            "path": str(effective_skills_dir),
        },
        "extensions_config_path": str(effective_extensions_file),
        "memory": {
            "enabled": True,
            "storage_path": str(
                self._pm.tenant_memory_dir(family_id, agent_name) / "memory.json"
            ),
        },
        "checkpointer": {
            "type": "sqlite",
            "connection_string": str(self._pm.db_dir / "deerflow-checkpoints.db"),
        },
    }
    return AppConfig.model_validate(config_dict)
```

### 4.4 Model Entry 构建（复用现有逻辑）

从现有 `family_adapter_cache._generate_temp_config()` 提取，输出目标从 YAML dict 变为 Python dict：

```python
PROVIDER_CLASS_MAP = {
    "anthropic": "langchain_anthropic:ChatAnthropic",
    "openai": "langchain_openai:ChatOpenAI",
    "openai_compatible": "langchain_openai:ChatOpenAI",
}

THINKING_CLASS_OVERRIDES = {
    "deepseek": "deerflow.models.patched_deepseek:PatchedChatDeepSeek",
    "openai": "deerflow.models.patched_openai:PatchedChatOpenAI",
    "openai_compatible": "deerflow.models.patched_openai:PatchedChatOpenAI",
}

def _build_model_entry(self, ai_provider: dict) -> dict:
    provider = ai_provider.get("ai_provider", "openai")
    model_id = ai_provider["ai_model_id"]
    api_key = ai_provider["api_key"]
    base_url = ai_provider.get("ai_base_url")

    # Capability detection
    caps = ai_provider.get("model_1_capabilities") or []
    thinking_supported = "deep_thinking" in caps

    # Class resolution
    use_class = PROVIDER_CLASS_MAP.get(provider, "langchain_openai:ChatOpenAI")
    if thinking_supported:
        if "deepseek" in model_id.lower():
            use_class = THINKING_CLASS_OVERRIDES["deepseek"]
        elif provider in ("openai", "openai_compatible"):
            use_class = THINKING_CLASS_OVERRIDES[provider]

    entry = {
        "name": "main",
        "use": use_class,
        "model": model_id,
        "api_key": api_key,
        "supports_thinking": thinking_supported,
    }
    if base_url:
        entry["base_url"] = base_url

    # Thinking-specific config
    if thinking_supported:
        entry.update(self._build_thinking_config(provider, model_id))

    return entry
```

---

## 5. Agent Run 执行流程

### 5.1 新架构执行链路

```
HTTP POST /agent/{agent_id}/stream
  │
  ├─ Router: 提取 X-Family-Id, X-User-Id, auth 校验
  │
  ├─ AgentRunService.execute()
  │   ├─ BackendClient.get_agent_config(agent_id)     → agent 元数据
  │   ├─ BackendClient.get_family_ai_configs()        → provider 列表
  │   ├─ _select_model(providers, task_type)          → (provider, model_id, caps)
  │   ├─ BackendClient.get_enabled_skills(agent_id)   → skill 列表
  │   ├─ BackendClient.get_enabled_mcp(family_id)     → MCP 列表
  │   │
  │   ├─ EffectiveConfigBuilder.build(...)            → EffectiveConfig
  │   │   ├─ 生成 effective skills 目录
  │   │   ├─ 生成 extensions_config.json
  │   │   └─ 构造 AppConfig 对象（内存中）
  │   │
  │   ├─ 构造 RunnableConfig:
  │   │   config = {
  │   │     "configurable": {
  │   │       "thread_id": thread_id,
  │   │       "app_config": effective_config.app_config,
  │   │       "user_id": str(user_id),
  │   │     }
  │   │   }
  │   │
  │   ├─ agent_graph = make_lead_agent(config)
  │   │   └─ DeerFlow2 全链路自动透传 app_config
  │   │
  │   └─ async for event in agent_graph.astream(state, config):
  │       yield NDJSON events
  │
  └─ StreamingResponse(media_type="application/x-ndjson")
```

### 5.2 与现有 Orchestrator 的关系

| 路径 | 入口 | 用途 | 状态 |
|------|------|------|------|
| Capability-based | `orchestrator.stream_dispatch_events()` | 现有 6 个 capability 入口 | 保留，逐步迁移 |
| Agent-first | `AgentRunService.execute()` | 新 Agent 执行入口 | 新建 |

两条路径共享：
- `_select_model()` 多 Provider + 多 Slot 选择逻辑
- `EffectiveConfigBuilder` AppConfig 构造
- `PathManager` 路径管理
- 共享 checkpointer

迁移策略：现有 capability 路径（chat, allocation, alerts 等）继续通过 orchestrator → DeerFlowAdapter 走旧路径。新的 Agent-first 路径并行存在。待所有 capability 迁移为 Agent 内部 skill 后，移除旧路径。

### 5.3 Cascade Retry 兼容

```python
async def _execute_with_retry(self, ...):
    attempted = set()
    for attempt in range(len(providers)):
        provider, model_id, caps = _select_model(providers, task_type, exclude=attempted)
        effective = await self._builder.build(family_id, agent_name, provider, ...)
        config = {"configurable": {"app_config": effective.app_config, ...}}
        try:
            agent = make_lead_agent(config)
            async for event in agent.astream(state, config):
                yield event
            return
        except TransientError:
            attempted.add(provider["config_id"])
            continue
```

每次 retry 重新构造 `AppConfig`（新 provider 的 api_key/model），传给新的 `make_lead_agent()` 调用。

---

## 6. API 设计

### 6.1 Backend API（面向前端）

已有路由 `ai` prefix `/api/v1/ai`。新增 agent 相关端点：

```
GET    /api/v1/ai/agents              → 当前家庭可用 Agent 列表
GET    /api/v1/ai/agents/{id}         → Agent 详情
POST   /api/v1/ai/agents              → 创建自定义 Agent
PUT    /api/v1/ai/agents/{id}         → 更新 Agent
DELETE /api/v1/ai/agents/{id}         → 删除自定义 Agent

GET    /api/v1/ai/skills              → 当前家庭可用 Skill 列表
GET    /api/v1/ai/mcp-servers         → 当前家庭可用 MCP（脱敏）
PUT    /api/v1/ai/mcp-servers/{id}    → 更新 MCP overlay

POST   /api/v1/ai/uploads             → 上传文件
DELETE /api/v1/ai/tmp                  → 清理临时文件
```

所有端点通过 JWT 中的 `family_id` 做租户隔离，无需 URL 中显式传递 `family_id`。

Response 中包含 `source` 字段：`builtin` | `custom`，标识资源来源。

### 6.2 Internal API（Agent → Backend）

```
GET    /api/v1/internal/ai/agents/{id}         → Agent 配置（含 soul_md）
GET    /api/v1/internal/ai/agents/{id}/skills  → Agent 关联的启用 skills
GET    /api/v1/internal/ai/config              → Family AI providers（已有）
GET    /api/v1/internal/ai/mcp-servers         → Family MCP servers（含密钥）
```

Internal API 使用 `AGENT_INTERNAL_TOKEN` 认证，仅限 agent 服务调用。

### 6.3 Agent Stream API

```
POST   /agent/{agent_id}/stream        → Agent 流式执行（已有）
```

增强：支持 cascade retry、effective config 生成、PathManager 路径注入。

### 6.4 脱敏规则

前端 API 返回的 MCP/Provider 配置：
- `api_key` → `"sk-...****"`（保留前 4 位 + 掩码）
- `env` 中的 `$VAR` → `"******"`
- `api_key_encrypted` 字段不返回

Internal API 返回解密后的明文（仅 agent 服务可调用）。

---

## 7. MCP 配置管理

### 7.1 合并策略

```
effective_extensions_config.json =
    builtin/mcp/extensions_config.template.json   (base)
  + DB ai_mcp_servers 中 is_enabled=True 的配置    (动态)
  + tenants/{family_id}/mcp/extensions_config.overlay.json  (tenant overlay)
```

合并规则：
- 同名 server：tenant overlay 优先
- DB 中 `is_enabled=False` 的 server 从 effective 中移除
- DB 提供 transport、command、args、url、headers 等元数据
- tenant overlay 提供本地 env 覆盖

### 7.2 env 变量处理

MCP 配置中的 `env` 字段：
- DB 存储：`{"GITHUB_TOKEN": "$GITHUB_TOKEN"}` 占位符形式
- tenant overlay：`{"GITHUB_TOKEN": "$GITHUB_TOKEN"}` 同上
- effective 生成时：保留 `$VAR` 占位符
- DeerFlow2 运行时：`ExtensionsConfig.resolve_env_variables()` 解析 `os.getenv()`
- 实际密钥：通过服务端环境变量或 secrets manager 注入

### 7.3 Filesystem 安全限制

MCP filesystem 类工具的 `allowed_directories` 必须限制在：
```
workspaces/tenants/{family_id}/
```

由 `EffectiveConfigBuilder` 在生成 `extensions_config.json` 时自动注入限制：
```json
{
  "mcpServers": {
    "filesystem": {
      "args": ["--allowed-directories", "/data/workspaces/tenants/{family_id}"]
    }
  }
}
```

---

## 8. 配置模板

### 8.1 `.env.example`

```bash
# ============================================================
# Numina 环境变量配置
# ============================================================

# DATA_ROOT
# 所有本地持久化文件的根目录。
# 默认：~/.numina/data
# Docker 部署请映射为持久化 volume/NAS，例如：
#   -v /data/numina:/root/.numina/data
# 否则容器重建会导致数据丢失（uploads/sessions/memory/db）。
DATA_ROOT=~/.numina/data

# DATABASE_URL
# DB 是 LLM Provider、Agent、Skill、MCP 元数据与启用策略的唯一 source of truth。
# SQLite 仅建议开发/单机使用；生产多实例建议 Postgres。
# SQLite: sqlite:///${DATA_ROOT}/db/numina.db
# Postgres: postgresql+asyncpg://user:pass@host:5432/numina
DATABASE_URL=sqlite:///~/.numina/data/db/numina.db

# AI_ENCRYPTION_KEY
# 用于加密存储在 DB 中的 API Key。Fernet key (base64 encoded 32 bytes)。
# 生成: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
AI_ENCRYPTION_KEY=

# AGENT_INTERNAL_TOKEN
# Agent 服务 → Backend 内部 API 认证 token。
# 生成: python -c "import secrets; print(secrets.token_urlsafe(32))"
AGENT_INTERNAL_TOKEN=

# JWT_SECRET_KEY
# JWT token 签名密钥。
JWT_SECRET_KEY=
```

### 8.2 `docker-compose.yml` 关键配置

```yaml
services:
  backend:
    volumes:
      - ${DATA_ROOT:-./data}:/app/.numina/data   # 必须持久化
    environment:
      - DATA_ROOT=/app/.numina/data
      - DATABASE_URL=sqlite:////app/.numina/data/db/numina.db

  agent:
    volumes:
      - ${DATA_ROOT:-./data}:/app/.numina/data   # 与 backend 共享
    environment:
      - DATA_ROOT=/app/.numina/data
```

---

## 9. 安全模型

### 9.1 访问控制矩阵

| 操作 | builtin/ | tenants/{own_family}/ | tenants/{other_family}/ | runtime/effective/ |
|------|---------|----------------------|------------------------|-------------------|
| 普通用户读 | ✅ | ✅ | ❌ | ✅（自己的） |
| 普通用户写 | ❌ | ✅ | ❌ | ❌ |
| 系统管理员 | ✅ R/W | ✅ R/W | ✅ R/W | ✅（生成物） |
| Agent 运行时 | ✅ 读 | ✅ 自己 family | ❌ | ✅ 自己 family |
| MCP filesystem | ❌ | ✅ 自己 family | ❌ | ❌ |

### 9.2 PathManager 防护层

1. **Slug 验证**：所有路径组件必须匹配白名单 pattern
2. **Resolve 检查**：`path.resolve()` 解析软链后 `is_relative_to(data_root)` 
3. **Tenant 边界**：`assert_tenant_access(path, family_id)` 确保不越界
4. **Builtin 只读**：PathManager 不提供 builtin 写入方法

### 9.3 运行时防护

- Agent 进程的 `thread_data.workspace_path` 设为 `tenants/{family_id}/agents/{agent_name}/sessions/{thread_id}/`
- `thread_data.uploads_path` 设为 `tenants/{family_id}/uploads/{user_id}/`
- MCP filesystem 的 `allowed_directories` 限制在 tenant 目录内
- 临时文件 `tmp/{user_id}/{request_id}/` 有 TTL 清理

---

## 10. 多实例部署考量

| 场景 | 推荐方案 |
|------|----------|
| 开发/单机 | SQLite + 本地文件系统 |
| 生产多实例 | Postgres + 共享 NAS/对象存储挂载 |
| events.jsonl 并发写 | 单实例可用文件；多实例应迁移为 DB 事件表 |
| checkpointer | SQLite（单实例）或 Postgres-backed（多实例）|
| 临时文件 | 本地 `/tmp`（不持久化），定时清理 |

---

## 11. 测试策略

### 单测覆盖

| 测试场景 | 预期行为 |
|----------|----------|
| 路径穿越 `../` | `PathSecurityError` |
| 软链逃逸 | `PathSecurityError`（resolve 后越界） |
| family_id 隔离 | `tenant_root(family_a)` 下的路径不被 `assert_tenant_access(path, family_b)` 通过 |
| builtin 只读 | PathManager 无 builtin 写方法；尝试写入 builtin 目录的操作被拒绝 |
| effective config 生成 | 给定 DB 数据 + builtin 文件 → 验证生成的 AppConfig 字段正确 |
| runtime/effective 删除后重建 | 删除 effective 目录 → 重新 build → 验证结果一致 |
| AppConfig 隔离 | 两个并发请求构造的 AppConfig 互不影响 |
| slug 验证 | 非法字符、空字符串、过长字符串均 reject |

### 集成测试

| 测试场景 | 验证 |
|----------|------|
| Agent run E2E | HTTP 请求 → effective config → make_lead_agent → 模拟 LLM 响应 → NDJSON stream |
| Cascade retry | Provider 1 失败 → 自动切换 Provider 2 → 新 AppConfig → 成功 |
| MCP 合并 | builtin + tenant overlay → 正确的 extensions_config.json |
| 文件上传 | 上传到 `tenants/{family_id}/uploads/` → 验证路径正确 |

---

## 12. 迁移策略

### Phase 1: PathManager + EffectiveConfigBuilder（本次实现）

1. 实现 `PathManager` 在 `server/packages/core/`
2. 实现 `EffectiveConfigBuilder` 在 `server/packages/core/`
3. 新建 `AgentRunService` 使用 Gateway 路径
4. 替换 `agent_dispatch.py` 中的 `create_family_adapter()` 为新路径
5. 保留 orchestrator 旧路径不变（向后兼容）

### Phase 2: 旧路径迁移（后续）

6. 将 orchestrator 的 6 个 capability 迁移为 Agent 内部 skill
7. orchestrator 使用 `EffectiveConfigBuilder` + `make_lead_agent()`
8. 移除 `family_adapter_cache.py`、`DeerFlowAdapter` 类
9. 移除 `_init_lock` 和 `reload_app_config()` 调用

### Phase 3: 前端迁移（后续）

10. AIHubPage 重构为 Agent 卡片模式
11. Agent 创建/编辑 UI
12. Skill/MCP 管理 UI

---

## 13. 验收标准

1. ✅ 全项目无散落路径拼接，所有本地文件路径统一通过 PathManager 获取
2. ✅ family_id 是强隔离边界，任意用户不能读写其他 family_id 的文件
3. ✅ user_id 只作为 family_id 内部用户维度
4. ✅ builtin 目录只读，普通用户不可写
5. ✅ 不存在 registry.json 依赖
6. ✅ DB 是元数据和启用策略的唯一 source of truth
7. ✅ 删除 runtime/effective/{family_id} 后，系统能重新生成配置
8. ✅ 用户面对的是 Agent，不是 Skill/MCP
9. ✅ Skill 作为 Agent 内部能力模块，由 Agent 调度
10. ✅ MCP 最终生成 DeerFlow2 可消费的 extensions_config.json
11. ✅ MCP 密钥展示必须脱敏
12. ✅ MCP filesystem 类工具不能访问其他租户或 DATA_ROOT 外部路径
13. ✅ Docker 重启后 uploads、memory、sessions、artifacts、db 不丢失
14. ✅ SQLite/Postgres 切换清晰
15. ✅ 配置模板注释完整
16. ✅ 单测覆盖路径穿越、软链逃逸、family_id 隔离、builtin 只读、effective 生成/重建
