---
date: 2026-04-10
type: feat
scope: ai-agent-module
status: draft
requirements:
  - docs/brainstorms/2026-04-10-001-ai-health-report-requirements.md
  - docs/brainstorms/2026-04-10-002-ai-smart-asset-intake-requirements.md
  - docs/brainstorms/2026-04-10-003-ai-asset-aging-alert-requirements.md
  - docs/brainstorms/2026-04-10-004-ai-liability-advisor-requirements.md
  - docs/brainstorms/2026-04-10-005-ai-disposal-advisor-requirements.md
  - docs/brainstorms/2026-04-10-006-ai-chat-assistant-requirements.md
  - docs/brainstorms/2026-04-10-007-ai-allocation-drift-requirements.md
---

# 实现规划：智能财务管家 AI Agent 模块

## 架构决策摘要

| 决策 | 选择 | 理由 |
|------|------|------|
| agent 部署形态 | 独立微服务（独立 Docker 容器） | 真正解耦，可独立扩展和替换 LLM Provider |
| agent ↔ backend 通信 | HTTP（内部网络），`X-Family-Id` header 传递用户上下文 | backend 强制验证 family_id，防止跨家庭数据泄露 |
| API Key 存储 | 数据库加密存储（AES-256 Fernet），per-family | 每个家庭自主管理 Key，自托管场景完全隔离 |
| LLM Provider | Anthropic Claude / OpenAI（首版） | 覆盖主流选择，不支持本地模型 |
| 脱敏策略 | 保留精确金额，剥离姓名/资产名/账号 | 自托管场景隐私风险可控，AI 建议更精准 |

---

## 整体目录结构

```
numina/
├── backend/                    # 现有 FastAPI 服务（不变）
│   └── app/
│       ├── models/             # 新增 AI 相关模型（见 Phase 0）
│       ├── routers/            # 新增 ai.py router
│       └── ...
├── agent/                      # 新增独立 AI 微服务
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── main.py                 # FastAPI app（agent 服务入口）
│   ├── config.py               # AgentSettings（AGENT_INTERNAL_TOKEN 等）
│   ├── core/
│   │   ├── llm.py              # LLM 调用封装（Anthropic / OpenAI 统一接口）
│   │   ├── desensitize.py      # 脱敏管道
│   │   └── backend_client.py   # 调用 backend 内部 HTTP 的客户端
│   ├── services/
│   │   ├── health_report.py    # 体检报告生成逻辑
│   │   ├── asset_suggest.py    # 资产录入智能补全
│   │   ├── aging_alert.py      # 固定资产老化预警
│   │   ├── liability_advisor.py # 负债优化顾问
│   │   ├── disposal_advisor.py  # 处置建议
│   │   ├── chat.py             # 问答助手
│   │   └── allocation_drift.py  # 配置漂移检测
│   ├── scheduler.py            # APScheduler（agent 侧定时任务）
│   └── routers/
│       ├── report.py
│       ├── suggest.py
│       ├── alerts.py
│       ├── liability.py
│       ├── disposal.py
│       ├── chat.py
│       └── allocation.py
├── frontend/                   # 现有 Vue 3 前端
│   └── src/
│       ├── pages/              # 新增 AI 相关页面
│       ├── components/ai/      # 新增 AI 相关组件
│       └── api/ai.ts           # 新增 AI API 调用层
└── docker-compose.yml          # 新增 agent 服务
```

---

## Phase 0：基础设施（所有功能的前提）

### 0.1 数据库模型扩展

**新增字段（迁移）：**

`families` 表：
- `ai_enabled: Boolean` default `False`
- `ai_provider: String(20)` nullable（`anthropic` / `openai`）
- `ai_api_key_encrypted: String(512)` nullable（AES-256 Fernet 加密）

`users` 表：
- `ai_chat_last_read_at: DateTime` nullable（未读红点时间戳）

**新增表（迁移）：**
- `ai_reports`（体检报告，Phase 1）
- `ai_asset_alerts`（老化预警，Phase 2）
- `ai_disposal_suggestions`（处置建议，Phase 2）
- `ai_allocation_targets`（配置目标，Phase 3）
- `ai_allocation_alerts`（配置漂移预警，Phase 3）
- `ai_chat_messages`（问答历史，Phase 3）

> 所有新表的迁移脚本统一放在 `backend/migrations/` 目录，按 Phase 分批执行。

### 0.2 backend：AI 配置接口

**新增文件：** `backend/app/routers/ai_config.py`

