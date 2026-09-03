# Area 13 — AI 资产报告深度验证 (Hub 弹窗 / 报告重入 / 步骤去重 / 取消按钮)

Shared conventions in [`_common.md`](../../_common.md).

本 Area 覆盖 2026-09-02 手工仿真测试中发现并修复的 AI 资产报告相关问题。
这些问题不在 Area 3（正常路径）和 Area 12（通用韧性）的覆盖范围内，而是聚焦于：

1. AI Hub 报告卡 stat popover 的内容准确性 + 显示完整性
2. 报告页离开再返回时 SSE 重连 + 步骤去重 + 取消按钮可见性

> **AI prerequisite:** AI 必须已启用 + provider 已配置（同 Area 3）。
> **Auth:** 复用 G0 成人 session（`demouser`），同 Area 3 的 cookie+localStorage 注入方式。

---

## 背景（修复提交）

本 Area 用例对应以下已提交修复（2026-09-02）：

| Commit | 修复内容 |
|--------|----------|
| `4ef652d9` | AI Hub stat popover 显示最低分 indicator 的 narrative（非仅 score）；报告页 `retryTrigger()` 重连 |
| `a7634b9c` | 移除 `:teleport="null"`，popover 挂载到 body 而非 `.hub-stats`，解决 z-index 被报告卡遮挡 |
| `81eb31af` | `handleAiMessage()` / `handleToolMessage()` 增加 ID-based dedup，防止 SSE 回放重复追加 |
| `5c9bcca5` | Dashboard narrative 在缓存命中时从 `generatedAt` 推导 `thinkingElapsed` |

---

## 用例

### C13.1 AI Hub — stat popover 内容准确性（alerts / suggestions / completeness）

**问题来源:** 手工测试发现点击不同 stat info 图标时，弹出的 popover 内容总是显示 completeness 的内容，而非对应的 alerts 或 suggestions。

**根因:** Vant Popover 内部 click handler 与外部 `activePopover` 状态管理冲突。`@update:show` 回调被内部 toggle 覆盖。

**修复:** 添加 `trigger="manual"` 禁用 Vant 内部 toggle；info 图标加 `@click.stop` 直接控制 `activePopover` 状态。

```
bsk navigate ${BASE}ai --session <id> --wait-until networkidle
bsk snapshot --session <id>

# 找到 3 个 stat card 的 info 图标（suggestions / alerts / completeness）
# 依次点击每个图标，验证 popover 内容正确

# 1) Alerts popover（最低分 indicator 的 narrative）
bsk click @eN --session <id>           # alerts info 图标
bsk snapshot --session <id>
bsk screenshot --session <id> --out dogfood-output/c13.1-alerts-popover.png

# 关闭 popover
bsk click @eBODY --session <id>        # 点击空白处关闭

# 2) Suggestions popover（最多建议 indicator 的 narrative）
bsk snapshot --session <id>
bsk click @eM --session <id>           # suggestions info 图标
bsk snapshot --session <id>
bsk screenshot --session <id> --out dogfood-output/c13.1-suggestions-popover.png

# 关闭 popover
bsk click @eBODY --session <id>

# 3) Completeness popover
bsk snapshot --session <id>
bsk click @eK --session <id>           # completeness info 图标
bsk snapshot --session <id>
bsk screenshot --session <id> --out dogfood-output/c13.1-completeness-popover.png
```

Assertions:
- [ ] **各图标独立触发**：点击 alerts 图标只显示 alerts popover，不触发其他 popover
- [ ] **Alerts 内容**：显示 score ≤ 2 的最低分 indicator 的 label + score + narrative（如"流动性（1/5）\n紧急备用金不足…"）
- [ ] **Suggestions 内容**：显示 suggestions 最多的 indicator 的 label + narrative
- [ ] **Completeness 内容**：显示数据完整度百分比 + 缺失项
- [ ] **关闭行为**：点击空白处 / 点击另一图标时当前 popover 关闭
- [ ] **互斥**：同时只有一个 popover 可见（`activePopover` 单值切换）
- [ ] `[console]` zero errors

### C13.2 AI Hub — stat popover 不被报告卡遮挡（z-index）

**问题来源:** 手工测试截图发现 AI Hub 页面的 stat popover 被下方的报告卡（report-summary-card）遮挡，只能看到 popover 上半部分。

**根因:** `:teleport="null"` 使 popover 渲染在 `.hub-stats` 内（inline），其 stacking context 低于后面的 `.report-card`。

