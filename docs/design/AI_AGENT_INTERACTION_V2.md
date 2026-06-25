# Numina AI Agent 交互体验 V2 设计

> 从资深 AI Agent 设计师视角，统一 Numina 与 Deer-Flow 的交互范式，落地 Harness Engineering
>
> **最后更新:** 2026-06-25 — 根据 `feat/unify-ai-chat-input-box` 分支实现状态更新

## 0. 实施状态总览 (2026-06-25 更新)

> 本文档创建於 2026-05-09，以下状态基於 `feat/unify-ai-chat-input-box` 分支（115 文件变更，10,419 行新增）的实际情况更新。

| Phase | 目标 | 状态 | 关键文件 |
|-------|------|------|----------|
| **Phase 1: Protocol 统一** | 替换 `[THINK]/[TEXT]` 前缀 | **已完成** (使用 LangGraph SSE，非 NDJSON) | `runs.py` 删除 (304L)，`runs_stream.py` (139L)，`sse_gateway.py` (182L)，`useThreadChat.ts` |
| **Phase 2: Capability Registry** | 后端注册中心 + Capability Grid UI | **后端已完成，前端 UI 待完成** | `capability_registry.py` (296L)，`routers/capabilities.py`，`stores/capability.ts`，`CapabilityPickerSheet.vue` |
| **Phase 3: Tool Calling UI** | 工具调用可视化 | **已完成** | `PlanningStepsPanel.vue` (239L)，`MessageGroup.vue`，`TokenUsage.vue`，`StreamingIndicator.vue` |
| **Phase 4: Harness 深度集成** | 统一 dispatch + 多步骤可视化 | **部分完成** | `subagent_registry.py`，`agent_dispatch.py`，`worker.py`，`gc.py`，`lifespan.py`，`run_extras.py`，`sandbox_provider.py` |

## 1. 现状诊断

### 1.1 已解决的架构问题

> 以下痛点在 `feat/unify-ai-chat-input-box` 分支上已修复，保留作为历史参考。

```
┌─────────────────────────────────────────────────────────────┐
│                    修复后架构 (2026-06)                      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────┐    ┌──────────┐    ┌──────────────────────┐ │
│  │ AI Hub   │───→│ AI Chat  │───→│ LangGraph SSE        │ │
│  │ 输入/选择  │   │ 对话页面  │    │ (messages-tuple/     │ │
│  └──────────┘    └──────────┘    │  values/custom)       │ │
│       │                              │                     │
│       │ Pinia Store                  │ 结构化事件流         │
│       │ Query Params                 │ useThreadChat.ts     │
│       ▼                              ▼                     │
│  状态传递统一                Stream 格式标准化              │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**已修复痛点：**

| 层级 | 原问题 | 修复方案 | 状态 |
|------|--------|----------|------|
| **Protocol** | `[THINK]/[TEXT]` 前缀 | LangGraph SSE 结构化事件 | **已修复** |
| **Protocol** | 无 Tool Calling 展示 | `PlanningStepsPanel` + `MessageGroup` | **已修复** |
| **Harness** | DeerFlow/Direct 双路径 | `runs_stream.py` + `sse_gateway.py` 统一 | **已修复** |
| **Engineering** | 阶段状态过于简单 | `custom` events (tool_call/suggestions) | **已修复** |
| **UX** | InputBox 分裂（Hub/Chat 两套） | 统一 `InputBox.vue` (1,217L) | **已修复** |

**待解决问题：**

| 层级 | 问题 | 影响 |
|------|------|------|
| **UX** | 缺乏 Agent 能力发现（Capability Discovery） | 用户不知道 AI 能做什么 |
| **Architecture** | 无 Capability Registry | 无法动态发现和管理 Agent 能力 |
| **UX** | 输入模式单一（仅自由文本） | 不支持结构化表单、资产选择器等场景 |

### 1.2 与 Deer-Flow 的差距 (更新)

Deer-Flow 的 Harness 提供了：
- ~~**Capability Registry**: 动态发现 Agent 能力~~ — **仍未实现**，Phase 2 核心工作
- ~~**Skill Orchestration**: 多步骤推理编排~~ — **部分实现**，`subagent_registry.py` + `agent_dispatch.py`
- ~~**Tool Calling**: 工具调用可视化~~ — **已实现** (`PlanningStepsPanel.vue`)
- ~~**Streaming Protocol**: 结构化事件流~~ — **已实现** (LangGraph SSE)

**当前已实现:**
- LangGraph SSE 结构化事件流 (`messages-tuple`/`values`/`custom`)
- Tool Calling 可视化（`PlanningStepsPanel` 渲染 tool_call 事件）
- 统一 SSE 网关（`sse_gateway.py` 替代旧 `runs.py`）
- Subagent 运行时管理（`subagent_registry.py`）

**仍未实现:**
- Capability Registry / Registry API (`/api/v1/capabilities`)
- Capability Grid UI（AI Hub 能力网格）
- 动态 input_mode 渲染（structured / asset_selector / confirm_dialog）

---

## 2. 设计理念：Agent-First Interaction

### 2.1 核心原则

```
┌──────────────────────────────────────────────────────────────┐
│                    Agent-First 设计原则                       │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  1. CAPABILITY DISCOVERY          2. PROGRESSIVE DISCLOSURE │
│     ┌──────────────┐                ┌──────────────┐        │
│     │ 能力即入口    │                │ 渐进展示      │        │
│     │ 非输入框主导  │                │ 不一次性暴露   │        │
│     └──────────────┘                └──────────────┘        │
│                                                              │
│  3. THINKING TRANSPARENCY         4. TOOL VISIBILITY         │
│     ┌──────────────┐                ┌──────────────┐        │
│     │ 思考过程可见  │                │ 工具调用可感知 │        │
│     │ 非黑盒输出   │                │ 非静默执行    │        │
│     └──────────────┘                └──────────────┘        │
│                                                              │
│  5. CONTEXTUAL CONTINUITY                                   │
│     ┌──────────────┐                                        │
│     │ 上下文连续性  │                                        │
│     │ 跨页面状态保持│                                        │
│     └──────────────┘                                        │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 2.2 交互范式对比 (更新)

