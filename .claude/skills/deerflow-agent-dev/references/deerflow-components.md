# DeerFlow Harness 可复用组件

> 优先复用 harness 包中的成熟组件，不自建等价功能。

| 组件 | 路径 (submodule 内) | 用法 |
|------|---------------------|------|
| `DeerFlowClient` | `backend/packages/harness/deerflow/client.py` | 同步 generator stream()，ThreadPoolExecutor 桥接 |
| `StreamBridge` | `runtime/stream_bridge/` | 跨进程事件分发（Redis Streams / in-memory） |
| `RunManager` | `runtime/runs/manager.py` | Run 生命周期管理（lease, orphan recovery） |
| `make_lead_agent()` | `agents/lead_agent/agent.py` | 构建 LangGraph agent 图 |
| `create_chat_model()` | `models/factory.py` | 供应商 class 路由 + base_url 规范化 |
| Checkpoint providers | `runtime/checkpointer/` | SQLite / Postgres 持久化 |
| `ExtensionsConfig` | `config/extensions_config.py` | Skill enable/disable + atomic write |
| Skill storage | `skills/storage.py` | LocalSkillStorage scanner |
| `MultiServerMCPClient` | `mcp/` | MCP server 连接管理 |
| Sandbox | `sandbox/` | write_file / read_file / str_replace |
| Trace context | `trace_context.py` | 分布式 trace id 绑定 |

**不自建原则**: 如果 harness 已有等价实现 → 直接复用。能力不足时按顺序尝试：
1. 扩展 adapter 层（`services/deerflow_adapter/`）
2. 检查上游 RFC / plan（`references/deerflow/backend/docs/rfc-*.md`）
3. 升级 `HARNESS_VERSION` 或向 DeerFlow 提 issue — **不得静默 fork**