端点：
- `GET /api/v1/ai/config` — 返回当前家庭 AI 配置（`ai_enabled`、`ai_provider`、API Key 脱敏展示 `sk-****xxxx`）
- `PUT /api/v1/ai/config` — 更新 AI 配置；仅 `role == 'owner'` 可调用；API Key 用 `Fernet` 加密后存储
- `POST /api/v1/ai/config/test` — 测试 API Key 连通性（向 LLM 发送最小 ping 请求）

**新增 FastAPI dependency：**
- `require_ai_enabled` — 检查 `family.ai_enabled`，否则返回 `403 {"code": "ai_disabled"}`
- `require_owner` — 检查 `user.role == 'owner'`，否则返回 `403 {"code": "ai_not_authorized"}`（复用现有 family.py 中的模式，提取为共享 dependency）

**Settings 新增（`backend/app/config.py`）：**
```
AI_ENCRYPTION_KEY: str = ""   # Fernet key，生产环境必填
AGENT_INTERNAL_TOKEN: str = ""  # agent ↔ backend service token
AGENT_BASE_URL: str = "http://agent:8001"  # agent 服务内部地址
```

**`main.py` 注册：**
- 新增 `from app.routers import ai_config` 并 `app.include_router(ai_config.router)`
- 新增 `from app.routers import ai` 并注册（Phase 1 起逐步添加）

### 0.3 backend：内部 agent 端点守卫

**新增 dependency：** `verify_agent_token`
- 验证请求 header `Authorization: Bearer {AGENT_INTERNAL_TOKEN}`
- 提取 `X-Family-Id` header，验证对应 family 存在
- 返回 `family_id`（所有 agent 调用的数据查询以此 family_id 为边界）

所有供 agent 调用的 backend 内部端点（`/api/v1/internal/*`）使用此 dependency，不暴露给前端。

### 0.4 agent 微服务骨架

**新增文件：** `agent/main.py`、`agent/config.py`、`agent/core/llm.py`、`agent/core/desensitize.py`、`agent/core/backend_client.py`

**`agent/core/llm.py`** — 统一 LLM 调用接口：
```python
# 方向性伪代码，非实现规范
class LLMClient:
    def __init__(self, provider: str, api_key: str): ...
    async def complete(self, prompt: str, max_tokens: int) -> str: ...
    async def complete_structured(self, prompt: str, schema: type[BaseModel]) -> BaseModel: ...
```
- Anthropic：使用 `anthropic` SDK，`claude-3-5-haiku` 作为默认模型（速度/成本平衡）
- OpenAI：使用 `openai` SDK，`gpt-4o-mini` 作为默认模型

**`agent/core/desensitize.py`** — 脱敏管道：
- `desensitize_assets(assets)` → 资产名替换为类别标签，保留金额
- `desensitize_liabilities(liabilities)` → 负债名/机构名替换为类别标签，金额转区间
- `desensitize_members(members)` → 姓名替换为"成员A/B/C"

**`agent/core/backend_client.py`** — 内部 HTTP 客户端：
- 使用 `httpx.AsyncClient`，自动附加 `Authorization` 和 `X-Family-Id` header
- 封装所有 backend 内部端点调用（dashboard、assets、liabilities 等）

### 0.5 Docker Compose 扩展

`docker-compose.yml` 新增 `agent` 服务：
```yaml
agent:
  build: ./agent
  environment:
    - AGENT_INTERNAL_TOKEN=${AGENT_INTERNAL_TOKEN}
    - AI_ENCRYPTION_KEY=${AI_ENCRYPTION_KEY}
    - BACKEND_BASE_URL=http://backend:8000
  depends_on:
    - backend
  networks:
    - internal
```

`backend` 服务新增环境变量：
```yaml
- AGENT_INTERNAL_TOKEN=${AGENT_INTERNAL_TOKEN}
- AI_ENCRYPTION_KEY=${AI_ENCRYPTION_KEY}
- AGENT_BASE_URL=http://agent:8001
```

### 0.6 前端：AI 配置页

**修改文件：** `frontend/src/pages/SettingsPage.vue`
- 新增"AI 智能功能"入口（仅 owner 可见）

**新增文件：** `frontend/src/pages/AIConfigPage.vue`
- AI 开关 Toggle
- Provider 选择（Anthropic / OpenAI）
- API Key 输入框（脱敏展示）
- 连接测试按钮

**新增文件：** `frontend/src/api/ai.ts`
- 封装所有 AI 相关 API 调用

**新增 store：** `frontend/src/stores/ai.ts`
- `aiEnabled`、`aiProvider` 状态
- `fetchAIConfig()`、`updateAIConfig()` actions

