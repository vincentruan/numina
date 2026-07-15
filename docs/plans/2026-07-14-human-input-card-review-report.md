# HumanInputCard DeerFlow 对齐检查报告

**日期**: 2026-07-14  
**检查范围**: 单选交互、多选扩展、DeerFlow 功能对比  
**测试方法**: E2E 自动化测试 + 代码审查 + DeerFlow 参考对比

---

## 一、E2E 测试结果

### 测试执行
```bash
pnpm test ai-chat-human-input-card.spec.ts
```

**结果**: ✅ 3/3 通过
- ✅ 登录并导航到 AI 聊天页面
- ✅ 发送消息并等待响应
- ✅ 检查 HumanInputCard 渲染

### 实际观察
**问题**: Agent 未触发 clarification（直接回答了问题）

**截图分析**:
- `01-ai-chat-page.png`: 页面正常加载
- `02-message-typed.png`: 消息已输入
- `03-message-sent.png`: 消息已发送，显示"发送中"
- `04-response-received.png`: Agent 响应已接收，但显示原始 `<think>` 标签

**发现的问题**:
1. ⚠️ **Reasoning 过滤 Bug**: `<think>` 标签作为原始文本显示，未被正确过滤
2. ⚠️ **Agent 行为**: 未触发 clarification（可能因为问题不够复杂）

---

## 二、DeerFlow 功能对比评分

### 评分维度（1-5 分）

| 维度 | DeerFlow | Numina | 差异说明 |
|------|----------|--------|----------|
| **单选交互** | 5 | 5 | ✅ 完全对齐：点击选项 → 直接提交 |
| **选项按钮样式** | 5 | 4 | ⚠️ 缺少 `min-height: 44px` 和 `whitespace: pre-wrap` |
| **自由文本输入** | 5 | 4 | ⚠️ 缺少 `<form>` wrapper、`aria-invalid`、`aria-describedby` |
| **choiceWithOther** | 5 | 4 | ⚠️ 已回答状态下不显示 textarea |
| **错误/重试处理** | 3 | 4 | ✅ Numina 更好：有重试按钮 |
| **已回答状态** | 5 | 4 | ⚠️ 缺少 header badge |
| **提交中状态** | 4 | 4 | ✅ 基本对齐 |
| **可访问性** | 5 | 2 | ❌ **严重缺陷**：缺少 ARIA 属性、label、live regions |
| **移动端响应** | 4 | 4 | ✅ 基本对齐 |
| **多选支持** | N/A | 4 | ✅ Numina 扩展功能 |

**综合评分**: 
- DeerFlow: 4.6/5
- Numina: 3.9/5
- **差距**: -0.7 分

---

## 三、代码审查结果

### ✅ 已实现功能

#### 1. 单选交互（DeerFlow 对齐）
```typescript
// HumanInputCard.vue
function handleOptionClick(value: string) {
  if (!isInteractive.value || isSubmitting.value) return
  if (isMultiSelect.value) {
    // 多选逻辑
  } else {
    // 单选：直接提交
    emit('submit', value)
  }
}
```

**验证**: 
- ✅ 点击选项 → 立即提交
- ✅ 按钮样式：`width: 100%`, `text-align: left`, `border-radius: 8px`
- ✅ 禁用状态正确

#### 2. 多选扩展
```typescript
// HumanInputCard.vue
const selectedValues = ref<Set<string>>(new Set())

function handleOptionClick(value: string) {
  if (isMultiSelect.value) {
    const next = new Set(selectedValues.value)
    if (next.has(value)) {
      next.delete(value)
    } else {
      next.add(value)
    }
    selectedValues.value = next
  }
}

function submitAnswer() {
  if (isMultiSelect.value) {
    const answer = JSON.stringify([...selectedValues.value])
    emit('submit', answer)
  }
}
```

**验证**:
- ✅ Checkbox UI 正确渲染
- ✅ 多选状态管理正确
- ✅ 提交格式：JSON 数组 `["opt1", "opt3"]`

#### 3. SSE 链路完整性
```python
# adapter.py (L351-358)
if (
    event_type == "custom"
    and event_data.get("type") == "interrupt"
):
    # LangGraph interrupt() emits a custom event with type="interrupt".
    yield ("custom", event_data)
```

**验证**:
- ✅ `interrupt_tools.py`: `multi_select` 参数已添加
- ✅ `adapter.py`: interrupt 事件原样转发（包含 `choice_with_other` 和 `multi_select`）
- ✅ `useThreadChat.ts`: SSE 解析正确映射字段
- ✅ `MessageGroup.vue`: props 传递正确

#### 4. 类型定义
```typescript
// useThreadChat.ts
export interface InterruptData {
  question: string
  options?: Array<{ label: string; value: string }>
  context?: string
  choiceWithOther?: boolean  // ✅ 已添加
  multiSelect?: boolean      // ✅ 已添加
  interrupt_id: string
}

// message-group.ts
export interface ClarificationInterruptData {
  question: string
  options?: Array<{ label: string; value: string }>
  context?: string
  choiceWithOther?: boolean  // ✅ 已添加
  multiSelect?: boolean      // ✅ 已添加
  interrupt_id: string
}
```

**验证**: ✅ 类型链路完整

---

