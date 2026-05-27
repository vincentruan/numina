---
date: 2026-05-26
topic: ai-page-agent-skill-restructure
---

# /ai 页面智能体与技能职责重构

## Summary

把 `/ai` 页面重构为以"智能体"为入口的统一界面：用户看到两个系统智能体（AI问答 = 通用问答；数鸣 = 品牌化家庭财务大使，运行时自动持有所有已启用 skill）、一个固定规则应用（资产时光机）、以及 N 个家庭自定义智能体。Skill 管理只负责 skill — 把当前错误归入"fixed skills"的 chat / time_machine 移除；把现有六个 builtin 业务智能体（资产体检、配置漂移、闲置清仓、资金泄漏、负债优化、老化预警）从 agent 降级为 skill。资产时光机保留独立页面入口，同时作为 MCP 工具暴露给智能体调用。

---

## Problem Frame

当前 `/ai` 页面的智能体与技能模型存在概念混淆，导致用户无法正确理解和使用 AI 入口：

**问题 1：系统智能体不可见。** 数据库 (`a53453cf574b_unified_agent_model.py`) 已经种入了两个 `agent_type='system'` 的智能体（`ai-assistant` 和 `time-machine`），但 `AIHubPage.vue` 调用 `<AgentGrid>` 时只传入了 `builtinAgents` 和 `customAgents`，过滤掉了 system 智能体。结果：用户在 `/ai` 上看不到 AI问答这个智能体；底部的聊天输入框是"游离"的，没有归属任何智能体卡片。

**问题 2：智能体与技能职责混淆。** `ai_skills.py` 的 `FIXED_CAPABILITIES = ["chat", "time_machine"]` 把"AI问答"和"资产时光机"放在了 SkillsManagePage 顶部作为只读"固定技能"。但概念上它们是两类完全不同的东西：`chat` 是 AI问答智能体的载体（应该是 agent），`time_machine` 是固定规则的应用（应该是独立 App）。它们和 `report` / `allocation` / `disposal` 这些业务能力（这些才是 skill）被错误地放在同一个管理页面里。

**问题 3：六个业务智能体的双重身份。** 资产体检、配置漂移、闲置清仓、资金泄漏、负债优化、老化预警目前同时以两种身份存在：(a) 在 `ai_agents` 表中作为 `agent_type='builtin'` 的智能体行；(b) 在 `agent/skills/*.md` 和 `BUILTIN_CAPABILITIES` 中作为可启用的 skill。它们不是规则计算，而是"应用规则 + LLM 总结"，本质上是 skill 而非智能体。这种双重身份让 `/ai` 网格被六张业务智能体卡片占据，遮蔽了"以智能体为入口"的产品意图。

**问题 4：缺少品牌化主入口。** 目前没有一个体现 Numina 品牌的"主智能体"。用户没有一个温暖的、有品牌人格的、能直接调用所有家庭已启用能力的入口；只有一个冷冰冰的"AI助手"和散落的功能卡片。

---

## Actors

- A1. **家庭主理人 (owner)**：管理智能体（启用、禁用、自定义、删除）和技能（启用、禁用、自定义）。是唯一可以创建自定义智能体、编辑数鸣技能选择的角色。
- A2. **家庭成年成员 (adult)**：在 `/ai` 页面消费智能体能力（与 AI问答、数鸣聊天，使用资产时光机）。可见所有已启用智能体。
- A3. **AI问答智能体 (system)**：通用对话能力，不绑定任何业务 skill。轻量、低 token 消耗。
- A4. **数鸣智能体 (system)**：Numina 品牌人格，soul 偏温暖管家风格；运行时自动持有家庭已启用的全部业务 skill；调用 skill 时在聊天中流式输出结果。
- A5. **资产时光机 (固定规则 App)**：基于既有规则的 What-if 模拟与财务推演计算器，独立页面入口；同时作为 MCP 工具暴露给智能体调用。
- A6. **自定义智能体 (custom)**：owner 创建的智能体，可挑选要装载的 skill。

---

## Key Flows

- F1. **用户在 `/ai` 进入数鸣并询问"看看我们家配置漂移"**
  - **Trigger:** 用户点击数鸣卡片或在聊天输入框选中数鸣后输入问题
  - **Actors:** A2、A4
  - **Steps:**
    1. 进入 `/ai/chat?agentId=<numina_id>`
    2. 前端加载该智能体的 `soul_md` 和已启用 skill 列表（数鸣使用 sentinel `["*"]` 含所有 family 已启用 skill）
    3. 用户输入问题，agent 服务进行意图识别匹配到 `allocation` skill
    4. 调用对应 skill 后端，结果（数据 + 文本总结）以流式 SSE 返回到聊天界面
    5. 聊天界面流式渲染文本总结，并附上一个"查看完整页面"的 CTA 按钮跳转到对应 `/ai/<skill>` 页面（本期不渲染图表组件）
  - **Outcome:** 用户在不离开聊天的前提下看到配置漂移结果；如需深入可点击 CTA 跳转 `/ai/allocation`
  - **Covered by:** R3、R4、R6、R7、R11

