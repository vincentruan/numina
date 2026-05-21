# Agent-First Architecture Design Spec

> Numina AI 功能重构：从 Skill-first 升级为 Agent-first，复用 DeerFlow Harness 原生能力，保留家庭租户隔离

**Date:** 2026-05-21
**Status:** Draft
**Author:** Claude (brainstorming session)

---

## 1. Overview

### 1.1 Problem Statement

当前 Numina AI 功能以"Skill"为用户入口，存在以下问题：

1. **入口层级混乱** — 用户看到 6 个独立功能入口（alerts、allocation、disposal、liability、report、spending_leak），缺乏统一的服务角色感
2. **Skill 与 Agent 概念模糊** — DeerFlow 2.0 的 Agent 架构（SOUL.md + config.yaml + ThreadState + tools + memory）未被充分利用
3. **租户隔离不完整** — 现有 skill_registry 表支持按 family_id 启用/禁用，但缺乏完整的 Agent 级租户管理
4. **执行链路自建** — orchestrator 直接调用 DeerFlowClient.stream()，绕过了 harness 的 make_lead_agent、middleware 链、ThreadState 管理

### 1.2 Design Goals

1. **Agent-first 入口** — 用户选择 Agent（而非 Skill），Skill 作为 Agent 内部能力模块按需调度
2. **数据库驱动租户管理** — Agent 元数据存储在数据库中，按 family_id 隔离，支持权限控制、配置持久化、审计
3. **Harness 原生执行** — 从数据库读取 Agent 配置后，动态构建 make_lead_agent 实例，走完整的 LangGraph 链路
4. **复用 DeerFlow 能力** — ThreadState、tools、memory、subagent、middleware 链全部复用，不自建

### 1.3 Key Decisions (from Brainstorming)

| 决策项 | 选择 |
|--------|------|
| 内置 Agent 拆分 | 2 个：资产健康顾问（report+alerts+allocation+disposal）、财务优化师（liability+spending_leak） |
| 固定能力 | chat（AI问答）、time_machine（资产时光机）保持不变，不属于 Agent |
| 用户自定义 Agent | 中等配置：名称/描述/头像/SOUL.md + skill 勾选 + 模型选择 + subagent 开关 |
| 执行交互 | 内置 Agent 保留结构化结果页 + 底部对话追问；自定义 Agent 纯对话式 |
| Hub 页面 | 保留顶部 Dashboard + 下方 Agent 卡片网格 |

---

## 2. Architecture

### 2.1 High-Level Architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│                              Frontend                                     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐      │
│  │   AI Hub    │  │ Agent Page  │  │Agent Create │  │  Chat Page  │      │
│  │(Dashboard+  │  │(结果页+     │  │   Form      │  │(自定义Agent)│      │
│  │ Agent Grid) │  │ 对话追问)   │  │             │  │             │      │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘      │
└──────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ REST API / NDJSON Stream
                                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                           Backend (FastAPI)                               │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                      ai_agents.py Router                         │    │
│  │  GET /ai/agents          POST /ai/agents                        │    │
│  │  PUT /ai/agents/{id}     DELETE /ai/agents/{id}                 │    │
│  │  POST /ai/agents/{id}/stream                                     │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                    │                                      │
│                                    │ AgentRegistryService                 │
│                                    ▼                                      │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                      PostgreSQL                                  │    │
│  │                    agent_registry 表                             │    │
│  └─────────────────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ Agent Config (SOUL.md + skills + model)
                                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                           Agent Service                                   │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                    orchestrator.py (重构)                        │    │
│  │  stream_agent_dispatch(agent_id, family_id, thread_id, msg)     │    │
│  │    → 读取 AgentConfig from DB                                    │    │
│  │    → 生成临时 SOUL.md + config.yaml                              │    │
│  │    → make_lead_agent(RunnableConfig)                            │    │
│  │    → agent.stream() → NDJSON events                             │    │
│  └─────────────────────────────────────────────────────────────────┐    │
└──────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ make_lead_agent()
                                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                         DeerFlow Harness                                  │
│  ┌───────────────┐ ┌───────────────┐ ┌───────────────┐ ┌─────────────┐  │
│  │  Lead Agent   │ │  ThreadState  │ │    Tools      │ │  Memory     │  │
│  │  (LangGraph)  │ │ uploaded_files│ │ present_files │ │ (per-family)│  │
│  │               │ │ artifacts     │ │ ask_clarify   │ │             │  │
│  │               │ │ todos         │ │ view_image    │ │             │  │
│  │               │ │ sandbox       │ │ task(subagent)│ │             │  │
│  └───────────────┘ └───────────────┘ └───────────────┘ └─────────────┘  │
│  ┌───────────────┐ ┌───────────────┐ ┌───────────────┐                  │
│  │   Skills      │ │  Middleware   │ │  Subagents    │                  │
│  │ SKILL.md      │ │ DynamicContext│ │ SubagentExec  │                  │
│  │ extensions    │ │ Summarization │ │               │                  │
│  │               │ │ TodoMiddleware│ │               │                  │
│  └───────────────┘ └───────────────┘ └───────────────┘                  │
└──────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ read_file(SKILL.md) when skill needed
                                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                          Skills Library                                   │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  skills/builtin/{skill_name}/SKILL.md                           │    │