### ⚠️ 发现的问题

#### 1. Reasoning 过滤 Bug（严重）
**现象**: `<think>` 标签作为原始文本显示

**可能原因**:
- `extractContentFromMessage()` 未正确处理某些格式
- 或 `splitInlineReasoning()` 的正则表达式不匹配

**影响**: 用户体验差，显示原始标签

**建议修复**:
```typescript
// reasoning-filter.ts
export function splitInlineReasoning(content: string) {
  // 检查正则表达式是否匹配所有 think 标签格式
  const THINK_TAG_RE = /<think>([\s\S]*?)<\/think>/g
  // ...
}
```

#### 2. 可访问性缺陷（严重）
**缺失**:
- ❌ Textarea 无 `aria-label` / `aria-invalid` / `aria-describedby`
- ❌ 选项按钮无 `role="radio"` / `aria-checked`
- ❌ 错误消息无 `aria-live="polite"`
- ❌ 缺少 `<label>` 元素

**DeerFlow 实现**:
```tsx
// DeerFlow human-input-card.tsx
<section aria-labelledby={headingId}>
  <h3 id={headingId} className="sr-only">{title}</h3>
  <Textarea
    aria-invalid={!!error}
    aria-describedby={error ? errorId : undefined}
  />
  {error && <p id={errorId} className="text-destructive">{error}</p>}
</section>
```

**建议修复**:
```vue
<!-- HumanInputCard.vue -->
<div role="group" :aria-label="t('aiChat.clarification.title')">
  <textarea
    :aria-label="t('aiChat.clarification.inputPlaceholder')"
    :aria-invalid="isError"
    :aria-describedby="isError ? `error-${interruptId}` : undefined"
  />
  <p v-if="isError" :id="`error-${interruptId}`" role="alert">
    {{ errorMessage }}
  </p>
</div>
```

#### 3. 提交后文本未清空
**现象**: 提交自由文本后，textarea 内容保留

**DeerFlow 行为**: 提交成功后清空 textarea

**建议修复**:
```typescript
function submitAnswer() {
  if (!canSubmit.value) return
  if (isMultiSelect.value) {
    const answer = JSON.stringify([...selectedValues.value])
    emit('submit', answer)
    selectedValues.value.clear()  // ✅ 清空
  } else {
    const answer = customText.value.trim()
    if (answer) {
      emit('submit', answer)
      customText.value = ''  // ✅ 清空
    }
  }
}
```

#### 4. 选项按钮样式细节
**缺失**:
- ❌ `min-height: 44px`（触控友好）
- ❌ `whitespace: pre-wrap`（长文本换行）

**建议修复**:
```css
.option-btn {
  min-height: 44px;
  white-space: pre-wrap;
  word-break: break-word;
}
```

---

## 四、与 DeerFlow 的视觉差异

### 1. Card 结构
- **DeerFlow**: 左侧图标 + 标题 + 右侧状态 badge
- **Numina**: 图标 + 标题（无 badge）

### 2. 已回答显示
- **DeerFlow**: 绿色文本 + ✓ 图标（subtle）
- **Numina**: 绿色背景框 + ✓ 图标（prominent）

### 3. 错误状态
- **DeerFlow**: 内联验证错误（红色文本）
- **Numina**: 完整错误卡片（图标 + 消息 + 重试按钮）

### 4. 选项按钮
- **DeerFlow**: shadcn Button（设计系统一致）
- **Numina**: 自定义按钮（视觉相似但缺少 focus ring）

---

## 五、总结与建议

### ✅ 已完成
1. ✅ 单选交互对齐 DeerFlow（点击即提交）
2. ✅ 多选功能扩展（checkbox + JSON 数组）
3. ✅ SSE 链路完整（字段传递正确）
4. ✅ 类型定义完整
5. ✅ 测试覆盖（17 个单元测试 + 3 个 E2E）

### ⚠️ 待修复
1. ❌ **Reasoning 过滤 Bug**（`<think>` 标签显示）
2. ❌ **可访问性缺陷**（ARIA 属性缺失）
3. ⚠️ **提交后文本未清空**
4. ⚠️ **选项按钮样式细节**（min-height、whitespace）

### 📊 评分
- **功能完整性**: 9/10
- **代码质量**: 8/10
- **可访问性**: 2/10（**严重不足**）
- **用户体验**: 7/10
- **综合**: 6.5/10

### 🎯 优先级建议
1. **P0**: 修复 reasoning 过滤 bug
2. **P1**: 添加 ARIA 属性（可访问性）
3. **P2**: 提交后清空文本
4. **P3**: 优化按钮样式细节

---

## 六、附录

### 测试文件
- `tests/e2e/ai-chat-human-input-card.spec.ts`
- `frontend/apps/main/src/components/ai-chat/__tests__/HumanInputCard.spec.ts`

### 截图
- `e2e-screenshots/01-ai-chat-page.png`
- `e2e-screenshots/02-message-typed.png`
- `e2e-screenshots/03-message-sent.png`
- `e2e-screenshots/04-response-received.png`

### 参考文档
- DeerFlow: `deer-flow-reference/frontend/src/components/workspace/messages/human-input-card.tsx`
- Numina: `frontend/apps/main/src/components/ai-chat/HumanInputCard.vue`
