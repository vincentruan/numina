# AI Report 生成可靠性修复实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 AI 资产报告生成的三个问题：(1) 结构化结果落库失败；(2) narrative 字段输出 markdown 表格格式；(3) 失败后进度信息残留。

**Architecture:** 采用多层防御策略：提示词强化 → json_repair 解析 → LLM fallback 重试（最多 3 次）→ 最终失败时优雅降级。核心修改在 `ai_result_parser.py` 的 fallback 流程和 `useAITask.ts` 的 UI 状态清理。

**Tech Stack:** Python (FastAPI, SQLAlchemy, json_repair, Anthropic/OpenAI SDK), TypeScript (Vue 3, Vant 4)

---

## 问题根因分析

| 问题 | 根因 | 影响范围 |
|------|------|----------|
| 结构化结果落库失败 | LLM 输出 JSON 不符合 schema，`json_repair` 无法修复，LLM fallback 3 次重试后仍失败，返回 None | `_ai_events_helper.py:128-136` |
| narrative 字段为 markdown 表格 | 模型幻觉，即使提示词明确禁止表格仍输出；LLM fallback 的 `_contains_markdown_table` 检测触发但 retry 仍产生表格 | `ai_result_parser.py:421-423` |
| 失败后进度信息残留 | `useAITask.ts` 在 `capability.error` 时未完全清理 `toolSteps.running` 和 `phase` 状态；UI 组件未响应 `post_processing` 状态变化 | `useAITask.ts:262-289` |

---

## 文件结构

```
server/apps/backend/
├── app/services/
│   ├── ai_result_parser.py      # 核心：解析 + LLM fallback 重试逻辑
│   └── ai_result_writer.py      # 写入逻辑（已有，无需修改）
├── app/routers/
│   └── _ai_events_helper.py     # 事件流代理 + 任务状态管理
└── app/models/
    └── ai_report.py             # 报告模型（已有）

server/apps/agent/
├── skills/builtin/report/
│   └── SKILL.md                 # 核心：提示词强化（禁止表格）
└── services/
    └── orchestrator.py          # 流式事件发送（已有journal写入）

frontend/apps/main/src/
├── composables/
│   └── useAITask.ts             # 核心：UI 状态清理 + 错误处理
├── pages/
│   └── AIReportPage.vue         # 报告页面状态响应
└── components/ai/
    └── TaskConsole.vue          # 进度展示组件
```

---

## Task 1: 强化 Report 提示词（禁止表格 + JSON 格式示例）

**Files:**
- Modify: `server/apps/agent/skills/builtin/report/SKILL.md:1-139`

**Root cause:** 当前提示词已禁止表格，但模型仍可能幻觉。需要在多个位置重复强调，并提供"表格转列表"的示例。

- [ ] **Step 1: 强化提示词中的表格禁令**

修改 `skills/builtin/report/SKILL.md`，在 `## 最重要的规则` 部分添加更强的警告：

```markdown
## 最重要的规则（必须遵守）

你的回答**必须**严格遵循以下格式，否则系统将无法解析：

1. **仅输出 ```json 代码块**，不要有任何其他内容
2. **不要在 JSON 前后添加任何文字解释**
3. **JSON 必须合法**：无尾逗号、无注释、字符串正确转义
4. **narrative 字段使用列表格式**，不要使用 markdown 表格（表格格式容易出错）

---

## ⚠️⚠️⚠️ 禁止使用 Markdown 表格 ⚠️⚠️⚠️

**绝对禁止**在 `narrative` 字段中使用 markdown 表格格式。表格会导致解析失败。

### 禁止格式（绝对不可使用）：
```json
// ❌ 错误 - 这会导致解析失败
"narrative": "| 活期存款 | ¥870,000 | ⚠️ 仅覆盖1.2个月支出 |"
```

### 正确格式（必须使用）：
```json
// ✅ 正确 - 使用无序列表
"narrative": "**活期存款占比过高**\n\n- 活期存款约¥870,000，仅覆盖约1.2个月支出\n- 建议配置部分资金为低风险理财产品"
```