- F2. **用户使用 AI问答询问"我家净资产是多少"**
  - **Trigger:** 用户点击 AI问答卡片或在聊天输入框选中 AI问答
  - **Actors:** A2、A3
  - **Steps:**
    1. 进入 `/ai/chat?agentId=<ai-assistant_id>`
    2. AI问答智能体仅装载 `chat` 能力，不调用业务 skill
    3. 通过 LLM 直接回答，不进入 skill 调度，**不调用** dashboard 等家庭财务数据 API
  - **Outcome:** 用户得到通用问答回复，不触发业务 skill 计算路径
  - **Covered by:** R2、R8

- F3. **owner 在设置页管理 skill**
  - **Trigger:** owner 进入 `/settings/ai/skills`
  - **Actors:** A1
  - **Steps:**
    1. 页面顶部的"固定技能"区被移除
    2. 列表显示六个 builtin 业务 skill（report / alerts / allocation / disposal / liability / spending_leak）+ 任意自定义 skill，每项可独立开关
    3. owner 切换某个 skill 的开关，立即生效
    4. 数鸣下次对话自动反映新的 skill 列表（无需手动同步）
  - **Outcome:** Skill 管理页只管 skill；chat 与 time_machine 不再以 skill 身份出现
  - **Covered by:** R5、R6、R8、R9、R12

- F4. **用户从 `/ai` 直接进入资产时光机**
  - **Trigger:** 用户点击资产时光机卡片
  - **Actors:** A2、A5
  - **Steps:**
    1. 跳转 `/ai/time-machine`（现有页面，逻辑不变）
    2. 用户使用 What-if 模拟器、购买力计算器等
  - **Outcome:** 资产时光机继续作为独立功能页面工作，未受重构影响
  - **Covered by:** R13

---

## Requirements

**`/ai` 页面智能体网格**

- R1. `/ai` 页面（`AIHubPage.vue`）的智能体网格按以下顺序渲染：
  1. 系统智能体区（i18n key: `agents.systemAgents`）：AI问答、数鸣
  2. 应用区（i18n key: `agents.apps`）：资产时光机（作为单独的固定规则应用卡片，非智能体）
  3. 自定义智能体区（i18n key: `agents.customAgents`）：family 创建的所有 custom agent
  4. owner 看到末尾的"创建智能体"占位卡片

  原本占据网格的六个 builtin 业务智能体卡片不再出现在 `/ai`。

  **空态约定**：当 family 没有任何自定义智能体时，自定义智能体区仍渲染章节标题，下方显示 `agents.noCustomAgents` 的提示文案；owner 视图额外显示"创建智能体"占位卡，非 owner 视图不显示占位卡。

- R2. **AgentGrid 组件契约修改**：`AgentGrid.vue` 现有 `builtinAgents`/`customAgents` props 替换为 `systemAgents` 和 `customAgents`；`builtinAgents` prop 移除。AIHubPage 同步修改：移除对 `agentStore.builtinAgents` 的绑定，改为传 `agentStore.systemAgents.filter(a => a.is_enabled)`。

  **应用区 (资产时光机) 不通过 AgentGrid 渲染**：在 AIHubPage 模板中直接渲染一张独立的"应用"卡片（数据来源是前端常量），位于系统智能体区与自定义智能体区之间。这避免 AgentGrid 接受异构数据源 (typed `Agent[]` + 前端常量)，保持组件契约纯净。应用卡片可复用 AgentCard 视觉样式或单独定义。

- R3. 数鸣智能体卡片的图标渲染：当 `agent.agent_name === 'numina'` 时，使用 LoginPage 已有的 cursive Numina SVG 花体字 logo（提取为可复用的 `<NuminaLogo>` 组件）；其他智能体继续使用 `agent.icon` emoji。

  **NuminaLogo 组件实现细节**：
  - 提取后的组件需对所有 `<defs>` 中的 `id` 属性（`flourishGrad`, `textGrad`, `logoGlow`, `logoSoftglow`）进行实例级作用域处理（使用 Vue `useId()` 或前缀化），并相应更新所有 `url(#...)` 与 `filter` 引用，避免组件在同一页面渲染多次时的 SVG 引用冲突。
  - 在卡片图标槽位中的展示尺寸：`width: 100%; max-width: 80px; height: auto`，水平居中。卡片整体高度不因数鸣特殊渲染而变化。

