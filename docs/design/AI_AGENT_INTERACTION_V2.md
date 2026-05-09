# Numina AI Agent 交互体验 V2 设计

> 从资深 AI Agent 设计师视角，统一 Numina 与 Deer-Flow 的交互范式，落地 Harness Engineering

## 1. 现状诊断

### 1.1 当前架构问题

```
┌─────────────────────────────────────────────────────────────┐
│                    当前交互流程                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────┐    ┌──────────┐    ┌──────────────────────┐ │
│  │ AI Hub   │───→│ AI Chat  │───→│ /api/v1/ai/chat/     │ │
│  │ 输入问题  │    │ 对话页面  │    │ stream               │ │
│  └──────────┘    └──────────┘    └──────────────────────┘ │
│       │                              │                     │
│       │ Pinia Store                  │ [THINK]/[TEXT]      │
│       │ Query Params                 │ 前缀解析             │
│       ▼                              ▼                     │
│  状态传递双通道              Stream 格式非结构化            │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**痛点识别：**

| 层级 | 问题 | 影响 |
|------|------|------|
| **UX** | Hub → Chat 状态双通道传递 | 复杂度高，易出 bug |
| **UX** | 缺乏 Agent 能力发现 | 用户不知道 AI 能做什么 |
| **Protocol** | [THINK]/[TEXT] 前缀 | 非标准，解析脆弱 |
| **Protocol** | 无 Tool Calling 展示 | 用户看不到 AI 思考过程 |
| **Harness** | DeerFlow/Direct 双路径 | 维护成本高，行为不一致 |
| **Engineering** | 阶段状态过于简单 | 缺乏细粒度反馈 |

### 1.2 与 Deer-Flow 的差距

Deer-Flow 的 Harness 提供了：
- **Capability Registry**: 动态发现 Agent 能力
- **Skill Orchestration**: 多步骤推理编排
- **Tool Calling**: 工具调用可视化
- **Streaming Protocol**: 结构化事件流

Numina 当前仅使用了 Deer-Flow 的基础 LLM 调用，未充分利用 Harness 工程化能力。

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

### 2.2 交互范式对比

| 范式 | 当前 | 目标 |
|------|------|------|
| **Hub 模式** | 输入框主导 | Capability Grid 主导 |
| **对话启动** | 用户输入即开始 | 选择 Capability → 进入专用对话 |
| **状态传递** | Pinia + Query 双通道 | Capability Context 单通道 |
| **Stream 格式** | [THINK]/[TEXT] 前缀 | NDJSON 结构化事件 |
| **工具展示** | 无 | Tool Calling Cards |
| **阶段反馈** | 简单文字 | 可视化进度条 |

---

## 3. Harness Engineering 架构

### 3.1 统一 Capability Model

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

### 3.2 Capability Registry

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

### 3.3 结构化 Stream Protocol

```typescript
// frontend/src/types/agent-stream.ts

/** Agent Stream 事件类型 - 基于 Deer-Flow Harness 标准 */
export type AgentEventType = 
  | 'capability.start'      // Capability 开始执行
  | 'phase.connecting'      // 连接模型
  | 'phase.thinking'        // 深度思考中
  | 'tool.call'             // 工具调用
  | 'tool.result'           // 工具结果
  | 'token.stream'          // 文本流
  | 'phase.answering'       // 组织回答
  | 'capability.end'        // Capability 完成
  | 'capability.error';     // 错误

/** 基础事件 */
export interface AgentEvent {
  id: string;
  type: AgentEventType;
  timestamp: string;
  capability_id: string;
  task_id: string;
}

/** 阶段事件 */
export interface PhaseEvent extends AgentEvent {
  type: 'phase.connecting' | 'phase.thinking' | 'phase.answering';
  phase: string;
  metadata?: {
    model?: string;
    elapsed_ms?: number;
    think_budget?: number;
  };
}

/** 工具调用事件 */
export interface ToolCallEvent extends AgentEvent {
  type: 'tool.call';
  tool: {
    id: string;
    name: string;
    display_name: string;
    icon: string;
    arguments: Record<string, any>;
  };
}

/** 工具结果事件 */
export interface ToolResultEvent extends AgentEvent {
  type: 'tool.result';
  tool_id: string;
  result: {
    success: boolean;
    data?: any;
    error?: string;
    execution_time_ms: number;
  };
}