│  │  ├── report/SKILL.md      # 家庭资产体检                         │    │
│  │  ├── alerts/SKILL.md      # 资产老化预警                         │    │
│  │  ├── allocation/SKILL.md  # 资产配置分析                         │    │
│  │  ├── disposal/SKILL.md    # 闲置资产处置                         │    │
│  │  ├── liability/SKILL.md   # 负债健康分析                         │    │
│  │  └── spending_leak/SKILL.md # 消费漏洞扫描                       │    │
│  └─────────────────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Component Responsibilities

| Component | Responsibility |
|-----------|---------------|
| `agent_registry` DB 表 | Agent 元数据存储：SOUL.md 内容、skills 列表、model 选择、subagent 开关、租户隔离 |
| `AgentRegistryService` | CRUD 操作、权限校验、内置 Agent 种子数据管理 |
| `orchestrator.stream_agent_dispatch()` | Agent 执行入口：读取配置 → 动态构建 → make_lead_agent → 流式返回 |
| `DynamicAgentBuilder` | 临时 SOUL.md + config.yaml 生成、缓存管理 |
| `make_lead_agent()` | DeerFlow harness 入口：构建 LangGraph agent、注入 middleware 链 |
| `ThreadState` | 会话状态：uploaded_files、artifacts、todos、sandbox、thread_data |
| `Skills Library` | Skill 定义文件：流程说明、allowed-tools、最佳实践 |

---

## 3. Database Schema

### 3.1 agent_registry 表

```sql
CREATE TABLE agent_registry (
    id              BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    family_id       BIGINT NOT NULL,           -- 租户隔离；内置 Agent family_id=0
    agent_name      VARCHAR(64) NOT NULL,      -- URL-safe identifier
    display_name    VARCHAR(128) NOT NULL,     -- 用户可见名称
    description     TEXT,                       -- 一句话描述（用于 Agent 卡片）
    icon            VARCHAR(16),               -- emoji 或图标标识
    color           VARCHAR(16),               -- 主题色 (hex, 如 #10B981)

    -- DeerFlow 配置字段
    soul_md         TEXT NOT NULL,              -- SOUL.md 完整内容
    skills          JSONB,                      -- 允许的 skill 列表: ["report", "alerts"] 或 null (=全部)
    model           VARCHAR(64),               -- 模型选择: null=继承家庭默认
    subagent_enabled BOOLEAN DEFAULT FALSE,     -- 是否启用 subagent 能力
    tool_groups     JSONB,                      -- 工具组白名单: ["web", "files"] 或 null (=全部)

    -- 元信息与控制
    is_builtin      BOOLEAN DEFAULT FALSE,      -- 内置 Agent 标记（不可删除）
    is_enabled      BOOLEAN DEFAULT TRUE,       -- 启用/禁用状态
    display_order   INT DEFAULT 0,             -- 卡片排序权重
    created_by      BIGINT,                     -- 创建者 user_id（自定义 Agent）
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),

    -- 约束
    CONSTRAINT agent_name_format CHECK (agent_name ~ '^[a-z][a-z0-9_-]*$'),
    CONSTRAINT unique_agent_per_family UNIQUE (family_id, agent_name)
);

-- 索引
CREATE INDEX idx_agent_registry_family ON agent_registry(family_id);
CREATE INDEX idx_agent_registry_builtin ON agent_registry(is_builtin) WHERE is_builtin = TRUE;
CREATE INDEX idx_agent_registry_enabled ON agent_registry(is_enabled) WHERE is_enabled = TRUE;
```

### 3.2 Skill List Field Semantics

| `skills` 值 | 含义 |
|-------------|------|
| `NULL` | 该 Agent 可访问所有 skill（默认） |
| `[]` (空数组) | 该 Agent 无 skill 能力 |
| `["report", "alerts"]` | 该 Agent 只能使用指定 skill |

### 3.3 Tenant Isolation Rules

1. **查询规则**：`WHERE (family_id = 0 AND is_builtin = TRUE) OR family_id = {current_family_id}`
2. **权限规则**：
   - 内置 Agent（`is_builtin=TRUE`）：所有家庭成员可见，owner 可修改 icon/color/display_order，不可删除
   - 自定义 Agent（`is_builtin=FALSE`）：仅 owner 可 CRUD，其他家庭成员可使用
3. **唯一性规则**：同一 `family_id` 内 `agent_name` 不能重复；内置 Agent（`family_id=0`）全局唯一

### 3.4 Seed Data (Builtin Agents)