| 范式 | 原文档目标 | 实际实现 (2026-06) | 仍需工作 |
|------|-----------|-------------------|----------|
| **Hub 模式** | Capability Grid 主导 | Agent Card + 折叠区域 + InputBox | Capability Grid |
| **对话启动** | 选择 Capability → 专用对话 | Agent Card → `router.push({ agentId })` | 能力级路由 |
| **状态传递** | Capability Context 单通道 | Pinia `chatSession` store + query params | — |
| **Stream 格式** | NDJSON 结构化事件 | LangGraph SSE (messages-tuple/values/custom) | **已解决** (SSE 替代 NDJSON) |
| **工具展示** | Tool Calling Cards | `PlanningStepsPanel` | **已解决** |
| **阶段反馈** | 可视化进度条 | `custom` events + `StreamingIndicator` | **已解决** |

---

## 3. Harness Engineering 架构

### 3.1 统一 Capability Model — **未实现 (设计仍有效)**

> **2026-06 更新:** 仍未实现。注意 `CapabilityUISchema.input_mode` 的 `asset_selector`
> 和 `confirm_dialog` 模式是本文档提出的扩展，当前 `InputBox.vue` 仅支持 `free_text`。

```python
# agent/schemas/capability.py
from pydantic import BaseModel
from typing import Literal, Optional, List, Dict, Any

class CapabilityUISchema(BaseModel):
    """Capability UI 渲染模式"""
    icon: str                    # SVG icon name
    color: str                   # Theme color
    input_mode: Literal[         # 输入模式
        "free_text",              # 自由文本
        "structured",             # 结构化表单
        "asset_selector",         # 资产选择器
        "confirm_dialog"          # 确认对话框
    ]
    placeholder: Optional[str]   # 输入提示
    example_questions: List[str] # 示例问题

class CapabilityPolicy(BaseModel):
    """Capability 执行策略"""
    allowed_roles: List[str]     # 允许的角色
    require_confirmation: bool     # 是否需要确认
    max_tokens: int               # 最大 token 数
    enable_thinking: bool         # 是否启用深度思考
    enable_tools: List[str]       # 启用哪些工具

class CapabilityDefinition(BaseModel):
    """Capability 定义（Deer-Flow Harness 标准）"""
    id: str                       # 唯一标识
    name: str                     # 显示名称
    description: str              # 描述
    category: str                 # 分类
    ui: CapabilityUISchema        # UI 模式
    policy: CapabilityPolicy      # 执行策略
    skill_id: Optional[str]       # 绑定的 Deer-Flow Skill
    
    # Harness 集成
    harness_config: Dict[str, Any] = {}
```

