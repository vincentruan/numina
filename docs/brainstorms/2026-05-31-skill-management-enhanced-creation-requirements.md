---
date: 2026-05-31
topic: skill-management-enhanced-creation
---

# 技能管理增强 — 三页签创建 + AI 辅助 + 命令安装

## Summary

将现有"添加自定义技能"页面重构为三页签结构：页签一"命令安装"（统一输入框，简单模式正则解析 + 复杂模式 fallback 到 skill-installer 内置技能），页签二"AI 生成"（skill-creator 元技能生成标准 SKILL.md），页签三"手动编辑"（现有流程）。三渠道统一落库到租户隔离目录 + `ai_skills` 表，并标记来源类型。

---

## Problem Frame

当前自定义技能创建只有一种方式：用户在表单中手动填写名称、图标、提示词内容，系统拼接为 SKILL.md 保存。这带来两个问题：

**问题 1：格式质量不可控。** 用户手写的 prompt_content 缺乏结构化约束（没有 `## When to Use`、`## Instructions`、边界限制等标准段落），导致技能执行效果参差不齐。没有 AI 辅助优化的入口。

**问题 2：无法利用外部技能生态。** skills.sh、GitHub 等平台已有大量高质量的技能定义，但用户无法直接安装到自己的租户空间。只能手动复制粘贴内容到表单中，且无法保证格式兼容。

---

## Actors

- A1. **家庭主理人 (owner)**：唯一可以创建、安装、AI 生成技能的角色。管理技能的全生命周期。
- A2. **通用智能体 (ai-assistant)**：不带业务技能、仅有联网能力的系统智能体。执行 skill-installer 内置技能来解析复杂安装命令。
- A3. **skill-creator 元技能**：内置技能，接收用户描述后通过 LLM 生成标准 SKILL.md 结构。
- A4. **skill-installer 元技能**：内置技能，接收非标准安装命令后通过联网能力解析意图、定位技能源、下载安装。

---

## Key Flows

- F1. **用户通过命令安装技能（简单模式）**
  - **Trigger:** owner 在页签一输入框粘贴 `npx skills add anthropics/deploy-staging` 或 GitHub URL
  - **Actors:** A1
  - **Steps:**
    1. 前端提交输入文本到后端安装端点
    2. 后端正则解析器匹配为变体 A 或 B，提取 `provider/skill-name` 或仓库地址
    3. 后端通过安全 HTTP 客户端下载目标技能文件夹中的 SKILL.md
    4. 解析 SKILL.md frontmatter 提取 name/description
    5. 写入租户隔离目录 `{family_id}/skills_custom/{skill_id}/SKILL.md`
    6. 写入 `ai_skills` 表，`creation_type='cmd'`，`source_url` 记录原始来源
  - **Outcome:** 技能安装完成，出现在技能管理列表中
  - **Covered by:** R1, R2, R3, R5, R6

- F2. **用户通过命令安装技能（复杂模式 — AI fallback）**
  - **Trigger:** owner 在页签一输入框粘贴 `curl -fsSL https://skills.sh/install.sh | sh -s -- deploy-staging` 或其他非标准格式
  - **Actors:** A1, A2, A4
  - **Steps:**
    1. 前端提交输入文本到后端安装端点
    2. 后端正则解析器无法匹配已知模式
    3. 后端调用 skill-installer 内置技能（通过通用智能体 + 联网），传入原始文本
    4. skill-installer 理解用户意图，定位技能源 URL，下载 SKILL.md
    5. 后端接收 skill-installer 返回的技能内容
    6. 同 F1 步骤 4-6
  - **Outcome:** 同 F1
  - **Covered by:** R1, R2, R3, R4, R5, R6

- F3. **用户通过 AI 生成技能**
  - **Trigger:** owner 在页签二的 markdown 编辑器中输入技能描述，点击"AI 智能分析和生成"按钮
  - **Actors:** A1, A3
  - **Steps:**
    1. 前端提交用户描述文本到 AI 生成端点
    2. 后端调用 skill-creator 内置技能（通过 DeerFlowAdapter.dispatch）
    3. skill-creator 使用特定 system prompt 调用 LLM，生成包含标准 frontmatter + 结构化段落的 SKILL.md
    4. 后端返回生成的 SKILL.md 内容给前端预览
    5. 用户确认后，前端调用保存端点
    6. 写入租户隔离目录 + `ai_skills` 表，`creation_type='ai_created'`
  - **Outcome:** 用户获得专业级 SKILL.md，确认后保存
  - **Covered by:** R7, R8, R9, R5, R6

---

## Requirements

**页签一：命令安装**