---

## Phase 1：旗舰功能

### 1.1 家庭资产体检报告

**backend 新增：**
- `backend/app/models/ai_report.py` — `AIReport` 模型（`id`、`family_id`、`report_json`、`generated_at`、`data_completeness_score`）
- `backend/app/routers/ai_report.py` — `GET /api/v1/ai/report`、`POST /api/v1/ai/report/generate`、`WS /api/v1/ai/report/ws/{family_id}`
- `backend/app/routers/ai_internal.py` — 供 agent 调用的内部端点（`/api/v1/internal/dashboard/*`）

**agent 新增：**
- `agent/services/health_report.py` — 聚合 dashboard 数据 → 脱敏 → LLM 生成叙事 → 返回结构化报告 JSON
- `agent/routers/report.py` — `POST /agent/report/generate`（由 backend WebSocket handler 调用）
- `agent/scheduler.py` — 月度定时任务（每月 1 日 08:00 Asia/Shanghai + 随机偏移）

**报告 JSON 结构（固定，LLM 只填叙事字段）：**
```json
{
  "net_worth_health": { "score": 4, "narrative": "...", "data": {...} },
  "allocation_analysis": { "score": 3, "narrative": "...", "data": {...} },
  "liability_pressure": { "score": 2, "narrative": "...", "data": {...} },
  "asset_efficiency": { "score": 4, "narrative": "...", "data": {...} },
  "overall_score": 72,
  "summary": "...",
  "generated_at": "...",
  "data_completeness_score": 85
}
```

**frontend 新增：**
- `frontend/src/pages/AIReportPage.vue` — 独立报告页，卡片组滚动展示
- `frontend/src/components/ai/ReportCard.vue` — 单个报告模块卡片
- `frontend/src/components/ai/ReportScoreBadge.vue` — 健康评分徽章
- WebSocket 连接管理（`useAIReportWS` composable）

**SettingsPage.vue 修改：** 新增"AI 体检报告"入口

### 1.2 智能资产录入助手

**backend 新增：**
- `backend/app/routers/ai_suggest.py` — `POST /api/v1/ai/asset-suggest`（转发给 agent）

**agent 新增：**
- `agent/services/asset_suggest.py` — 资产名 + 类别列表 → LLM → 结构化建议（pydantic 约束输出）
- `agent/routers/suggest.py` — `POST /agent/suggest/asset`

**frontend 修改：**
- `frontend/src/components/asset/AssetForm.vue`：
  - `usage_frequency` 初始值改为 `null`
  - 名称字段 `@blur` 事件触发 AI 补全
  - AI 填入字段显示 `--ai-fill-bg` 样式
  - `tag_names` 建议以 Chip 形式展示
- `frontend/src/api/ai.ts` 新增 `suggestAssetFields()`

---

## Phase 2：数据驱动功能

### 2.1 固定资产老化预警

**backend 新增：**
- `backend/app/models/ai_asset_alert.py` — `AIAssetAlert` 模型
- `backend/app/routers/ai_alerts.py` — `GET /api/v1/ai/asset-alerts`、`POST /api/v1/ai/asset-alerts/{id}/dismiss`

**agent 新增：**
- `agent/services/aging_alert.py` — 扫描到期资产 → 评分 → LLM 生成建议
- `agent/scheduler.py` 新增每周一定时任务（与处置建议共享同一 job）

**frontend 修改：**
- `frontend/src/pages/DashboardPage.vue` — 新增资产预警卡片区
- `frontend/src/components/ai/AssetAlertCard.vue` — 预警卡片组件（SwipeCell 左滑忽略）

### 2.2 负债优化顾问

**backend 新增：**
- `backend/app/routers/ai_liability.py` — `GET /api/v1/ai/liability-advice`、`POST /api/v1/ai/liability-advice/chat`

**agent 新增：**
- `agent/services/liability_advisor.py` — 确定性策略计算（雪崩/滚雪球/混合）+ LLM 叙事
- `agent/routers/liability.py`

**frontend 新增：**
- `frontend/src/pages/AILiabilityAdvisorPage.vue` — 策略对比 Tab + 问答区
- `frontend/src/components/ai/StrategyCompareTab.vue`
- `frontend/src/components/ai/ChatBubble.vue`（可复用于 Phase 3 问答助手）
- Dashboard 负债摘要卡片（修改 `DashboardPage.vue`）

### 2.3 低效资产处置建议