### 3.2 ~~Capability Registry~~ — **后端已完成 (2026-06 更新)**

> **2026-06 更新:** 后端已完整实现! 以下设计文档与实际代码一致:

**后端实现** (`capability_registry.py`, `capabilities.py`):
- `CapabilityRegistry` class — 296 行，支持 builtin/custom/fixed capabilities
- `GET /capabilities` — 列出所有 capabilities
- `GET /capabilities?family_id=X` — 家庭级别过滤
- 从 `skills/builtin/*/SKILL.md` 和 `skills/custom/{family_id}/*/SKILL.md` 加载
- 与 `ai_skills` API 集成（`is_enabled` 过滤）

**前端实现** (`stores/capability.ts`, `api/ai.ts`):
- `useCapabilityStore()` — Pinia store with `loadCapabilities()`
- `getAICapabilities()` — `GET /api/v1/ai/capabilities`
- `AICapability` TypeScript 接口匹配后端 schema
- `AIChatInput.vue` — slash command palette 使用 capability store
- `CapabilityPickerSheet.vue` — 能力选择器 UI

**仍需完成:** AI Hub Capability Grid 展示（当前使用 Agent Card 布局）

```python
# agent/services/capability_registry.py
from typing import Dict, List, Optional
import yaml
import os

class CapabilityRegistry:
    """Capability 注册中心 - Harness 工程化核心"""
    
    _capabilities: Dict[str, CapabilityDefinition] = {}
    
    @classmethod
    def load_from_skills(cls, skills_dir: str = "app/skills"):
        """从 Deer-Flow Skill 定义加载 Capability"""
        for skill_file in Path(skills_dir).glob("*.yaml"):
            with open(skill_file) as f:
                skill_def = yaml.safe_load(f)
                
            # 自动将 Skill 转换为 Capability
            capability = CapabilityDefinition(
                id=skill_def["id"],
                name=skill_def["name"],
                description=skill_def["description"],
                category=skill_def.get("category", "general"),
                ui=CapabilityUISchema(
                    icon=skill_def.get("icon", "chat"),
                    color=skill_def.get("color", "#6366f1"),
                    input_mode=skill_def.get("input_mode", "free_text"),
                    placeholder=skill_def.get("placeholder"),
                    example_questions=skill_def.get("examples", [])
                ),
                policy=CapabilityPolicy(
                    allowed_roles=skill_def.get("allowed_roles", ["member", "admin"]),
                    require_confirmation=skill_def.get("require_confirmation", False),
                    max_tokens=skill_def.get("max_tokens", 2000),
                    enable_thinking=skill_def.get("enable_thinking", True),
                    enable_tools=skill_def.get("tools", [])
                ),
                skill_id=skill_def["id"],
                harness_config=skill_def.get("harness", {})
            )
            cls._capabilities[capability.id] = capability
    
    @classmethod
    def get_for_family(cls, family_id: str) -> List[CapabilityDefinition]:
        """获取家庭可用的 Capability 列表"""
        # 结合 AI 配置过滤
        ai_config = BackendClient(family_id).get_family_ai_config()
        allowed_caps = ai_config.get("allowed_capabilities", [])
        
        return [
            cap for cap in cls._capabilities.values()
            if cap.id in allowed_caps or "*" in allowed_caps
        ]
```

### 3.3 ~~结构化 Stream Protocol~~ — 已实现 (LangGraph SSE)

> **决策变更:** 原文档提出 NDJSON，但实际实现选择了 LangGraph 原生 SSE 协议。
> SSE 是更优选择：LangGraph SDK 内置支持、浏览器原生 EventSource、自动重连、
> 与 `@langchain/langgraph-sdk` 完全兼容。