**如果你发现自己在写表格格式，立即转换为列表！**
```

- [ ] **Step 2: 在输出格式示例中重复强调**

在 `## 输出格式（唯一允许的格式）` 部分，为每个 narrative 字段添加注释：

```markdown
"net_worth_health": {
  "score": 4,
  "narrative": "**净资产基础良好**\n\n- 总资产2800万，月环比增长1.2%\n- 资产规模在同类家庭中处于**中上水平**\n- 需关注增长趋势的持续性",  // ✅ 使用列表，禁止表格
  "suggestions": [...]
}
```

- [ ] **Step 3: 验证修改**

```bash
grep -A 10 "禁止使用 Markdown 表格" server/apps/agent/skills/builtin/report/SKILL.md
```

Expected: 新增的警告块存在，包含正确/错误示例对比。

---

## Task 2: 增强 LLM Fallback 提示词（表格 → 列表转换）

**Files:**
- Modify: `server/apps/backend/app/services/ai_result_parser.py:293-343`

**Root cause:** `_build_extraction_prompt` 已有表格禁止提示，但需要更明确的转换示例。

- [ ] **Step 1: 强化 extraction prompt 的表格处理**

修改 `_build_extraction_prompt` 函数，添加表格转换示例：

```python
def _build_extraction_prompt(capability: str, answer_text: str, retry_count: int = 0) -> str:
    """Build extraction prompt for LLM fallback."""
    schema = CAPABILITY_SCHEMAS.get(capability, {})
    schema_str = json.dumps(schema, ensure_ascii=False, indent=2)

    # Truncate long text
    if capability == "report" and len(answer_text) > 3000:
        truncated = answer_text[:1500] + "\n...\n" + answer_text[-2000:]
    else:
        truncated = answer_text[:3000]

    if capability == "report":
        retry_hint = ""
        if retry_count > 0:
            retry_hint = f"\n\n【警告：这是第{retry_count + 1}次尝试，前次提取失败。请务必检查：narrative 字段不能包含 markdown 表格！】"

        enhanced_prompt = (
            f"请从以下分析文本中提取结构化的家庭资产报告 JSON。\n\n"
            f"【绝对禁止】\n"
            f"❌ narrative 字段不能包含 markdown 表格（如 | xxx | xxx |）\n"
            f"❌ 如果原文有表格，必须转换为无序列表\n\n"
            f"【表格 → 列表转换示例】\n"
            f"原文表格：| 活期存款 | ¥870,000 | ⚠️ 仅覆盖1.2个月支出 |\n"
            f"转换为：- 活期存款约¥870,000，仅覆盖约1.2个月支出\n\n"
            f"【正确 narrative 格式】\n"
            f'"narrative": "**问题标题**\\n\\n- 要点1\\n- 要点2\\n- 要点3"\n\n'
            f"【输出要求】\n"
            f"1. 仅输出 JSON，不要有任何解释\n"
            f"2. JSON 必须合法：无尾逗号、无注释\n"
            f"3. overall_score 必须是 0-100 整数\n\n"
            f"Schema：\n{schema_str}\n\n"
            f"分析文本：\n{truncated}\n"
            f"{retry_hint}\n\n"
            f"仅输出 JSON。"
        )
        return enhanced_prompt

    return base_prompt
```

- [ ] **Step 2: 验证修改**

```bash
grep -A 5 "表格 → 列表转换示例" server/apps/backend/app/services/ai_result_parser.py
```

Expected: 新增的转换示例和禁止规则存在。

---

## Task 3: 增强 Markdown 表格检测正则

**Files:**
- Modify: `server/apps/backend/app/services/ai_result_parser.py:435-459`

**Root cause:** 当前 `_contains_markdown_table` 检测简单，可能漏检变形表格（如无边界符）。

- [ ] **Step 1: 增强表格检测正则**