**backend 新增：**
- `backend/app/models/ai_disposal_suggestion.py` — `AIDisposalSuggestion` 模型
- `backend/app/routers/ai_disposal.py` — `GET /api/v1/ai/disposal-suggestions`、`POST /api/v1/ai/disposal-suggestions/{id}/dismiss`

**agent 新增：**
- `agent/services/disposal_advisor.py` — 多维度评分（规则）+ LLM 渠道建议
- 与老化预警共享每周定时 job

**frontend 新增：**
- `frontend/src/pages/AIDisposalPage.vue` — 清仓清单页（分组折叠）
- Dashboard 闲置资产摘要卡片（修改 `DashboardPage.vue`）

---

## Phase 3：高级交互

### 3.1 自然语言资产问答助手

**backend 新增：**
- `backend/app/models/ai_chat_message.py` — `AIChatMessage` 模型（含 `status` 字段：`pending`/`completed`/`error`）
- `backend/app/routers/ai_chat.py` — `POST /api/v1/ai/chat`、`GET /api/v1/ai/chat/history`、`DELETE /api/v1/ai/chat/history`、`PUT /api/v1/ai/chat/read`

**agent 新增：**
- `agent/services/chat.py` — 意图识别（8 个固定意图）→ 数据查询 → LLM 回答
- `agent/routers/chat.py`

**frontend 新增：**
- `frontend/src/pages/AIChatPage.vue` — 全屏聊天页
- `frontend/src/components/ai/FloatingChatButton.vue` — Dashboard 浮动按钮（含未读红点）
- 复用 `ChatBubble.vue`（Phase 2 已建）

### 3.2 资产分配漂移检测

**backend 新增：**
- `backend/app/models/ai_allocation_target.py` — `AIAllocationTarget` 模型
- `backend/app/models/ai_allocation_alert.py` — `AIAllocationAlert` 模型
- `backend/app/routers/ai_allocation.py` — `GET/PUT /api/v1/ai/allocation-target`、`GET /api/v1/ai/allocation-alert`、`POST /api/v1/ai/allocation-alert/dismiss`

**agent 新增：**
- `agent/services/allocation_drift.py` — 漂移计算（直接查 DB via backend client）+ LLM 建议
- 与 Phase 2 定时任务共享每周 job

**frontend 修改：**
- `AIConfigPage.vue` 新增"资产配置目标"设置区（大类滑块 + 类别级可折叠）
- `DashboardPage.vue` 新增配置漂移卡片

---

## 关键文件变更清单

### backend（现有服务）

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `app/config.py` | 修改 | 新增 `AI_ENCRYPTION_KEY`、`AGENT_INTERNAL_TOKEN`、`AGENT_BASE_URL` |
| `app/models/family.py` | 修改 | 新增 `ai_enabled`、`ai_provider`、`ai_api_key_encrypted` |
| `app/models/user.py` | 修改 | 新增 `ai_chat_last_read_at` |
| `app/main.py` | 修改 | 注册新 router，导入新模型 |
| `app/auth/deps.py` | 修改 | 新增 `require_owner`、`require_ai_enabled`、`verify_agent_token` |
| `app/routers/ai_config.py` | 新增 | AI 配置管理端点 |
| `app/routers/ai_internal.py` | 新增 | 供 agent 调用的内部端点（`/api/v1/internal/*`） |
| `app/routers/ai_report.py` | 新增 | 体检报告端点 + WebSocket |
| `app/routers/ai_suggest.py` | 新增 | 资产补全端点 |
| `app/routers/ai_alerts.py` | 新增 | 老化预警端点 |
| `app/routers/ai_liability.py` | 新增 | 负债顾问端点 |
| `app/routers/ai_disposal.py` | 新增 | 处置建议端点 |
| `app/routers/ai_chat.py` | 新增 | 问答助手端点 |
| `app/routers/ai_allocation.py` | 新增 | 配置漂移端点 |
| `app/models/ai_*.py` | 新增（8个） | 各 AI 功能数据模型 |

### agent（新增微服务）

| 文件 | 说明 |
|------|------|
| `agent/main.py` | FastAPI 应用入口 |
| `agent/config.py` | AgentSettings |
| `agent/core/llm.py` | LLM 统一调用封装 |
| `agent/core/desensitize.py` | 脱敏管道 |
| `agent/core/backend_client.py` | backend 内部 HTTP 客户端 |
| `agent/scheduler.py` | APScheduler 定时任务 |
| `agent/services/*.py` | 各功能业务逻辑（7个） |
| `agent/routers/*.py` | 各功能路由（7个） |
| `agent/Dockerfile` | 容器构建 |
| `agent/requirements.txt` | 依赖（anthropic、openai、httpx、apscheduler、fastapi、pydantic） |