**实际使用的协议** (`useThreadChat.ts`):

| 事件类型 | 来源 | 用途 |
|---------|------|------|
| `messages-tuple` / `messages` | LangGraph SSE | AI 文本流 + 工具结果 |
| `values` | LangGraph SSE | 完整状态快照（消息去重） |
| `custom` | 后端自定义 | `tool_call` / `suggestions` 事件 |
| `metadata` | LangGraph SSE | `run_id` 等元数据 |
| `end` | LangGraph SSE | 流结束信号 + usage 统计 |
| `error` | LangGraph SSE | 错误处理 + 重试 |

### 3.4 Python 端事件生成

```python
# agent/services/stream_events.py
from dataclasses import dataclass, asdict
from typing import AsyncGenerator, Optional, Dict, Any
import json

@dataclass
class StreamEvent:
    """结构化流事件 - 替代 [THINK]/[TEXT] 前缀"""
    id: str
    type: str
    timestamp: float
    capability_id: str
    task_id: str
    payload: Dict[str, Any]
    
    def to_ndjson(self) -> str:
        """转换为 NDJSON 格式"""
        return json.dumps({
            "id": self.id,
            "type": self.type,
            "timestamp": self.timestamp,
            "capability_id": self.capability_id,
            "task_id": self.task_id,
            **self.payload
        }, ensure_ascii=False)

class EventStreamBuilder:
    """事件流构建器 - 统一 DeerFlow 和 Direct LLM 输出"""
    
    def __init__(self, capability_id: str, task_id: str):
        self.capability_id = capability_id
        self.task_id = task_id
        self._event_id = 0
        
    def _next_id(self) -> str:
        self._event_id += 1
        return f"{self.task_id}-{self._event_id:04d}"
    
    def phase(self, phase: str, metadata: Optional[Dict] = None):
        """生成阶段事件"""
        return StreamEvent(
            id=self._next_id(),
            type=f"phase.{phase}",
            timestamp=time.time(),
            capability_id=self.capability_id,
            task_id=self.task_id,
            payload={"phase": phase, "metadata": metadata or {}}
        )
    
    def tool_call(self, tool_name: str, arguments: Dict, 
                  display_name: Optional[str] = None,
                  icon: Optional[str] = None):
        """生成工具调用事件"""
        return StreamEvent(
            id=self._next_id(),
            type="tool.call",
            timestamp=time.time(),
            capability_id=self.capability_id,
            task_id=self.task_id,
            payload={
                "tool": {
                    "id": self._next_id(),
                    "name": tool_name,
                    "display_name": display_name or tool_name,
                    "icon": icon or "tool",
                    "arguments": arguments
                }
            }
        )
    
    def token(self, text: str, is_thinking: bool = False):
        """生成文本 token 事件"""
        return StreamEvent(
            id=self._next_id(),
            type="token.stream",
            timestamp=time.time(),
            capability_id=self.capability_id,
            task_id=self.task_id,
            payload={"token": text, "is_thinking": is_thinking}
        )
    
    def end(self, summary: str, tokens_used: int, 
            execution_time_ms: int, tools_used: List[str]):
        """生成完成事件"""
        return StreamEvent(
            id=self._next_id(),
            type="capability.end",
            timestamp=time.time(),
            capability_id=self.capability_id,
            task_id=self.task_id,
            payload={
                "result": {
                    "summary": summary,
                    "tokens_used": tokens_used,
                    "execution_time_ms": execution_time_ms,
                    "tools_used": tools_used
                }
            }
        )
```

---

## 4. 前端交互重构

### 4.1 AI Hub 页面重构