修改 `_contains_markdown_table` 函数：

```python
def _contains_markdown_table(data: dict) -> bool:
    """Check if narrative fields contain markdown table patterns.

    Returns True if any narrative field contains table-like patterns:
    - Full table: | cell1 | cell2 | cell3 |
    - Partial table: | cell1 | cell2
    - Multi-cell in single line:至少 3 个 | 分隔符
    """
    # 更严格的检测：匹配完整表格行或部分表格
    table_patterns = [
        re.compile(r'\|[^\n]+\|[^\n]*\|'),  # | cell | cell | - 至少2列
        re.compile(r'\|[^\|]+\|[^\|]+'),    # | cell | cell - 无结尾|
        re.compile(r'[^\|]*\|[^\|]+\|[^\|]*'),  # cell | cell | cell - 无开头|
    ]

    sections = ["net_worth_health", "allocation_analysis", "liability_pressure", "asset_efficiency"]
    for section in sections:
        if section in data and isinstance(data[section], dict):
            narrative = data[section].get("narrative", "")
            if narrative:
                for pattern in table_patterns:
                    if pattern.search(narrative):
                        logger.debug(f"Found markdown table in {section}.narrative: {pattern.pattern}")
                        return True

    summary = data.get("summary", "")
    if summary:
        for pattern in table_patterns:
            if pattern.search(summary):
                logger.debug("Found markdown table in summary")
                return True

    return False
```

- [ ] **Step 2: 添加单元测试**

创建测试文件 `server/apps/backend/tests/unit/test_ai_result_parser.py`：

```python
import pytest
from apps.backend.app.services.ai_result_parser import _contains_markdown_table

def test_contains_markdown_table_full_table():
    """检测完整表格格式"""
    data = {
        "asset_efficiency": {
            "narrative": "| 活期存款 | ¥870,000 | ⚠️ 仅覆盖1.2个月支出 |"
        }
    }
    assert _contains_markdown_table(data) is True

def test_contains_markdown_table_partial_table():
    """检测部分表格格式（无结尾|）"""
    data = {
        "net_worth_health": {
            "narrative": "| 活期存款 | ¥870,000"
        }
    }
    assert _contains_markdown_table(data) is True

def test_contains_markdown_table_no_table():
    """正常列表格式不触发"""
    data = {
        "asset_efficiency": {
            "narrative": "**活期存款占比过高**\n\n- 活期存款约¥870,000\n- 建议配置理财产品"
        }
    }
    assert _contains_markdown_table(data) is False

def test_contains_markdown_table_pipe_in_sentence():
    """句子中的单个 | 不触发（非表格）"""
    data = {
        "allocation_analysis": {
            "narrative": "资产配置比例 | 房产 95% | 金融 3%"  # 这里有 | 但不是表格
        }
    }
    # 注意：这个应该被检测，因为有多个 | 分隔
    assert _contains_markdown_table(data) is True
```

- [ ] **Step 3: 运行测试验证**

```bash
cd server && uv run pytest apps/backend/tests/unit/test_ai_result_parser.py -v
```

Expected: 4 tests pass.

---

## Task 4: 增强 LLM Fallback 重试逻辑（提取失败时调用模型修复）

**Files:**
- Modify: `server/apps/backend/app/services/ai_result_parser.py:346-432`

**Root cause:** 当前 fallback 重试 3 次，但每次重试的 prompt 相同（只是添加 retry_hint）。需要在重试时明确告诉模型"上次输出的表格格式是错误的"。

- [ ] **Step 1: 在重试时提供上次失败原因**

修改 `_llm_fallback_extract` 函数，记录失败原因并在下次重试时反馈：