```sql
-- 内置 Agent 1: 资产健康顾问
INSERT INTO agent_registry (
    family_id, agent_name, display_name, description,
    icon, color, soul_md, skills, is_builtin, display_order
) VALUES (
    0,
    'asset-health-advisor',
    '资产健康顾问',
    '全方位监控家庭资产健康状况，提供体检报告、预警提醒、配置分析和闲置处置建议',
    '🏥',
    '#10B981',
    '你是一位专业的家庭资产健康顾问。你的职责是帮助用户全面了解家庭资产的健康状况，发现潜在风险，并提供专业的改善建议。

## 核心能力
- **资产体检**：综合评估家庭资产的整体健康度，输出结构化体检报告
- **老化预警**：扫描资产老化、高维护成本、闲置情况，提前预警
- **配置分析**：分析资产配置比例，识别偏离最优配置的资产类别
- **处置建议**：识别闲置资产，提供处置或盘活建议

## 工作原则
1. 数据驱动：所有分析基于用户的实际资产数据，不做无依据的推测
2. 风险优先：优先关注高风险、高老化、高闲置的资产
3. 可操作性：每条建议都要有具体的执行路径
4. 保守表达：对不确定的结论使用"可能"、"建议进一步确认"等措辞

## 禁止事项
- 不提供具体投资建议（如"买入某股票"）
- 不做收益预测或承诺
- 不替用户做出财务决策',
    '["report", "alerts", "allocation", "disposal"]'::jsonb,
    TRUE,
    100
);

-- 内置 Agent 2: 财务优化师
INSERT INTO agent_registry (
    family_id, agent_name, display_name, description,
    icon, color, soul_md, skills, is_builtin, display_order
) VALUES (
    0,
    'finance-optimizer',
    '财务优化师',
    '分析家庭负债结构和消费漏洞，提供优化建议和还款策略',
    '💰',
    '#F59E0B',
    '你是一位专业的财务优化师。你的职责是帮助用户识别财务漏洞，优化负债结构，制定科学的还款策略。

## 核心能力
- **负债分析**：评估负债健康度，识别高利率负债、还款压力过大的负债
- **消费漏洞扫描**：识别重复支出、低价值订阅、可替代的高成本服务

## 工作原则
1. 省钱优先：优先识别可立即削减的无意义支出
2. 利率敏感：高利率负债优先偿还
3. 心理友好：建议循序渐进，不一次性要求用户大幅改变消费习惯
4. 长期视角：关注优化后的长期收益，而非短期节省金额

## 禁止事项
- 不提供具体投资建议
- 不推荐具体金融产品
- 不替用户做出财务决策',
    '["liability", "spending_leak"]'::jsonb,
    TRUE,
    200
);
```

---

## 4. Backend API Design

### 4.1 Router: ai_agents.py

```python
# server/apps/backend/app/routers/ai_agents.py

from fastapi import APIRouter, Depends, HTTPException
from typing import List
from ..schemas.agent import (
    AgentResponse, AgentListResponse, AgentCreateRequest,
    AgentUpdateRequest, AgentStreamRequest
)
from ..services.agent_registry_service import AgentRegistryService
from ..auth import get_current_family, require_owner

router = APIRouter(prefix="/ai/agents", tags=["AI Agents"])

@router.get("", response_model=AgentListResponse)
async def list_agents(
    family_id: int = Depends(get_current_family),
    service: AgentRegistryService = Depends(),
) -> AgentListResponse:
    """
    列出所有可见 Agent。
    - 内置 Agent（family_id=0）
    - 当前家庭的自定义 Agent
    """
    return await service.list_for_family(family_id)


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(
    agent_id: int,
    family_id: int = Depends(get_current_family),
    service: AgentRegistryService = Depends(),
) -> AgentResponse:
    """获取单个 Agent 详情"""
    return await service.get(agent_id, family_id)


@router.post("", response_model=AgentResponse, status_code=201)
async def create_agent(
    req: AgentCreateRequest,
    family_id: int = Depends(get_current_family),
    user_id: int = Depends(require_owner),
    service: AgentRegistryService = Depends(),
) -> AgentResponse:
    """
    创建自定义 Agent。
    - 仅 owner 可操作
    - agent_name 必须符合格式约束且不与已有 Agent 冲突
    """
    return await service.create(family_id, req, user_id)


@router.put("/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: int,
    req: AgentUpdateRequest,
    family_id: int = Depends(get_current_family),
    user_id: int = Depends(require_owner),
    service: AgentRegistryService = Depends(),
) -> AgentResponse:
    """
    更新 Agent 配置。
    - 内置 Agent：仅允许修改 icon、color、display_order
    - 自定义 Agent：允许修改所有字段
    """
    return await service.update(agent_id, family_id, req)


@router.delete("/{agent_id}", status_code=204)
async def delete_agent(
    agent_id: int,
    family_id: int = Depends(get_current_family),
    user_id: int = Depends(require_owner),
    service: AgentRegistryService = Depends(),
) -> None:
    """
    删除自定义 Agent。
    - 内置 Agent（is_builtin=TRUE）不可删除，返回 403
    """
    await service.delete(agent_id, family_id)


@router.put("/{agent_id}/toggle", response_model=AgentResponse)
async def toggle_agent(
    agent_id: int,
    enabled: bool,
    family_id: int = Depends(get_current_family),
    user_id: int = Depends(require_owner),
    service: AgentRegistryService = Depends(),
) -> AgentResponse:
    """启用/禁用 Agent"""
    return await service.toggle(agent_id, family_id, enabled)
```

### 4.2 Stream Endpoint (in Agent Service)

```python
# server/apps/agent/app/routers/agent_gateway.py

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from ..services.orchestrator import stream_agent_dispatch
from ..core.backend_client import get_family_context

router = APIRouter(prefix="/agent", tags=["Agent Gateway"])

@router.post("/{agent_id}/stream")
async def stream_agent(
    agent_id: int,
    family_id: int = Depends(get_family_context),
    thread_id: str = None,
    message: str,
    enable_thinking: bool = False,
):
    """
    Agent 执行流式入口。
    返回 NDJSON 事件流。
    """
    return StreamingResponse(
        stream_agent_dispatch(
            agent_id=agent_id,
            family_id=family_id,
            thread_id=thread_id,
            message=message,
            enable_thinking=enable_thinking,
        ),
        media_type="application/x-ndjson",
    )
```