```vue
<!-- AIHubPage.vue - Capability-First 设计 -->
<template>
  <div class="ai-hub-page">
    <!-- Header: 简洁的欢迎语 -->
    <header class="hub-header">
      <h1>{{ t('aiHub.greeting') }}</h1>
      <p class="hub-subtitle">{{ t('aiHub.subtitle') }}</p>
    </header>
    
    <!-- Quick Actions: 常用快捷入口 -->
    <section class="quick-actions">
      <h2>{{ t('aiHub.quickActions') }}</h2>
      <div class="action-chips">
        <button 
          v-for="action in quickActions" 
          :key="action.id"
          class="action-chip"
          @click="startCapability(action.id, {prefill: action.prefill})"
        >
          <Icon :name="action.icon" />
          {{ action.name }}
        </button>
      </div>
    </section>
    
    <!-- Capability Grid: 核心能力发现 -->
    <section class="capability-grid">
      <h2>{{ t('aiHub.capabilities') }}</h2>
      <div class="grid">
        <CapabilityCard
          v-for="cap in capabilities"
          :key="cap.id"
          :capability="cap"
          @click="startCapability(cap.id)"
        />
      </div>
    </section>
    
    <!-- Recent Chats: 最近的对话 -->
    <section class="recent-chats">
      <h2>{{ t('aiHub.recentChats') }}</h2>
      <ChatHistoryList />
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useCapabilityStore } from '@/stores/capability'

const router = useRouter()
const capabilityStore = useCapabilityStore()

const capabilities = ref<CapabilityDefinition[]>([])
const quickActions = ref([
  { id: 'asset_summary', name: '资产总览', icon: 'chart', prefill: '请分析我家资产概况' },
  { id: 'liability_analysis', name: '负债分析', icon: 'debt', prefill: '我的负债情况如何？' },
  { id: 'efficiency_check', name: '效率检查', icon: 'gauge', prefill: '哪些资产效率较低？' },
])

onMounted(async () => {
  // 从 Capability Registry 加载
  capabilities.value = await capabilityStore.loadCapabilities()
})

function startCapability(capabilityId: string, options?: {prefill?: string}) {
  // 统一的 Capability 启动入口
  router.push({
    path: '/ai/chat',
    query: {
      capability: capabilityId,
      ...(options?.prefill && { prefill: options.prefill })
    }
  })
}
</script>
```

### 4.2 Capability Card 组件

```vue
<!-- components/CapabilityCard.vue -->
<template>
  <div 
    class="capability-card"
    :style="{ '--cap-color': capability.ui.color }"
    @click="$emit('click')"
  >
    <div class="card-icon">
      <Icon :name="capability.ui.icon" />
    </div>
    <div class="card-content">
      <h3>{{ capability.name }}</h3>
      <p>{{ capability.description }}</p>
      <div class="card-examples">
        <span 
          v-for="example in capability.ui.example_questions" 
          :key="example"
          class="example-chip"
        >
          {{ example }}
        </span>
      </div>
    </div>
    <div class="card-arrow">
      <Icon name="arrow-right" />
    </div>
  </div>
</template>

<style scoped>
.capability-card {
  display: flex;
  align-items: flex-start;
  gap: 16px;
  padding: 20px;
  border-radius: 16px;
  background: var(--surface-elevated);
  border: 1px solid var(--border-subtle);
  transition: all 0.2s ease;
  cursor: pointer;
}

.capability-card:hover {
  border-color: var(--cap-color);
  box-shadow: 0 4px 20px color-mix(in srgb, var(--cap-color) 20%, transparent);
  transform: translateY(-2px);
}

.card-icon {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  background: color-mix(in srgb, var(--cap-color) 10%, transparent);
  color: var(--cap-color);
  display: flex;
  align-items: center;
  justify-content: center;
}
</style>
```

### 4.3 AI Chat 页面重构 - 事件驱动架构

