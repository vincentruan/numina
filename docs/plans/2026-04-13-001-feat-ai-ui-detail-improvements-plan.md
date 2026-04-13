---
title: "feat: AI UI 细节优化 — 导航图标、BaseURL 配置、功能重新规划"
type: feat
status: completed
date: 2026-04-13
---

# feat: AI UI 细节优化 — 导航图标、BaseURL 配置、功能重新规划

## Overview

三项独立的 UI 细节优化：

1. **底部导航 AI 标签去掉文字标签**，仅保留 SVG 大脑图标（已有渐变圆形按钮），与其他标签的文字标签形成视觉区分，突出 AI 入口的特殊性。
2. **AI 配置页新增 Base URL 字段**，支持自定义 API 端点（兼容 OpenAI 兼容协议的第三方服务，如 Azure OpenAI、本地 Ollama、国内代理等）。需要前后端同步修改。
3. **Settings 页 AI 功能区重新规划**：将"AI 智能助手"（配置入口）保留，其余 6 个功能性入口从 Settings 移除，因为它们已经在 AIHubPage 的功能网格中有入口，放在 Settings 里属于错误归类。

## Problem Frame

- 导航栏 AI 标签当前显示 `<span class="ai-tab-label">AI</span>` 文字，与图标并列，视觉上冗余。其他标签用文字是因为没有特殊图标，AI 标签已有突出的渐变圆形图标，文字反而降低了视觉层次。
- AI 配置只支持 Anthropic 和 OpenAI 官方端点，无法配置自定义 Base URL，限制了兼容第三方 OpenAI 协议服务的能力。
- Settings 页的"AI 智能功能"分组混入了 6 个功能性页面链接（体检、预警、清仓、顾问、问答、漂移检测），这些功能的主入口是 `/ai`（AIHubPage），放在 Settings 里造成入口重复且语义错误（Settings 应只放配置项）。

## Requirements Trace

- R1. 底部导航 AI 标签不显示文字，仅显示 SVG 图标
- R2. AI 配置页（`/settings/ai`）新增 Base URL 输入字段，owner 可配置，支持空值（使用默认端点）
- R3. Base URL 字段需要识别"全路径"——即用户输入的值直接作为 API base，不再拼接默认域名
- R4. 后端 `Family` 模型新增 `ai_base_url` 字段，schema 和 router 同步更新
- R5. Settings 页"AI 智能功能"分组只保留"AI 智能助手"（配置入口），移除 6 个功能性链接
- R6. 所有改动保持无障碍合规（aria-label、键盘可访问性）

## Scope Boundaries

- 不修改 AIHubPage 的功能网格（功能入口已在那里，不需要改）
- 不修改 AI 功能页面本身（AIReportPage、AIChatPage 等）
- Base URL 不做格式校验（用户自行保证正确性），仅做非空时的基本 trim
- 不迁移已有数据库数据（新字段默认 NULL，等同于使用官方端点）
- 不修改 AI 服务调用逻辑（backend agent 层如何使用 base_url 属于独立任务）

## Context & Research

### Relevant Code and Patterns

- `frontend/src/components/common/AppTabBar.vue` — AI 标签当前在 `#icon` slot 内渲染 SVG + `<span class="ai-tab-label">AI</span>`，移除 span 即可
- `frontend/src/pages/AIConfigPage.vue` — 服务商配置区块（`van-cell-group inset title="服务商配置"`），新增 `van-field` 跟随 API Key 字段之后
- `frontend/src/pages/SettingsPage.vue` — "AI 智能功能" `van-cell-group`（lines 10–18），保留第一个 cell，删除后 6 个
- `frontend/src/api/ai.ts` — `AIConfig` 接口和 `AIConfigUpdate` 接口，需新增 `ai_base_url` 字段
- `frontend/src/stores/ai.ts` — `AIConfig` 类型透传，无需改动（类型从 api.ts 导入）
- `backend/app/models/family.py` — `Family` 模型，新增 `ai_base_url` 列
- `backend/app/schemas/ai_config.py` — `AIConfigResponse` 和 `AIConfigUpdate`，新增字段
- `backend/app/routers/ai_config.py` — GET/PUT 路由，需读写新字段