- R4. 用户点击智能体卡片或使用底部聊天输入框时，进入 `/ai/chat?agentId=<id>`，AIChatPage 根据 agentId 加载该智能体的 soul、可用 skill、显示名称与图标。**所有智能体卡片（含 ai-assistant、numina、custom）统一通过 `agentId` 路由**，不再保留 `agent_name === 'ai-assistant'` 之类的 special-case 分支。

  **底部输入框收件人绑定 UI**：
  - 输入框上方显示 "发送给：<icon> <agent_display_name> ▾" 形式的 chip。默认指向数鸣（按 `agent_name === 'numina'` 从 `agentStore.systemAgents` 解析 ID）。
  - 点击 chip 弹出 Vant action sheet 列出所有已启用的 system + custom 智能体供切换。
  - `startChat()` 函数必须在路由 query 中注入 `agentId`，不再使用无 agentId 的旧路径。
  - AIChatPage 收到无 `agentId` 的旧链接（如 dashboard 浮动按钮）时，默认 fallback 到数鸣，不渲染错误状态。

  **Dashboard 浮动按钮**：必须更新为携带数鸣 `agentId` 跳转 `/ai/chat?agentId=<numina_id>`。

**系统智能体定义**

- R5. 系统智能体共两个，由 alembic migration 种入 `ai_agents` 表（`family_id=0`，`agent_type='system'`）：
  - **AI问答** (`agent_name='ai-assistant'`)：通用问答，`skills=["chat"]` 仅含通用聊天能力，soul 中性、专业。AI问答**不调用业务 skill**，也**不直接读取家庭财务数据 API**（如 dashboard）；其能力边界严格限于 LLM 通用对话。如用户提出业务问题，AI问答应礼貌引导用户切换到数鸣。这与数鸣的"业务全能体"形成清晰差异。
  - **数鸣** (`agent_name='numina'`)：品牌化家庭财务大使，`skills=["*"]` (sentinel) 表示运行时自动持有所有 family 已启用 skill。Soul 风格温暖、有 Numina 品牌人格、主动建议下一步行动。
  - 新建 alembic migration 必须同时插入数鸣的 system agent 行（agent_name='numina'，skills=["*"]）。两个系统智能体的 `soul_md` 内容**不可**直接以 markdown 字符串 inline 写入 migration 文件；应提取为 `server/packages/db/seeds/system_agents.py`（或同等 fixture），migration 通过 import 引用，避免迁移文件膨胀且支持 down 路径恢复。
  - **`chat` 能力的处理**：`chat` 从 BUILTIN_CAPABILITIES 移除（见 R8）后，作为**保留内部能力名**继续存在；dispatch 层识别 `skills=["chat"]` 为"纯 LLM 对话模式"，不进入 skill catalog 查找。在 R8 或本要求中明确该约定。

- R6. 数鸣的 sentinel 解析规则：当 agent.skills 包含 `"*"` 时，agent_dispatch / chat_adapter 在每次会话开始时查询当前 family 的 `family_skill_config` 表，把所有 `is_enabled=true` 的 skill 注入到运行时 skill 列表。skill toggle 后**不需要**回写 `ai_agents.skills` 字段。

  **零技能态行为**：当 sentinel 解析后返回空列表（新家庭、所有 skill 都未启用），数鸣不报错；它在首次问候时主动告知"目前没有启用任何业务能力，可前往设置 → AI → 技能管理开启"，并提供跳转入口。该行为通过 acceptance example 覆盖。

- R7. 数鸣调用 skill 的体验（**本期范围限制**）：默认在聊天界面流式输出**纯文本总结**，并附带"查看完整页面"的 CTA 按钮跳转到对应 `/ai/<skill>` 页面。**本期不包含在聊天内嵌入图表/卡片组件的渲染能力** — chart widget 渲染、SSE event protocol 扩展属于后续迭代（见 Scope Boundaries）。AE6 的环形图渲染描述移至 follow-on 需求；本期 AE6 仅保留文本总结 + CTA 按钮的验收。

**Skill 管理重构**

- R8. `BUILTIN_CAPABILITIES` 调整为只含六个业务 skill：`["report", "alerts", "allocation", "disposal", "liability", "spending_leak"]`。从中移除 `chat` 和 `time_machine`。

  **前端联动**：`SkillsManagePage.vue` 中的硬编码 `builtinIds` 数组同步更新为同一份六项列表（移除 `chat` 和 `time_machine`）；这两个 ID 仍**保留**为自定义 skill 的保留命名（不允许 owner 创建同名 custom skill），以避免 ID 重碰。