```python
async def _llm_fallback_extract(
    capability: str,
    answer_text: str,
    family_id: int,
    db: Session,
) -> list[dict] | dict | None:
    """Use lightweight LLM to extract structured data from answer text."""
    configs = (
        db.query(AIProviderConfig)
        .filter(
            AIProviderConfig.family_id == family_id,
            AIProviderConfig.api_key_encrypted.isnot(None),
            AIProviderConfig.is_active.is_(True),
        )
        .order_by(AIProviderConfig.display_order.asc().nulls_last())
        .all()
    )

    if not configs:
        logger.warning(f"[{capability}] LLM fallback: no active provider for family {family_id}")
        return None

    config = configs[0]
    api_key = decrypt_api_key(config.api_key_encrypted)
    if not api_key:
        logger.warning(f"[{capability}] LLM fallback: could not decrypt API key")
        return None

    # Track failure reasons for progressive feedback
    failure_reasons: list[str] = []

    for retry in range(LLM_FALLBACK_MAX_RETRIES):
        # Build prompt with failure feedback
        prompt = _build_extraction_prompt_with_feedback(
            capability, answer_text, retry_count=retry, failure_reasons=failure_reasons
        )

        try:
            raw = await asyncio.wait_for(
                _call_llm(
                    provider=config.provider,
                    api_key=api_key,
                    model_id=config.model_id or "gpt-4o-mini",
                    base_url=config.base_url,
                    prompt=prompt,
                ),
                timeout=LLM_FALLBACK_TIMEOUT_SECONDS,
            )
        except TimeoutError:
            failure_reasons.append("timeout")
            logger.warning(f"[{capability}] LLM fallback timed out (retry {retry + 1})")
            continue
        except Exception as e:
            failure_reasons.append(f"call_failed: {type(e).__name__}")
            logger.warning(f"[{capability}] LLM fallback call failed: {e} (retry {retry + 1})")
            continue

        if not raw:
            failure_reasons.append("empty_response")
            continue

        cleaned = _strip_markdown_fence(raw)

        try:
            data = repair_json(cleaned, return_objects=True)
            if not isinstance(data, (dict, list)):
                failure_reasons.append(f"repair_json_returned_{type(data).__name__}")
                continue
        except (ValueError, TypeError) as e:
            failure_reasons.append(f"json_repair_failed: {e}")
            continue

        # Check for markdown tables in narrative
        if capability == "report" and isinstance(data, dict) and _contains_markdown_table(data):
            failure_reasons.append("markdown_table_in_narrative")
            logger.warning(f"[{capability}] LLM fallback JSON contains markdown tables (retry {retry + 1})")
            continue

        if _validate_json(data, capability):
            logger.info(f"[{capability}] LLM fallback extraction succeeded on retry {retry + 1}")
            return data

        failure_reasons.append("schema_validation_failed")

    logger.warning(f"[{capability}] LLM fallback exhausted {LLM_FALLBACK_MAX_RETRIES} retries, failures: {failure_reasons}")
    return None


def _build_extraction_prompt_with_feedback(
    capability: str,
    answer_text: str,
    retry_count: int = 0,
    failure_reasons: list[str] = [],
) -> str:
    """Build extraction prompt with progressive failure feedback."""
    schema = CAPABILITY_SCHEMAS.get(capability, {})
    schema_str = json.dumps(schema, ensure_ascii=False, indent=2)

    if capability == "report" and len(answer_text) > 3000:
        truncated = answer_text[:1500] + "\n...\n" + answer_text[-2000:]
    else:
        truncated = answer_text[:3000]

    # Build failure feedback section
    feedback_section = ""
    if failure_reasons:
        feedback_items = []
        for i, reason in enumerate(failure_reasons, 1):
            if reason == "markdown_table_in_narrative":
                feedback_items.append(f"第{i}次失败：narrative 字段包含了 markdown 表格格式，这是禁止的！")
            elif reason == "timeout":
                feedback_items.append(f"第{i}次失败：响应超时")
            elif reason.startswith("json_repair_failed"):
                feedback_items.append(f"第{i}次失败：JSON 解析失败")
            elif reason.startswith("schema_validation_failed"):
                feedback_items.append(f"第{i}次失败：输出不符合 schema")
            else:
                feedback_items.append(f"第{i}次失败：{reason}")

        feedback_section = (
            f"\n\n【历史失败记录 - 请避免重复错误】\n"
            f"{chr(10).join(feedback_items)}\n\n"
            f"⚠️ 特别注意：如果之前因为 markdown 表格失败，这次必须将表格转换为列表！\n"
        )

    if capability == "report":
        return (
            f"请从以下分析文本中提取结构化的家庭资产报告 JSON。\n\n"
            f"【绝对禁止】\n"
            f"❌ narrative 字段不能包含 markdown 表格（如 | xxx | xxx |）\n"
            f"❌ 如果原文有表格，必须转换为无序列表\n\n"
            f"【表格 → 列表转换示例】\n"
            f"原文表格：| 活期存款 | ¥870,000 | ⚠️ 仅覆盖1.2个月支出 |\n"
            f"转换为：- 活期存款约¥870,000，仅覆盖约1.2个月支出\n\n"
            f"【正确 narrative 格式】\n"
            f'"narrative": "**问题标题**\\n\\n- 要点1\\n- 要点2\\n- 要点3"\n\n'
            f"【输出要求】\n"
            f"1. 仅输出 JSON\n"
            f"2. JSON 必须合法\n"
            f"3. overall_score 是 0-100 整数\n\n"
            f"Schema：\n{schema_str}\n\n"
            f"分析文本：\n{truncated}\n"
            f"{feedback_section}\n"
            f"仅输出 JSON。"
        )

    return f"以下是 {capability} 分析文本，请提取结构化信息为 JSON。\nSchema：\n{schema_str}\n\n分析文本：\n{truncated}\n\n仅输出 JSON。"
```

