---
date: 2026-04-10
topic: ai-chat-assistant
---

# 自然语言资产问答助手

## Problem Frame

非主要用户（配偶、老人、子女）很少主动导航到正确的 Dashboard 面板——他们有问题，但不知道去哪里找答案。即使是主要用户，在多个面板之间切换来回答一个简单问题（"我们家净资产比去年涨了多少？"）也需要多步操作。

自然语言问答助手将访问门槛降至零：任何家庭成员都能用中文提问，助手将问题翻译为对家庭数据的结构化查询，返回直接答案。这是所有 AI 功能中杠杆效应最高的单一界面改变。

**设计约束：**
- 支持固定意图集（8-10个），意图识别失败时优雅降级
- 对话历史持久化到数据库，严格按家庭隔离
- Dashboard 浮动按钮入口 + 全屏聊天页

```
Dashboard 右下角浮动按钮（ai_enabled == true 时显示）
         │ 点击
         ▼
AIChatPage.vue（全屏聊天界面）
         │
         ├── 加载历史对话（GET /api/v1/ai/chat/history）
         │
         └── 用户输入问题
                  │
                  ▼
         POST /api/v1/ai/chat
                  │
                  ▼
         意图识别（LLM 分类，固定意图集）
                  │
         ┌────────┴────────┐
         │ 识别成功         │ 识别失败
         ▼                 ▼
  调用对应数据 API    返回降级回复
  组装上下文          + 示例问题
         │
         ▼
  LLM 生成自然语言回答
         │
         ▼
  存储对话记录（family_id 隔离）
         │
         ▼
  返回回答 + 追加到对话历史
```

---

## Requirements

**AI 基础设施前提（依赖 Phase 0）**

- R0. 依赖 `docs/brainstorms/2026-04-10-001-ai-health-report-requirements.md` 中 R0-R6 的基础设施。

**后端：对话存储**

- R1. 新增 `ai_chat_messages` 表，字段：`id`、`family_id`（FK，严格隔离，所有查询必须带 `family_id` 过滤）、`user_id`（发送消息的成员）、`role`（`user` / `assistant`）、`content`（消息文本）、`intent`（识别到的意图，`assistant` 消息专属，可为 NULL）、`created_at`。
- R2. 数据隔离保证：
  - 所有 `ai_chat_messages` 的读写操作必须同时过滤 `family_id == current_user.family_id`
  - 不存在跨家庭读取消息的接口
  - `GET /api/v1/ai/chat/history` 仅返回当前用户所在家庭的消息
- R3. 每个家庭保留最近 100 条消息（`user` + `assistant` 各计一条）；超出时在数据库事务中使用 `SELECT FOR UPDATE` 锁定后删除最旧的消息对（一条 `user` + 对应一条 `assistant`），保证并发写入时清理逻辑的原子性。
- R4. `GET /api/v1/ai/chat/history` 返回当前家庭最近 50 条消息（按 `created_at` 升序），用于页面初始化时加载历史对话。
- R5. `DELETE /api/v1/ai/chat/history` 清空当前家庭的全部对话历史；仅家庭管理员（`role == 'owner'`）可调用，权限检查通过可复用的 FastAPI dependency（`require_owner = Depends(...)`）实现，与 `family.py` 中现有 owner 检查模式一致。

**后端：问答接口**

- R6. `POST /api/v1/ai/chat` 接收 `{"message": str}`，执行以下步骤：
  1. 在单一事务中同时写入用户消息（`role: user`）和占位 AI 消息（`role: assistant, content: "__pending__", status: pending`），保证消息对完整性
  2. 执行意图识别 → 数据查询 → LLM 生成回答
  3. 更新占位 AI 消息为实际回答内容（`status: completed`）
  4. LLM 超时或失败时，将占位消息更新为错误提示文本（"查询超时，请稍后再试"，`status: error`），不删除消息对
  5. 返回 AI 回答文本
