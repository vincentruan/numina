---
date: 2026-04-20
topic: chat-history-jsonl
focus: 将 AI 对话历史从 DB 全量存储迁移到 JSONL 文件存储，DB 仅保留会话索引，JSONL 文件与现有文件备份模块互通
status: approved
---

# 需求文档：AI 对话历史 JSONL 存储优化

## 背景

当前 `ai_chat_messages` 表将每条消息的完整内容存储在 SQLite TEXT 列中。随着对话历史增长，存在以下问题：

- **DB 膨胀**：消息内容直接写入 SQLite，长期积累导致数据库体积增大
- **可移植性差**：对话历史无法独立备份、导出或迁移，与文件备份模块完全割裂
- **DeerFlow 不一致**：DeerFlow adapter 已使用 `thread_id` 管理会话状态，但 chat 路由绕过了这套框架

## 目标

1. **DB 瘦身**：`ai_chat_sessions` 表只存会话元数据（路径、计数、预览），不存消息内容
2. **JSONL 为主**：每个会话对应一个 JSONL 文件，每行一条消息，文件是消息的唯一来源
3. **复用 DeerFlow 会话框架**：`session_id` 与 DeerFlow `thread_id` 对齐，`USE_DEERFLOW=true` 时两者共享同一 session_id
4. **文件备份互通**：JSONL 文件通过现有 `CachedFile` + `FileRemoteLocation` 机制自动同步到远端（GitHub/WebDAV）

## 非目标

- 不修改其他 agent 功能（report、suggest、alerts 等）的存储方式——本次只覆盖 chat
- 不支持跨会话全文搜索（可作为后续迭代）
- 不引入新的备份基础设施——复用现有 storage 模块

---

## 数据模型变更

### 新增：`ai_chat_sessions` 表

```
ai_chat_sessions
├── id              String(36) PK          会话 ID，同时作为 DeerFlow thread_id
├── family_id       String(36) FK(families) 家庭隔离
├── jsonl_path      String(500)            JSONL 文件的本地绝对路径
├── cached_file_id  String(36) FK(cached_files) nullable  关联文件备份记录
├── message_count   Integer default 0      消息总数（含 user + assistant）
├── last_preview    Text nullable          最后一条 assistant 消息的前 100 字（用于列表展示）
├── created_at      DateTime
└── updated_at      DateTime
```

### 废弃：`ai_chat_messages` 表

- 保留表结构（不 DROP），通过 Alembic 迁移将现有数据导出为 JSONL 后标记为已迁移
- 新代码不再写入此表

### JSONL 文件格式

每行一个 JSON 对象：

```jsonl
{"message_id": "uuid", "role": "user", "content": "...", "timestamp": "2026-04-20T10:00:00Z"}
{"message_id": "uuid", "role": "assistant", "content": "...", "timestamp": "2026-04-20T10:00:05Z"}
```

### 文件存储路径

```
{UPLOAD_DIR}/chat_sessions/{family_id}/{session_id}.jsonl
```

与现有 `CachedFile.local_path` 规范一致，`date_dir` 使用会话创建日期（`yyyyMMdd`）。

---

## 接口变更

### `POST /api/v1/ai/chat`

**变更：**
- 创建或复用 `ai_chat_sessions` 记录（通过 `session_id` query param，缺省则新建）
- 将 user 消息 append 到 JSONL 文件
- 调用 agent，将 assistant 回答 append 到 JSONL 文件
- 更新 `ai_chat_sessions.message_count` 和 `last_preview`
- 首次写入后，将 JSONL 文件注册到 `CachedFile`（触发备份同步）

**Request 新增可选字段：**
```json
{ "question": "...", "session_id": "optional-existing-session-id" }
```

**Response 新增字段：**
```json
{ "question": "...", "answer": "...", "message_id": "...", "session_id": "..." }
```

### `GET /api/v1/ai/chat/history`