- R1. 后端提供安装端点，接收用户输入的原始文本，支持以下变体的安全解析：
  - 变体 A（CLI 命令）：`npx skills add <provider>/<skill-name>`、`skillhub install <user>/<repo>`
  - 变体 B（直接 URL）：`https://github.com/<user>/<repo>`、`https://skills.sh/v1/skills/<skill-id>`
  - 变体 C 及其他非标准格式：fallback 到 skill-installer 内置技能

- R2. 安全解析器严禁直接执行 Shell 命令。通过正则/文本解析提取核心元数据（provider/skill-name 或 Git 地址），使用安全 HTTP 客户端定向拉取 SKILL.md 及配套资产。路径穿越（`../`）、命令注入字符必须被拒绝。

- R3. 正则解析失败时，调用 skill-installer 内置技能。该技能通过通用智能体（不带业务技能）+ 联网能力执行，理解用户意图后返回技能内容。

- R4. skill-installer 作为 builtin skill 注册在 `skills/builtin/skill-installer/SKILL.md`，其 SKILL.md 定义 skill-installer 的行为：接收安装命令文本 → 联网解析 → 返回 SKILL.md 内容。

**页签二：AI 生成**

- R7. 后端提供 AI 生成端点（如 `POST /api/v1/ai/skills/ai-create`），接收用户的自然语言描述，调用 skill-creator 生成标准 SKILL.md 内容并返回。

- R8. skill-creator 作为 builtin skill 安装在 `skills/builtin/skill-creator/SKILL.md`，内容参考 https://raw.githubusercontent.com/anthropics/skills/refs/heads/main/skills/skill-creator/SKILL.md 。其职责：接收大白话描述 → 输出包含 Frontmatter（name, description, trigger_phrases）、`## When to Use`、`## Instructions` 的完整专业级 SKILL.md。

- R9. AI 生成流程为两步：先生成预览（返回 SKILL.md 文本给前端展示），用户确认后再调用现有保存端点落库。不是一步到位自动保存。

**页签三：手动编辑**

- R10. 保留现有的手动创建流程不变（表单填写 skill_id、name、icon、color、prompt_content）。`creation_type='manual'`。

**跨页签通用约束**

- R5. 租户目录隔离（硬性）：所有渠道创建的技能文件必须存储在 `WORKSPACE_ROOT/{family_id}/skills_custom/{skill_id}/` 下。`family_id` 从 JWT token 的 `current_user.family_id` 获取，严禁从 request body 接受。路径组装时必须校验 skill_id 不含 `../` 或其他路径穿越字符。

- R6. DB 记录：所有渠道创建的技能均写入 `ai_skills` 表，必须包含：`family_id`、`skill_id`、从 SKILL.md frontmatter 解析的 `name`/`description`、`creation_type`（`'cmd'` | `'manual'` | `'ai_created'`）、`source_url`（命令安装时记录原始来源，其他渠道为 null）、`is_enabled=True`。

- R11. 并发控制：依赖 `ai_skills` 表已有的 `(family_id, skill_id)` unique constraint。安装/创建时若触发唯一约束冲突，返回明确错误提示"该技能已存在"。不引入额外锁机制。

- R12. skill-creator 和 skill-installer 两个内置技能必须从数鸣 sentinel `["*"]` 解析中排除。引入 `INTERNAL_ONLY_SKILLS` 排除列表，sentinel 解析时过滤这些技能，使其不暴露给数鸣智能体。

- R13. SKILL.md frontmatter 解析：安装/AI 生成后，后端必须解析 SKILL.md 头部的 YAML frontmatter 提取 `name` 和 `description` 字段写入 DB。解析失败时使用 skill_id 作为 fallback name。

---

## Acceptance Examples

- AE1. **Covers R1, R2, R5, R6.** Given owner 在页签一输入 `npx skills add anthropics/deploy-staging`，when 提交安装，then 后端解析出 `anthropics/deploy-staging`，从对应源下载 SKILL.md，写入 `{family_id}/skills_custom/deploy-staging/SKILL.md`，DB 记录 `creation_type='cmd'`、`source_url` 包含原始来源。

- AE2. **Covers R2.** Given 用户输入 `npx skills add ../../etc/passwd`，when 提交安装，then 后端拒绝请求，返回 400 错误"非法技能标识符"。

- AE3. **Covers R3, R4.** Given 用户输入 `curl -fsSL https://skills.sh/install.sh | sh -s -- deploy-staging`，when 正则解析失败，then 后端调用 skill-installer 内置技能，AI 解析出目标为 skills.sh 上的 deploy-staging 技能，联网下载并安装成功。

- AE4. **Covers R7, R8, R9.** Given owner 在页签二输入"帮我创建一个分析家庭月度支出趋势的技能"，when 点击 AI 生成按钮，then 返回包含标准 frontmatter + `## When to Use` + `## Instructions` 的 SKILL.md 预览；用户确认后保存，DB 记录 `creation_type='ai_created'`。