/** 文本流事件 */
export interface TokenStreamEvent extends AgentEvent {
  type: 'token.stream';
  token: string;
  is_thinking: boolean;
}

/** Capability 完成事件 */
export interface CapabilityEndEvent extends AgentEvent {
  type: 'capability.end';
  result: {
    summary: string;
    tokens_used: number;
    execution_time_ms: number;
    tools_used: string[];
  };
}
```

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

## 5. Harness 工程化实施路线图

### 5.1 Phase 1: Protocol 统一 (Week 1)

**目标**: 替换 [THINK]/[TEXT] 前缀为结构化 NDJSON

```python
# agent/routers/chat.py - 修改点

# BEFORE: 使用前缀
if chunk.startswith("[THINK]") or chunk.startswith("[TEXT]"):
    yield chunk
else:
    yield f"[TEXT]{chunk}"

# AFTER: 使用 EventStreamBuilder
events = EventStreamBuilder(capability_id, task_id)

# 1. 发送阶段事件
yield events.phase("connecting").to_ndjson()

# 2. 工具调用
yield events.tool_call("asset_search", {"query": "房产"}).to_ndjson()

# 3. 思考流
yield events.token(chunk, is_thinking=True).to_ndjson()

# 4. 文本流
yield events.token(chunk, is_thinking=False).to_ndjson()

# 5. 完成
yield events.end(summary, tokens_used, elapsed_ms, tools_used).to_ndjson()
```

### 5.2 Phase 2: Capability Registry (Week 2)

**目标**: 建立 Capability 注册中心，前端动态渲染

1. 创建 `agent/services/capability_registry.py`
2. 添加 `/api/v1/capabilities` 端点
3. 前端创建 `CapabilityStore`
4. AI Hub 页面改为 Capability Grid

### 5.3 Phase 3: Tool Calling UI (Week 3)

**目标**: 可视化工具调用过程

1. 设计 Tool Call Card 组件
2. 设计 Tool Result Card 组件
3. 在 Stream 中支持 tool.call/tool.result 事件
4. 添加工具执行动画

### 5.4 Phase 4: Harness Deep Integration (Week 4)

**目标**: 完全接入 Deer-Flow Harness

1. 所有 Agent 调用统一走 `orchestrator.dispatch`
2. DeerFlow 和 Direct LLM 输出格式统一
3. 支持 Capability 级别的权限控制
4. 支持多步骤推理可视化

---

## 6. 关键设计决策

### 6.1 为什么使用 NDJSON 而非 SSE?

| 方案 | 优点 | 缺点 | 选择 |
|------|------|------|------|
| **NDJSON** | 解析简单、可恢复、标准格式 | 需要手动处理连接 | ✅ 首选 |
| SSE | 原生支持重连 | 格式限制多、调试困难 | ❌ 排除 |
| WebSocket | 双向通信 | 开销大、需要额外管理 | ❌ 排除 |
| gRPC Stream | 性能高 | 浏览器支持差 | ❌ 排除 |

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

### 7.1 功能验收

- [ ] AI Hub 页面展示 Capability Grid 而非输入框
- [ ] 每个 Capability 有独立图标、颜色、示例问题
- [ ] 点击 Capability 进入专用对话流
- [ ] Stream 输出为结构化 NDJSON
- [ ] 前端正确渲染 phase/tool/token 事件
- [ ] Tool Calling 过程可视化
- [ ] DeerFlow 和 Direct LLM 输出格式统一

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

## 9. 结语

这份设计文档从资深 AI Agent 设计师视角，提出了：

1. **交互范式转变**：从自由输入 → Capability 发现
2. **协议标准化**：从 [THINK]/[TEXT] 前缀 → 结构化 NDJSON
3. **工程化落地**：Deer-Flow Harness 深度集成
4. **体验提升**：Tool Calling 可视化、阶段反馈细化

核心价值：
- **用户**: 更快发现 AI 价值，更透明地理解 AI 工作
- **开发**: 统一协议、统一架构、降低维护成本
- **产品**: 可扩展的 Capability 体系，支持未来更多场景

建议按 Phase 1→4 逐步实施，每个 Phase 都有明确的验收标准和回滚方案。