- R6a. `agent/` 模块在每次内部 HTTP 调用时，将原始用户的 `family_id` 作为不可篡改的请求 header（`X-Family-Id`）传递；backend 端点验证该 header 与 `AGENT_INTERNAL_TOKEN` 绑定的服务身份一致，并强制以此 `family_id` 过滤所有数据查询，不接受 caller 自行传入的 `family_id` 参数。
- R7. 支持的意图集（8个）及对应数据源：

  | 意图 | 示例问题 | 数据源 |
  |------|---------|--------|
  | `net_worth_query` | 我们家净资产是多少？ | `/dashboard/overview` |
  | `net_worth_trend` | 净资产比去年涨了多少？ | `/dashboard/trend` |
  | `asset_allocation` | 我们家资产怎么分配的？ | `/dashboard/allocation` |
  | `top_assets` | 哪项资产价值最高？ | `/dashboard/top-assets` |
  | `liability_status` | 我们还有多少负债？ | `/dashboard/overview` + liabilities |
  | `idle_assets` | 有哪些闲置资产？ | `/dashboard/low-usage` |
  | `daily_cost` | 哪项资产最费钱？ | `/dashboard/daily-cost-ranking` |
  | `member_assets` | 谁的资产最多？ | `/family/aggregate`（仅此端点，**禁止**调用 `/family/members/{id}/summary` 或任何返回 `UserResponse` 的端点，避免真实姓名泄露给 LLM） |

- R8. 意图识别失败时（LLM 无法将问题映射到上述 8 个意图之一），返回固定降级回复："我暂时无法回答这个问题。你可以试试问：[随机展示 3 个示例问题]"；降级回复同样写入 `ai_chat_messages`，`intent` 字段为 `unknown`。
- R9. 脱敏要求：发送给 LLM 的数据为各数据源返回的聚合数据（比率、排名、区间），不包含成员姓名（替换为"成员A/B/C"）、精确账号信息；金额保留精确值（与体检报告一致的脱敏策略）。
- R10. 问答接口 per-family 限速：每小时最多 60 次（问答是高频交互）。
- R11. 单次问答端到端响应时间目标 < 6 秒（P90）；超时时将占位 AI 消息更新为"查询超时，请稍后再试"（`status: error`），消息对保持完整，不出现孤儿消息。

**前端：浮动入口**

- R12. `DashboardPage.vue` 右下角新增浮动按钮（Vant `FloatingBubble` 或自定义），仅当 `ai_enabled == true` 时显示；按钮使用 AI 相关图标（sprite icon）。
- R13. 浮动按钮位置固定在右下角，不遮挡底部 Tab 栏（`bottom` 偏移量 = Tab 栏高度 + 16px）；支持用户拖拽调整位置（Vant `FloatingBubble` 原生支持）。
- R14. 浮动按钮上显示未读消息红点：当有新的 AI 回复（`created_at` 晚于用户上次打开聊天页的时间）时显示红点；进入聊天页后红点消失。未读时间戳存储在服务端 User 模型的 `ai_chat_last_read_at` 字段（Phase 0 新增），通过 `PUT /api/v1/ai/chat/read` 更新；与 httpOnly cookie 安全策略一致，跨设备同步。

**前端：聊天页面**

- R15. 新增 `AIChatPage.vue`，全屏展示，顶部 PageHeader 显示"AI 助手"+ 右上角"清空记录"按钮（仅管理员可见）。
- R16. 页面初始化时调用 `GET /api/v1/ai/chat/history` 加载历史消息，滚动到最新消息。
- R17. 消息气泡样式：用户消息右对齐（主题色背景），AI 回答左对齐（灰色背景）+ AI 头像图标；消息下方显示发送时间（`HH:mm` 格式）。
- R18. 页面底部固定输入区：文本输入框（最多 200 字，多行自适应高度）+ 发送按钮；发送按钮在输入非空时激活。
- R19. 输入区上方展示快捷问题 Chip 组（横向滚动，8 个意图各一个示例问题）；点击 Chip 后填入输入框并自动发送；Chip 组在用户开始输入时收起，输入框清空后展开。
- R20. 发送后 AI 回答位置立即显示 loading 气泡（三点动画），收到回答后替换为实际内容。
- R21. 当 `ai_enabled == false` 时，浮动按钮不渲染；直接访问 `/ai/chat` 路由时守卫重定向至 Dashboard。
- R22. 清空记录时弹出 Vant `Dialog` 确认框（"确认清空所有对话记录？此操作不可撤销"），确认后调用 `DELETE /api/v1/ai/chat/history`，清空前端消息列表。

