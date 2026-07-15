# HumanInputCard DeerFlow 对齐 + 多选扩展

> 日期: 2026-07-14
> 模块: frontend/ai-chat, server/agent
> 状态: 待实施

## 背景

DeerFlow 调研结论（基于 `deer-flow-reference/frontend/src/core/messages/human-input.ts` 和 `human-input-card.tsx`）：

| 特性 | DeerFlow | 我们当前 | 差异 |
|------|----------|----------|------|
| 输入模式 | `free_text` / `single_choice` / `choice_with_other` | 隐式（有 options → 单选，无 → 文本） | DeerFlow 更明确 |
| 选项交互 | 点击选项 → **直接提交** | 选择 → 点提交（两步） | **需改回 DeerFlow** |
| 选项 UI | 全宽 outline 按钮 | 圆角药丸 + radio 圆圈 | **需改回 DeerFlow** |
| 多选 | ❌ 不支持 | ❌ 不支持 | **扩展支持** |
| 连续问题 | `deriveHumanInputThreadState` 按 request_id 追踪 | 每个 interrupt 独立 group | 基本等价 |

核心约束（来自用户）：
1. **手机端 H5**：文件查看不能左右两屏，需按页懒加载
2. **租户隔离**：模型/MCP/搜索/skill/agent 由家庭管理员预配置，用户不可选

这两个约束**不影响** HumanInputCard 的交互设计，因此直接复刻 DeerFlow。

---

## Part 1: 交互对齐 DeerFlow（单选模式）

### 1.1 改动概述

将 HumanInputCard 的选项交互从两步（选择 → 确认）改回 DeerFlow 的一步（点击即提交）。

### 1.2 交互规则

| 模式 | 选项区 | 文本区 | 提交方式 |
|------|--------|--------|----------|
| `single_choice` | 全宽按钮列表 | 无 | 点击选项 → 直接提交 |
| `choice_with_other` | 全宽按钮列表 | textarea + 提交按钮 | 点击选项 → 直接提交；或输入文本 → 点提交/Enter |
| `free_text` | 无 | textarea + 提交按钮 | 输入文本 → 点提交/Enter |
| `multi_choice` | checkbox 按钮列表 | 无 | 勾选 → 点提交（Part 2） |
| `multi_choice_with_other` | checkbox 按钮列表 | textarea + 提交按钮 | 勾选 → 点提交（Part 2） |

### 1.3 涉及文件

| 文件 | 改动 |
|------|------|
| `HumanInputCard.vue` | 重写选项交互逻辑 |
| `HumanInputCard.spec.ts` | 更新测试 |

### 1.4 HumanInputCard.vue 改动

```vue
<!-- 选项按钮：点击直接提交（DeerFlow 模式） -->
<div v-if="hasOptions && isInteractive && !isMultiChoice" class="card-options">
  <button
    v-for="(opt, idx) in options"
    :key="idx"
    class="option-btn"
    :disabled="isSubmitting"
    @click="submitOption(opt.value)"
  >
    {{ opt.label }}
  </button>
</div>

<!-- 多选模式：checkbox 样式，需确认提交（Part 2） -->
<div v-if="hasOptions && isInteractive && isMultiChoice" class="card-options card-options--multi">
  <label
    v-for="(opt, idx) in options"
    :key="idx"
    class="option-check-btn"
    :class="{ 'option-check-btn--checked': selectedValues.has(opt.value) }"
  >
    <input
      type="checkbox"
      :checked="selectedValues.has(opt.value)"
      :disabled="isSubmitting"
      @change="toggleValue(opt.value)"
    />
    <span>{{ opt.label }}</span>
  </label>
</div>
```

**关键变化**：
- 单选：`selectOption()` → `submitOption()` 直接提交，移除 `selectedValue` ref
- 多选：`selectedValues: Set<string>` + `toggleValue()` + 独立提交按钮
- 按钮样式：全宽 `width: 100%`，`text-align: left`，`border: 1px solid border-color`

---

## Part 2: 多选扩展（全栈）

### 2.1 数据流

```
Agent LLM
  → ask_clarification(multi_select=True, options=[...])
  → LangGraph interrupt()
  → adapter.py 转发 custom event (type=interrupt)
  → worker.py SSE 推送
  → useThreadChat.ts 解析 InterruptData (新增 multi_select 字段)
  → HumanInputCard.vue 渲染 checkbox 列表
  → 用户勾选 → 点击提交
  → resumeInterrupt() → POST /api/threads/{id}/runs/resume
  → resume.py: answer = JSON.stringify(["opt1", "opt3"]) 或 "opt1,opt3"
  → LangGraph Command(resume=answer)
  → Agent LLM 收到回答继续
```

### 2.2 后端改动

#### 2.2.1 `interrupt_tools.py` — 添加 `multi_select` 参数

```python
class AskClarificationInput(BaseModel):
    question: str
    options: list[dict[str, str]] | None = None
    context: str | None = None
    choice_with_other: bool = False
    multi_select: bool = Field(
        default=False,
        description="Allow selecting multiple options (checkbox mode)",
    )
```

`_ask_clarification()` 将 `multi_select` 写入 interrupt value dict，LangGraph 会将其序列化到 custom event 中。

