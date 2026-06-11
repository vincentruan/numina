---
name: ai-agent-execution-display-optimization
description: AI Agent 执行过程展示优化需求文档 — 解决 MCP 调用展示体验、历史恢复完整性、宽度优化等问题
metadata:
  type: project
---

# AI Agent 执行过程展示优化

**日期**: 2026-06-10
**状态**: 需求定义阶段
**优先级**: 高（核心用户体验改进）

## 背景

用户在 AI Chat 页面与 Agent 交互时，存在以下体验问题：

1. **MCP 调用视觉体验问题** — 实时流式对话中，工具调用从 running → done 的状态变化让用户感知为"重复展示"（先显示参数，后显示结果）
2. **历史恢复不完整** — Journal 未记录 `plan.update`、`subagent.update` 等事件，导致历史会话无法恢复完整执行过程
3. **宽度利用不足** — 短任务 Agent 回答仍使用窄气泡宽度，未充分利用页面空间

## 现状分析

### 已具备的能力（可复用）

| 能力 | 实现位置 | 说明 |
|------|---------|------|
| 事件归一化 | `aiEventNormalizer.ts` | tool.call → tool.result 按 toolCallId 合并 |
| 状态压缩 | `AiProcessBlock.vue:296` | done 状态自动 `compressed=true` |
| CSS 状态过渡 | `AiStepBlock.vue:59-77` | `<Transition mode="out-in">` 确保顺序过渡 |
| 全宽容器 | `AgentRunCanvas.vue` | 长任务使用全宽展示 |
| 内容过滤 | `contentFilter.ts` | 防止 prompt 泄露（应用于 reasoning） |
| 历史恢复路由 | `AIChatPage.vue:1179-1303` | 通过 normalizer 重构 processSteps |

### 需要改进的问题

#### 问题 1：工具调用视觉过渡体验

**现象**：实时流式对话中，用户看到：
- Phase 1: 工具调用开始 → 显示"正在调用" + 参数详情（展开状态）
- Phase 2: 工具调用完成 → 状态变为"已完成" + 结果摘要（压缩状态）

**用户感知**：这是"两次展示"或"重复"，但实际上是同一卡片的状态变化。

**根本原因**：running 状态默认展开显示参数，done 状态自动压缩。过渡期间参数 → 结果的变化让用户感知为"两条消息"。

**改进方向**：
- 让 running 状态也使用简化显示（默认压缩参数，用户可点击展开）
- 或优化 CSS transition 动画效果，让状态变化更平滑

#### 问题 2：历史恢复事件缺失

**Journal 未记录的事件类型**：

| 事件类型 | 用途 | 影响 |
|---------|------|------|
| `plan.update` | Plan 进度条 | 历史恢复无计划步骤 |
| `subagent.update` | 子代理执行 | 历史恢复无子代理信息 |
| `artifact.created` | 产出物元数据 | 可从 tool_call 推断，优先级较低 |

**改进方向**：扩展 `session_journal.py` 的写入方法，补充缺失事件类型。

#### 问题 3：Agent 回答宽度

**现状**：`AgentRunCanvas` 仅用于长任务（≥3 步骤或 deepThink 模式）。

**期望**：Agent 最终回答区域应尽量利用页面宽度，而非被窄气泡限制。

**改进方向**：调整 `shouldUseCanvas()` 逻辑或让 Agent 回答默认使用更宽布局。

## 解决方案

### 方案 A：工具调用视觉优化

**改动范围**：前端 `AiStepBlock.vue` + `AiProcessBlock.vue`

**改动内容**：

1. **调整 running 状态默认显示**：
   - running 状态也使用 `compressed` 模式（参数默认折叠）
   - 用户点击展开时才显示详细参数
   - 保持状态过渡动画的平滑性

2. **或：优化 CSS transition**：
   - 增加 args 消失 → result 出现的过渡动画时长
   - 使用 `opacity` + `transform` 组合让变化更自然