### 4.3 Schema Definitions

```python
# server/apps/backend/app/schemas/agent.py

from pydantic import BaseModel, Field, field_validator
from typing import List, Optional
from datetime import datetime

class AgentBase(BaseModel):
    agent_name: str = Field(..., min_length=1, max_length=64)
    display_name: str = Field(..., min_length=1, max_length=128)
    description: Optional[str] = None
    icon: Optional[str] = Field(None, max_length=16)
    color: Optional[str] = Field(None, max_length=16)
    soul_md: str = Field(..., min_length=10)
    skills: Optional[List[str]] = None
    model: Optional[str] = None
    subagent_enabled: bool = False
    tool_groups: Optional[List[str]] = None

    @field_validator('agent_name')
    @classmethod
    def validate_agent_name(cls, v):
        import re
        if not re.match(r'^[a-z][a-z0-9_-]*$', v):
            raise ValueError('agent_name 必须以小写字母开头，仅包含小写字母、数字、下划线和连字符')
        return v

class AgentCreateRequest(AgentBase):
    pass

class AgentUpdateRequest(BaseModel):
    display_name: Optional[str] = None
    description: Optional[str] = None
    icon: Optional[str] = None
    color: Optional[str] = None
    soul_md: Optional[str] = None
    skills: Optional[List[str]] = None
    model: Optional[str] = None
    subagent_enabled: Optional[bool] = None
    tool_groups: Optional[List[str]] = None
    display_order: Optional[int] = None

class AgentResponse(AgentBase):
    id: int
    family_id: int
    is_builtin: bool
    is_enabled: bool
    display_order: int
    created_by: Optional[int]
    created_at: datetime
    updated_at: datetime

    # 前端辅助字段
    can_edit: bool  # True 如果当前用户可以编辑
    can_delete: bool  # True 如果当前用户可以删除

class AgentListResponse(BaseModel):
    builtin: List[AgentResponse]  # 内置 Agent 列表
    custom: List[AgentResponse]   # 当前家庭的自定义 Agent
```

---

## 5. Agent Execution Flow

### 5.1 orchestrator.stream_agent_dispatch()

```python
# server/apps/agent/services/orchestrator.py

import tempfile
import shutil
from pathlib import Path
import yaml
from typing import AsyncGenerator

from deerflow.agents.lead_agent.agent import make_lead_agent
from deerflow.config.app_config import reload_app_config
from langchain_core.messages import HumanMessage
from langgraph.types import RunnableConfig

from .schemas import StreamChunk
from .output_mapper import map_harness_event_to_chunk
from ..core.backend_client import BackendClient

async def stream_agent_dispatch(
    agent_id: int,
    family_id: int,
    thread_id: str,
    message: str,
    enable_thinking: bool = False,
) -> AsyncGenerator[StreamChunk, None]:
    """
    Agent-first 执行入口。
    完整复用 DeerFlow harness 的 make_lead_agent 链路。
    """

    # 1. 从 backend 获取 Agent 配置
    backend = BackendClient()
    agent_config = await backend.get_agent_config(agent_id, family_id)

    # 2. 权限校验
    if agent_config.family_id != 0 and agent_config.family_id != family_id:
        yield StreamChunk(type="error", content="Agent 不属于当前家庭")
        return

    if not agent_config.is_enabled:
        yield StreamChunk(type="error", content="Agent 已禁用")
        return

    # 3. 构建临时 Agent 目录
    temp_dir = Path(tempfile.mkdtemp(prefix=f"agent_{agent_id}_f{family_id}_"))
    soul_path = temp_dir / "SOUL.md"
    config_path = temp_dir / "config.yaml"

    # 写入 SOUL.md
    soul_path.write_text(agent_config.soul_md)

    # 写入 config.yaml
    config_data = {
        "name": agent_config.agent_name,
        "model": agent_config.model or "inherit",
        "skills": agent_config.skills or [],  # 空列表表示无限制
        "tool_groups": agent_config.tool_groups or [],
        "subagent_enabled": agent_config.subagent_enabled,
    }
    config_path.write_text(yaml.dump(config_data))

    # 4. 构建 RunnableConfig
    runnable_config = RunnableConfig(
        configurable={
            "agent_name": agent_config.agent_name,
            "agent_dir": str(temp_dir),
            "thread_id": thread_id,
            "thinking_enabled": enable_thinking,
            "subagent_enabled": agent_config.subagent_enabled,
        },
        context={
            "user_id": str(family_id),  # DeerFlow 的 user_id 映射为 family_id
        }
    )

    # 5. 刷新 DeerFlow 全局配置（注入临时 agent 目录）
    reload_app_config(str(temp_dir))

    # 6. 创建 LangGraph agent
    agent = make_lead_agent(runnable_config)

    # 7. 执行并流式返回事件（LangGraph agent.stream() 方法）
    try:
        input_state = {"messages": [HumanMessage(content=message)]}
        # LangGraph stream 返回事件字典，每个事件包含 event_type 和 data
        for event in agent.stream(input_state, config=runnable_config):
            chunk = map_harness_event_to_chunk(event)
            if chunk:
                yield chunk
    finally:
        # 8. 清理临时目录（延迟清理策略：保留用于后续追问）
        # 实际实现中应使用 LRU 缓存管理 temp_dir 生命周期
        pass
```