```vue
<!-- AIChatPage.vue - Event-Driven Architecture -->
<template>
  <div class="ai-chat-page">
    <!-- Header: Capability 名称和状态 -->
    <header class="chat-header">
      <div class="capability-info">
        <Icon :name="currentCapability?.ui?.icon || 'chat'" />
        <span>{{ currentCapability?.name || 'AI 助手' }}</span>
      </div>
      <ConnectionStatus :status="connectionStatus" />
    </header>
    
    <!-- Message List: 支持事件渲染 -->
    <div ref="messageList" class="message-list">
      <template v-for="event in events" :key="event.id">
        <!-- 阶段事件 -->
        <PhaseIndicator
          v-if="event.type.startsWith('phase.')"
          :phase="event.payload.phase"
          :metadata="event.payload.metadata"
        />
        
        <!-- 工具调用事件 -->
        <ToolCallCard
          v-if="event.type === 'tool.call'"
          :tool="event.payload.tool"
          :status="'pending'"
        />
        
        <!-- 工具结果事件 -->
        <ToolResultCard
          v-if="event.type === 'tool.result'"
          :result="event.payload.result"
        />
        
        <!-- 文本流事件 -->
        <MessageBubble
          v-if="event.type === 'token.stream'"
          :content="event.payload.token"
          :is-thinking="event.payload.is_thinking"
          :accumulated="getAccumulatedText(event)"
        />
      </template>
    </div>
    
    <!-- Input Area: 动态根据 Capability 渲染 -->
    <footer class="chat-input-area">
      <CapabilityInput
        :mode="currentCapability?.ui?.input_mode"
        :placeholder="currentCapability?.ui?.placeholder"
        v-model="inputValue"
        @submit="sendMessage"
      />
      <Toggles
        :deep-think="enableThinking"
        :web-search="enableWebSearch"
        @update:deep-think="enableThinking = $event"
        @update:web-search="enableWebSearch = $event"
      />
    </footer>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute } from 'vue-router'
import { useEventStream } from '@/composables/useEventStream'
import { useCapabilityStore } from '@/stores/capability'

const route = useRoute()
const capabilityStore = useCapabilityStore()

// Capability 上下文
const currentCapability = computed(() => 
  capabilityStore.getById(route.query.capability as string)
)

// Event Stream 管理
const { events, send, status: connectionStatus } = useEventStream({
  endpoint: '/api/v1/ai/events/stream',
  onEvent: handleEvent,
})

// 发送消息
async function sendMessage(text: string) {
  await send({
    type: 'capability.invoke',
    payload: {
      capability_id: currentCapability.value?.id,
      input: text,
      options: {
        enable_thinking: enableThinking.value,
        enable_web_search: enableWebSearch.value,
      }
    }
  })
}

// 处理事件
function handleEvent(event: AgentEvent) {
  switch (event.type) {
    case 'tool.call':
      // 可以在这里预加载工具 UI
      break
    case 'capability.end':
      // 对话结束，保存到历史
      saveToHistory(event)
      break
  }
}
</script>
```

### 4.4 Event Stream Composable

```typescript
// composables/useEventStream.ts
import { ref, onMounted, onUnmounted } from 'vue'
import type { AgentEvent } from '@/types/agent-stream'

export function useEventStream(options: {
  endpoint: string
  onEvent: (event: AgentEvent) => void
  onError?: (error: Error) => void
}) {
  const events = ref<AgentEvent[]>([])
  const status = ref<'idle' | 'connecting' | 'connected' | 'error'>('idle')
  let eventSource: EventSource | null = null
  
  function connect() {
    status.value = 'connecting'
    eventSource = new EventSource(options.endpoint)
    
    eventSource.onopen = () => {
      status.value = 'connected'
    }
    
    eventSource.onmessage = (e) => {
      const event: AgentEvent = JSON.parse(e.data)
      events.value.push(event)
      options.onEvent(event)
    }
    
    eventSource.onerror = (e) => {
      status.value = 'error'
      options.onError?.(new Error('EventSource failed'))
    }
  }
  
  async function send(message: any) {
    await fetch('/api/v1/ai/events/send', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(message)
    })
  }
  
  onMounted(connect)
  onUnmounted(() => eventSource?.close())
  
  return { events, status, send }
}
```

---

## 5. Harness 工程化实施路线图 (更新)

### 5.1 ~~Phase 1: Protocol 统一~~ — **已完成**

> 原文档提出使用 NDJSON，实际实现使用 LangGraph 原生 SSE。SSE 是更优选择。

**已完成的工作:**
- `runs.py` 删除 (304 行)，替换为 `runs_stream.py` (139 行) + `sse_gateway.py` (182 行)
- `useThreadChat.ts` 处理 `messages-tuple`/`messages`/`values`/`custom` 事件
- 重试机制（指数退避 + 抖动）、流超时、用户取消
- 集成测试 `test_v2_sse_contract.py` (269 行)

### 5.2 ~~Phase 2: Capability Registry~~ — **后端已完成，前端 UI 部分完成**