**变更：**
- 接受 `session_id` query param（必填）
- 从 JSONL 文件读取消息，返回格式不变
- 不再查询 `ai_chat_messages` 表

### `GET /api/v1/ai/chat/sessions`（新增）

列出当前家庭的所有会话：

```json
[
  {
    "session_id": "...",
    "created_at": "...",
    "message_count": 12,
    "last_preview": "建议优先偿还利率最高的..."
  }
]
```

### `DELETE /api/v1/ai/chat/history`

**变更：**
- 接受 `session_id` query param（必填）
- 删除 JSONL 文件（软删除：通过 `CachedFile.deleted_at`）
- 删除 `ai_chat_sessions` 记录

---

## DeerFlow 集成

当 `USE_DEERFLOW=true`：

- `session_id` 直接作为 DeerFlow `thread_id` 传入 `deerflow_adapter.dispatch()`
- DeerFlow checkpointer 管理 LangGraph 状态（工具调用、上下文窗口）
- JSONL 文件作为独立的消息审计轨迹，由 agent 侧写入（不依赖 checkpointer 格式）

当 `USE_DEERFLOW=false`：

- `session_id` 仅用于 JSONL 文件命名和会话索引
- 消息直接 append 到 JSONL，无 checkpointer

两条路径均产出相同的 JSONL 格式，备份模块无需感知 DeerFlow 状态。

---

## 文件备份互通

JSONL 文件通过现有 `CachedFile` 机制接入备份流程：

1. 首次写入 JSONL 后，创建 `CachedFile` 记录（`mime_type: "application/x-ndjson"`）
2. 现有 file sync scheduler 自动将 JSONL 同步到已配置的远端 backend（GitHub/WebDAV）
3. `ai_chat_sessions.cached_file_id` 关联此记录，方便查询备份状态
4. 每次 append 消息后，更新 `CachedFile.sha256` 和 `size_bytes`，触发重新同步

**不需要修改备份模块本身**——JSONL 文件对 storage backend 来说与图片、附件无异。

---

## 迁移策略

1. **Alembic 迁移脚本**：
   - 创建 `ai_chat_sessions` 表
   - 将 `ai_chat_messages` 中现有数据按 `family_id` 分组，每个家庭生成一个 `legacy_{family_id}.jsonl` 文件
   - 为每个 legacy 文件创建 `ai_chat_sessions` 记录
   - 不 DROP `ai_chat_messages` 表（保留作为只读历史备份）

2. **向后兼容**：
   - `GET /api/v1/ai/chat/history` 无 `session_id` 时，返回该家庭最新会话的历史（兼容现有前端）

---

## 文件变更清单

### backend

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `app/models/ai_chat_session.py` | 新增 | `AIChatSession` 模型 |
| `app/routers/ai_chat.py` | 修改 | 切换到 JSONL 读写，新增 sessions 端点 |
| `app/services/chat_session.py` | 新增 | JSONL append/read 逻辑，CachedFile 注册 |
| `alembic/versions/xxxx_chat_history_jsonl.py` | 新增 | 建表 + 数据迁移 |

### agent

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `routers/chat.py` | 修改 | 接收并透传 `session_id`，支持 DeerFlow thread_id 对齐 |

### frontend

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `src/pages/AIChatPage.vue` | 修改 | 传递 `session_id`，支持会话列表切换 |
| `src/api/ai.ts` | 修改 | 新增 `getSessions()`，更新 `getHistory(sessionId)` |

---

## 成功标准

- `ai_chat_messages` 表不再有新写入
- 每次对话后，JSONL 文件正确 append，内容与 API 返回一致
- 文件备份模块能正常同步 JSONL 文件到远端
- `USE_DEERFLOW=true` 和 `false` 两条路径均产出相同 JSONL 格式
- 现有前端无 `session_id` 时仍能正常加载历史（向后兼容）
- 迁移后现有对话历史可通过新 API 访问