### 5.2 Event Mapping (output_mapper.py)

```python
# server/apps/agent/services/output_mapper.py

from .schemas import StreamChunk
from typing import Any, Optional

def map_harness_event_to_chunk(event: dict) -> Optional[StreamChunk]:
    """
    将 DeerFlow harness 事件映射为 StreamChunk。
    DeerFlow 事件类型:
    - on_chain_start: agent 开始
    - on_chain_end: agent 结束
    - on_llm_stream: token 输出（含 thinking/content 区分）
    - on_tool_start: 工具调用开始
    - on_tool_end: 工具调用结束
    - on_custom_event: 自定义事件（artifacts、todos 等）
    """

    event_type = event.get("event")

    if event_type == "on_llm_stream":
        data = event.get("data", {})
        token = data.get("chunk", {}).get("content", "")
        is_thinking = data.get("chunk", {}).get("additional_kwargs", {}).get("is_thinking", False)
        return StreamChunk(
            type="thinking" if is_thinking else "text",
            content=token,
        )

    elif event_type == "on_tool_start":
        tool_name = event.get("name", "unknown")
        tool_input = event.get("data", {}).get("input", {})
        return StreamChunk(
            type="tool_call",
            content=json.dumps({
                "tool": tool_name,
                "arguments": tool_input,
            }),
        )

    elif event_type == "on_tool_end":
        tool_name = event.get("name", "unknown")
        tool_output = event.get("data", {}).get("output", {})
        return StreamChunk(
            type="tool_result",
            content=json.dumps({
                "tool": tool_name,
                "result": tool_output,
            }),
        )

    elif event_type == "on_custom_event":
        custom_type = event.get("name")
        if custom_type == "artifact_presented":
            return StreamChunk(
                type="artifact",
                content=json.dumps(event.get("data")),
            )
        elif custom_type == "todos_updated":
            return StreamChunk(
                type="todos",
                content=json.dumps(event.get("data")),
            )

    elif event_type == "on_chain_end":
        return StreamChunk(type="end", content="")

    return None
```

### 5.3 Temp Directory Cache Strategy

临时 Agent 目录的生命周期管理：

```python
# server/apps/agent/services/agent_temp_cache.py

from pathlib import Path
import tempfile
import time
from collections import OrderedDict
from typing import Tuple

class AgentTempCache:
    """
    LRU 缓存管理 Agent 临时目录。
    - 缓存键: (agent_id, family_id)
    - 缓存值: (temp_dir_path, created_at, last_used_at)
    - 最大容量: 100
    - 过期时间: 30 分钟未使用
    """

    MAX_SIZE = 100
    EXPIRE_SECONDS = 1800  # 30 min

    _cache: OrderedDict[Tuple[int, int], Tuple[Path, float, float]] = OrderedDict()
    _lock = threading.Lock()

    @classmethod
    def get_or_create(cls, agent_id: int, family_id: int, soul_md: str, config_data: dict) -> Path:
        key = (agent_id, family_id)
        with cls._lock:
            if key in cls._cache:
                dir_path, created, last_used = cls._cache[key]
                cls._cache[key] = (dir_path, created, time.time())
                cls._cache.move_to_end(key)
                return dir_path

            # 创建新目录
            temp_dir = Path(tempfile.mkdtemp(prefix=f"agent_{agent_id}_f{family_id}_"))
            (temp_dir / "SOUL.md").write_text(soul_md)
            (temp_dir / "config.yaml").write_text(yaml.dump(config_data))

            # 检查容量，驱逐最旧
            if len(cls._cache) >= cls.MAX_SIZE:
                oldest_key = next(iter(cls._cache))
                oldest_dir = cls._cache[oldest_key][0]
                shutil.rmtree(oldest_dir, ignore_errors=True)
                cls._cache.pop(oldest_key)

            cls._cache[key] = (temp_dir, time.time(), time.time())
            return temp_dir

    @classmethod
    def cleanup_expired(cls):
        """后台任务：清理过期目录"""
        now = time.time()
        with cls._lock:
            to_remove = []
            for key, (dir_path, created, last_used) in cls._cache.items():
                if now - last_used > cls.EXPIRE_SECONDS:
                    to_remove.append(key)

            for key in to_remove:
                dir_path = cls._cache[key][0]
                shutil.rmtree(dir_path, ignore_errors=True)
                cls._cache.pop(key)
```

---

## 6. Frontend Design

### 6.1 AI Hub Page Redesign

**文件**: `frontend/apps/main/src/pages/AIHubPage.vue`