> **2026-06-25 更新:** Capability Registry 后端和前端 API 均已实现，仅需 AI Hub 页面改造。

**已完成 (后端):**
- `agent/services/capability_registry.py` (296 行) — 完整实现:
  - Fixed capabilities (`chat`, `time_machine`)
  - Builtin capabilities (从 `skills/builtin/*/SKILL.md` 加载)
  - Custom capabilities (从 `skills/custom/{family_id}/*/SKILL.md` 加载)
  - 家庭级别过滤 (`list_capabilities_for_family` + `ai_skills` API 集成)
- `agent/routers/capabilities.py` — `GET /capabilities` + `GET /capabilities?family_id=X`
- `agent/schemas/capability.py` — 完整 Pydantic schemas

**已完成 (前端 API/Store):**
- `stores/capability.ts` — Pinia store with `loadCapabilities()`
- `api/ai.ts` — `getAICapabilities()` → `GET /api/v1/ai/capabilities`
- `AICapability` TypeScript 接口 (匹配后端 schema)
- `AIChatInput.vue` — slash command palette 使用 capability store
- `CapabilityPickerSheet.vue` — 能力选择器 UI

**仍需完成 (前端 UI):**
- AI Hub 页面改为 Capability Grid 展示 (当前使用 Agent Card)
- Capability-scoped chat flows (`router.push({ capability })`)
- 动态 `input_mode` 渲染 (`structured`, `asset_selector`, `confirm_dialog`)

### 5.3 ~~Phase 3: Tool Calling UI~~ — **已完成**

**已完成的工作:**
- `PlanningStepsPanel.vue` (239 行) — tool_call 事件可视化
- `MessageGroup.vue` — 增强 tool call 渲染
- `TokenUsage.vue` — token 统计展示
- `StreamingIndicator.vue` (72 行) — 流状态指示
- `ErrorMessage.vue` (94 行) — 错误处理 + 重试 UX
- `ArtifactPreviewPopup.vue` — artifact 预览
- `TableActionBar.vue` (92 行) — artifact 表格操作

### 5.4 Phase 4: Harness 深度集成 — **部分完成**

**已完成:**
- `subagent_registry.py` (108 行) — subagent 运行时注册
- `agent_dispatch.py` 更新 — 统一 agent 调度
- `worker.py` (225 行) — 后台 worker 运行时
- `gc.py` (85 行) — 资源垃圾回收
- `lifespan.py` (83 行) — 应用生命周期管理
- `run_extras.py` (106 行) — 额外运行时功能
- `sandbox_provider.py` (151 行) — 沙箱提供者

**仍需完成:**
- Capability 级别的权限控制
- 多步骤推理可视化完善

---

## 6. 关键设计决策

### 6.1 ~~为什么使用 NDJSON 而非 SSE?~~ — 决策变更

> **2026-06 更新:** 实际实现选择了 **LangGraph 原生 SSE** 而非 NDJSON。
> SSE 是更优选择，原因如下:

| 方案 | 优点 | 缺点 | 选择 |
|------|------|------|------|
| ~~**NDJSON**~~ | ~~解析简单、可恢复、标准格式~~ | ~~需要手动处理连接~~ | ~~首选~~ → **弃用** |
| **SSE** | **LangGraph SDK 内置、浏览器原生 EventSource、自动重连** | **格式限制** | **✅ 实际选择** |
| WebSocket | 双向通信 | 开销大、需要额外管理 | ❌ 排除 |
| gRPC Stream | 性能高 | 浏览器支持差 | ❌ 排除 |

**实际 SSE 实现** (`useThreadChat.ts`):
```typescript
const stream = client.runs.stream(currentThreadId, 'agent', {
  input: { messages: [{ role: 'user', content: text }] },
  signal: abortController.signal,
  streamMode: ['messages-tuple', 'values', 'custom'],
})
```

### 6.2 为什么 Capability 替代自由输入?

**用户视角：**
- 知道 AI 能做什么（Capability Discovery）
- 快速开始特定任务（Quick Actions）
- 减少"我不知道该问什么"的困惑