**修复:** 移除 `:teleport="null"`，Vant 默认将 popover teleport 到 `<body>`，z-index 自然高于报告卡。

```
bsk navigate ${BASE}ai --session <id> --wait-until networkidle
bsk snapshot --session <id>
# 点击任意 stat info 图标展开 popover
bsk click @eN --session <id>           # 任一 info 图标
bsk screenshot --session <id> --out dogfood-output/c13.2-popover-zindex.png
```

Assertions:
- [ ] Popover 完整显示，不被下方报告卡截断或遮挡
- [ ] Popover 无 `max-height: 120px` 限制，内容无滚动截断（`overflow-y: auto` 已移除）
- [ ] Popover 的 `placement` 正确：alerts 使用 `bottom-end`，其他使用 `bottom`
- [ ] Popover 位置偏移 8px（`:offset="[0, 8]"`），不紧贴图标
- [ ] `[console]` zero errors

### C13.3 报告页 — 步骤时间轴去重（SSE 回放不重复追加）

**问题来源:** 每次进入正在运行的报告详情页面，"结构化解析"和"生成报告"步骤会重复追加（同一步骤出现 2 次以上）。

**根因:** `restoreStateFromStorage()` 从 sessionStorage 恢复了 `toolCalls` / `toolResults`，随后 SSE 回放事件又将同一批数据 push 进数组，导致重复。

**修复:** `handleAiMessage()` 和 `handleToolMessage()` 增加 ID-based dedup：检查 `tool_calls[i].id` / `tool_call_id` 是否已存在，存在则跳过。

```
# 前置：触发报告生成，等待 step1 出现 tool_call（如 get_family_overview）
bsk navigate ${BASE}ai/report --session <id> --wait-until networkidle
bsk snapshot --session <id>
bsk click @eN --session <id>           # 开始分析
bsk wait-ms 8s                         # 等待至少一个 tool_call 出现
bsk snapshot --session <id>

# 记录当前步骤数量
# 通过 snapshot 计算 tool-call-entry 数量
# N_BEFORE = count of tool-call entries visible

# 切走再回来（触发 restoreStateFromStorage + SSE 回放）
bsk navigate ${BASE}ai --session <id> --wait-until networkidle
bsk wait-ms 2s
bsk navigate ${BASE}ai/report --session <id> --wait-until networkidle
bsk wait-ms 3s                         # 等待 SSE 重连 + 回放
bsk snapshot --session <id>
bsk screenshot --session <id> --out dogfood-output/c13.3-step-dedup.png

# 再次切走再回来（二次验证）
bsk navigate ${BASE}ai --session <id> --wait-until networkidle
bsk wait-ms 2s
bsk navigate ${BASE}ai/report --session <id> --wait-until networkidle
bsk wait-ms 3s
bsk snapshot --session <id>
bsk screenshot --session <id> --out dogfood-output/c13.3-step-dedup-2nd.png
```

Assertions:
- [ ] **首次进入**：每个 tool_call 只出现一次（如 `get_family_overview` 仅一条）
- [ ] **第一次重入**：步骤数量不增加，没有重复追加（N_AFTER_1 == N_BEFORE）
- [ ] **第二次重入**：步骤数量仍不增加（N_AFTER_2 == N_BEFORE）
- [ ] tool_result 同样不重复（每个 tool_call 对应一条 result）
- [ ] 步骤状态正确：已完成步骤显示 done 状态，进行中步骤显示 running
- [ ] `[console]` zero errors

### C13.4 报告页 — 重入 SSE 重连 + 取消按钮可见性

**问题来源:** 手工测试发现：生成报告后退出页面再进入，页面一直卡在第一步（进度不推进），且没有显示终止按钮。

**根因:** `resume()` 失败（API error / race condition）时，sessionStorage 中 stream status 仍为 `'streaming'`，但 `reportTaskId` 为 null、SSE 未重连。结果 UI 显示"生成中"但实际没有 SSE 连接，也没有取消按钮（按钮依赖 `reportTaskId` 非 null）。

**修复:** `onMounted` 增加 `retryTrigger()` fallback：当 `resume()` 失败但 `isGenerating` 为 true 时，调用 `resumeHandle.retryTrigger()` 重新查找 task 并启动 SSE，同时设置 `reportTaskId`（使取消按钮可见）并注册 background task。