- R9. `FIXED_CAPABILITIES` 常量及"固定技能"概念被删除。`SkillsManagePage.vue` 顶部的"固定技能"分组**整段移除**（删除 `<van-cell-group :title="t('skills.fixedSkills')">` 元素及其 i18n key），不是用 `v-if` 条件隐藏。

  **后端 cleanup 三个位点**（必须全部清理，缺一不可）：
  1. `ai_skills.py` 中的 `FIXED_CAPABILITIES` 常量声明删除
  2. `toggle_skill_endpoint` 中 `if skill_id in FIXED_CAPABILITIES: raise ...` 守卫删除
  3. `list_skills_grouped` 中硬编码构造 `chat` / `time_machine` SkillDefinitionResponse 的 `fixed = [...]` 块删除；返回 schema 的 `fixed` 字段返回空数组或从 schema 中移除（与 R10 的字段决策对齐）

- R10. 现有 `/ai/skills` 路由及其它对 skill 的内部使用做对应清理：任何代码路径都不再把 `chat` 或 `time_machine` 当作 skill 处理。**显式包含**以下前端清理点：
  - `AIChatPage.vue` 的 `capabilityMeta` 常量：移除 `chat` 键；`time_machine` 键的处理（保留作为历史会话过滤标签 vs 完全移除）需要在 ce-plan 阶段确认现有历史会话数据。
  - `AIChatPage.vue` 中 `selectedCapability.value = 'chat'` 的默认值改为 `'all'` 或 family 已启用的第一个 skill。
  - 既有依赖 `chat` skill catalog 项的 health report 调度逻辑切换到"内部保留能力"路径（见 R5 中 chat 的处理约定）。

**业务智能体降级为 skill**

- R11. 通过 alembic migration 删除 `ai_agents` 表中六个 builtin 业务智能体行（资产体检、配置漂移、闲置清仓、资金泄漏、负债优化、老化预警）。这些功能继续作为 skill 存在于 `agent/skills/*.md` 文件和 `family_skill_config` 表中，不变。

- R12. 任何对这六个被删除智能体的引用同步清理：包括前端 `agent.agent_name` 路由判断、`AgentGrid` 默认排序、capability_catalog 中的 agent 关联（如有）。它们各自的页面（`/ai/report`、`/ai/allocation` 等）保留，作为 skill 调用结果的"详情页"使用。

  **明确清理清单**（缺一不可）：
  - `AIHubPage.vue` 的 `handleAgentConsult` 中 `if (agent.skills?.includes('report')) { router.push('/ai/report') }` 等基于 skill 的路由分支整体删除（这些智能体行已被 migration 删除，分支变成死代码）。`agent_name === 'ai-assistant'`、`agent_name === 'time-machine'` 等 special-case 分支也删除（per R4 改为统一 agentId 路由）。
  - `AgentsManagePage.vue` 的"内置智能体" `<van-cell-group :title="ai.builtinAgents">` section 移除（migration 后该 list 永远为空）。
  - 前端 `agentStore.builtinAgents` ref 仍保留（types `Agent[]` 不变），但因后端不再返回 builtin agents，运行时一律为空数组；后端 `AgentListResponse.builtin` 字段保留为兼容性目的、始终返回 `[]`（与 R17 决策一致）。
  - `capability_catalog.py` 中如存在与六个 builtin agent 关联的 metadata 字段，移除（仅保留作为 skill 描述的部分）。

**资产时光机的双重入口**

- R13. 资产时光机的现有页面 `/ai/time-machine` 保留，UI 不变；在 `/ai` 网格中以独立"应用"卡片形式展示（不属于智能体）。卡片图标可继续使用现有的 ⏰ emoji。

- R14. 资产时光机额外暴露为 MCP 工具的能力**降级为 follow-on 需求**，不在本期范围内。本期仅完成 R13 描述的页面入口与卡片展示；MCP 工具注册路径与 schema 设计推迟到下一迭代验证后再实现。**AE8 从本期 acceptance criteria 中移除**。

**自定义智能体的 skill 装载**

- R15. 自定义智能体（`agent_type='custom'`）的 skill 装载方式不变（owner 在创建/编辑时手动勾选要启用的 skill），不引入 sentinel — sentinel 仅适用于数鸣。

- R16. 数鸣（system 智能体）允许 owner 通过编辑入口查看其装载的 skill，但**不允许编辑** sentinel — 数鸣的"全能"特性是产品设计的一部分。

  **view-only UI 实现**：
  - owner 点击数鸣的 edit 按钮进入与 custom agent 相同的 `AgentEdit` 路由；该路由检测 `agent.agent_type === 'system'` 时进入 read-only 模式：
    - 所有表单 field（name、icon、color、soul_md、skills 多选）渲染为 disabled 态
    - skills 区域显示运行时**已解析的 family 已启用 skill 列表**（不显示字面 `["*"]` sentinel），每项前有锁形图标
    - 顶部显示 banner：`这是系统智能体，"数鸣"自动装载所有已启用技能。如需调整数鸣的能力，请前往「设置 → AI → 技能管理」开启或关闭技能。`
    - 保存按钮隐藏（不是 disabled，是从 DOM 中移除）；只保留"返回"按钮
  - 该路由不发起任何 PUT/PATCH 调用