### Institutional Learnings

- `docs/solutions/ui-bugs/vant4-field-modelvalue-binding-2026-04-08.md`：`van-field` 必须用 `:model-value`（不是 `:value`）绑定响应式数据；只读 picker 字段用 `van-field` + `readonly` + `is-link` + `@click` 模式
- `docs/solutions/integration-issues/deerflow-harness-silent-fallback-and-concurrency-fixes-2026-04-12.md`：`AIConfigPage.vue` 中 `:aria-hidden` 必须绑定 boolean，不能是字符串 `'true'`；`role="button"` 的 div 需要 `@keydown.enter` + `@keydown.space.prevent`

### External References

- 无需外部研究，改动均为已知模式的直接应用

## Key Technical Decisions

- **移除 AI 标签文字而非替换**：`<span class="ai-tab-label">` 直接删除，不替换为空字符串或空格，避免 Vant tabbar 渲染空文字节点影响布局
- **Base URL 字段存储原始值**：后端存储用户输入的完整 URL（trim 后），不做标准化。调用方（agent 层）负责使用该值替换默认 base。字段为 `Text` 类型，允许 NULL（NULL = 使用默认端点）
- **Base URL 不加 provider 校验联动**：Base URL 对 anthropic 和 openai 均适用（用户可能用 anthropic 兼容代理），不做 provider 限制
- **Settings 页只删不加**：移除 6 个功能性 cell，不新增任何替代入口。AIHubPage 已是功能入口，Settings 不需要重复
- **数据库迁移**：新增 `ai_base_url` 列需要 Alembic migration，`nullable=True` 无需 default 值

## Open Questions

### Resolved During Planning

- **Base URL 是否需要前端格式校验？** 不需要。用户输入的是完整 URL（如 `https://my-proxy.com/v1`），trim 后直接存储，错误的 URL 会在测试连接时暴露
- **移除 Settings 功能链接后用户如何找到这些功能？** 通过底部导航 AI 标签 → AIHubPage 功能网格，这是设计上的主入口，Settings 里的链接本就是冗余的

### Deferred to Implementation

- Backend agent 层如何读取并使用 `ai_base_url` 替换 API 调用的 base endpoint（属于独立的 agent 层改动，不在本计划范围内）

## Implementation Units

- [ ] **Unit 1: 移除底部导航 AI 标签文字**

**Goal:** 底部导航 AI 标签只显示 SVG 图标，不显示"AI"文字

**Requirements:** R1, R6

**Dependencies:** 无

**Files:**
- Modify: `frontend/src/components/common/AppTabBar.vue`

**Approach:**
- 删除 `<span class="ai-tab-label">AI</span>`（line 27）
- 删除 `.ai-tab-label` CSS 规则（lines 94–98）
- `aria-label="AI 智能助手"` 已在 `van-tabbar-item` 上，无障碍不受影响

**Patterns to follow:**
- 现有 `#icon` slot 结构保持不变，仅移除 slot 外的文字 span

**Test scenarios:**
- Happy path: AI 标签渲染后，DOM 中不存在 `.ai-tab-label` 元素
- Happy path: AI 标签的 `aria-label="AI 智能助手"` 仍然存在
- Happy path: 其他 5 个标签的文字标签不受影响

**Verification:**
- `npm run build` 无类型错误
- 视觉检查：AI 标签只显示渐变圆形图标，无文字

---

- [ ] **Unit 2: Settings 页移除 AI 功能性链接**

**Goal:** "AI 智能功能"分组只保留"AI 智能助手"配置入口，移除 6 个功能性页面链接

**Requirements:** R5

**Dependencies:** 无（可与 Unit 1 并行）

