# DeerFlow 文档分类索引

> 本索引将 `references/deerflow/backend/docs/` 和 `references/deerflow/docs/` 下的文档按开发场景分类。
> 需要时按需阅读对应文档，无需全部加载。

## 核心架构 (Core Architecture)

理解 DeerFlow 整体架构、请求生命周期、流式传输机制。

| 文档 | 路径 | 何时阅读 |
|------|------|----------|
| 架构总览 | `backend/docs/ARCHITECTURE.md` | 首次了解 DeerFlow 全貌 |
| API 参考 | `backend/docs/API.md` | 查找 Gateway API 端点契约 |
| 流式传输 | `backend/docs/STREAMING.md` | 理解 SSE/事件流协议 |
| Run 事件流 | `backend/docs/RUN_EVENT_STREAM.md` | 理解 run 生命周期事件 |
| Middleware 执行流 | `backend/docs/middleware-execution-flow.md` | 理解 middleware 链（Numina 的 TodoMiddleware 基于此） |
| Plan Mode | `backend/docs/plan_mode_usage.md` | 理解 plan_mode 开关 |
| TUI | `backend/docs/TUI.md` | 终端 UI（Numina 不使用，仅供参考） |

## Skills / Tools / MCP

技能加载、工具注册、MCP 服务器集成、沙盒执行。

| 文档 | 路径 | 何时阅读 |
|------|------|----------|
| MCP Server | `backend/docs/MCP_SERVER.md` | MCP 集成问题 |
| Guardrails | `backend/docs/GUARDRAILS.md` | 安全护栏、工具执行约束 |
| Sandbox 性能分析 | `backend/docs/SANDBOX_MEMORY_PROFILING.md` | 沙盒内存优化 |
| Task Tool 改进 | `backend/docs/task_tool_improvements.md` | TodoList/Task tool 机制 |
| Skill Name 冲突修复 | `docs/SKILL_NAME_CONFLICT_FIX.md` | skill name 冲突排查 |

## Memory / Checkpoint / State

会话记忆、检查点持久化、线程压缩。

| 文档 | 路径 | 何时阅读 |
|------|------|----------|
| Memory 改进 | `backend/docs/MEMORY_IMPROVEMENTS.md` | DeerMem 记忆机制 |
| Memory 设置评审 | `backend/docs/MEMORY_SETTINGS_REVIEW.md` | 记忆配置调优 |
| Memory 改进总结 | `backend/docs/MEMORY_IMPROVEMENTS_SUMMARY.md` | 记忆改进概览 |
| 线程压缩 | `backend/docs/summarization.md` | compact_thread_context 原理 |
| Title 生成 | `backend/docs/AUTO_TITLE_GENERATION.md` | 自动标题机制 |
| Title 实现 | `backend/docs/TITLE_GENERATION_IMPLEMENTATION.md` | 标题生成实现细节 |

## 配置 / 部署 / 设置

安装、配置、Docker 部署。

| 文档 | 路径 | 何时阅读 |
|------|------|----------|
| 配置参考 | `backend/docs/CONFIGURATION.md` | config.yaml 完整字段说明 |
| 安装指南 | `backend/docs/SETUP.md` | 首次搭建开发环境 |
| 文件上传 | `backend/docs/FILE_UPLOAD.md` | 文件上传机制 |
| Apple Container | `backend/docs/APPLE_CONTAINER.md` | macOS 容器部署（Numina 不使用） |

## 认证 / 安全

SSO、鉴权、授权设计。

| 文档 | 路径 | 何时阅读 |
|------|------|----------|
| Auth 设计 | `backend/docs/AUTH_DESIGN.md` | 认证架构 |
| Auth 升级 | `backend/docs/AUTH_UPGRADE.md` | 认证升级路径 |
| SSO | `backend/docs/SSO.md` | SSO 集成 |

## 顶层文档 (Top-Level)

DeerFlow 项目的总体设计和规划文档。

| 文档 | 路径 | 何时阅读 |
|------|------|----------|
| 总体架构 | `docs/ARCHITECTURE.md` | 全栈架构总览 |
| Maintainer Orchestrator | `docs/agents/maintainer-orchestrator-design.md` | 维护者编排设计 |
| OpenViking | `docs/OPENVIKING.md` | OpenViking 集成 |

## RFC / Plans (进阶参考)

设计方案和实施计划，需要深入了解某个子系统时阅读。

| 文档 | 路径 | 何时阅读 |
|------|------|----------|
| 创建 DeerFlow Agent | `backend/docs/rfc-create-deerflow-agent.md` | 创建自定义 agent |
| 共享模块提取 | `backend/docs/rfc-extract-shared-modules.md` | 模块解耦 |
| Grep/Glob 工具 | `backend/docs/rfc-grep-glob-tools.md` | 搜索工具设计 |
| Replay E2E | `backend/docs/REPLAY_E2E.md` | 端到端回放测试 |
| Blocking I/O 检测 | `backend/docs/BLOCKING_IO_DETECTION.md` | 阻塞 IO 检测 |
| IM Channel 连接 | `backend/docs/IM_CHANNEL_CONNECTIONS.md` | IM 渠道集成 |
| GitHub Agents | `backend/docs/GITHUB_AGENTS.md` | GitHub agent 集成 |
| Auth 测试计划 | `backend/docs/AUTH_TEST_PLAN.md` | 认证测试方案 |
| Auth Docker Gap | `backend/docs/AUTH_TEST_DOCKER_GAP.md` | 认证 Docker 测试缺口 |
| Path 示例 | `backend/docs/PATH_EXAMPLES.md` | 路径示例 |
| TODO | `backend/docs/TODO.md` | DeerFlow 待办事项 |
| plans/ 子目录 | `docs/plans/` | 各特性的详细实施计划 |
| superpowers/ | `docs/superpowers/` | 规格说明和设计方案 |