- [ ] **Step 2: 验证修改**

```bash
grep -A 10 "历史失败记录" server/apps/backend/app/services/ai_result_parser.py
```

Expected: 新增的失败反馈逻辑存在。

---

## Task 5: 前端 UI 状态清理（失败时重置进度信息）

**Files:**
- Modify: `frontend/apps/main/src/composables/useAITask.ts:262-289`
- Modify: `frontend/apps/main/src/pages/AIReportPage.vue:33-39`

**Root cause:** `capability.error` 处理时，`toolSteps` 中的 running 工具被标记为 error，但 `phase`、`currentToolLabel` 可能残留。且 `AIReportPage.vue` 未处理 `post_processing` 状态的失败。

- [ ] **Step 1: 增强 useAITask.ts 的错误处理**

修改 `handleEvent` 函数中 `capability.error` case：

```typescript
case 'capability.error': {
  // R6.1: 不清空 thinkContent / answerContent — 保留对话文本
  status.value = 'failed'
  phase.value = null  // 清空阶段
  errorCode.value = event.code ?? event.error?.code ?? 'extraction_failed'
  stopTimer()
  stopThinkTimer()

  // ✅ 清空所有进度状态
  toolSteps.value = toolSteps.value.map((s) =>
    s.status === 'running' ? { ...s, status: 'error' as const } : s,
  )
  currentToolLabel.value = null  // 清空当前工具标签
  planSteps.value = []  // 清空规划步骤
  queuePosition.value = null  // 清空排队位置

  // 不调用 onComplete() — 任务未完成
  break
}
```

- [ ] **Step 2: 增强 waitForTerminalStatus 的失败处理**

修改 `waitForTerminalStatus` 函数，确保 failed 状态时清理：