**Files:**
- Modify: `frontend/src/pages/SettingsPage.vue`

**Approach:**
- 保留 `<van-cell title="AI 智能助手" icon="smile-o" is-link to="/settings/ai" />`（line 11）
- 删除 lines 12–17（家庭资产体检、资产老化预警、闲置资产清仓、负债优化顾问、AI 问答助手、配置漂移检测）
- 分组标题"AI 智能功能"保留，或改为"AI 配置"更准确——实现时选择更合适的措辞

**Patterns to follow:**
- 其他 `van-cell-group` 的单 cell 结构（如数据管理分组）

**Test scenarios:**
- Happy path: Settings 页"AI 智能功能"分组只有 1 个 cell（AI 智能助手）
- Happy path: 点击"AI 智能助手"仍然导航到 `/settings/ai`
- Edge case: 分组标题文字更新后 i18n key 不存在时不报错（若改为硬编码中文则无此问题）

**Verification:**
- `npm run build` 无错误
- Settings 页 AI 分组只显示一个配置入口

---

- [ ] **Unit 3: 后端新增 ai_base_url 字段**

**Goal:** `Family` 模型、Pydantic schemas、ai_config router 全部支持 `ai_base_url` 字段

**Requirements:** R2, R3, R4

**Dependencies:** 无（可与 Unit 1、2 并行）

**Files:**
- Modify: `backend/app/models/family.py`
- Modify: `backend/app/schemas/ai_config.py`
- Modify: `backend/app/routers/ai_config.py`
- Create: `backend/alembic/versions/<hash>_add_ai_base_url_to_families.py`
- Modify: `backend/tests/test_auth.py` 或相关测试（若有 AI config 测试）

**Approach:**
- `Family` 模型新增：`ai_base_url: Mapped[str | None] = mapped_column(Text, nullable=True)`
- `AIConfigResponse` 新增：`ai_base_url: str | None`
- `AIConfigUpdate` 新增：`ai_base_url: str | None = None`，加 `field_validator` 做 trim（`v.strip() if v else None`）
- `ai_config.py` router 的 GET 路由在构建 response 时包含 `ai_base_url`；PUT 路由在有值时写入 `family.ai_base_url`
- 生成 Alembic migration：`uv run alembic revision --autogenerate -m "add ai_base_url to families"`

**Patterns to follow:**
- `ai_api_key_encrypted` 的 nullable Text 列模式
- `AIConfigUpdate.validate_provider` 的 `field_validator` 模式（v2 风格）
- `AIConfigResponse` 的 `model_config = {"from_attributes": True}` 已有

**Test scenarios:**
- Happy path: GET `/ai/config` 返回 `ai_base_url: null`（未配置时）
- Happy path: PUT `/ai/config` 传入 `{"ai_base_url": "https://my-proxy.com/v1"}` 后 GET 返回该值
- Happy path: PUT `/ai/config` 传入 `{"ai_base_url": "  https://trimmed.com/v1  "}` 后存储为 trim 后的值
- Happy path: PUT `/ai/config` 传入 `{"ai_base_url": null}` 后 GET 返回 `null`
- Edge case: PUT `/ai/config` 传入 `{"ai_base_url": ""}` 后存储为 `null`（空字符串等同于未配置）

**Verification:**
- `uv run pytest tests/ -v` 全部通过
- `uv run mypy app/` 无新增类型错误
- `uv run alembic upgrade head` 成功执行

---

- [ ] **Unit 4: 前端 AI 配置页新增 Base URL 字段**

**Goal:** `AIConfigPage.vue` 在服务商配置区块新增 Base URL 输入字段，owner 可编辑，保存时一并提交

**Requirements:** R2, R3, R6

**Dependencies:** Unit 3（后端字段需先存在）

**Files:**
- Modify: `frontend/src/api/ai.ts`
- Modify: `frontend/src/pages/AIConfigPage.vue`

**Approach:**