```
# 前置：触发报告生成（确保进入 streaming）
bsk navigate ${BASE}ai/report --session <id> --wait-until networkidle
bsk snapshot --session <id>
bsk click @eN --session <id>           # 开始分析
bsk wait-ms 5s                         # 确认 streaming（step1 running）
bsk snapshot --session <id>

# 切走
bsk navigate ${BASE}ai --session <id> --wait-until networkidle
bsk wait-ms 3s

# 返回报告页
bsk navigate ${BASE}ai/report --session <id> --wait-until networkidle
bsk wait-ms 3s                         # 等待 onMounted 恢复
bsk snapshot --session <id>
bsk screenshot --session <id> --out dogfood-output/c13.4-reentry-reconnect.png
```

Assertions:
- [ ] **恢复后步骤推进**：返回后步骤不再卡住，后续步骤正常从 pending → running → done
- [ ] **取消按钮可见**：若任务仍在 running，取消按钮（终止）立即出现（`reportTaskId` 被正确设置）
- [ ] **SSE 重连**：stream 状态为 reconnecting → streaming，新事件正常渲染
- [ ] **若 resume 成功**：走正常 resume 路径，`retryTrigger()` 不被调用
- [ ] **若 resume 失败但 task 存在**：`retryTrigger()` 找到 task 并重连 SSE
- [ ] **若 task 已完成**：直接加载报告，不显示生成中 UI
- [ ] `[console]` zero errors

### C13.5 Dashboard — narrative thinkingElapsed 缓存命中推导

**问题来源:** Dashboard 页面从缓存加载 narrative 时，thinking 耗时计时器不显示（或显示 0）。

**根因:** 缓存命中时 `generatedAt` 已设置但 `thinkingElapsed` 未从中推导，计时器 watcher 依赖 live streaming 的 timer，不适用于静态缓存。

**修复:** 添加 watcher：当 content 加载且 `generatedAt` 存在但 `thinkingElapsed` 为 0 时，从 `generatedAt` 推导 thinking 耗时。

```
# 前置：Dashboard narrative 已生成并缓存（首次访问后 narrative 已落库）
bsk navigate ${BASE} --session <id> --wait-until networkidle
bsk snapshot --session <id>
# 找到"本月洞察"卡片（DashboardNarrativeCard）
bsk screenshot --session <id> --out dogfood-output/c13.5-narrative-cache.png
```

Assertions:
- [ ] **缓存命中时**：narrative 内容立即显示（不闪烁 loading）
- [ ] **thinking 耗时显示**：即使从缓存加载，thinkingElapsed 仍显示合理值（从 `generatedAt` 推导）
- [ ] **非 streaming 状态**：缓存命中后 thinking timer 不持续跳动（静态值，非 live timer）
- [ ] **首次生成时**：thinkingElapsed 仍由 live timer 驱动（watcher 不干扰 streaming 路径）
- [ ] `[console]` zero errors

---

## 与已有 Area 的关系

| Area | 覆盖范围 | 本 Area 差异 |
|------|----------|------------|
| Area 3 (C3.1/C3.4) | AI Hub 正常渲染 + 报告 3 步时间轴 | C13.1/C13.2 聚焦 popover 交互缺陷回归 |
| Area 12 (C12.1/C12.2) | 通用韧性（离开/刷新/失败/取消） | C13.3/C13.4 聚焦本次修复的具体场景（dedup + retryTrigger fallback） |

执行建议：本 Area 用例可与 Area 3 合并执行（共用 AI Hub session），
C13.3/C13.4 在 Area 12 的 C12.1 之后运行（共用报告生成流程）。

---

## Quick Reference

| Case | 验证场景 | 对应修复 | 关键断言 |
|------|----------|----------|----------|
| C13.1 | Hub popover 内容准确性 | `trigger="manual"` + `@click.stop` | 各图标独立触发，内容对应 |
| C13.2 | Hub popover z-index | 移除 `:teleport="null"` | 不被报告卡遮挡，无 max-height 截断 |
| C13.3 | 步骤时间轴去重 | ID-based dedup in `handleAiMessage/handleToolMessage` | 多次重入步骤不重复 |
| C13.4 | 重入 SSE 重连 + 取消按钮 | `retryTrigger()` fallback in `onMounted` | 步骤推进 + 取消按钮可见 |
| C13.5 | narrative thinkingElapsed 推导 | watcher from `generatedAt` | 缓存命中仍显示耗时 |