- R17. **AE7 字段决策**：`AgentListResponse.builtin` 字段**保留**为后端 schema 字段，始终返回 `[]`，前端 TypeScript 类型保留 `builtin: Agent[]` 字段定义。这是后端 API 兼容性策略 — 不破坏现有调用方，前端组件不依赖该字段（per R12）。AE7 的验收文案相应更新（见 AE7 修订）。

---

## Acceptance Examples

- AE1. **Covers R1, R2, R3.** Given owner 进入 `/ai` 页面，when 页面渲染完成，then 网格依次显示：AI问答（系统）、数鸣（系统，使用花体字 logo）、资产时光机（应用区，⏰）、N 个自定义智能体、"创建智能体"占位卡。资产体检 / 配置漂移等六个旧 builtin 智能体卡片不再出现。

- AE2. **Covers R5, R6, R7.** Given 一个新注册的家庭只启用了 `report` 和 `allocation` 两个 skill，when 用户在数鸣聊天里问"我家闲置资产怎么样"，then agent 因为 `disposal` skill 未启用，回复"未启用闲置清仓能力，建议在设置中开启"，不调用 disposal skill。

- AE3. **Covers R5, R6.** Given 数鸣 agent 当前装载了 4 个 skill，when owner 在设置页启用第 5 个 skill，when 用户立刻在数鸣开始新对话，then 该新 skill 在本次对话中即可被调用，不需要重启 agent 服务或修改 agent.skills 字段。

- AE4. **Covers R8, R9.** Given owner 进入 `/settings/ai/skills`，when 页面渲染完成，then 顶部的"固定技能"分组消失；列表只显示六个业务 skill 的开关 + 自定义 skill；不再看到 chat 或 time_machine 这两个条目。

- AE5. **Covers R3.** Given 数鸣的 `agent.icon` 字段保持为 emoji '🤖'（兜底值），when 卡片渲染，then 实际显示的是 Numina 花体字 SVG（从 `agent_name === 'numina'` 触发的渲染分支），而不是 emoji。

- AE6. **Covers R7.** Given 用户在数鸣聊天里成功触发 `allocation` skill 调用，when skill 计算完成并流式返回，then 聊天界面在助手消息中渲染：(a) 文本总结、(b) 一个跳转到 `/ai/allocation` 的"查看完整页面" CTA 按钮。本期不渲染图表组件（chart widget 渲染推迟到 follow-on 迭代）。

- AE7. **Covers R11, R17.** Given migration 已应用并删除了六个 builtin agent 行，when 前端调用 `GET /ai/agents`，then 返回的 `builtin` 数组为 `[]`（字段保留以兼容现有调用方），`system` 数组只含 ai-assistant 和 numina；前端 `agentStore.builtinAgents` 也为空数组。

- AE8. **[已移除 — 推迟到 follow-on]** 资产时光机 MCP 工具调用验收推迟到 follow-on 迭代（per R14）。

- AE9. **Covers R6 (零技能态).** Given 一个新注册的家庭尚未启用任何 skill，when 用户进入数鸣对话并发送第一条消息，then 数鸣不报错，回复"目前没有启用任何业务能力"并附带"前往技能管理"的跳转 CTA；不进入 skill catalog 查找。

- AE10. **Covers R16 (数鸣只读编辑视图).** Given owner 点击 `/ai` 上数鸣卡片的 edit 按钮，when 进入 AgentEdit 路由，then 表单全部 disabled，skills 区显示 family 当前已启用的 skill 列表（每项前有锁形图标），顶部显示说明 banner，保存按钮从 DOM 移除；用户返回时不发起任何 PUT/PATCH 请求。

- AE11. **Covers R1 (非 owner 空态).** Given 一个非 owner 的家庭成员（adult）进入 `/ai` 页面，且 family 尚未创建任何 custom agent，when 页面渲染完成，then 自定义智能体区显示章节标题与"暂无自定义智能体"提示文案，**不显示**"创建智能体"占位卡。

---

## Success Criteria

**人类视角**

- 用户进入 `/ai` 后能立刻识别到"哪些是智能体（可对话）/ 哪些是应用（直接使用）"的清晰分区。
- owner 在 SkillsManagePage 不再因为"为什么 chat 和 time_machine 不能改？"而困惑。
- 当 owner 启用一个新 skill，数鸣自然能用，不需要任何额外步骤。
- 数鸣作为品牌主入口出现时，用户能感受到 Numina 的视觉品牌（花体字 logo）。