### frontend（现有前端）

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `src/api/ai.ts` | 新增 | AI API 调用层 |
| `src/stores/ai.ts` | 新增 | AI 状态管理 |
| `src/pages/AIConfigPage.vue` | 新增 | AI 配置页 |
| `src/pages/AIReportPage.vue` | 新增 | 体检报告页 |
| `src/pages/AILiabilityAdvisorPage.vue` | 新增 | 负债顾问页 |
| `src/pages/AIDisposalPage.vue` | 新增 | 清仓清单页 |
| `src/pages/AIChatPage.vue` | 新增 | 问答助手页 |
| `src/components/ai/*.vue` | 新增（8个） | AI 相关组件 |
| `src/pages/SettingsPage.vue` | 修改 | 新增 AI 功能入口 |
| `src/pages/DashboardPage.vue` | 修改 | 新增 AI 卡片区（预警/处置/漂移/浮动按钮） |
| `src/components/asset/AssetForm.vue` | 修改 | 集成智能补全 |
| `src/router/index.ts` | 修改 | 新增 AI 页面路由 + ai_enabled 守卫 |

---

## 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| LLM API 调用延迟高（>10s） | 用户等待体验差 | WebSocket 推送进度；体检报告异步生成；建议接口 3s 超时静默降级 |
| agent 服务不可用 | 所有 AI 功能失效 | backend 对 agent 调用加 try/except；AI 功能不可用时前端展示友好提示，不影响核心功能 |
| API Key 泄露 | 用户 LLM 费用损失 | Fernet 加密存储；日志中不打印 Key；API Key 展示时脱敏 |
| 多实例部署定时任务重复触发 | 重复 LLM 调用，费用浪费 | agent 服务设计为单实例（`replicas: 1`）；若需扩展，用 Redis 分布式锁保护定时任务 |
| LLM 幻觉污染财务数字 | 用户信任损失 | 结构化数据后端计算，LLM 只生成叙事文本；报告 JSON 结构固定，LLM 无法修改数字字段 |
| `category_targets` JSON 校验绕过 | 漂移计算错误 | 后端 Pydantic validator 强制校验总和 = 100；部分填写返回 422 |

---

## 实现顺序建议

```
Week 1-2: Phase 0（基础设施）
  ├── 数据库迁移（Family/User 字段扩展）
  ├── backend AI 配置接口 + dependencies
  ├── agent 微服务骨架（main.py、config、llm、desensitize、backend_client）
  ├── Docker Compose 扩展
  └── 前端 AI 配置页 + ai store

Week 3-4: Phase 1（旗舰功能）
  ├── 体检报告（backend WebSocket + agent 生成逻辑 + 前端报告页）
  └── 智能资产录入助手（agent suggest + 前端 AssetForm 集成）

Week 5-6: Phase 2（数据驱动功能）
  ├── 固定资产老化预警（agent 定时任务 + 前端 Dashboard 卡片）
  ├── 负债优化顾问（agent 策略计算 + 前端顾问页）
  └── 低效资产处置建议（agent 评分 + 前端清仓清单）

Week 7-8: Phase 3（高级交互）
  ├── 自然语言问答助手（agent 意图路由 + 前端聊天页）
  └── 资产分配漂移检测（agent 漂移计算 + 前端配置设置 + Dashboard 卡片）
```

---

## 未解决问题（规划阶段遗留）

- **[Phase 1][WebSocket 鉴权]** FastAPI WebSocket 端点的 JWT 鉴权方式：query param `?token=xxx` 还是首条消息携带 token？建议：query param（与现有 httpOnly cookie 策略兼容，WebSocket 握手时验证）。
- **[Phase 1][报告生成并发]** 月度定时任务中，多个家庭并发生成报告时的 LLM 调用并发控制：建议使用 `asyncio.Semaphore(5)` 限制同时进行的 LLM 调用数量。
- **[Phase 2][AllocationItem 扩展]** `get_allocation()` 返回的 `AllocationItem` 无 `asset_type` 字段，漂移计算需要区分实物/金融。规划时决定：在 `AllocationItem` schema 中新增 `asset_type` 字段，`get_allocation()` 服务层同步更新。
- **[Phase 3][问答流式输出]** 问答是否支持 SSE 流式输出？首版建议非流式（loading 动画），Phase 3.1 完成后评估是否值得增加流式支持。