**隐私与安全**

- R23. `ai_chat_messages` 表中的 `content` 字段存储明文（不加密）；数据库层面的安全依赖自托管部署的文件系统权限。
- R24. 管理员清空对话历史时，`security_log` 记录审计事件 `[ai_chat_cleared] family_id=X user_id=Y`。
- R25. 非管理员成员调用 `DELETE /api/v1/ai/chat/history` 时返回 `403 {"code": "ai_not_authorized"}`。

---

## Success Criteria

- 8 个支持意图的问题能得到基于真实家庭数据的准确回答。
- 意图识别失败时返回降级回复 + 示例问题，不返回空白或错误信息。
- 对话历史在刷新页面后保持，重新进入聊天页时正确加载。
- 不同家庭的对话历史严格隔离，无法跨家庭读取（可通过 API 测试验证）。
- 发送消息到收到回答 < 6 秒（P90）。
- 管理员清空记录后历史消息从 UI 和数据库中完全删除。

---

## Scope Boundaries

- 不包含语音输入（文字输入只）。
- 不包含图片/附件发送。
- 不包含消息的已读/未读状态追踪（红点仅基于时间戳判断）。
- 不包含多轮追问的上下文记忆——每次问答独立处理，不携带历史对话作为 LLM 上下文（降低 token 消耗和复杂度；历史仅用于 UI 展示）。
- 不包含 AI 主动发起对话或推送消息。
- 问答范围严格限于 8 个支持意图；不支持的问题返回降级回复，不尝试"尽力回答"。
- 不包含消息的导出功能。

---

## Key Decisions

- **固定意图集 + 优雅降级** — 范围清晰，不会因 LLM 自由调用 API 产生错误答案；降级回复引导用户提问可支持的问题。
- **对话历史持久化，严格家庭隔离** — 用户下次进入时可继续上下文；所有读写操作双重过滤 `family_id`，无跨家庭泄露风险。
- **每次问答独立处理，不携带历史作为 LLM 上下文** — 大幅降低 token 消耗；历史对话仅用于 UI 展示，不影响 AI 回答质量（每个问题都是独立查询）。
- **浮动按钮入口** — 不改变现有导航结构；移动端浮动气泡是成熟的聊天入口模式。
- **每家庭保留最近 100 条消息** — 平衡历史可查性与存储成本；自托管场景下存储敏感。
- **管理员专属清空权限** — 对话历史属于家庭共享数据，清空操作影响所有成员，需要管理员授权。

---

## Dependencies / Assumptions

- 依赖 Phase 0 基础设施（`agent/` 模块、`ai_enabled` 开关、限速中间件）。
- `family store`（`frontend/src/stores/family.ts`）已存在，`ai_enabled` 字段由 Phase 0 新增后可直接读取。
- Vant 4 的 `FloatingBubble` 组件支持拖拽定位，无需自定义实现。
- 意图识别通过单次 LLM 调用完成（分类任务），数据查询通过 `agent/` 模块内部 HTTP 调用 backend API，整体流程串行执行。
- 假设 8 个意图覆盖 80% 的用户实际问题；降级率可通过 `intent == 'unknown'` 的消息比例监控。

---

## Outstanding Questions

### Resolve Before Planning

无阻塞问题。

### Deferred to Planning

- **[影响 R6][需要研究]** 意图识别是否使用独立 LLM 调用（分类）+ 回答生成（第二次调用），还是合并为单次调用（分类 + 回答一步完成）？两次调用更清晰但延迟更高；单次调用更快但 prompt 更复杂。
- **[影响 R3][技术]** 消息对删除逻辑：超出 100 条时删除最旧的"消息对"（user + assistant），需要确保删除时两条消息原子性删除，避免出现孤立的 user 消息或 assistant 消息。
- **[影响 R14][技术]** 未读红点的"上次打开时间"存储方式：`localStorage`（前端）还是数据库字段（`ai_chat_last_read_at` on User）？localStorage 更简单但跨设备不同步。
- **[影响 R19][技术]** 快捷问题 Chip 的 8 个示例问题文案需要在规划时确定（中文，简洁，覆盖 8 个意图各一个）。

---

## Next Steps

→ `/ce:brainstorm`（创意 #7：资产分配漂移检测与再平衡提醒）