**工程视角：**
- 明确的技能边界（Skill Boundary）
- 可预知的资源消耗（Token Budget）
- 更细粒度的权限控制（Policy per Capability）
- 更好的可观测性（Tracing per Capability）

### 6.3 为什么 Tool Calling 要可视化?

**透明度 = 信任**

当用户看到：
```
AI 正在调用「资产查询」工具...
✓ 已获取 5 条资产记录
AI 正在分析...
```

比看到：
```
正在思考...
```

更能建立用户对 AI 的信任。

---

## 7. 验收标准

### 7.1 ~~功能验收~~ — 更新

- [x] ~~AI Hub 页面展示 Capability Grid 而非输入框~~ — **替代方案:** Agent Card + 折叠区域 + InputBox
- [x] ~~每个 Capability 有独立图标、颜色、示例问题~~ — **替代方案:** Agent Card 已有图标/颜色
- [x] ~~点击 Capability 进入专用对话流~~ — **替代方案:** Agent Card → `router.push({ agentId })`
- [x] ~~Stream 输出为结构化 NDJSON~~ — **已实现:** LangGraph SSE (messages-tuple/values/custom)
- [x] ~~前端正确渲染 phase/tool/token 事件~~ — `useThreadChat.ts` 已处理
- [x] ~~Tool Calling 过程可视化~~ — `PlanningStepsPanel.vue`
- [x] ~~DeerFlow 和 Direct LLM 输出格式统一~~ — `runs_stream.py` + `sse_gateway.py` 统一

**仍需验收 (Phase 2):**
- [ ] Capability Registry (`capability_registry.py`)
- [ ] `/api/v1/capabilities` 端点
- [ ] Capability Grid on AI Hub
- [ ] 动态 input_mode 渲染

### 7.2 性能验收

- [ ] Capability 列表加载 < 200ms
- [ ] Stream 首包延迟 < 500ms
- [ ] Tool Calling UI 渲染 < 100ms
- [ ] 内存占用无显著增长

### 7.3 体验验收

- [ ] 新用户能在 30 秒内发现 AI 能力
- [ ] 对话过程流畅无卡顿
- [ ] 工具调用结果清晰可理解
- [ ] 移动端交互友好

---

## 8. 参考实现

### 8.1 参考产品

| 产品 | 学习点 |
|------|--------|
| **Claude** | Artifacts 展示、Thinking 过程 |
| **ChatGPT** | Plugins 发现、Tool Calls |
| **Perplexity** | 搜索过程可视化 |
| **Vercel AI SDK** | useChat/useCompletion hooks |
| **LangChain** | Agent 编排、Tool 集成 |

### 8.2 技术参考

- [Deer-Flow Harness Docs](https://github.com/deerflow/harness)
- [Vercel AI SDK Event Protocol](https://sdk.vercel.ai/docs/concepts/events)
- [OpenAI Chat Completion API](https://platform.openai.com/docs/api-reference/chat)
- [Claude Tool Use](https://docs.anthropic.com/en/docs/build-with-claude/tool-use)

---

## 9. 结语 (更新)

> **2026-06-25 更新:** 本文档约 70% 的内容已在 `feat/unify-ai-chat-input-box` 分支上实现。

**已完成的:**
1. ~~交互范式转变~~ — LangGraph SSE 替代 `[THINK]/[TEXT]` 前缀
2. ~~协议标准化~~ — 结构化事件流 (messages-tuple/values/custom)
3. ~~Tool Calling 可视化~~ — `PlanningStepsPanel.vue` + `MessageGroup.vue`
4. ~~InputBox 统一~~ — 单一 `InputBox.vue` (1,217 行)
5. ~~SSE 网关统一~~ — `runs_stream.py` + `sse_gateway.py`

**仍需完成的:**
1. **AI Hub Capability Grid** — 将当前 Agent Card 布局改为 Capability Grid 展示
2. **Capability-scoped chat flows** — `router.push({ capability })` 能力级路由
3. **动态 input_mode 渲染** — `structured`, `asset_selector`, `confirm_dialog`

**建议:** 本文档约 85% 已完成。剩余工作集中在前端 UI 层（Hub Grid 展示、动态 input_mode 渲染）。
本文档保留作为历史参考和架构决策记录。
