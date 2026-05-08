# 设计文档：模型测试功能迁移至 Agent 模块

**日期：** 2026-05-08  
**状态：** 已批准，待实施

---

## 背景

当前 `POST /api/v1/ai/config/{config_id}/test` 端点位于 backend 的 `ai_config.py` 路由中，直接调用 Anthropic/OpenAI API 执行四项模型能力测试。这与 backend 的职责（数据持久化、业务逻辑）不符——所有 LLM 交互应集中在 agent 模块。

---

## 目标

1. 将四项模型测试的 LLM 调用逻辑迁移至 agent 模块
2. Backend 保留配置读取和结果持久化，改为中转调用 agent
3. Frontend 无需任何改动

---

## 架构

### 调用链（迁移后）

```
前端（不变）
  ↓ POST /api/v1/ai/config/{config_id}/test
backend ai_config.py（保留路由，改为中转）
  ↓ 读取 AIProviderConfig from DB，解密 api_key
  ↓ POST {AGENT_URL}/test/model（internal token）
agent /test/model（新端点，无状态）
  ↓ 执行四项 LLM 测试
  ↓ 返回 ModelTestResult JSON
backend
  ↓ upsert 结果到 AIProviderTestResult 表
  ↓ 返回 AIConfigTestResult 给前端
```

### 测试执行顺序（与现有逻辑一致）

1. **connection** — 主模型连通性（30s timeout）
2. **thinking** — 仅在 connection 成功后执行（120s timeout）
3. **vision** — 仅在 `vision_model_id` 存在且与主模型不同时执行（120s timeout）
4. **vision_ocr** — 始终执行，使用 `vision_model_id` 或回退到主模型（120s timeout）

---

## Agent 新端点

### `POST /test/model`

**认证：** `Authorization: Bearer {AGENT_INTERNAL_TOKEN}`（与其他 agent 端点一致）

**Request schema（新建 `agent/schemas/model_test.py`）：**

```python
class ModelTestRequest(BaseModel):
    provider: str                        # "anthropic" | "openai"
    api_key: str                         # 明文，由 backend 解密后传入
    model_id: str                        # 主模型 ID
    base_url: str | None = None          # 自定义 API base URL（可选）
    vision_model_id: str | None = None   # 视觉模型 ID（可选）
    test_types: list[str]                # ["connection", "thinking", "vision", "vision_ocr"]
```

**Response schema（复用现有 `AIConfigTestResult` 结构，在 agent 侧定义等价 schema）：**

```python
class ModelTestResult(BaseModel):
    connected: bool
    message: str
    latency_ms: int | None = None
    thinking_success: bool | None = None
    thinking_message: str | None = None
    thinking_latency_ms: int | None = None
    vision_success: bool | None = None
    vision_message: str | None = None
    vision_latency_ms: int | None = None
    vision_text_success: bool | None = None
    vision_text_message: str | None = None
    vision_text_latency_ms: int | None = None
```

---

## 实施范围

### Agent 模块（新增）

| 文件 | 变更 |
|------|------|
| `agent/schemas/model_test.py` | 新建：`ModelTestRequest`、`ModelTestResult` |
| `agent/services/model_tester.py` | 新建：四个测试函数，从 backend `_test_*` 迁移，改用 `core/llm.py` 的 `LLMClient` |
| `agent/routers/model_test.py` | 新建：`POST /test/model` 路由 |
| `agent/app/main.py` | 注册新路由 |

### Backend 模块（修改）

| 文件 | 变更 |
|------|------|
| `backend/app/routers/ai_config.py` | 删除 `_test_connection`、`_test_thinking`、`_test_vision_model`、`_test_vision_text_ocr` 四个私有函数（约 360 行）；`test_ai_config` 改为读取 config → 调 agent → 持久化结果 |

### Frontend（不变）

`frontend/apps/main/src/api/ai.ts`、`stores/ai.ts`、`AIConfigPage.vue` 均无需改动。

---

## 关键设计决策

### 为什么 agent 接收明文凭证而非 config_id

Agent 端点设计为无状态——"给我凭证，我帮你测"。若接收 config_id，agent 需反向调用 backend 拉取配置，引入循环依赖。明文 api_key 在 backend→agent 的 service-to-service 通信中传输，与现有其他内部调用的安全模型一致（均通过 `AGENT_INTERNAL_TOKEN` 保护）。

### 为什么不复用 `core/llm.py` 的 `LLMClient` 单例

`LLMClient` 当前是按 family 配置初始化的单例，绑定了特定的 api_key 和 model。测试端点需要用**任意传入的凭证**临时构造客户端，不应污染单例状态。`model_tester.py` 将直接实例化 Anthropic/OpenAI SDK 客户端（与 `core/llm.py` 相同的方式），不复用单例。

### 持久化保留在 backend

`AIProviderTestResult` 表属于 backend 的数据模型，agent 不应感知 DB。Backend 在收到 agent 响应后执行 upsert，职责边界清晰。

---

## 不在本次范围内

- 统一 `skill_loader.py` 的 httpx 调用到 `backend_client.py` 连接池（独立小改动，可单独处理）
- 模型健康检查定时任务（B 场景，本次只做 A 场景）
- Frontend 任何改动

---

## 验证标准

- `POST /test/model` 返回与现有端点相同的 JSON 结构
- Backend `test_ai_config` 端点行为对 frontend 完全透明（相同请求，相同响应）
- Agent 单元测试覆盖四个测试函数的成功/超时/失败路径
- `uv run pytest tests/ -v` 在 backend 和 agent 均通过
- `uv run mypy .` 无新增类型错误