**布局结构**:
```
┌─────────────────────────────────────────────────┐
│  Header: 欢迎语 + 健康评分环 (保留)              │
├─────────────────────────────────────────────────┤
│  Stats Bar: 建议数/预警数/完整度/报告时间 (保留) │
├─────────────────────────────────────────────────┤
│  Section: 内置智能体                            │
│  ┌───────────────┐  ┌───────────────┐          │
│  │ 资产健康顾问   │  │ 财务优化师     │          │
│  │ 🏥            │  │ 💰            │          │
│  │ "全面监控..." │  │ "分析负债..." │          │
│  │ [立即咨询]    │  │ [立即咨询]    │          │
│  └───────────────┘  └───────────────┘          │
├─────────────────────────────────────────────────┤
│  Section: 我的智能体                            │
│  ┌───────────────┐  ┌───────────────┐  ┌───┐  │
│  │ 我的理财助手   │  │ 预算追踪器     │  │ + │  │
│  │ 🎯            │  │ 📊            │  │   │  │
│  │ [对话] [编辑] │  │ [对话] [编辑] │  │   │  │
│  └───────────────┘  └───────────────┘  └───┘  │
├─────────────────────────────────────────────────┤
│  Chat Input Bar (保留，用于快速对话入口)        │
└─────────────────────────────────────────────────┘
```

### 6.2 Agent Result Page (Builtin Agents)

**文件**: `frontend/apps/main/src/pages/AgentResultPage.vue`

**布局结构**:
```
┌─────────────────────────────────────────────────┐
│  Header: Agent 名称 + 执行时间                  │
├─────────────────────────────────────────────────┤
│  Structured Result Section                      │
│  ┌─────────────────────────────────────────┐   │
│  │  (取决于 Agent 类型)                     │   │
│  │  - 资产健康顾问: 评分卡 + 预警列表 + 配置图 │   │
│  │  - 财务优化师: 负债健康图 + 漏洞列表      │   │
│  └─────────────────────────────────────────┘   │
├─────────────────────────────────────────────────┤
│  Tool Timeline (collapsible)                    │
│  ┌─────────────────────────────────────────┐   │
│  │  🔧 read_file(SKILL.md)  ✅              │   │
│  │  🔧 get_dashboard()      ✅              │   │
│  │  🔧 analyze_assets()     ✅              │   │
│  └─────────────────────────────────────────┘   │
├─────────────────────────────────────────────────┤
│  Conversation Follow-up Section                 │
│  ┌─────────────────────────────────────────┐   │
│  │  Chat history (如果已有追问)              │   │
│  │  ┌─────────────────────────────────────┐│   │
│  │  │ User: 这些预警怎么处理？             ││   │
│  │  │ Agent: 我来逐条分析...               ││   │
│  │  └─────────────────────────────────────┘│   │
│  │  Input: [继续追问...]                   │   │
│  └─────────────────────────────────────────┘   │
└─────────────────────────────────────────────────┘
```

### 6.3 Agent Create Form

**文件**: `frontend/apps/main/src/pages/AgentCreatePage.vue`

**表单字段**:
```
┌─────────────────────────────────────────────────┐
│  Header: 创建智能体                             │
├─────────────────────────────────────────────────┤
│  Basic Info                                     │
│  ├─ 名称: [输入框]                              │
│  ├─ 描述: [输入框]                              │
│  ├─ 头像: [Emoji Picker] (20 个选项)            │
│  └─ 颜色: [Color Picker] (8 个 hex 选项)        │
├─────────────────────────────────────────────────┤
│  Personality (SOUL.md)                          │
│  ├─ [Markdown 编辑器]                           │
│  │  提示: "定义智能体的性格、价值观、工作原则"   │
│  ├─ [预览按钮]                                  │
├─────────────────────────────────────────────────┤
│  Capabilities                                   │
│  ├─ 可用技能: [Checkbox 列表]                   │
│  │  ☐ report (资产体检)                        │
│  │  ☐ alerts (老化预警)                        │
│  │  ☐ allocation (配置分析)                    │
│  │  ☐ disposal (闲置处置)                      │
│  │  ☐ liability (负债分析)                     │
│  │  ☐ spending_leak (消费漏洞)                 │
│  ├─ 模型选择: [下拉框]                          │
│  │  - 继承家庭默认                              │
│  │  - claude-haiku-4-5                         │
│  │  - claude-sonnet-4-6                        │
│  │  - deepseek-r1                              │
│  ├─ 子智能体: [Toggle] 启用/禁用                │
├─────────────────────────────────────────────────┤
│  [保存] [取消]                                  │
└─────────────────────────────────────────────────┘
```

### 6.4 Component Tree

```
src/pages/
├── AIHubPage.vue          # 改造: Agent 卡片网格替代 capability grid
├── AgentResultPage.vue    # 新增: 内置 Agent 结果页 + 对话追问
├── AgentCreatePage.vue    # 新增: 创建/编辑 Agent 表单
├── AIChatPage.vue         # 改造: 自定义 Agent 对话入口
├── AIConfigPage.vue       # 保留: AI provider 配置
└── ...

src/components/agent/
├── AgentCard.vue          # Agent 卡片组件 (icon + name + desc + action)
├── AgentGrid.vue          # Agent 卡片网格布局
├── AgentResultPanel.vue   # 结构化结果渲染 (按 agent_type 分支)
├── AgentChatSection.vue   # 对话追问区域 (嵌入结果页)
├── AgentCreateForm.vue    # 创建表单组件
├── SoulMdEditor.vue       # SOUL.md Markdown 编辑器
├── SkillSelector.vue      # Skill 勾选组件
└── ModelSelector.vue      # 模型下拉选择器

src/stores/
├── agentStore.ts          # Pinia store: Agent 列表、当前 Agent、CRUD
├── agentEventStore.ts     # Pinia store: 执行事件流状态

src/api/
├── agent.ts               # Agent CRUD API + stream API
├── agentStream.ts         # NDJSON 事件流解析
```