**下游交付质量**

- `/ai` 页面与 `/settings/ai/skills` 页面的概念边界清晰：智能体在前者、skill 在后者，无重叠管理界面。
- 对 `chat` / `time_machine` / 六个 builtin 业务智能体的所有遗留引用被清理，无 `agent_type='builtin'` 的孤儿行。
- 数据迁移可双向（up + down）：down 路径恢复 builtin agents（通过 migration 重新插入），保留回滚能力。
- 单元/集成测试覆盖 sentinel skill 解析、SkillsManagePage 列表、AIHubPage 渲染、AIChatPage agentId 路由分支。

---

## Scope Boundaries

- 儿童前端 (`frontend/apps/child`) 不在本次重构范围。
- 资产时光机本身的计算逻辑、UI、规则不改。仅新增 `/ai` 卡片入口（R13）。**MCP 工具暴露推迟到 follow-on 迭代**（R14 降级）。
- 自定义智能体的创建/编辑流程不改（仅微调 skill 选择列表 — 排除 chat / time_machine）。
- 不在本次新增"切换收件人"以外的多智能体并行对话能力。
- 不修改 `/ai/chat` 的会话存储模型（`ai_chat_messages` 表结构不变）。
- 不重新设计 dashboard 浮动按钮的视觉，但**必须更新其跳转 URL**为携带数鸣 agentId（per R4）。
- 不修改其他 AI 业务页面（`/ai/report` 等）的现有 UI 与逻辑；它们依然作为 skill 调用的"详情页"存在。
- **聊天内嵌入图表/卡片组件渲染推迟到 follow-on 迭代**：本期数鸣调用 skill 仅返回文本总结 + CTA 按钮，不扩展 SSE event protocol、不引入新的 widget 渲染机制。

---

## Key Decisions

- **数鸣 skill 装载使用 sentinel `["*"]` 而非同步写入。** 理由：避免每次 skill toggle 都要回写 agent.skills，减少同步点和数据漂移风险。代价：引入一个新的解析约定，但只此一例。
- **数鸣调用 skill 默认在聊天中流式输出，不跳转到原页面。** 理由：保持"以智能体为入口"的体验连贯性。代价：聊天界面最终需要支持图表/卡片组件渲染（本期以 CTA 按钮代替，chart widget 渲染推迟到 follow-on 迭代）。通过附加 CTA 按钮兼顾深度查看场景。
- **六个 builtin 业务智能体硬删除而非软隐藏。** 理由：`ai_agents` 表已被概念化为"用户对话入口"，把不再展示的行留在表中只会让查询和测试更混乱。down 路径保留可恢复性。
- **数鸣使用花体字 logo 通过特殊渲染分支而非新增字段。** 理由：唯一特例不值得引入 `icon_kind` 字段。代价：渲染组件中要识别 `agent_name === 'numina'`。如未来出现第二个特殊渲染智能体再考虑加字段。
- **资产时光机保留为独立页面 + MCP 工具，不变成智能体。** 理由：它是确定性规则计算，与"对话型智能体"语义不同。同时通过 MCP 让智能体能调用，二者不冲突。
- **AI问答与数鸣并存而非合并。** 理由：AI问答提供轻量、不绑业务的纯聊天，节省 token；数鸣是业务全能体。两者人格与能力不同。

---

## Dependencies / Assumptions

- 现有 `agent_dispatch` / `chat_adapter` 服务可以扩展支持 sentinel skill 解析（需在 ce-plan 阶段验证 `chat_adapter.py` 当前的 skill 加载逻辑）。
- 前端聊天界面（`AIChatPage.vue`）当前对结构化消息的渲染能力有限；现有 `AiFinalAnswer.vue` / `AiProcessBlock.vue` 组件提供了基础，但具体 widget 渲染**推迟到 follow-on 迭代**（本期不在范围内，见 Scope Boundaries）。
- LoginPage 中的 cursive Numina SVG 可以提取为独立 `<NuminaLogo>` 组件（[已验证] LoginPage.vue:14 处的 SVG 是 self-contained，仅依赖 inline gradient defs，可剥离）。
- MCP 工具暴露依赖现有 MCP server 注册机制（[未验证假设] 需 ce-plan 验证 numina 项目的 MCP 工具注册路径与 `time_machine` router 的兼容性）。
- 删除 builtin agent 行后，前端 `agent.ts` 类型 `AgentListResponse.builtin` 字段可能为空数组或废弃，需要决定是保留字段以兼容 API 形态，还是直接从类型中移除。

---

## Outstanding Questions

### Resolve Before Planning