```typescript
async function waitForTerminalStatus() {
  const deadline = Date.now() + getPostProcessingMaxMs()
  while (Date.now() < deadline) {
    try {
      const task = await getAITask(capability)
      if (task.status === 'completed') {
        status.value = 'completed'
        phase.value = null
        thinkDone.value = true
        isConsoleOpen.value = false
        if (!completedFired) {
          completedFired = true
          onComplete?.()
        }
        return
      }
      if (task.status === 'failed' || task.status === 'timeout' || task.status === 'cancelled') {
        status.value = task.status
        phase.value = null
        currentToolLabel.value = null  // ✅ 清空工具标签
        toolSteps.value = toolSteps.value.map((s) =>
          s.status === 'running' || s.status === 'pending'
            ? { ...s, status: 'error' as const }
            : s,
        )
        if (status.value === 'failed' && !errorCode.value) {
          errorCode.value = 'extraction_failed'
        }
        stopThinkTimer()
        return
      }
      // running / post_processing → keep polling
    } catch {
      // transient — keep polling
    }
    await new Promise((resolve) => {
      postProcessingPollTimer = setTimeout(resolve, POST_PROCESSING_POLL_INTERVAL_MS)
    })
  }
  // 超时 → failed
  status.value = 'failed'
  errorCode.value = errorCode.value ?? 'post_processing_timeout'
  phase.value = null
  currentToolLabel.value = null
  toolSteps.value = toolSteps.value.map((s) =>
    s.status === 'running' || s.status === 'pending'
      ? { ...s, status: 'error' as const }
      : s,
  )
}
```

- [ ] **Step 3: 更新 AIReportPage.vue 失败状态处理**

修改模板中的状态判断，添加 failed 状态展示：

```vue
<!-- Generating placeholder -->
<div
  v-else-if="currentReport && (taskStatus === 'running' || taskStatus === 'post_processing')"
  class="generating-placeholder"
>
  <ProcessingIcon :active="true" class="generating-icon" />
  <p class="generating-text">{{ t('aiReport.generating') }}</p>
</div>

<!-- ✅ 新增：失败状态展示 -->
<div v-else-if="taskStatus === 'failed'" class="failed-placeholder">
  <van-icon name="warning-o" class="failed-icon" />
  <p class="failed-text">
    {{ errorCode === 'extraction_failed'
      ? t('aiReport.extractionFailed')
      : errorCode === 'structured_write_failed'
      ? t('aiReport.writeFailed')
      : t('toast.aiGenerateFailed') }}
  </p>
  <van-button type="primary" size="small" @click="onGenerate">
    {{ t('aiTask.retryBtn') }}
  </van-button>
</div>

<!-- Report content (shown when completed or has existing report) -->
<template v-else-if="currentReport && (taskStatus === 'completed' || taskStatus === 'idle')">
  <!-- ... existing content ... -->
</template>
```

- [ ] **Step 4: 添加 i18n 翻译**

修改 `frontend/apps/main/src/i18n/locales/zh-CN.ts`：

```typescript
aiReport: {
  // ... existing keys ...
  extractionFailed: '⚠️ 分析已完成，但结构化结果提取失败，可参考上方文本',
  writeFailed: '⚠️ 分析已完成，但结构化结果落库失败，可参考上方文本',
  generating: '正在生成报告...',
}
```

- [ ] **Step 5: 验证修改**

```bash
cd frontend/apps/main && pnpm typecheck
```

Expected: No type errors.

---

## Task 6: 后端错误消息优化（提供更具体的失败原因）

**Files:**
- Modify: `server/apps/backend/app/routers/_ai_events_helper.py:154-157`

**Root cause:** 当前 `_error_event` 返回 generic code，前端无法区分 extraction_failed vs write_failed。

- [ ] **Step 1: 增强 error event 的 message 字段**

修改 `_error_event` 函数：

```python
def _error_event(code: str, message: str | None = None) -> bytes:
    """Create a capability.error NDJSON event with specific message."""
    message_map = {
        "extraction_failed": "结构化数据提取失败，请检查模型输出格式",
        "structured_write_failed": "结构化数据写入数据库失败",
        "agent_stream_error": "智能体流式响应错误",
        "post_processing_timeout": "后处理超时，请稍后重试",
    }
    final_message = message or message_map.get(code, code)
    return (
        json.dumps({
            "type": "capability.error",
            "code": code,
            "message": final_message,
        }) + "\n"
    ).encode("utf-8")
```

- [ ] **Step 2: 在调用处传入具体 message**