---

## 7. Skill System Changes

### 7.1 Skill Definition Files (No Change in Format)

Skill 文件格式保持不变，继续遵循 DeerFlow SKILL.md 规范：

```yaml
---
name: report
description: 家庭资产体检 - 全面评估家庭资产健康度
trigger_phrases:
  - 资产体检
  - 健康评估
  - 资产状况
allowed_tools:
  - get_dashboard
  - get_assets
  - get_liabilities
thinking: true
---

## 执行流程

1. 获取用户家庭资产和负债数据
2. 计算净资产、资产配置比例、负债率
3. 识别风险资产（老化、高维护、闲置）
4. 输出结构化体检报告

## 输出格式

输出必须包含 `<!-- STRUCTURED_DATA -->` 块...
```

### 7.2 Skill Loading (Harness Native)

Skill 的加载和调度完全由 DeerFlow harness 处理：

1. Agent 的 system prompt 包含 `<skill_system>` 块，列出可用 skill
2. Agent 根据对话内容判断是否需要调用 skill
3. Agent 调用 `read_file(SKILL.md)` 读取 skill 定义
4. Agent 按 skill 定义的流程执行，使用 `allowed_tools` 中的工具

**Numina 不再自建 SkillLoader**，完全复用 harness 的 skill 加载机制。

### 7.3 Skill Storage Path

```
server/apps/agent/skills/
├── builtin/
│   ├── report/SKILL.md
│   ├── alerts/SKILL.md
│   ├── allocation/SKILL.md
│   ├── disposal/SKILL.md
│   ├── liability/SKILL.md
│   └── spending_leak/SKILL.md
└── custom/
    └── {family_id}/
        └── {skill_name}/SKILL.md  # 用户创建的自定义 skill (保留现有功能)
```

Harness 的 `skills.paths` 配置注入（在 `_generate_temp_config()` 中动态替换）：
```yaml
# deerflow_config/base/config.yaml (模板)
skills:
  paths:
    - /app/apps/agent/skills/builtin
    # 以下路径在生成 temp config 时动态注入，用实际 family_id 替换
    # - /app/apps/agent/skills/custom/{family_id}
```

**动态注入实现**：在 `family_adapter_cache._generate_temp_config()` 中读取模板 YAML，检测 `{family_id}` 占位符并替换为实际值，然后写入临时配置文件。

---

## 8. Migration Strategy

### 8.1 Phase Overview

| Phase | 名称 | 目标 | 时间估计 |
|-------|------|------|----------|
| P0 | 数据层准备 | agent_registry 表、种子数据、Backend CRUD API | 2-3 天 |
| P1 | 执行链路重构 | orchestrator 改造、make_lead_agent 集成 | 3-4 天 |
| P2 | 前端 Hub 改造 | Agent 卡片网格、Agent 结果页 | 3-4 天 |
| P3 | Agent 创建功能 | 创建表单、SOUL.md 编辑器 | 2-3 天 |
| P4 | 清理与文档 | 移除旧 router、更新 CLAUDE.md | 1-2 天 |

### 8.2 Phase P0: Data Layer

**Tasks**:
1. 创建 `agent_registry` 表的 Alembic migration
2. 实现种子数据 migration（插入 2 个内置 Agent）
3. 实现 `AgentRegistryService`（CRUD + 权限校验）
4. 实现 Backend router `ai_agents.py`
5. 添加 `/internal/agents/{agent_id}` API（供 Agent Service 调用）
6. 单元测试：Agent CRUD、权限校验

**验收标准**:
- `GET /ai/agents` 返回内置 + 自定义 Agent 列表
- owner 可以创建/编辑/删除自定义 Agent
- 非 owner 只能使用，不能修改

### 8.3 Phase P1: Execution Refactor

**Tasks**:
1. 重构 `orchestrator.py`：新增 `stream_agent_dispatch()`
2. 实现 `AgentTempCache`（临时目录 LRU 管理）
3. 实现 `map_harness_event_to_chunk()`（事件映射）
4. 删除旧的 skill router（alerts.py、allocation.py 等）— 或保留为 fallback
5. 新增 Agent gateway router：`/agent/{agent_id}/stream`
6. 集成测试：Agent 执行流、多轮追问

**验收标准**:
- `POST /agent/{agent_id}/stream` 返回 NDJSON 事件流
- 事件流包含：thinking、text、tool_call、tool_result、artifact
- 多轮追问走同一个 thread_id，Agent 有记忆

### 8.4 Phase P2: Frontend Hub

**Tasks**:
1. 改造 `AIHubPage.vue`：Agent 卡片网格替代 capability grid
2. 实现 `AgentCard.vue` 组件
3. 实现 `AgentGrid.vue` 布局
4. 改造 Hub → Agent 跳转逻辑
5. 实现 `AgentResultPage.vue`（内置 Agent 结果页）
6. 实现 `AgentResultPanel.vue`（按 Agent 类型渲染结构化结果）
7. 实现 `AgentChatSection.vue`（对话追问区域）
8. 实现 `agentStore.ts`（Pinia state management）