- **[Affects R6][Technical]** sentinel skill 解析的具体实现位置：在 `agent_dispatch.py` 入口处？还是 `chat_adapter.py` 装载 skill 时？现有代码 `agent_dispatch` 调用 `client.get_enabled_skills()` 直接传给 `EffectiveConfigBuilder`，没有读 `agent.skills` 字段的分支。需要在 ce-plan 阶段决定：(a) 在 dispatch 入口加 sentinel 展开层，还是 (b) 在 EffectiveConfigBuilder 里加 per-agent 过滤。该决定阻塞 R5/R6/R15 的实现。

- **[Affects R5/R15][Technical]** per-agent skill 范围限定的实现机制：当前 `agent_dispatch` 把 family 全部 enabled skills 注入给所有 agent，没有按 `agent.skills` 字段过滤的逻辑。R5（AI问答 仅 chat）和 R15（custom agent 手动选 skill）都依赖此过滤。需要在 ce-plan 阶段验证 DeerFlow harness 是否支持 per-conversation skill 子集激活，若不支持则需要其他方案（如调度层在 EffectiveConfig build 前对 enabled_skills 做 intersection）。

- **[Affects R17/AE7][Decision]** 后端 `AgentListResponse.builtin` schema 字段保留为空数组 vs 完全移除：本文档 R17 决定保留为兼容性策略；ce-plan 阶段需要进一步审视：是否有任何外部消费方（API 测试、第三方）会因字段缺失出错？若无，可考虑在更晚的清理迭代里移除该字段。

**[Round-2 review additions]** 以下条目由二轮 review 发现，必须在 ce-plan 启动前解决：

- **[Affects R5][Technical]** `soul_md` fixture 路径决策：`server/packages/db/seeds/` 当前不存在；现有 migration `a53453cf574b` 直接 inline `soul_md` 为 SQL 字符串。R5 要求新的数鸣 migration 通过 fixture 引用，但没有可参考的先例。需要决定：(a) 创建 `server/packages/db/seeds/system_agents.py` 并验证 alembic env.py sys.path 可以 import；(b) 接受新 migration 也 inline（与现有 pattern 保持一致），并放弃 fixture 提取要求。该决定影响整个 R5 migration 的实现路径。

- **[Affects R4][Spec]** Dashboard 浮动聊天按钮当前在 `DashboardPage.vue` 中**不存在**（`grep` 全工程无匹配）。R4 写法是"必须更新"，但实际是"必须新建"。需要重新表述 R4：明确该按钮要在 DashboardPage.vue 新建（位置、视觉规格、是否依赖 family 是否启用 AI），并在 ce-plan 阶段决定具体实现细节。

- **[Affects R5][Architecture]** `chat` 保留能力的 dispatch path 二义性：当前代码有两条聊天执行路径——`routers/chat.py → ChatAdapter → DeerFlow` （硬编码 `capability='chat'`）和 `routers/agent_stream.py → agent_dispatch.py → EffectiveConfigBuilder`（新的 agentId 路径）。R5 的"`skills=["chat"]` 识别为纯 LLM 模式"约定没有指明 AI问答 / 数鸣 使用哪条 path。需在 ce-plan 阶段统一为一条 path，否则 chat 保留能力的语义无法落地。

- **[Affects R5+R11][Migration]** 新 migration 的 `down()` 路径与现有 `a53453cf574b` 的 `down()` 交互未规定：现有 migration `down()` 执行 `DELETE FROM ai_agents WHERE agent_type='system'`，会同时删除新 migration 插入的 numina 行。需要决定 numina migration 的 `down()` 是否应该是仅删除 numina 行（避免重复删除 ai-assistant），以及如何避免回滚链中的双删除问题。

- **[Affects R5/R6][Constraint]** 在 sentinel 解析与 per-agent skill scoping 都被推迟到 RBP 的情况下，R5（AI问答 不调用业务 skill）的语义在本期**无法被运行时强制执行**。如不在本期补上 enforcement，AI问答 在产线上会接收到全部 family enabled skills，与产品宣称的"轻量纯聊天"边界冲突。需要决定：(a) 把 R5 的 enforcement 也明确并入 RBP（即 R5 文字与运行时分离）；(b) 在本期至少补一个 minimal enforcement（如 dispatch 层硬编码 `if agent.skills == ["chat"]: enabled_skills = []` 简单守卫）。

- **[Affects R8][Backend]** `chat` / `time_machine` 作为"保留命名"在 R8 中说明，但当前 `CustomSkillCreate.validate_skill_id` 仅检查 `BUILTIN_CAPABILITIES`。R8 移除二者后，验证器不再阻止 owner 创建 `skill_id='chat'` 的 custom skill。需要在 ce-plan 中加入：新增独立 `RESERVED_NAMES = ["chat", "time_machine"]` 常量，并在 validate_skill_id 中追加该检查。建议视为可直接 Apply 的 gated_auto 修复。