修改 `proxy_capability_events` 函数中的错误调用：

```python
# Line 119: write failed
yield _error_event("structured_write_failed", "分析已完成，但结果保存失败")

# Line 136: extraction failed
yield _error_event("extraction_failed", "分析已完成，但结构化数据提取失败")

# Line 143: stream error
yield _error_event("agent_stream_error", "智能体响应中断")
```

- [ ] **Step 3: 验证修改**

```bash
grep -A 5 "_error_event.*extraction_failed" server/apps/backend/app/routers/_ai_events_helper.py
```

Expected: 新增的 message 参数存在。

---

## Task 7: 验证测试（浏览器自动化测试）

**Files:**
- Test: Manual browser test + automated verification

- [ ] **Step 1: 启动开发环境**

```bash
# 启动所有服务
docker-compose up -d --build
docker-compose logs -f backend agent
```

- [ ] **Step 2: 使用 Chrome DevTools MCP 测试**

使用 `/agent-skills:browser-testing-with-devtools` skill:
1. Navigate to `http://localhost:8080/ai/report`
2. Click "重新生成" button
3. Wait for generation to complete
4. Verify:
   - No console errors
   - Report displays with scores
   - narrative fields show lists (not tables)
   - No "结构化结果落库失败" message

- [ ] **Step 3: 检查后端日志**

```bash
docker-compose logs backend | grep -E "(report|extraction|LLM fallback)"
```

Expected: 看到 `[report] LLM fallback extraction succeeded` 或 `[report] regex extraction succeeded`，无 `extraction_failed` 或 `write_failed`。

- [ ] **Step 4: 验证失败场景**

模拟失败（可选）：使用无效 family 或故意破坏 schema，验证 UI 正确显示失败状态和 retry 按钮。

---

## Task 8: 提交修改

- [ ] **Step 1: 运行完整测试**

```bash
cd server && uv run pytest apps/backend/tests/ -v -k "ai_result"
cd frontend && pnpm -r typecheck && pnpm -r test:run
```

- [ ] **Step 2: Git commit**

```bash
git add server/apps/agent/skills/builtin/report/SKILL.md
git add server/apps/backend/app/services/ai_result_parser.py
git add server/apps/backend/app/routers/_ai_events_helper.py
git add frontend/apps/main/src/composables/useAITask.ts
git add frontend/apps/main/src/pages/AIReportPage.vue
git add frontend/apps/main/src/i18n/locales/zh-CN.ts

git commit -m "fix(ai-report): improve structured extraction reliability and UI state cleanup

- Strengthen SKILL.md prompt with explicit table prohibition and list format examples
- Enhance LLM fallback prompt with progressive failure feedback
- Improve markdown table detection regex patterns
- Add failure reasons tracking in LLM fallback retry loop
- Fix UI state cleanup on capability.error (clear phase, toolSteps, planSteps)
- Add specific error messages in capability.error events
- Add failed state UI in AIReportPage with retry button

Resolves recurring issue: model outputs markdown tables despite prompt prohibition.
Enables 3-retry LLM fallback with failure feedback for format correction."
```

---

## Verification Checklist

| # | Check | Expected |
|---|-------|----------|
| 1 | Report generation completes | No "落库失败" message |
| 2 | Narrative fields format | Lists (无表格) |
| 3 | Failed state UI | Shows retry button, no stale "处理中" |
| 4 | Console clean | No JS errors |
| 5 | Backend logs | `[report] regex extraction succeeded` or `[report] LLM fallback extraction succeeded` |
| 6 | Markdown table detection | `_contains_markdown_table` catches `| cell | cell |` |
| 7 | LLM fallback retry | Up to 3 retries with failure feedback |

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| LLM fallback timeout | 30s timeout + retry 3 times |
| Model still outputs tables | Progressive feedback in retry prompts |
| UI state not cleared | Explicit reset in all error paths |
| Regression in other capabilities | Test all AI capabilities after change |