`api/ai.ts`：
- `AIConfig` 接口新增 `ai_base_url: string | null`
- `AIConfigUpdate` 接口新增 `ai_base_url?: string | null`

`AIConfigPage.vue`：
- 在 API Key 字段之后，新增 `van-field` for Base URL：
  - `v-model="baseUrlInput"`
  - `label="Base URL"`
  - `placeholder="留空使用默认端点（可选）"`
  - `clearable`，`:disabled="saving"`
  - 无需 password toggle（URL 不是敏感信息）
- `onMounted` 时从 `aiStore.config.ai_base_url` 初始化 `baseUrlInput`
- `onSave` 时：若 `baseUrlInput.trim()` 非空则加入 payload；若为空字符串则传 `null`（清除已有值）
- 非 owner 视图：新增只读 cell 显示当前 Base URL（若有值）

**Patterns to follow:**
- `apiKeyInput` 的 `van-field` 模式（`:model-value` 绑定、`clearable`、`:disabled="saving"`）
- `docs/solutions/ui-bugs/vant4-field-modelvalue-binding-2026-04-08.md`：使用 `v-model` 或 `:model-value` + `@update:model-value`

**Test scenarios:**
- Happy path: 页面加载时 Base URL 字段显示已保存的值（或空）
- Happy path: 输入 Base URL 后点击保存，`updateConfig` 被调用且 payload 包含 `ai_base_url`
- Happy path: 清空 Base URL 字段后保存，payload 中 `ai_base_url` 为 `null`
- Edge case: 输入仅含空格的 Base URL，保存时传 `null`
- Happy path: 非 owner 用户看到 Base URL 只读展示（若已配置）

**Verification:**
- `npm run build` 无类型错误
- `npm run typecheck` 通过
- 手动测试：输入 Base URL → 保存 → 刷新页面 → 字段显示已保存的值

## System-Wide Impact

- **Interaction graph:** AppTabBar 是全局组件，修改影响所有使用 MainLayout 的页面；AIConfigPage 改动仅影响 `/settings/ai` 路由
- **Error propagation:** Base URL 字段为可选，空值不影响现有 AI 功能（agent 层继续使用默认端点）
- **State lifecycle risks:** `aiStore.config` 在 `onMounted` 时加载，新字段需在 `fetchConfig` 后才可读取——`onMounted` 中初始化 `baseUrlInput` 的时机已正确
- **API surface parity:** 后端 `AIConfigResponse` 新增字段是向后兼容的（前端旧版本会忽略未知字段）
- **Integration coverage:** Unit 3 的 Alembic migration 需在 Unit 4 前端改动部署前先执行
- **Unchanged invariants:** AI 功能页面（AIReportPage、AIChatPage 等）、AIHubPage 功能网格、路由配置均不变

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| Alembic migration 在 SQLite 上 ALTER TABLE 有限制 | SQLite 支持 ADD COLUMN，新增 nullable 列无问题 |
| 移除 Settings 功能链接后用户找不到功能入口 | AIHubPage 是主入口，底部导航 AI 标签直达；Settings 的链接本就是冗余的 |
| Base URL 字段空字符串 vs null 语义不一致 | 前端 trim 后空字符串传 null；后端 validator trim 后空字符串存 null，统一语义 |
| Unit 4 依赖 Unit 3 后端先部署 | 本地开发可同时改动；生产部署需先跑 migration |

## Sources & References

- Related code: `frontend/src/components/common/AppTabBar.vue`
- Related code: `frontend/src/pages/AIConfigPage.vue`
- Related code: `frontend/src/pages/SettingsPage.vue`
- Related code: `frontend/src/api/ai.ts`
- Related code: `backend/app/models/family.py`
- Related code: `backend/app/schemas/ai_config.py`
- Institutional: `docs/solutions/ui-bugs/vant4-field-modelvalue-binding-2026-04-08.md`
- Institutional: `docs/solutions/integration-issues/deerflow-harness-silent-fallback-and-concurrency-fixes-2026-04-12.md`