- **[Affects R16][Frontend Scope]** `AgentFormPage.vue` 当前仅有 `isBuiltin` payload-restriction 守卫（限制 builtin agent 的可编辑字段），**没有** `agent_type === 'system'` 检查、字段 disabled、保存按钮 DOM 移除、banner 显示等 R16 要求的视图行为。R16 是实质性新 UI 工作（不是小修补），同时需要验证 `GET /ai/agents/:id` 返回的 schema 是否暴露 `agent_type` — 若否，还需后端 schema 调整。ce-plan 应据此估算更准的工作量。

- **[Affects AE1][Doc]** AE1 标注 "Covers R1, R2, R3" 但其 Given 仅写 owner 视角；R1 包含 owner 与非 owner 两个分支，非 owner 分支由 AE11 单独覆盖。AE1 的 Covers 标签更准确的写法是 `Covers R1 (owner view), R2, R3`。可作为 ce-plan 中的 doc-cleanup 任务直接修复。

- **[Affects AE9+AE10][Test]** AE9（零技能态）的 acceptance 依赖 sentinel 解析（已 RBP 推迟）；AE10（数鸣 read-only edit view）的 precondition 依赖 AgentGrid 对 system agent 暴露 edit 按钮——但 R2 / R16 都未指定 AgentGrid 是否对 system agent 渲染 edit affordance。两条 AE 在 RBP 决定之前都不可独立通过；需在 ce-plan 阶段明确 AE9/AE10 的实施顺序与依赖。

- **[Affects R10][Frontend]** `AIChatPage.vue` 的 `chat` filter tab 处理：保留则会显示历史 chat session（与 R10 移除 chat 概念矛盾）；移除则会隐藏既有用户的历史会话（静默回归）。该决策的两条路径都有产品代价，需在 ce-plan 阶段查阅现有 `ai_chat_messages` 中已有 `capability='chat'` 数据量后再决定。

### Deferred to Planning

- **[Affects R7][Technical]** 聊天界面渲染图表 / 卡片组件的具体协议（仅当 follow-on 迭代启动时需要）：是 SSE event type 区分（`event: chart_data`），还是消息内嵌结构化 JSON 由前端解析？需要看现有 `useAgentEventStream.ts` 的事件协议设计。本期不解决。

- **[Affects R14][Needs research]** 资产时光机暴露为 MCP 工具的具体 schema（仅当 follow-on 迭代启动时需要）：哪些参数（What-if、购买力、退休模拟等）作为独立工具，哪些合并为一个工具的多 mode？需要看 `ai_time_machine.py` 当前的输入输出 contract，以及 numina 项目 MCP 工具注册路径与 `time_machine` router 的兼容性。

- **[Affects R11][Technical]** alembic migration 的实现细节：六个 builtin agent 行的 down 路径如何恢复？per R5 决定，soul_md 应**不**在 migration 中 inline，而是从 `server/packages/db/seeds/system_agents.py` (或 `seeds/builtin_agents.py`) fixture 引用。ce-plan 阶段需确定 fixture 文件路径与 migration 之间的依赖关系。

- **[Affects R3][Technical]** `<NuminaLogo>` 组件应放在 `frontend/packages/` 还是 `frontend/apps/main/src/components/`？取决于子前端是否也会用到。建议放 `frontend/packages/`，因为 LoginPage 也会用（已经在 main app 中），未来 child app 若需品牌展示可复用。

- **[Affects R10][Technical]** `AIChatPage.vue` 中 `time_machine` 历史会话过滤标签的处理：保留作为"全部" tab 下的回看入口，还是作为独立 capability filter 删除？依赖现有 `ai_chat_messages` 中已存的 `capability='time_machine'` 数据量与产品价值判断。

- **[Affects R10][Technical]** 既有依赖 `chat` skill catalog 的 health report 调度逻辑（如 `ai_report.py` 是否调用 `BUILTIN_CAPABILITIES`）需要在 ce-plan 阶段全文搜索确认与重构。

- **[Affects R12][Technical]** `capability_catalog.py` 中 `_CAPABILITY_OVERRIDES` 是否包含 builtin agent 关联 metadata 而非仅 skill 描述？需在 ce-plan 阶段全文 audit。

- **[Affects R5][Technical]** AI问答 是否有 dashboard 数据 API 的读权限？文档 R5 决定 AI问答**不直接读取**家庭财务数据，仅 LLM 通用对话；ce-plan 阶段验证现有 `/ai/chat` 路径是否已经有数据访问，并在必要时收紧 AI问答 的工具集。
