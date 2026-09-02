# Numina Agent 开发经验索引

> 项目已有的 agent 模块开发经验和踩坑记录。按场景分类，遇到相关问题时先查阅这里。

## 架构模式 (Architecture Patterns)

| 文档 | 路径 | 核心教训 |
|------|------|----------|
| 统一 stream_run 多 app 调度 | `docs/solutions/architecture-patterns/two-ai-apps-unified-dispatch-stream-run.md` | 单一入口 worker.run_agent，ContextVar 传播，R1 allowlist |
| DeerFlow adapter 解耦 | `docs/solutions/architecture-patterns/deerflow-adapter-decoupling-stream-bridge-subclass.md` | 子类替代 monkey-patch，共享包按域放置 |
| 三态熔断器 | `docs/solutions/architecture-patterns/three-state-circuit-breaker-with-cascade-retry-2026-05-20.md` | FSM + 4 adapters, cascade retry |
| MCP caller-bound principal | `docs/solutions/architecture-patterns/mcp-caller-bound-principal-2026-05-31.md` | tenant isolation 在 SSE 握手时冻结 |
| MCP chat adapter 架构 | `docs/solutions/architecture-patterns/mcp-chat-adapter-architecture-2026-05-21.md` | ChatAdapter 历史架构（已被统一调度取代） |
| Gateway-Worker 职责分离 | `docs/solutions/architecture-patterns/gateway-worker-responsibility-separation-2026-08-15.md` | gateway 和 worker 的职责边界 |
| Checkpoint retry | `docs/solutions/architecture-patterns/ai-chat-checkpoint-retry-architecture.md` | checkpoint 重试机制 |
| 页面离开连续性 | `docs/solutions/architecture-patterns/ai-task-page-leave-continuity-2026-08-21.md` | chat on_disconnect=continue; narrative KeepAlive |
| 统一数据根路径 | `docs/solutions/architecture-patterns/unified-data-root-path-management-2026-05-17.md` | DATA_ROOT 统一管理 |

## 集成问题 (Integration Issues)

| 文档 | 路径 | 核心教训 |
|------|------|----------|
| DeerFlow stream 类型不匹配 | `docs/solutions/integration-issues/deerflow-adapter-stream-type-mismatch-and-security-issues-2026-05-16.md` | generator yield 类型变更须同步所有 caller |
| GLM5 thinking endpoint | `docs/solutions/integration-issues/deerflow-glm5-thinking-provider-endpoint-mismatch-2026-05-16.md` | provider 和 endpoint 匹配 |
| Harness 静默 fallback | `docs/solutions/integration-issues/deerflow-harness-silent-fallback-and-concurrency-fixes-2026-04-12.md` | 永不静默吞异常 |
| MCP asyncio.Lock 死锁 | `docs/solutions/integration-issues/mcp-cache-asyncio-lock-threading-deadlock.md` | 跨线程 Lock vs asyncio.Lock |
| Thinking block 泄漏 | `docs/solutions/integration-issues/thinking-block-content-leaking-into-titles.md` | 标题中间件须过滤 thinking |
| Stream 提前关闭 | `docs/solutions/integration-issues/stream-closure-fix-2026-06-15.md` | SSE 连接中断处理 |
| 部署配置差异 | `docs/solutions/integration-issues/production-deployment-config-mismatches.md` | CSP/pool/nginx/icon 差异 |

## Memory 文件 (关键经验)

以下 memory 文件包含 agent 开发的核心架构知识和踩坑经验。
路径前缀: `~/.claude/projects/-Volumes-LexarSSDNQ790-geek-space-github-numina-dev-space-numina/memory/`

### 必读（架构级）

| 文件 | 内容 |
|------|------|
| `agent-stream-run-architecture.md` | v2 stream_run 调度架构，5 app 路由，完整流程图 |
| `ai-chat-skill-system-architecture.md` | 17 个 builtin skills 的三个子系统分类 |
| `ai-two-apps-unified-dispatch-progress.md` | 统一调度重构进度和决策 |
| `backend-deerflow-dependency-decouple.md` | stream_bridge 提取，NuminaDeerFlowClient 子类 |
| `mcp-contextvar-optimization-complete.md` | RunContext facade，MCP ContextVar 优化 |
| `circuit-breaker-unification-complete.md` | 熔断器 FSM + 4 adapters |

### DeerFlow 集成陷阱

| 文件 | 内容 |
|------|------|
| `deerflow-harness-upgrade-rev.md` | harness 升级经验（4538c322→10890e10） |
| `deerflow-exclusive-routing-fix.md` | thinking bubble 互斥路由 |
| `deerflow-middleware-duplicate-pitfall.md` | 不可重复添加 native middlewares |
| `deerflow-todo-middleware-name-collision.md` | TodoMiddleware 命名冲突 |
| `supabase-deerflow-separate-database.md` | 独立 DB 避免 alembic_version 冲突 |
| `f2-sandbox-contextvar-not-propagated-fix.md` | sandbox ContextVar 未传播到 executor |
| `extensions-config-contextvar-multifamily-fix.md` | extensions_config 环境变量并发泄漏 |
| `narrative-cache-stream-wrapper.md` | DashScope reasoning_content patch |

### 前端-AI 交互

| 文件 | 内容 |
|------|------|
| `ai-chat-frontend-architecture.md` | 路由、SSE 协议 |
| `ai-chat-known-bugs.md` | token/planning/group 已知 bug |
| `ai-chat-blank-response-fix.md` | blank/error/copy/JSONL/MCP 修复 |
| `ai-chat-streaming-burstiness-root-cause.md` | "few chars→pause→dump" 主因 |
| `ai-chat-mcp-stale-cache-root-cause.md` | MCP stale cache 根因 |
| `skill-id-mismatch-pitfall.md` | 前端 useTaskResume 须匹配后端 SKILL_ID |
| `ai-task-page-leave-continuity.md` | chat on_disconnect=continue |

### Skill 系统

| 文件 | 内容 |
|------|------|
| `skill-refactor-tier3-complete.md` | 12 tasks + 7 函数名正名 |
| `ai-chat-path-c-skill-migration.md` | Path C 迁移决策 |
| `ai-chat-deerflow-step-parity.md` | DeerFlow 步骤对齐 |
| `ai-chat-tool-call-deerflow-parity.md` | tool call DeerFlow 对齐 |
| `ai-chat-token-usage-deerflow-presets.md` | token 使用 DeerFlow 预设 |

### 安全 & 对抗测试

| 文件 | 内容 |
|------|------|
| `ai-security-adversarial-test-area-11.md` | 20 个红队用例 |
| `finance-coach-target-id-hallucination.md` | LLM 杜撰 target_id 三层防御 |
| `finance-coach-validate-repair-cycle.md` | validate→repair 循环 |