**验收标准**:
- Hub 显示 2 个内置 Agent + 用户自定义 Agent
- 点击内置 Agent → 执行 → 显示结构化结果页
- 结果页底部可追问，追问内容嵌入对话区域

### 8.5 Phase P3: Agent Create

**Tasks**:
1. 实现 `AgentCreatePage.vue`
2. 实现 `AgentCreateForm.vue` 组件
3. 实现 `SoulMdEditor.vue`（Markdown 编辑 + 预览）
4. 实现 `SkillSelector.vue`（Checkbox 勾选）
5. 实现 `ModelSelector.vue`（下拉选择）
6. 前端 API `agent.ts`：create、update、delete
7. 权限控制：只有 owner 可见创建按钮

**验收标准**:
- owner 可以创建自定义 Agent（名称、描述、头像、SOUL.md、skill 勾选、模型、subagent）
- 创建成功后 Agent 卡片出现在 Hub
- 编辑/删除功能正常

### 8.6 Phase P4: Cleanup

**Tasks**:
1. 删除旧 router（alerts.py、allocation.py、disposal.py、liability.py、report.py、spending_leak.py）
2. 删除旧 frontend pages（AIAlertsPage.vue 等）
3. 更新 `server/apps/agent/CLAUDE.md`
4. 更新 `frontend/apps/main/CLAUDE.md`
5. 更新路由配置
6. 端到端测试

**验收标准**:
- 所有旧 skill router 已删除
- 所有旧 frontend pages 已删除
- 文档更新完成
- 端到端流程正常

---

## 9. API Summary

### 9.1 New APIs

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/ai/agents` | GET | 列出 Agent（内置 + 自定义） |
| `/ai/agents` | POST | 创建自定义 Agent |
| `/ai/agents/{id}` | GET | 获取 Agent 详情 |
| `/ai/agents/{id}` | PUT | 更新 Agent 配置 |
| `/ai/agents/{id}` | DELETE | 删除自定义 Agent |
| `/ai/agents/{id}/toggle` | PUT | 启用/禁用 Agent |
| `/agent/{id}/stream` | POST | Agent 执行（NDJSON） |

### 9.2 Deprecated APIs (to remove in P4)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/alerts` | POST | 资产老化预警（被 Agent 取代） |
| `/allocation` | POST | 资产配置分析（被 Agent 取代） |
| `/disposal` | POST | 闲置资产处置（被 Agent 取代） |
| `/liability` | POST | 负债健康分析（被 Agent 取代） |
| `/report` | POST | 家庭资产体检（被 Agent 取代） |
| `/spending_leak` | POST | 消费漏洞扫描（被 Agent 取代） |

### 9.3 Retained APIs

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/chat/ask` | POST | 通用对话（保留） |
| `/chat/ask/stream` | POST | 对话流式（保留） |
| `/time_machine` | POST | 资产时光机（保留，作为固定能力） |
| `/sessions` | GET | 会话列表（保留） |
| `/sessions/{id}/events` | GET | 会话事件（保留） |

---

## 10. Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| harness API 变更 | 锁定 harness 版本（`.vendor-manifest.json`），定期同步 |
| 临时目录清理 | AgentTempCache + 后台清理任务 |
| 多轮对话记忆丢失 | ThreadState + SqliteSaver checkpointer，thread_id 持久化 |
| 前端事件流解析错误 | 严格 NDJSON 格式，前端容错处理 |
| 租户权限遗漏 | Service 层统一校验，单元测试覆盖 |

---

## 11. Resolved Decisions

1. **内置 Agent 的结构化结果格式**
   - **决策**：每个 skill 的 SKILL.md 中定义输出格式（包含 `<!-- STRUCTURED_DATA -->` 块），前端根据 Agent 类型选择渲染器组件（如 `AgentResultPanel.vue` 按 `agent_name` 分支渲染）

2. **用户创建 Agent 时 SOUL.md 的模板**
   - **决策**：提供 2-3 个预设模板（财务顾问模板、预算追踪模板），用户可在模板基础上修改。模板列表存储在前端，创建表单提供"从模板创建"选项

3. **Chat 功能的归属**
   - **决策**：Chat 和 time_machine 保持为固定能力，不属于 Agent 系统。用户无需创建或配置这些功能，它们始终可用且不可禁用

---

## 12. Appendix: SOUL.md Templates

### A. 财务顾问模板

```markdown
你是一位专业的家庭财务顾问。你的职责是帮助用户管理和优化家庭财务。

## 核心能力
- 资产分析
- 负债分析
- 支出优化

## 工作原则
1. 数据驱动：基于用户实际数据进行分析
2. 可操作性：每条建议都要有具体执行路径
3. 保守表达：不确定的结论使用谨慎措辞

## 禁止事项
- 不提供具体投资建议
- 不推荐具体金融产品
```

### B. 预算追踪模板

```markdown
你是一位家庭预算追踪助手。你的职责是帮助用户监控日常支出，识别超支风险。

## 核心能力
- 消费漏洞扫描
- 预算提醒
- 支出趋势分析

## 工作原则
1. 及时提醒：发现超支趋势立即告知用户
2. 渐进改善：建议循序渐进的优化方案
```

---

**End of Spec**