- AE5. **Covers R11.** Given family_id=100 已安装 skill_id='deploy-staging'，when 同一家庭再次安装同名技能，then 返回错误"该技能已存在"，不覆盖已有文件。

- AE6. **Covers R12.** Given 数鸣智能体 skills=["*"] sentinel 解析，when 查询 family 已启用技能列表，then 返回结果不包含 skill-creator 和 skill-installer。

---

## Success Criteria

**用户视角**
- owner 可以通过三种方式创建技能，每种方式都能产出格式规范的 SKILL.md
- 命令安装支持主流格式（GitHub URL、npx/skillhub 命令），非标准格式也能通过 AI fallback 处理
- AI 生成的技能质量明显优于手动编写（有标准段落结构、边界约束、触发短语）

**工程质量**
- 命令注入防御覆盖所有已知攻击向量（路径穿越、shell 元字符、超长输入）
- 租户隔离无越权路径 — 任何渠道都无法写入其他家庭的目录
- skill-creator/skill-installer 不会意外暴露给数鸣智能体

---

## Scope Boundaries

- 不做 skills.sh 内嵌浏览/搜索市场 UI — 本期只支持用户粘贴命令/URL
- 不做技能版本管理或升级检测 — 安装即最终态，不跟踪上游变更
- 不修改页签三（手动编辑）的现有 UI 和逻辑
- 不修改数鸣/AI问答智能体的 soul 或行为
- 不做技能的导出/分享功能
- 前端页签切换的 UI 交互细节（动画、默认选中页签）留给实现阶段决定

---

## Key Decisions

- **复杂输入 fallback 到 AI 而非穷举正则**：覆盖面更广，代价是多一次 LLM 调用。正则只处理明确的 A/B 变体，其余全部交给 skill-installer。
- **skill-creator 走 DeerFlowAdapter.dispatch() 而非 LLMClient.complete()**：符合架构约束（CLAUDE.md 明确要求所有 capability 执行走 DeerFlow），且 skill-creator 本身就是一个标准 DeerFlow skill。
- **并发控制用 DB unique constraint 乐观锁**：`(family_id, skill_id)` 约束已存在，安装操作天然幂等，不引入 Redis 等额外依赖。
- **sentinel 排除列表而非修改 sentinel 语义**：引入 `INTERNAL_ONLY_SKILLS = ["skill-creator", "skill-installer"]`，sentinel 解析时做差集过滤。这比修改 `["*"]` 的含义更安全、更可扩展。
- **AI 生成为两步流程（预览 + 确认保存）**：避免 LLM 输出不符合预期时直接落库，给用户一次审核机会。

---

## Dependencies / Assumptions

- skills.sh 和 GitHub 上的技能仓库为公开可访问（不需要认证 token）。如需支持私有仓库，需要额外的凭证管理机制（本期不在范围内）。
- skill-creator 的 SKILL.md 内容可从 anthropics/skills 仓库获取并适配为本项目的 builtin skill 格式。
- 通用智能体（ai-assistant）已具备联网/web_search 能力，skill-installer 可以利用该能力定位技能源。
- 现有 `DeerFlowAdapter.dispatch()` 支持以非流式方式调用 skill 并获取完整文本结果（用于 skill-creator 和 skill-installer 的同步调用场景）。

---

## Outstanding Questions

### Resolve Before Planning

- **[Affects R4][Technical]** skill-installer 的 SKILL.md 如何定义其"联网解析安装"行为？需要确认 DeerFlow skill 是否支持在 SKILL.md 中声明 `allowed-tools: [web_search]` 来启用联网能力，以及通用智能体如何被指定为执行者。

- **[Affects R12][Technical]** sentinel 排除列表的实现位置：在 `agent_dispatch.py` 的 sentinel 展开逻辑中？还是在 `CapabilityRegistry.list_capabilities_for_family()` 中？需要确认当前 sentinel 解析的具体代码路径。

### Deferred to Planning

- **[Affects R1][Needs research]** skills.sh API 的具体下载协议：是直接 GET raw 文件，还是有专门的 API endpoint？需要调研 skills.sh 的实际 HTTP 接口。

- **[Affects R8][Technical]** skill-creator 的 SKILL.md 从 anthropics/skills 仓库获取后，需要哪些适配修改才能作为本项目的 builtin skill 正常工作（如 frontmatter 字段对齐、allowed-tools 配置）。

- **[Affects R6][Technical]** `ai_skills` 表需要新增 `creation_type` 和 `source_url` 字段的 alembic migration。需要确认字段类型和默认值（现有记录的 `creation_type` 默认为 `'manual'`）。

- **[Affects R7][Technical]** AI 生成端点的超时策略：skill-creator 调用 LLM 生成可能耗时较长（10-30s），需要确认是同步等待还是异步轮询。