#### 2.2.2 `resume.py` — 无需改动

`ResumeRequest.answer` 是 `str` 类型，前端将多选结果序列化为 JSON 数组字符串（如 `["opt1","opt3"]`）传入即可。Agent LLM 能理解 JSON 格式的回答。

### 2.3 前端改动

#### 2.3.1 类型定义

**`useThreadChat.ts` — `InterruptData` 接口**：
```typescript
export interface InterruptData {
  question: string
  options?: Array<{ label: string; value: string }>
  context?: string
  interrupt_id: string
  multi_select?: boolean  // 新增
}
```

**`message-group.ts` — `ClarificationInterruptData` 接口**：
```typescript
export interface ClarificationInterruptData {
  question: string
  options?: Array<{ label: string; value: string }>
  context?: string
  choiceWithOther?: boolean
  interrupt_id: string
  multi_select?: boolean  // 新增
}
```

#### 2.3.2 SSE 事件解析

**`useThreadChat.ts` — interrupt 事件处理**（~L587）：
```typescript
const interruptPayload: InterruptData = {
  question: customData.question || '',
  options: customData.options,
  context: customData.context,
  interrupt_id: customData.interrupt_id || genId('intr'),
  multi_select: customData.multi_select,  // 新增
}
```

#### 2.3.3 `HumanInputCard.vue` — 多选 UI

```typescript
// props 新增
multiSelect?: boolean

// 状态
const selectedValues = ref<Set<string>>(new Set())

// 计算属性
const isMultiChoice = computed(() => props.multiSelect === true)

// 方法
function toggleValue(value: string) {
  const next = new Set(selectedValues.value)
  if (next.has(value)) next.delete(value)
  else next.add(value)
  selectedValues.value = next
}

function submitMultiAnswer() {
  if (selectedValues.value.size === 0) return
  const answer = JSON.stringify([...selectedValues.value])
  emit('submit', answer)
}
```

**提交格式**：多选结果序列化为 JSON 数组字符串，如 `["是","否"]`。Agent LLM 能理解此格式。

#### 2.3.4 `MessageGroup.vue` — 传递 `multiSelect` prop

```vue
<HumanInputCard
  :question="..."
  :options="clarificationInterruptData?.options"
  :multi-select="clarificationInterruptData?.multi_select"
  ...
/>
```

### 2.4 涉及文件清单

| 文件 | 改动类型 | 说明 |
|------|----------|------|
| `server/.../interrupt_tools.py` | 修改 | 添加 `multi_select` 参数 |
| `frontend/.../useThreadChat.ts` | 修改 | `InterruptData` 接口 + SSE 解析 |
| `frontend/.../message-group.ts` | 修改 | `ClarificationInterruptData` 接口 |
| `frontend/.../HumanInputCard.vue` | 修改 | 多选 checkbox UI + 提交逻辑 |
| `frontend/.../MessageGroup.vue` | 修改 | 传递 `multiSelect` prop |
| `frontend/.../HumanInputCard.spec.ts` | 修改 | 多选测试用例 |
| `frontend/.../i18n/locales/zh-CN.ts` | 修改 | 新增 `multiSelectHint` 等 i18n key |
| `frontend/.../i18n/locales/en-US.ts` | 修改 | 同上 |

---

## 实施步骤

### Step 1: 单选交互对齐 DeerFlow
1. 修改 `HumanInputCard.vue` — 单选模式点击直接提交
2. 修改 `HumanInputCard.spec.ts` — 更新测试
3. 验证 typecheck + 测试通过

### Step 2: 多选后端
4. 修改 `interrupt_tools.py` — 添加 `multi_select` 参数
5. 验证 `test_interrupt_tools.py` 通过

### Step 3: 多选前端
6. 修改类型定义（`InterruptData`, `ClarificationInterruptData`）
7. 修改 SSE 解析（`useThreadChat.ts` interrupt 事件处理）
8. 修改 `HumanInputCard.vue` — 多选 checkbox UI
9. 修改 `MessageGroup.vue` — 传递 `multiSelect` prop
10. 添加 i18n keys
11. 更新测试
12. 验证 typecheck + 测试通过

### Step 4: 集成验证
13. 端到端手动测试（单选 + 多选 + 连续问题）
14. 更新 memory 文档

---

## 验收标准

| 场景 | 预期行为 |
|------|----------|
| 单选 + 选项 | 点击选项 → 直接提交 → agent 继续 |
| 单选 + choice_with_other | 点击选项 → 直接提交；或输入文本 → 点提交 |
| 多选 + 选项 | 勾选多个 → 点提交 → JSON 数组发送给 agent |
| 多选 + choice_with_other | 勾选 + 自定义文本 → 合并提交 |
| 纯文本 | 输入 → 点提交/Enter → 发送 |
| 连续问题 | 回答第一个 → agent 继续 → 第二个问题出现 → 回答 → agent 继续 |
| 已回答状态 | 显示已选答案 + ✓ 图标，不可再交互 |
| 提交中状态 | 显示 spinner + 禁用交互 |
| 错误状态 | 显示错误信息 + 重试按钮 |
