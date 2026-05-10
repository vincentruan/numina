# AI Agent 会话 JSONL 记录功能需求文档

**版本**：v1.1
**状态**：草稿
**日期**：2026-05-10
**作者**：产品 & 架构团队
**评审对象**：产品、研发、测试

> **v1.1 变更说明**：在 v1.0 基础上补充以下内容：数据库与 JSONL 分工章节（§4a）、会话标题事件、附件与图片事件、引用与上下文事件、消息编辑/删除/反馈事件、模型生成过程事件、技能调用与 Agent 步骤事件、会话恢复流程（§14）、搜索与导出需求（§15）、AI 思考内容可见性策略、完整事件优先级清单（§16）、扩展验收标准。

---

## 目录

1. [背景与目标](#1-背景与目标)
2. [现状分析](#2-现状分析)
3. [差距分析](#3-差距分析)
4. [功能范围](#4-功能范围)
5. [数据库与 JSONL 分工](#5-数据库与-jsonl-分工)
6. [会话 JSONL 文件要求](#6-会话-jsonl-文件要求)
7. [通用事件字段设计](#7-通用事件字段设计)
8. [事件类型目录](#8-事件类型目录)
9. [文件路径与租户隔离](#9-文件路径与租户隔离)
10. [与现有系统的集成策略](#10-与现有系统的集成策略)
11. [会话恢复与接续会话](#11-会话恢复与接续会话)
12. [搜索与导出需求](#12-搜索与导出需求)
13. [非功能性要求](#13-非功能性要求)
14. [完整事件优先级清单](#14-完整事件优先级清单)
15. [验收标准](#15-验收标准)
16. [边界约定](#16-边界约定)
17. [开放问题](#17-开放问题)

---

## 1. 背景与目标

### 1.1 为什么需要增强 AI Agent 会话记录能力

Numina 是一个以家庭为租户单位的资产管理系统，已基于 DeerFlow 2.0 框架实现了 AI 问答（chat）、资产体检报告（report）、负债分析（liability）等多项 Agent 能力。

当前系统的会话记录存在以下局限：

- **审计日志（`agent-audit.log`）** 仅记录每次调用的摘要（截断至 200 字符），不保留完整对话内容，无法用于回放或恢复。
- **DeerFlow Checkpointer（SQLite）** 保存 LangGraph 状态快照，适合多轮对话的状态恢复，但不是面向业务层的可读事件流，且 Numina 层尚未暴露任何查询接口。
- **DeerFlow RunJournal（JSONL）** 已在 harness 内部实现了 JSONL 事件记录，但路径固定为 `.deer-flow/threads/{thread_id}/runs/{run_id}.jsonl`，与 Numina
的家庭租户体系完全解耦，无法按家庭隔离、无法被 Numina 业务层直接消费。
- **前端无法获取历史会话**：没有会话列表 API，用户刷新页面后历史对话丢失。

### 1.2 为什么仅靠数据库存储不够

数据库（SQLite/Postgres）适合结构化查询和事务保证，但对于 AI Agent 会话场景存在以下不足：

| 维度 | 数据库存储 | JSONL 文件存储 |
|------|-----------|---------------|
| 流式写入 | 需要事务，延迟高 | 追加写入，延迟极低 |
| 部分读取 | 需要 OFFSET/LIMIT | 按行流式读取，无需全量加载 |
| 调试可读性 | 需要 SQL 工具 | 直接 `cat` / `jq` 可读 |
| 迁移/备份 | 需要 dump 工具 | 直接复制文件 |
| 长会话大文件 | 单行 BLOB 膨胀 | 每行独立，天然分片 |
| 离线分析 | 需要数据库连接 | 标准文件工具即可 |

两者互补：**数据库作为索引层**（会话元数据、状态、检索），**JSONL 作为事件明细层**（完整事件流、可回放）。

### 1.3 为什么采用类似 Claude Code 的 JSONL 会话记录方式

Claude Code 的会话记录设计经过大规模生产验证，其核心原则适用于本场景：

- **每会话一文件**：文件即会话边界，天然隔离，无需跨文件 JOIN。
- **每行一事件**：每行是完整 JSON 对象，支持流式读取，单行损坏不影响其他行。
- **追加写入**：无锁竞争，写入性能接近磁盘顺序写入上限。
- **不覆盖历史**：所有变更（编辑、重试、压缩）通过新增事件表达，历史状态永久可查。

### 1.4 设计原则说明

| 原则 | 理由 |
|------|------|
| 每次会话一个 JSONL 文件 | 文件即会话边界，隔离清晰，便于按会话归档和清理 |
| 每行一个独立事件 | 支持流式读取；单行 JSON 解析失败不影响其他行；便于 `grep`/`jq` 分析 |
| 追加写入 | 无需加锁，写入性能高；与流式输出天然匹配（token 逐个到达） |
| 不覆盖历史状态 | 保留完整操作历史，支持审计；避免并发写入冲突；便于 debug 回放 |
| 数据库作索引，JSONL 作明细 | 数据库提供快速检索和状态查询；JSONL 提供完整事件流和可读性 |

---

## 2. 现状分析

### 2.1 现有会话记录机制全景

请求入口
    │
    ├── routers/chat.py          X-Thread-Id header → effective_thread_id
    │
    ├── services/orchestrator.py
    │     ├── AuditLogger        → logs/agent-audit.log（KV 文本，摘要截断200字）
    │     └── DeerFlowAdapter    → thread_id 传入 harness
    │
    └── vendor/deerflow-harness/
          ├── Checkpointer       → /app/data/deerflow-checkpoints.db（LangGraph 状态）
          ├── RunJournal         → .deer-flow/threads/{thread_id}/runs/{run_id}.jsonl
          └── ThreadMetaRepo     → ORM 表 threads_meta（未被 Numina 暴露）

### 2.2 现有 DeerFlow JSONL 实现（`JsonlRunEventStore`）

DeerFlow harness 已实现 `JsonlRunEventStore`，路径为：

.deer-flow/
    threads/
      {thread_id}/
        runs/
          {run_id}.jsonl

每行记录格式：

```json
{
    "thread_id": "abc-123",
    "run_id": "run-456",
    "event_type": "llm.ai.response",
    "category": "message",
    "content": { "..." },
    "metadata": { "caller": "lead_agent", "usage": {}, "latency_ms": 342 },
    "seq": 5,
    "created_at": "2026-05-10T08:30:00.123Z"
}

支持的事件类型：run.start, run.end, run.error, llm.human.input, llm.ai.response, llm.tool.result, llm.error, middleware:{tag}

关键问题：此路径与 Numina 的 family_id 租户体系完全无关，无法按家庭隔离，也无法被 Numina 业务层直接消费。

2.3 现有 StreamEvent（NDJSON 流协议）

services/stream_events.py 的 EventStreamBuilder 已定义了面向前端的 NDJSON 事件协议：

phase.connecting / phase.thinking / phase.answering
token.stream
tool.call / tool.result
capability.end / capability.error

这是前端实时消费的协议，不是持久化格式。两者需要统一映射。

2.4 SPEC-AI-HARNESS.md 中的相关设计

现有规格文档已提到"复用 AIChatSession JSONL 机制"，说明项目已有 AIChatSession 模型和 ChatSessionService（位于 backend），但 agent 层尚未与之集成。

---

## 3. 差距分析

┌─────────────────────┬────────────────────────────────────────────────────┬──────────────────────────────────────┬────────────────────────────────────────┐
│        能力         │                        现状                        │                 目标                 │                  差距                  │
├─────────────────────┼────────────────────────────────────────────────────┼──────────────────────────────────────┼────────────────────────────────────────┤
│ 会话事件持久化      │ DeerFlow 内部 JSONL，路径无租户隔离                │ 按 family_id 隔离的 JSONL 文件       │ 需要在 Numina 层建立映射或扩展路径策略 │
├─────────────────────┼────────────────────────────────────────────────────┼──────────────────────────────────────┼────────────────────────────────────────┤
│ 会话列表 API        │ 无（harness 有 list_threads() 但未暴露）           │ GET /sessions 返回家庭会话列表       │ 需要新增路由 + 复用 harness 能力       │
├─────────────────────┼────────────────────────────────────────────────────┼──────────────────────────────────────┼────────────────────────────────────────┤
│ 会话历史查询 API    │ 无                                                 │ GET /sessions/{id}/events 返回事件流 │ 需要新增路由 + JSONL 读取              │
├─────────────────────┼────────────────────────────────────────────────────┼──────────────────────────────────────┼────────────────────────────────────────┤
│ 前端会话恢复        │ 无（刷新丢失）                                     │ 从 JSONL 恢复历史消息                │ 需要前端 + API 协同                    │
├─────────────────────┼────────────────────────────────────────────────────┼──────────────────────────────────────┼────────────────────────────────────────┤
│ 租户隔离            │ 无（thread_id 无 family 前缀）                     │ 文件路径包含 family_id               │ 需要路径策略变更                       │
├─────────────────────┼────────────────────────────────────────────────────┼──────────────────────────────────────┼────────────────────────────────────────┤
│ 事件字段统一        │ DeerFlow 内部字段 vs Numina StreamEvent 字段不一致 │ 统一通用事件字段                     │ 需要定义 Numina 层事件 schema          │
├─────────────────────┼────────────────────────────────────────────────────┼──────────────────────────────────────┼────────────────────────────────────────┤
│ thinking 内容持久化 │ [THINK] 前缀字符串，可能丢失                       │ thinking 内容作为独立事件类型持久化  │ 需要在 orchestrator 层捕获并写入       │
├─────────────────────┼────────────────────────────────────────────────────┼──────────────────────────────────────┼────────────────────────────────────────┤
│ 审计日志升级        │ KV 文本，摘要截断                                  │ 结构化 JSONL，完整内容               │ 可选：升级 audit_logger 输出格式       │
└─────────────────────┴────────────────────────────────────────────────────┴──────────────────────────────────────┴────────────────────────────────────────┘

---

## 4. 功能范围

### 4.1 本期范围（MVP）

- F1：定义 Numina 层 JSONL 会话事件 schema（通用字段 + 事件类型目录）
- F2：在 agent 层实现 SessionJournalService，在 stream_dispatch_events 流程中写入 JSONL
- F3：文件路径按 family_id 隔离，格式为 data/sessions/{family_id}/{session_id}.jsonl
- F4：新增 GET /sessions API（agent 层），返回家庭会话列表（复用 DeerFlow list_threads()）
- F5：新增 GET /sessions/{session_id}/events API，流式返回 JSONL 事件
- F6：session_id 与 thread_id 对齐，确保 DeerFlow checkpointer 和 Numina JSONL 使用同一 ID

### 4.2 本期不包含

- 前端会话历史 UI（由前端团队另行排期）
- JSONL 文件压缩/归档策略（后续迭代）
- 跨家庭会话搜索
- 会话删除 API（需要额外的权限设计）
- 消息编辑/删除/反馈事件（后续迭代）
- 技能调用与多步骤 Agent 执行轨迹（后续迭代）
- 导出功能（后续迭代）

---

## 5. 数据库与 JSONL 分工

两层存储互补，各司其职。数据库是**索引层**，JSONL 是**事件明细层**。

### 5.1 数据库负责的内容

数据库会话表（建议命名 `ai_sessions`）应包含以下字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| `session_id` | string PK | 会话唯一 ID，与 DeerFlow thread_id 一致 |
| `family_id` | string | 家庭租户 ID，所有查询必须带此条件 |
| `user_id` | string | 发起会话的用户 ID |
| `capability` | string | Agent 能力类型（chat / report / liability 等） |
| `agent_type` | string | deerflow / fallback |
| `title` | string | 当前有效会话标题（AI 生成或用户自定义） |
| `status` | string | active / completed / error / archived |
| `jsonl_path` | string | JSONL 文件相对路径，用于定位事件文件 |
| `last_message_summary` | string | 最后一条消息摘要（≤200字），用于列表展示 |
| `last_model` | string | 最后一次调用的模型名称 |
| `total_turns` | integer | 累计对话轮次 |
| `total_tokens` | integer | 累计 token 用量 |
| `is_compressed` | boolean | 是否已发生过会话压缩 |
| `is_archived` | boolean | 是否已归档 |
| `has_attachments` | boolean | 是否包含附件（用于筛选） |
| `created_at` | datetime | 会话创建时间 |
| `updated_at` | datetime | 最后更新时间 |

### 5.2 JSONL 文件负责的内容

JSONL 文件保存完整事件流，包括但不限于：

- 用户消息事件（含完整内容）
- Assistant 回复事件（含完整内容）
- 流式输出增量事件
- AI 思考过程事件
- 工具调用事件（含参数摘要、结果摘要）
- 技能调用事件
- 附件上传与处理事件
- 图片上传与分析事件
- 引用与上下文事件
- 会话标题生成/更新事件
- 会话压缩摘要事件
- 消息编辑/删除/反馈事件
- 系统事件（策略拒绝、降级、PII 脱敏）
- 错误事件

### 5.3 为什么数据库不应保存完整事件明细

- **性能**：完整对话内容可能达到数十 KB 甚至数百 KB，存入数据库单行会导致 BLOB 膨胀，影响索引和查询性能。
- **写入模式不匹配**：流式输出期间 token 逐个到达，数据库事务写入延迟远高于文件追加写入。
- **可读性**：数据库内容需要 SQL 工具才能查看，JSONL 文件可直接用 `cat`/`jq` 分析，调试效率更高。
- **扩展性**：新增事件类型只需在 JSONL 中追加，不需要修改数据库 schema。

### 5.4 为什么 JSONL 不能完全替代数据库

- **查询能力**：JSONL 不支持按家庭、用户、时间范围、标题等条件快速检索，必须全量扫描文件。
- **权限控制**：数据库可以在 SQL 层面强制 `family_id` 隔离，文件系统无法做到同等级别的访问控制。
- **列表展示**：会话列表需要快速返回标题、摘要、状态等元数据，从文件系统扫描效率低。
- **事务保证**：会话状态变更（归档、删除）需要原子操作，文件系统无法提供。

### 5.5 两层协作流程

```
用户查询会话列表
    → 查询数据库 ai_sessions（按 family_id 过滤）
    → 返回列表（session_id, title, status, created_at, last_message_summary）

用户点击某个会话
    → 从数据库读取 jsonl_path
    → 读取对应 JSONL 文件
    → 过滤 visibility=public 的事件
    → 格式化展示给用户

用户接续会话继续提问
    → 从数据库确认 session_id 归属当前 family_id（权限校验）
    → 读取 JSONL 文件构建模型上下文（使用压缩摘要 + 最近 N 轮）
    → 新事件追加写入同一 JSONL 文件
    → 更新数据库 updated_at、last_message_summary、total_turns
```

---

## 6. 会话 JSONL 文件要求

┌──────────────────┬────────────────────────────────────────────┬────────────────────────────────────────────┐
│       要求       │                    说明                    │                  实现方式                  │
├──────────────────┼────────────────────────────────────────────┼────────────────────────────────────────────┤
│ 一个会话一个文件 │ 每次新 Agent 会话生成一个独立 .jsonl 文件  │ 文件名 = {session_id}.jsonl                │
├──────────────────┼────────────────────────────────────────────┼────────────────────────────────────────────┤
│ 一行一个事件     │ 每行是完整 JSON 对象，行末 \n 分隔         │ json.dumps(...) + "\n"                     │
├──────────────────┼────────────────────────────────────────────┼────────────────────────────────────────────┤
│ 追加写入         │ 新事件追加到文件末尾，不修改已有行         │ open(path, "a")                            │
├──────────────────┼────────────────────────────────────────────┼────────────────────────────────────────────┤
│ 不覆盖历史       │ 编辑、删除、压缩、重试都通过新增事件表达   │ 事件类型 session.summary、message.retry 等 │
├──────────────────┼────────────────────────────────────────────┼────────────────────────────────────────────┤
│ 可流式读取       │ 支持长会话、大文件和部分加载               │ 按行迭代，无需全量加载到内存               │
├──────────────────┼────────────────────────────────────────────┼────────────────────────────────────────────┤
│ 可恢复           │ 能从文件恢复完整会话上下文                 │ session.start 事件包含完整元数据           │
├──────────────────┼────────────────────────────────────────────┼────────────────────────────────────────────┤
│ 可扩展           │ 支持新增事件类型，旧版本读取器忽略未知类型 │ event_type 字段 + 版本号                   │
├──────────────────┼────────────────────────────────────────────┼────────────────────────────────────────────┤
│ 可审计           │ 保留关键操作历史，含 PII 脱敏标记          │ 所有事件含 family_id、user_id、timestamp   │
├──────────────────┼────────────────────────────────────────────┼────────────────────────────────────────────┤
│ 租户隔离         │ 文件路径必须包含家庭租户边界               │ 路径前缀 data/sessions/{family_id}/        │
├──────────────────┼────────────────────────────────────────────┼────────────────────────────────────────────┤
│ 工作空间适配     │ 会话文件归属家庭工作空间                   │ 见第 8 节文件路径设计                      │
└──────────────────┴────────────────────────────────────────────┴────────────────────────────────────────────┘

### 6.1 文件归属原则

- 会话 JSONL 文件属于家庭工作空间，路径包含 family_id，家庭成员均可读（按角色控制）。
- 用户上传的个人文件仍位于个人工作空间（uploads/{user_id}/），不受本功能影响。
- JSONL 中只保存附件的引用（file_id、file_path、内容摘要），不直接复制大文件内容到 JSONL。
- 图片、文档等二进制内容通过 attachment.ref 事件类型引用，实际文件由 DeerFlow uploads 管理。

---

## 7. 通用事件字段设计

所有 JSONL 事件共用以下字段：

┌─────────────────┬─────────┬──────────┬────────────────────────────────────────┬──────────────────────────────────────────┐
│      字段       │  类型   │ 是否必填 │                  说明                  │                 典型取值                 │
├─────────────────┼─────────┼──────────┼────────────────────────────────────────┼──────────────────────────────────────────┤
│ event_id        │ string  │ 是       │ 当前事件唯一 ID                        │ UUID v4                                  │
├─────────────────┼─────────┼──────────┼────────────────────────────────────────┼──────────────────────────────────────────┤
│ session_id      │ string  │ 是       │ 所属会话 ID（= DeerFlow thread_id）    │ sess-20260510-a1b2c3d4                   │
├─────────────────┼─────────┼──────────┼────────────────────────────────────────┼──────────────────────────────────────────┤
│ family_id       │ string  │ 是       │ 家庭租户 ID                            │ UUID v4                                  │
├─────────────────┼─────────┼──────────┼────────────────────────────────────────┼──────────────────────────────────────────┤
│ user_id         │ string  │ 否       │ 触发事件的用户 ID（系统事件可为 null） │ UUID v4                                  │
├─────────────────┼─────────┼──────────┼────────────────────────────────────────┼──────────────────────────────────────────┤
│ agent_type      │ string  │ 是       │ Agent 类型                             │ "deerflow" / "fallback"                  │
├─────────────────┼─────────┼──────────┼────────────────────────────────────────┼──────────────────────────────────────────┤
│ event_type      │ string  │ 是       │ 事件类型（见第 7 节）                  │ "message.user"                           │
├─────────────────┼─────────┼──────────┼────────────────────────────────────────┼──────────────────────────────────────────┤
│ timestamp       │ string  │ 是       │ 事件发生时间，ISO 8601 UTC             │ "2026-05-10T08:30:00.123Z"               │
├─────────────────┼─────────┼──────────┼────────────────────────────────────────┼──────────────────────────────────────────┤
│ parent_event_id │ string  │ 否       │ 父事件 ID，用于建立事件树              │ 上一条消息事件的 event_id                │
├─────────────────┼─────────┼──────────┼────────────────────────────────────────┼──────────────────────────────────────────┤
│ turn            │ integer │ 否       │ 所属对话轮次（从 1 开始）              │ 3                                        │
├─────────────────┼─────────┼──────────┼────────────────────────────────────────┼──────────────────────────────────────────┤
│ role            │ string  │ 是       │ 事件发起方                             │ "user" / "assistant" / "system" / "tool" │
├─────────────────┼─────────┼──────────┼────────────────────────────────────────┼──────────────────────────────────────────┤
│ provider        │ string  │ 否       │ 模型供应商                             │ "anthropic" / "openai" / "custom"        │
├─────────────────┼─────────┼──────────┼────────────────────────────────────────┼──────────────────────────────────────────┤
│ model           │ string  │ 否       │ 模型名称（当前家庭配置模型）           │ "claude-opus-4-7"                        │
├─────────────────┼─────────┼──────────┼────────────────────────────────────────┼──────────────────────────────────────────┤
│ schema_version  │ string  │ 是       │ 事件结构版本                           │ "1.0"                                    │
├─────────────────┼─────────┼──────────┼────────────────────────────────────────┼──────────────────────────────────────────┤
│ visibility      │ string  │ 否       │ 可见性控制                             │ "public" / "internal" / "debug"          │
├─────────────────┼─────────┼──────────┼────────────────────────────────────────┼──────────────────────────────────────────┤
│ metadata        │ object  │ 否       │ 扩展元数据，不影响核心字段             │ {"capability": "report"}                 │
└─────────────────┴─────────┴──────────┴────────────────────────────────────────┴──────────────────────────────────────────┘

### 7.1 字段用途说明

用于恢复会话的字段：
- session_id：定位会话文件
- turn：重建对话轮次结构
- parent_event_id：重建事件树（如 thinking → answer 的父子关系）
- role：区分用户输入和 AI 输出
- schema_version：处理版本兼容性

用于权限隔离的字段：
- family_id：文件路径隔离 + API 层鉴权（必须与请求 header X-Family-Id 一致）
- user_id：记录操作人，支持家庭内成员级审计
- visibility：internal/debug 事件不暴露给普通用户

用于模型调用追踪的字段：
- provider + model：记录每次调用使用的模型，支持跨模型配置变更的历史追溯
- agent_type：区分 deerflow 路径和 fallback 路径

为什么需要统一事件字段：
- 不同 capability（chat、report、liability 等）共用同一读取器，字段必须一致
- 前端会话恢复逻辑只需处理一种 schema
- 审计和合规查询可以跨 capability 统一处理

---

## 8. 事件类型目录

### 8.1 会话生命周期事件

┌─────────────────────────┬────────────────────────────────────────────┬──────────────────────────────────────────────────────────────┐
│         事件类型        │                  触发时机                  │                     关键 payload 字段                        │
├─────────────────────────┼────────────────────────────────────────────┼──────────────────────────────────────────────────────────────┤
│ session.start           │ 会话首次创建时                             │ capability, thread_id, ai_config_snapshot                    │
├─────────────────────────┼────────────────────────────────────────────┼──────────────────────────────────────────────────────────────┤
│ session.resume          │ 已有会话被重新连接时                       │ resumed_at, last_event_id                                    │
├─────────────────────────┼────────────────────────────────────────────┼──────────────────────────────────────────────────────────────┤
│ session.end             │ 会话正常结束时                             │ total_turns, total_tokens, duration_ms                       │
├─────────────────────────┼────────────────────────────────────────────┼──────────────────────────────────────────────────────────────┤
│ session.error           │ 会话异常终止时                             │ error_type, error_message                                    │
├─────────────────────────┼────────────────────────────────────────────┼──────────────────────────────────────────────────────────────┤
│ session.summary         │ 对话历史被压缩时（DeerFlow summarization） │ summary_text, compressed_turn_start, compressed_turn_end     │
├─────────────────────────┼────────────────────────────────────────────┼──────────────────────────────────────────────────────────────┤
│ session.title_generated │ AI 自动生成会话标题时                      │ title, generated_by（模型名）                                │
├─────────────────────────┼────────────────────────────────────────────┼──────────────────────────────────────────────────────────────┤
│ session.title_updated   │ 用户手动修改会话标题时                     │ title, previous_title, updated_by（user_id）                 │
├─────────────────────────┼────────────────────────────────────────────┼──────────────────────────────────────────────────────────────┤
│ session.archived        │ 会话被归档时（软删除）                     │ archived_by, reason                                          │
├─────────────────────────┼────────────────────────────────────────────┼──────────────────────────────────────────────────────────────┤
│ session.size_warning    │ 文件超过 10MB 时                           │ current_size_bytes                                           │
└─────────────────────────┴────────────────────────────────────────────┴──────────────────────────────────────────────────────────────┘

**说明：**
- `session.start` 的 `ai_config_snapshot` 字段记录会话创建时家庭使用的模型配置快照（provider、model_id、temperature 等），确保历史会话可追溯，不受后续家庭模型配置变更影响。
- `session.title_generated` 和 `session.title_updated` 均追加到 JSONL，当前有效标题同步更新到数据库 `ai_sessions.title` 字段，用于列表展示。用户标题优先于 AI 生成标题。

### 8.2 消息事件

┌──────────────────────────┬──────────────────────────────────────────┬──────────────────────────────────────────────────────────────┐
│         事件类型         │                 触发时机                 │                      关键 payload 字段                       │
├──────────────────────────┼──────────────────────────────────────────┼──────────────────────────────────────────────────────────────┤
│ message.user             │ 用户发送消息时                           │ content, capability, free_text                               │
├──────────────────────────┼──────────────────────────────────────────┼──────────────────────────────────────────────────────────────┤
│ message.assistant        │ AI 完整回复生成后                        │ content, tokens_used, latency_ms                             │
├──────────────────────────┼──────────────────────────────────────────┼──────────────────────────────────────────────────────────────┤
│ message.thinking         │ AI thinking 内容（extended thinking）    │ content, thinking_budget, tokens_used                        │
├──────────────────────────┼──────────────────────────────────────────┼──────────────────────────────────────────────────────────────┤
│ message.retry            │ 用户重试某条消息时                       │ original_event_id, retry_reason                              │
├──────────────────────────┼──────────────────────────────────────────┼──────────────────────────────────────────────────────────────┤
│ message.edited           │ 用户编辑已发送消息时（后续迭代）         │ original_event_id, new_content, edit_reason                  │
├──────────────────────────┼──────────────────────────────────────────┼──────────────────────────────────────────────────────────────┤
│ message.deleted          │ 用户删除消息时（后续迭代）               │ original_event_id, deleted_by                                │
├──────────────────────────┼──────────────────────────────────────────┼──────────────────────────────────────────────────────────────┤
│ message.feedback         │ 用户对 AI 回复点赞/点踩/反馈（后续迭代）│ target_event_id, feedback_type（like/dislike/report）, note  │
└──────────────────────────┴──────────────────────────────────────────┴──────────────────────────────────────────────────────────────┘

**说明：**
- `message.thinking` 的 `visibility` 默认为 `"debug"`，不暴露给普通用户。如需展示思考摘要，应单独生成 `visibility: "public"` 的摘要字段，而非直接暴露原始思考内容。
- `message.edited` 和 `message.deleted` 均为追加事件，不修改原始消息行。读取器在构建展示视图时，应以最新的编辑/删除事件为准。
- 导出时默认不包含 `message.thinking` 内容；审计视图需要额外权限才能查看。

### 8.3 模型生成过程事件

| 事件类型 | 触发时机 | 关键 payload 字段 | visibility |
|---------|---------|-----------------|-----------|
| `generation.started` | Assistant 开始生成时 | parent_event_id（对应 message.user） | debug |
| `generation.delta` | 流式输出每个 token 增量（后续迭代） | delta_text, seq | debug |
| `generation.completed` | 生成正常结束时 | tokens_used, latency_ms, finish_reason | internal |
| `generation.failed` | 生成异常中断时 | error_type, error_message, tokens_used | internal |

**说明：**
- `generation.delta` 写入量大（每个 token 一行），MVP 阶段默认不写入，后续迭代按需开启。
- `generation.started` / `generation.completed` 用于计算延迟和 token 用量，写入 JSONL 但默认不展示给用户。
- 所有生成过程事件通过 `parent_event_id` 关联到触发它的 `message.user` 事件。

### 8.4 工具调用事件

┌─────────────┬──────────────────┬──────────────────────────────────────────────────────────────┐
│  事件类型   │     触发时机     │                      关键 payload 字段                       │
├─────────────┼──────────────────┼──────────────────────────────────────────────────────────────┤
│ tool.call   │ Agent 调用工具前 │ tool_name, tool_display_name, arguments_summary              │
├─────────────┼──────────────────┼──────────────────────────────────────────────────────────────┤
│ tool.result │ 工具调用返回后   │ tool_call_event_id, success, data_summary, execution_time_ms │
├─────────────┼──────────────────┼──────────────────────────────────────────────────────────────┤
│ tool.error  │ 工具调用失败时   │ tool_call_event_id, error_type, error_message                │
└─────────────┴──────────────────┴──────────────────────────────────────────────────────────────┘

**说明：**
- `arguments_summary` 保存参数摘要而非完整参数，避免记录敏感信息明文（如 API key、用户资产金额等）。
- `data_summary` 保存结果摘要（≤500字），完整结果不写入 JSONL。
- 工具调用事件的 `visibility` 默认为 `"internal"`，用户界面可选择性展示工具调用状态。

### 8.5 技能调用与 Agent 步骤事件（后续迭代）

| 事件类型 | 触发时机 | 关键 payload 字段 |
|---------|---------|-----------------|
| `skill.call` | Agent 调用技能前 | skill_name, skill_display_name, arguments_summary |
| `skill.result` | 技能调用返回后 | skill_call_event_id, success, data_summary, execution_time_ms |
| `skill.error` | 技能调用失败时 | skill_call_event_id, error_type, error_message |
| `agent.step_started` | 多步骤 Agent 开始某步骤时 | step_index, step_name, parent_event_id |
| `agent.step_completed` | 步骤完成时 | step_index, result_summary, execution_time_ms |
| `agent.step_failed` | 步骤失败时 | step_index, error_type, error_message |

**说明：**
- 技能调用和 Agent 步骤事件为后续迭代内容，MVP 阶段不要求实现。
- 多步骤 Agent 执行轨迹通过 `parent_event_id` 串联，形成执行树。

### 8.6 流式阶段事件

┌──────────────────┬──────────────────────┬───────────────────┐
│     事件类型     │       触发时机       │ 关键 payload 字段 │
├──────────────────┼──────────────────────┼───────────────────┤
│ phase.connecting │ 开始建立连接时       │ —                 │
├──────────────────┼──────────────────────┼───────────────────┤
│ phase.thinking   │ 进入 thinking 阶段时 │ —                 │
├──────────────────┼──────────────────────┼───────────────────┤
│ phase.answering  │ 进入回答阶段时       │ —                 │
└──────────────────┴──────────────────────┴───────────────────┘

`phase.*` 事件的 `visibility` 为 `"debug"`，不用于会话恢复。根据开放问题 Q3 的建议，写入 JSONL 但 API 默认过滤，需 `?include_debug=true` 参数才返回。

### 8.7 附件与图片事件

| 事件类型 | 触发时机 | 关键 payload 字段 | visibility |
|---------|---------|-----------------|-----------|
| `attachment.uploaded` | 用户上传附件时 | file_id, file_name, mime_type, file_size_bytes, file_hash, owner_user_id, workspace_path | public |
| `attachment.processed` | 附件解析完成时（后续迭代） | file_id, parse_result_ref, ocr_result_ref, page_count | internal |
| `attachment.failed` | 附件处理失败时（后续迭代） | file_id, error_type, error_message | internal |
| `image.uploaded` | 用户上传图片时 | file_id, file_name, mime_type, file_size_bytes, file_hash, owner_user_id, workspace_path | public |
| `image.analyzed` | 图片视觉分析完成时（后续迭代） | file_id, analysis_result_ref, analysis_model | internal |
| `attachment.ref` | 会话中引用已有文件时 | file_id, file_name, file_type, owner_user_id, content_summary | public |

**说明：**
- JSONL 中不存储文件二进制内容，只存储文件引用（file_id）、元数据和摘要。
- `workspace_path` 记录文件在家庭/个人工作空间中的相对路径，用于接续会话时恢复附件上下文。
- 附件或图片缺失时（文件已删除），读取器应根据 JSONL 中的元数据展示占位符（文件名 + 缺失提示），而非报错。
- `file_hash` 用于去重检测，不用于安全校验。

### 8.8 引用与上下文事件（后续迭代）

| 事件类型 | 触发时机 | 关键 payload 字段 |
|---------|---------|-----------------|
| `reference.message` | 用户引用历史消息时 | source_event_id, quoted_text_snapshot, quote_range |
| `reference.file` | 用户引用附件内容时 | file_id, file_name, quoted_content_snapshot |
| `reference.image` | 用户引用图片时 | file_id, file_name, region（可选，图片局部区域） |
| `context.selected` | 用户选择特定上下文（如资产数据）时 | context_type, context_summary |

**说明：**
- 引用事件必须保存被引用内容的**文本快照**（`quoted_text_snapshot`），而不仅是源事件 ID。原因：被引用的消息或文件后续可能被编辑或删除，仅保存 ID 会导致历史引用无法追溯。
- 引用关系（`reference.*`）与父子消息关系（`parent_event_id`）的区别：`parent_event_id` 表示事件的生成依赖关系（如 thinking 依赖 user message），引用关系表示用户主动选择的上下文关联。

### 8.9 系统事件

┌──────────────────────┬─────────────────────────────────┬───────────────────────────────────────┐
│       事件类型       │            触发时机             │           关键 payload 字段           │
├──────────────────────┼─────────────────────────────────┼───────────────────────────────────────┤
│ system.policy_denied │ 策略检查拒绝请求时              │ capability, reason                    │
├──────────────────────┼─────────────────────────────────┼───────────────────────────────────────┤
│ system.fallback      │ DeerFlow 失败降级到 fallback 时 │ original_error, fallback_path         │
├──────────────────────┼─────────────────────────────────┼───────────────────────────────────────┤
│ system.pii_redacted  │ PII 脱敏发生时                  │ fields_redacted（字段名列表，不含值） │
└──────────────────────┴─────────────────────────────────┴───────────────────────────────────────┘

---

## 9. 文件路径与租户隔离

### 9.1 推荐路径结构

```
data/
    sessions/
      {family_id}/
        {session_id}.jsonl
        {session_id}.jsonl
      {family_id}/
        {session_id}.jsonl
```

示例：

```
data/sessions/fam-abc123/sess-20260510-xyz789.jsonl
data/sessions/fam-abc123/sess-20260509-def456.jsonl
data/sessions/fam-def456/sess-20260510-ghi012.jsonl
```

### 9.2 session_id 生成规则

```
session_id = "sess-{YYYYMMDD}-{uuid8}"
示例：sess-20260510-a1b2c3d4
```

- date：YYYYMMDD 格式，便于按日期排序和清理
- uuid8：UUID v4 的前 8 位十六进制字符，保证唯一性
- session_id 同时作为 DeerFlow 的 thread_id，确保两套系统使用同一 ID

### 9.3 路径安全要求

- family_id 和 session_id 必须通过正则校验：`^[A-Za-z0-9_\-]+$`（复用 DeerFlow `_validate_id` 逻辑）
- 禁止路径穿越（`../`）
- 文件路径在 API 层由服务端构造，不接受客户端传入的路径字符串

### 9.4 与 DeerFlow JSONL 的关系

| 维度 | DeerFlow JsonlRunEventStore | Numina SessionJournalService |
|-----|---------------------------|------------------------------|
| 路径 | `.deer-flow/threads/{thread_id}/runs/{run_id}.jsonl` | `data/sessions/{family_id}/{session_id}.jsonl` |
| 事件 schema | DeerFlow 内部格式（run_id, seq, category） | Numina 业务格式（family_id, turn, role） |
| 写入时机 | LangChain 回调（harness 内部） | Orchestrator 层（Numina 边界） |
| 读取方 | DeerFlow 内部（list_messages, list_events） | Numina API 层（/sessions/{id}/events） |
| 用途 | LLM trace、token 统计、harness 调试 | 业务会话恢复、前端历史展示、合规审计 |

两套 JSONL 并存，互补不替代：DeerFlow JSONL 是 harness 内部 trace，Numina JSONL 是业务层事件日志。

---

## 10. 与现有系统的集成策略

### 10.1 优先复用 DeerFlow 已有能力

按照 agent/CLAUDE.md 的原则：优先复用 DeerFlow Harness 能力，只在确认需求超出 harness 边界后才引入新方案。

┌───────────────────────────────┬────────────────────────────────────────────────────────────────────────────────────────┐
│         DeerFlow 能力         │                                        复用方式                                        │
├───────────────────────────────┼────────────────────────────────────────────────────────────────────────────────────────┤
│ JsonlRunEventStore            │ 复用其追加写入、流式读取、路径安全校验逻辑，在 Numina 层扩展路径策略（加入 family_id） │
├───────────────────────────────┼────────────────────────────────────────────────────────────────────────────────────────┤
│ ThreadMetaRepository          │ 复用 list_threads() 和 get_thread() 作为会话列表 API 的数据源                          │
├───────────────────────────────┼────────────────────────────────────────────────────────────────────────────────────────┤
│ DeerFlowClient.list_threads() │ 直接调用，通过 family_adapter_cache 获取对应家庭的 client                              │
├───────────────────────────────┼────────────────────────────────────────────────────────────────────────────────────────┤
│ RunJournal 事件类型           │ 参考其事件类型命名（llm.human.input, llm.ai.response）设计 Numina 事件类型             │
├───────────────────────────────┼────────────────────────────────────────────────────────────────────────────────────────┤
│ session_id = thread_id        │ 统一 ID，避免两套系统 ID 不一致                                                        │
└───────────────────────────────┴────────────────────────────────────────────────────────────────────────────────────────┘

### 10.2 新增 SessionJournalService

在 agent/services/ 下新增 session_journal.py，职责：

1. 接收来自 orchestrator.stream_dispatch_events() 的 StreamEvent 对象
2. 将 StreamEvent 映射为 Numina JSONL 事件格式
3. 追加写入到 data/sessions/{family_id}/{session_id}.jsonl
4. 提供 list_sessions(family_id) 和 read_session_events(family_id, session_id) 方法

### 10.3 Orchestrator 集成点

stream_dispatch_events() 是最合适的集成点，因为：

- 它已经是 Numina 边界层（不在 harness 内部）
- 它已经处理了 PII 脱敏
- 它已经有 audit_id、family_id、user_id、capability 等上下文
- 它产出的 StreamEvent 已经是结构化事件

集成方式：在 _stream_dispatch_event_lines() 中，每 yield 一个 StreamEvent 时，同步追加写入 JSONL（`open(path, "a")`），不阻塞流式输出。采用同步写入而非 `asyncio.create_task()` 的原因：SSD 上文件 append 通常 < 1ms，远低于 5ms 预算；且 `asyncio.create_task()` 在 async generator 退出后 task 可能被 GC 取消，导致事件丢失。写入失败时静默捕获异常并写入 `agent-audit.log`，不影响主流程。

### 10.4 新增 API 路由

在 agent/routers/ 下新增 sessions.py：

GET  /sessions                     → 返回家庭会话列表（分页）
GET  /sessions/{session_id}        → 返回单个会话元数据
GET  /sessions/{session_id}/events → 流式返回会话 JSONL 事件

所有路由复用现有鉴权机制（X-Agent-Token + X-Family-Id）。

---

## 11. 会话恢复与接续会话

### 11.1 恢复流程

```
1. 用户查询会话列表
   → GET /sessions?family_id={fid}
   → 查询数据库 ai_sessions（按 family_id 过滤，按 updated_at 倒序）
   → 返回列表（session_id, title, capability, status, created_at, last_message_summary）

2. 用户点击某个会话
   → GET /sessions/{session_id}/events
   → 从数据库读取 jsonl_path，校验 family_id 归属
   → 按行读取 JSONL 文件
   → 过滤 visibility="public" 的事件
   → 按 turn + timestamp 排序，格式化返回

3. 用户接续会话继续提问
   → POST /chat（携带 X-Thread-Id: {session_id}）
   → 从数据库确认 session_id 归属当前 family_id（权限校验）
   → 读取 JSONL 文件构建模型上下文（见 §11.2）
   → 新事件追加写入同一 JSONL 文件
   → 更新数据库 updated_at、last_message_summary、total_turns
```

### 11.2 两种视图的区分

恢复会话时必须构建两种独立视图，不可混用：

| 视图 | 用途 | 包含事件 | 排除事件 |
|-----|------|---------|---------|
| **用户完整历史视图** | 前端展示，让用户看到完整对话历史 | `visibility="public"` 的所有事件，含压缩前的原始消息 | debug、internal 事件；原始 thinking 内容 |
| **模型上下文视图** | 构建发送给 LLM 的 messages 列表 | 最近 N 轮的 `message.user` + `message.assistant`；若有压缩，使用 `session.summary` 替代被压缩的轮次 | 工具调用摘要、phase 事件、系统事件、附件元数据 |

**关键原则：**
- 用户完整历史视图保留所有原始消息，压缩不删除历史。
- 模型上下文视图使用压缩摘要替代被压缩轮次，控制 token 用量。
- 两种视图均从同一 JSONL 文件读取，通过 `visibility` 和 `event_type` 过滤区分。

### 11.3 附件与图片上下文恢复

接续会话时，系统应根据 JSONL 中的 `attachment.uploaded` / `image.uploaded` 事件恢复附件上下文：

- 检查 `file_id` 对应的文件是否仍存在于工作空间。
- 若文件存在，将附件引用加入模型上下文（作为 file 类型消息）。
- 若文件已删除，在用户历史视图中展示占位符（文件名 + "文件已删除"提示），不报错，不阻断会话。

---

## 12. 搜索与导出需求

### 12.1 会话搜索能力（基于数据库）

| 搜索维度 | 实现方式 | MVP |
|---------|---------|-----|
| 按家庭查询 | `WHERE family_id = ?`（必须） | ✅ |
| 按用户查询 | `WHERE user_id = ?` | ✅ |
| 按 capability 筛选 | `WHERE capability = ?` | ✅ |
| 按会话标题搜索 | `WHERE title LIKE ?` | ✅ |
| 按时间范围筛选 | `WHERE created_at BETWEEN ? AND ?` | ✅ |
| 按模型筛选 | `WHERE last_model = ?` | 后续 |
| 按是否含附件筛选 | `WHERE has_attachments = true` | 后续 |
| 按是否发生错误筛选 | `WHERE status = 'error'` | 后续 |
| 按反馈状态筛选 | 需要单独 feedback 表 | 后续 |

### 12.2 导出能力（后续迭代）

| 导出格式 | 说明 | 默认包含 thinking |
|---------|------|-----------------|
| Markdown | 用户可读格式，含消息、工具调用摘要 | 否 |
| HTML | 带样式的富文本，含附件占位符 | 否 |
| JSON | 结构化事件列表，含所有 public 事件 | 否 |
| JSONL 原始 | 完整 JSONL 文件，含所有事件 | 是（需权限） |
| 脱敏版本 | 任意格式 + PII 脱敏处理 | 否 |

**导出时的处理规则：**
- 附件：导出文件引用和元数据，不导出二进制内容。
- 图片：导出图片引用，可选导出 base64（需用户确认，文件可能较大）。
- 压缩摘要：导出 `session.summary` 内容，标注"以下为历史摘要"。
- AI 思考过程：默认不导出；JSONL 原始格式导出时包含，需要额外权限。
- 用户不可见事件（internal/debug）：默认不导出；JSONL 原始格式导出时包含，需要额外权限。

---

## 13. 非功能性要求

┌──────────┬──────────────────────────────────────────────────────────────────────────────────────┐
│   维度   │                                         要求                                         │
├──────────┼──────────────────────────────────────────────────────────────────────────────────────┤
│ 写入延迟 │ JSONL 写入不得增加流式响应延迟超过 5ms（异步 fire-and-forget）                       │
├──────────┼──────────────────────────────────────────────────────────────────────────────────────┤
│ 文件大小 │ 单个会话文件超过 10MB 时，写入 `session.size_warning` 事件并记录告警日志；不压缩、不删除已有行。文件大小上限由运维层面的磁盘监控处理 │
├──────────┼──────────────────────────────────────────────────────────────────────────────────────┤
│ 读取性能 │ list_sessions 响应时间 < 200ms（基于文件系统目录扫描）                               │
├──────────┼──────────────────────────────────────────────────────────────────────────────────────┤
│ 容错性   │ JSONL 写入失败不得影响主流程（与 audit_logger 相同的静默失败策略）                   │
├──────────┼──────────────────────────────────────────────────────────────────────────────────────┤
│ PII 安全 │ 写入 JSONL 前必须经过 pii_redactor 处理；system.pii_redacted 事件记录脱敏字段名      │
├──────────┼──────────────────────────────────────────────────────────────────────────────────────┤
│ 租户隔离 │ API 层必须校验 X-Family-Id 与 session_id 对应的 family_id 一致                       │
├──────────┼──────────────────────────────────────────────────────────────────────────────────────┤
│ 磁盘清理 │ 超过 90 天的会话文件由定时任务（scheduler.py）清理；清理前写入 session.archived 事件 │
└──────────┴──────────────────────────────────────────────────────────────────────────────────────┘

| 维度 | 要求 |
|------|------|
| 写入延迟 | JSONL 写入不得增加流式响应延迟超过 5ms（同步追加写入，SSD append < 1ms） |
| 文件大小 | 单个会话文件超过 10MB 时，写入 `session.size_warning` 事件并记录告警日志；不压缩、不删除已有行 |
| 读取性能 | list_sessions 响应时间 < 200ms（基于数据库查询，不扫描文件系统） |
| 容错性 | JSONL 写入失败不得影响主流程（与 audit_logger 相同的静默失败策略） |
| PII 安全 | 写入 JSONL 前必须经过 pii_redactor 处理；system.pii_redacted 事件记录脱敏字段名 |
| 租户隔离 | API 层必须校验 X-Family-Id 与 session_id 对应的 family_id 一致 |
| 磁盘清理 | 超过 90 天的会话文件由定时任务（scheduler.py）清理；清理前写入 session.archived 事件 |
| 并发安全 | 同一会话的并发写入通过文件追加（O_APPEND）保证原子性，不引入额外锁 |

---

## 14. 完整事件优先级清单

### 14.1 MVP 必须支持

| 事件类型 | 触发时机 | 主要内容 | 用户可见 | 进入模型上下文 |
|---------|---------|---------|---------|--------------|
| `session.start` | 会话首次创建 | capability, ai_config_snapshot | 否 | 否 |
| `session.resume` | 已有会话重连 | resumed_at, last_event_id | 否 | 否 |
| `session.end` | 会话正常结束 | total_turns, total_tokens | 否 | 否 |
| `session.error` | 会话异常终止 | error_type, error_message | 是（错误提示） | 否 |
| `session.summary` | 对话历史压缩 | summary_text, 压缩范围 | 是（摘要标注） | 是（替代被压缩轮次） |
| `session.title_generated` | AI 自动生成标题 | title, generated_by | 否（同步到 DB） | 否 |
| `session.title_updated` | 用户修改标题 | title, previous_title | 否（同步到 DB） | 否 |
| `message.user` | 用户发送消息 | content, capability | 是 | 是 |
| `message.assistant` | AI 完整回复 | content, tokens_used, latency_ms | 是 | 是 |
| `message.thinking` | AI 思考内容 | content, thinking_budget | 否（debug） | 否 |
| `message.retry` | 用户重试消息 | original_event_id | 否 | 否 |
| `generation.started` | 开始生成 | parent_event_id | 否 | 否 |
| `generation.completed` | 生成完成 | tokens_used, latency_ms | 否 | 否 |
| `generation.failed` | 生成失败 | error_type, error_message | 是（错误提示） | 否 |
| `tool.call` | 工具调用前 | tool_name, arguments_summary | 是（可折叠） | 否 |
| `tool.result` | 工具调用返回 | success, data_summary | 是（可折叠） | 否 |
| `tool.error` | 工具调用失败 | error_type, error_message | 是 | 否 |
| `attachment.uploaded` | 附件上传 | file_id, file_name, mime_type, file_hash | 是 | 是（文件引用） |
| `image.uploaded` | 图片上传 | file_id, file_name, mime_type, file_hash | 是 | 是（图片引用） |
| `attachment.ref` | 会话中引用文件 | file_id, file_name, content_summary | 是 | 是 |
| `system.policy_denied` | 策略拒绝 | capability, reason | 是（提示） | 否 |
| `system.fallback` | DeerFlow 降级 | original_error, fallback_path | 否 | 否 |
| `system.pii_redacted` | PII 脱敏 | fields_redacted | 否（audit） | 否 |
| `phase.connecting` | 建立连接 | — | 否（debug） | 否 |
| `phase.thinking` | 进入 thinking | — | 否（debug） | 否 |
| `phase.answering` | 进入回答 | — | 否（debug） | 否 |

### 14.2 后续迭代支持

| 事件类型 | 触发时机 | 优先级 |
|---------|---------|-------|
| `generation.delta` | 流式 token 增量 | P2 |
| `message.edited` | 用户编辑消息 | P2 |
| `message.deleted` | 用户删除消息 | P2 |
| `message.feedback` | 用户点赞/点踩 | P2 |
| `attachment.processed` | 附件解析完成 | P2 |
| `attachment.failed` | 附件处理失败 | P2 |
| `image.analyzed` | 图片视觉分析 | P2 |
| `reference.message` | 引用历史消息 | P2 |
| `reference.file` | 引用附件内容 | P2 |
| `reference.image` | 引用图片 | P3 |
| `context.selected` | 选择上下文 | P3 |
| `skill.call` | 技能调用前 | P2 |
| `skill.result` | 技能调用返回 | P2 |
| `skill.error` | 技能调用失败 | P2 |
| `agent.step_started` | Agent 步骤开始 | P3 |
| `agent.step_completed` | Agent 步骤完成 | P3 |
| `agent.step_failed` | Agent 步骤失败 | P3 |
| `session.archived` | 会话归档 | P2 |
| `session.size_warning` | 文件超 10MB | P2 |

---

## 15. 验收标准

### 15.1 MVP 核心验收标准

| # | 场景 | 验收条件 |
|---|------|---------|
| AC-01 | 正常多轮 AI 问答 | 每轮对话后 JSONL 文件新增 `message.user` + `generation.started` + `message.assistant` + `generation.completed` 四条事件；turn 字段递增 |
| AC-02 | AI 资产负债建议 Agent | capability="liability" 的会话 JSONL 包含 `session.start`（含 ai_config_snapshot）、`message.user`、`tool.call`/`tool.result`、`message.assistant` |
| AC-03 | 流式输出会话 | 流式响应期间 JSONL 实时追加事件；流式响应延迟增加 < 5ms（与无 JSONL 写入对比） |
| AC-04 | 同步输出会话 | `generation.completed` 事件在 `message.assistant` 之后写入；两者 parent_event_id 均指向对应 `message.user` |
| AC-05 | 工具调用成功 | `tool.call` 事件包含 tool_name 和 arguments_summary；`tool.result` 包含 tool_call_event_id 和 data_summary；success=true |
| AC-06 | 工具调用失败 | `tool.error` 事件包含 tool_call_event_id、error_type、error_message；主流程继续，不中断会话 |
| AC-07 | 会话标题自动生成 | `session.title_generated` 事件写入 JSONL；数据库 ai_sessions.title 同步更新；GET /sessions 返回新标题 |
| AC-08 | 用户修改会话标题 | `session.title_updated` 事件写入 JSONL，包含 previous_title；数据库 title 更新；用户标题优先于 AI 标题 |
| AC-09 | 附件上传 | `attachment.uploaded` 事件包含 file_id、file_name、mime_type、file_size_bytes、file_hash、owner_user_id；JSONL 中无二进制内容 |
| AC-10 | 图片上传 | `image.uploaded` 事件字段同 AC-09；数据库 has_attachments=true |
| AC-11 | 长会话压缩 | `session.summary` 事件包含 summary_text、compressed_turn_start、compressed_turn_end；原始消息行不删除；数据库 is_compressed=true |
| AC-12 | 用户查询会话历史列表 | GET /sessions 按 family_id 过滤，返回 session_id、title、capability、status、created_at、last_message_summary；跨家庭访问返回 403 |
| AC-13 | 用户点击会话查看内容 | GET /sessions/{id}/events 返回 visibility="public" 的事件列表；按 turn+timestamp 排序；跨家庭访问返回 403 |
| AC-14 | 用户接续历史会话 | POST /chat 携带已有 session_id，新事件追加到同一 JSONL 文件；数据库 updated_at、total_turns 更新 |
| AC-15 | 附件缺失时恢复展示 | 接续会话时文件已删除，前端展示占位符（文件名 + "文件已删除"），不报错，不阻断会话 |
| AC-16 | 安全权限控制 | 传入含 `../` 的 session_id 返回 400；X-Family-Id 与 session 归属不符返回 403；JSONL 文件路径由服务端构造 |
| AC-17 | PII 脱敏 | JSONL 文件中不含原始身份证号、手机号、银行卡号；`system.pii_redacted` 事件记录脱敏字段名（不含值） |
| AC-18 | 容错性 | 模拟磁盘写入失败时主流程正常返回流式响应；错误写入 agent-audit.log；不抛出 500 |
| AC-19 | DeerFlow ID 一致性 | JSONL 中的 session_id 与 DeerFlow checkpointer 中的 thread_id 完全一致，可通过日志交叉验证 |
| AC-20 | fallback 路径覆盖 | USE_DEERFLOW=false 时，fallback 路径同样写入 JSONL；`system.fallback` 事件记录降级原因 |

---

## 16. 边界约定

**Always（必须）：**
- 写入 JSONL 前必须经过 `pii_redactor` 处理
- 所有事件必须包含 `family_id`、`session_id`、`event_type`、`timestamp`、`schema_version`
- `session_id` 必须与 DeerFlow `thread_id` 保持一致
- JSONL 写入失败必须静默处理，不得抛出异常影响主流程
- 文件路径必须由服务端构造，禁止接受客户端传入的路径字符串
- `message.thinking` 的 `visibility` 必须为 `"debug"`，不得默认暴露给用户

**Ask first（需确认）：**
- 修改 DeerFlow `JsonlRunEventStore` 的路径策略（影响 harness 内部）
- 修改 `stream_dispatch_events()` 的现有行为（影响所有 capability）
- 为 JSONL 文件引入压缩格式（`.jsonl.gz`）
- 修改 `session_id` 生成规则（影响已有会话的 ID 连续性）
- 开启 `generation.delta` 写入（写入量大，需评估磁盘影响）

**Never（禁止）：**
- 覆盖已写入的 JSONL 行（只能追加）
- 在 JSONL 中存储原始 PII 数据
- 在 JSONL 中存储二进制文件内容（只存引用）
- 跳过 `family_id` 校验直接读取任意路径的 JSONL 文件
- 在 JSONL 写入路径上引入同步锁（会阻塞流式输出）
- 将原始内部思考内容（`message.thinking`）默认暴露给用户或包含在默认导出中

---

## 17. 开放问题

| # | 问题 | 影响范围 | 建议 |
|---|------|---------|------|
| Q1 | `data/sessions/` 目录是否挂载持久化卷？Docker Compose 中需要配置 volume | 部署 | 建议与 `/app/data/deerflow-checkpoints.db` 同卷 |
| Q2 | 会话列表 API 是放在 agent 服务还是 backend 服务？ | 架构 | 建议放 agent 服务（数据在 agent 侧），backend 通过内部 API 代理；数据库 ai_sessions 表建在 backend DB 中，agent 通过 BackendClient 写入 |
| Q3 | `visibility: "debug"` 的 `phase.*` 事件是否写入 JSONL？ | 存储成本 | 建议写入（便于调试），但 API 默认过滤，需 `?include_debug=true` 参数才返回 |
| Q4 | 90 天清理策略是否需要用户确认？ | 产品 | 建议先实现软删除（写 `session.archived` 事件），30 天后再物理删除 |
| Q5 | `fallback_engine` 路径（`USE_DEERFLOW=false`）是否也写 JSONL？ | 覆盖率 | 建议是，两条路径都应写入，保证审计完整性 |
| Q6 | `ai_sessions` 数据库表建在 backend 还是 agent 侧？ | 架构 | 建议建在 backend DB（统一数据源），agent 通过 BackendClient 写入会话元数据 |
| Q7 | session_id 格式 `sess-{YYYYMMDD}-{uuid8}` 是否与 DeerFlow thread_id 格式兼容？ | 集成 | 需确认 DeerFlow `_validate_id` 正则是否接受此格式；若不兼容需增加映射层 |
| Q8 | `generation.delta` 事件是否在 MVP 中写入？ | 存储成本 | 建议 MVP 不写入；后续迭代按需通过配置开关控制 |

---

## 附录 A：完整事件示例

### A.1 会话开始

```json
{"event_id":"evt-001","session_id":"sess-20260510-a1b2c3d4","family_id":"fam-abc123","user_id":"usr-xyz789","agent_type":"deerflow","event_type":"session.start","timestamp":"2026-05-10T08:30:00.000Z","turn":0,"role":"system","schema_version":"1.0","visibility":"internal","metadata":{"capability":"chat","skill":"chat","ai_model":"claude-opus-4-7","provider":"anthropic"}}
```

### A.2 用户消息

```json
{"event_id":"evt-002","session_id":"sess-20260510-a1b2c3d4","family_id":"fam-abc123","user_id":"usr-xyz789","agent_type":"deerflow","event_type":"message.user","timestamp":"2026-05-10T08:30:01.123Z","turn":1,"role":"user","schema_version":"1.0","visibility":"public","metadata":{"capability":"chat"},"content":"我家的净资产健康吗？"}
```

### A.3 AI Thinking

```json
{"event_id":"evt-003","session_id":"sess-20260510-a1b2c3d4","family_id":"fam-abc123","user_id":null,"agent_type":"deerflow","event_type":"message.thinking","timestamp":"2026-05-10T08:30:02.456Z","turn":1,"role":"assistant","parent_event_id":"evt-002","schema_version":"1.0","visibility":"debug","metadata":{"thinking_budget":5000,"tokens_used":312},"content":"用户询问净资产健康状况，需要查询dashboard_overview数据..."}
```

### A.4 AI 回复

```json
{"event_id":"evt-004","session_id":"sess-20260510-a1b2c3d4","family_id":"fam-abc123","user_id":null,"agent_type":"deerflow","event_type":"message.assistant","timestamp":"2026-05-10T08:30:05.789Z","turn":1,"role":"assistant","parent_event_id":"evt-002","model":"claude-opus-4-7","provider":"anthropic","schema_version":"1.0","visibility":"public","metadata":{"tokens_used":486,"latency_ms":3333,"capability":"chat"},"content":"根据您家庭的资产数据，净资产为 ¥128.5万，整体健康状况良好..."}
```

### A.5 会话结束

```json
{"event_id":"evt-010","session_id":"sess-20260510-a1b2c3d4","family_id":"fam-abc123","user_id":null,"agent_type":"deerflow","event_type":"session.end","timestamp":"2026-05-10T08:35:22.000Z","turn":3,"role":"system","schema_version":"1.0","visibility":"internal","metadata":{"total_turns":3,"total_tokens":1842,"duration_ms":322000}}
```

---

## 附录 B：API 接口草案

### B.1 会话列表

```
GET /sessions
Headers: X-Agent-Token, X-Family-Id
Query:   ?capability=chat&limit=20&before=sess-20260509-xxx
```

Response 200:

```json
{
    "sessions": [
      {
        "session_id": "sess-20260510-a1b2c3d4",
        "capability": "chat",
        "status": "completed",
        "created_at": "2026-05-10T08:30:00Z",
        "ended_at": "2026-05-10T08:35:22Z",
        "total_turns": 3,
        "total_tokens": 1842
      }
    ],
    "has_more": true,
    "next_cursor": "sess-20260509-def456"
}
```

### B.2 会话事件流

```
GET /sessions/{session_id}/events
Headers: X-Agent-Token, X-Family-Id
Query:   ?after_seq=0&limit=100&include_debug=false
```

Response 200 (application/x-ndjson):

```
{"event_id":"evt-001","event_type":"session.start",...}
{"event_id":"evt-002","event_type":"message.user",...}
{"event_id":"evt-004","event_type":"message.assistant",...}
```

---

文档版本 v1.0 — 2026-05-10