**代码改动点**：
- `AiProcessBlock.vue:296` — `compressed` 计算逻辑
- `AiStepBlock.vue:59-77` — CSS transition 结构
- `AiStepBlock.vue:166-168` — effectiveDefaultExpanded 计算

### 方案 B：Journal 事件扩展

**改动范围**：后端 `session_journal.py`

**改动内容**：

1. **添加 `write_plan_update()` 方法**：
```python
def write_plan_update(
    self,
    *,
    family_id: str,
    session_id: str,
    todos: list[dict[str, Any]],
) -> None:
    event = _make_event(
        "plan.update",
        session_id=session_id,
        family_id=family_id,
        actor="assistant",
        visibility="public",
        payload={"todos": todos},
    )
    self.append_event(family_id, session_id, event)
```

2. **添加 `write_subagent_update()` 方法**：
```python
def write_subagent_update(
    self,
    *,
    family_id: str,
    session_id: str,
    task_id: str,
    status: str,
    title: str | None = None,
    description: str | None = None,
    result: str | None = None,
    error: str | None = None,
) -> None:
    event = _make_event(
        "subagent.update",
        session_id=session_id,
        family_id=family_id,
        actor="assistant",
        visibility="public",
        payload={
            "subagent": {
                "taskId": task_id,
                "status": status,
                "title": title,
                "description": description,
                "result": result,
                "error": error,
            }
        },
    )
    self.append_event(family_id, session_id, event)
```

3. **调用点集成**：
   - 在 `agent_dispatch.py` 或 `orchestrator.py` 中调用新增方法
   - 确保 DeerFlow 的 plan 和 subagent 事件被持久化

### 方案 C：Agent 回答宽度优化

**改动范围**：前端 `AIChatPage.vue` + `AgentRunCanvas.vue`

**改动内容**：

1. **调整 `shouldUseCanvas()` 逻辑**：
   - 降低长任务判定门槛（如 ≥1 工具调用即使用全宽）
   - 或：Agent 回答区域默认使用全宽布局（不依赖 canvas）

2. **或：调整气泡 CSS**：
   - Agent 回答 `.bubble.assistant` 使用更宽 max-width
   - 保持用户消息窄气泡不变

**代码改动点**：
- `AIChatPage.vue:614-619` — `shouldUseCanvas()` 函数
- `aiTaskDetection.ts` — `isLongTask()` 逻辑
- `AIChatPage.vue` style section — `.bubble.assistant` CSS

## 验收标准

| ID | 验收项 | 验证方式 |
|----|--------|---------|
| AC-1 | 实时流式对话中，工具调用 running → done 过渡平滑，无视觉"重复"感 | 人工测试 + 录屏对比 |
| AC-2 | 工具调用参数默认折叠，用户可点击展开 | 人工测试 |
| AC-3 | 历史会话恢复后，Plan 进度条可见 | 人工测试 + 代码 review |
| AC-4 | 历史会话恢复后，子代理执行过程可见 | 人工测试 + 代码 review |
| AC-5 | Agent 回答区域宽度 ≥ 用户消息气泡宽度 1.5x | 人工测试 + CSS 测量 |
| AC-6 | 现有能力不受影响（模型选择、高可用、会话管理等） | 回归测试 |

## 风险与依赖

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| Journal 扩展增加写入量 | 存储空间增长 | 评估增量，考虑压缩或清理策略 |
| CSS transition 调整可能影响其他组件 | 视觉一致性 | 集中测试过渡效果 |
| width 调整可能影响移动端布局 | 响应式适配 | 重点测试移动端 H5 |

## 关联文档

- [[2026-06-09-ai-chat-process-display-optimization-design]] — 现有设计规范
- [[aiEventNormalizer]] — 事件归一化实现
- [[session_journal]] — Journal 服务实现
- [[DeerFlow Session Persistence]] — DeerFlow 会话持久化机制

## 下一步

1. 确认方案优先级（建议 A → B → C 顺序）
2. 进入 `/ce-plan` 详细规划实现步骤
3. 分阶段实现并验证