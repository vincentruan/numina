# Together AI UI 重构实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 frontend/apps/main 的视觉层从 Cohere 设计系统迁移至 Together AI 设计系统，手机端优先，支持日间/夜间双主题，不改任何交互逻辑。

**Architecture:** 以 `style.css` 全局 token 迁移为基础（P0），访客页面和核心组件为第二层（P1），仪表盘细节和 AI 页面为第三层（P2）。每个 task 独立可验证，通过 `npm run typecheck && npm run lint` 作为质量门。

**Tech Stack:** Vue 3 + TypeScript + Vant 4 + CSS 自定义属性（`[data-theme='dark']` 机制）

---

## 文件变更清单

| 文件 | 操作 | Task |
|---|---|---|
| `src/style.css` | 修改：token 全量迁移 | Task 1 |
| `src/composables/starField.config.ts` | 修改：更新 STAR_COLORS 和 GRADIENT_COLORS | Task 2 |
| `src/pages/LoginPage.vue` | 修改：背景色、标题排版、PIN 键盘圆角 | Task 3 |
| `src/pages/RegisterPage.vue` | 修改：背景色、标题排版 | Task 4 |
| `src/pages/JoinFamilyPage.vue` | 修改：背景色、标题排版 | Task 4 |
| `src/components/dashboard/NetWorthCard.vue` | 修改：深色模式背景、数字排版 | Task 5 |
| `src/components/asset/AssetCard.vue` | 修改：选中态颜色 | Task 6 |
| `src/components/dashboard/StatusSummaryGrid.vue` | 修改：激活态颜色 | Task 7 |
| `src/pages/DashboardPage.vue` | 修改：FAB 深色模式颜色 | Task 8 |
| `src/pages/AIHubPage.vue` | 修改：header 背景 | Task 9 |
| `src/pages/AIChatPage.vue` | 修改：气泡颜色 | Task 9 |

---

## Task 1：style.css — 全局 Token 迁移（P0）

**Files:**
- Modify: `frontend/apps/main/src/style.css`

这是整个重构的基础。改完后全局颜色、按钮圆角、阴影自动生效。

- [ ] **Step 1：更新 `:root` 中的品牌色和表面色**

将 `src/style.css` 中 `:root` 块的以下变量替换：

```css
/* 旧值 → 新值 */
--color-primary: #010120;           /* 旧: #17171c */
--color-soft-stone: #f5f5ff;        /* 旧: #eeece7 */
--color-hairline: rgba(1,1,32,0.08);  /* 旧: #d9d9dd */
--color-border-light: rgba(1,1,32,0.08); /* 旧: #e5e7eb */
```

在 `:root` 块末尾（`--color-action-primary-active` 之前）新增：

```css
/* ── Together AI 新增 token ── */
--color-lavender: #bdbbff;
--color-magenta: #ef2cc1;
--color-brand-orange: #fc4c02;
--shadow-elevated: rgba(1,1,32,0.1) 0px 4px 10px;
```

- [ ] **Step 2：更新深色模式 `[data-theme='dark']` 块**

将整个 `[data-theme='dark']` 块替换为：

```css
[data-theme='dark'] {
  --bg-primary: #010120;
  --bg-secondary: #0a0a1a;
  --bg-tertiary: #12122a;
  --text-primary: #f5f5f5;
  --text-secondary: #c8c8d0;
  --text-tertiary: var(--color-muted);
  --separator: rgba(255,255,255,0.08);
  --card-bg: #12122a;
  --color-canvas: #0a0a1a;
  --color-soft-stone: #12122a;
  --color-card-border: rgba(255,255,255,0.08);
  --color-hairline: rgba(255,255,255,0.08);

  --van-primary-color: #bdbbff;
  --van-button-primary-background: #bdbbff;
  --van-button-primary-border-color: #bdbbff;
  --van-button-primary-color: #010120;
  --van-tabs-bottom-bar-color: #bdbbff;
  --van-tab-active-text-color: #bdbbff;
  --van-checkbox-checked-icon-color: #bdbbff;
  --van-switch-on-background: #bdbbff;
}
```

- [ ] **Step 3：更新按钮圆角全局覆盖**

找到 `.van-button--primary`、`.van-button--normal`、`.van-button--small` 三条规则，将圆角改为：

```css
.van-button--primary {
  border-radius: 8px !important;
  font-weight: 500;
  letter-spacing: 0;
  min-height: 44px;
}

.van-button--normal {
  border-radius: 4px !important;
  min-height: 44px;
}

.van-button--small {
  border-radius: 4px !important;
  min-height: 36px;
  padding: 0 16px;
  font-size: 14px;
}
```

- [ ] **Step 4：在 `body` 规则后新增 heading 负字距**

在 `body { ... }` 规则之后插入：

```css
h1, h2, h3, h4, .display-text {
  letter-spacing: -0.02em;
}
```

- [ ] **Step 5：验证**

```bash
cd frontend/apps/main && npm run typecheck && npm run lint
```

预期：无错误，无警告（或仅有预存警告）。

- [ ] **Step 6：提交**

```bash
git add frontend/apps/main/src/style.css
git commit -m "feat(main): migrate global CSS tokens to Together AI design system

- Primary color: #17171c → #010120 (midnight blue)
- Dark mode accent: coral → lavender #bdbbff
- Button radius: pill → 8px CTA / 4px small
- Add shadow-elevated, lavender, magenta tokens
- Dark surfaces: #0d0d10 → #010120 / #0a0a1a / #12122a

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 2：starField.config.ts — 星空粒子色迁移（P1）

**Files:**
- Modify: `frontend/apps/main/src/composables/starField.config.ts`

将星空粒子颜色从白色系改为薰衣草紫色系，与 `#010120` 背景搭配。

- [ ] **Step 1：更新 STAR_COLORS**

找到 `export const STAR_COLORS = { ... }` 块，替换为：

```ts
export const STAR_COLORS = {
  // Primary star color — soft lavender-white
  primary: 'rgba(220, 218, 255, 1)',
  // Secondary — slightly cooler lavender
  secondary: 'rgba(189, 187, 255, 1)',
  // Bright stars — near-white with lavender tint
  bright: 'rgba(240, 239, 255, 1)',
  // Accent — deeper lavender for mid-layer variety
  accent: 'rgba(150, 140, 255, 1)',
}
```

- [ ] **Step 2：更新 GRADIENT_COLORS**

找到 `export const GRADIENT_COLORS = { ... }` 块，替换为：

```ts
export const GRADIENT_COLORS = {
  start: '#010120',
  end: '#000010',
  angle: 160,
}
```

- [ ] **Step 3：验证**

```bash
cd frontend/apps/main && npm run typecheck
```

预期：0 errors。

- [ ] **Step 4：提交**

```bash
git add frontend/apps/main/src/composables/starField.config.ts
git commit -m "feat(main): update star field colors to lavender palette for Together AI theme

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 3：LoginPage.vue — 访客页视觉迁移（P1）

**Files:**
- Modify: `frontend/apps/main/src/pages/LoginPage.vue`

更新背景渐变、标题排版、PIN 键盘圆角。不改任何 script 逻辑。

- [ ] **Step 1：更新背景渐变**

在 `<style scoped>` 中找到 `.login-page`，将 `background` 改为：

```css
.login-page {
  min-height: 100vh;
  background: linear-gradient(160deg, #010120 0%, #000010 100%);
  display: flex;
  flex-direction: column;
  align-items: center;
  padding-top: 15vh;
  position: relative;
  overflow: hidden;
}
```

- [ ] **Step 2：更新标题排版**

找到 `.app-title`，改为：

```css
.app-title {
  font-size: 36px;
  font-weight: 500;
  color: #fff;
  margin: 0;
  letter-spacing: -0.02em;
}
```

- [ ] **Step 3：更新 PIN 键盘按钮圆角**

找到 `.numpad-btn`，将 `border-radius: 12px` 改为 `border-radius: 4px`，并更新背景：

```css
.numpad-btn {
  height: 60px;
  border: none;
  border-radius: 4px;
  background: rgba(255, 255, 255, 0.12);
  color: #fff;
  font-size: 22px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s, transform 0.1s;
}
```

- [ ] **Step 4：验证**

```bash
cd frontend/apps/main && npm run typecheck && npm run lint
```

预期：0 errors。

- [ ] **Step 5：提交**

```bash
git add frontend/apps/main/src/pages/LoginPage.vue
git commit -m "feat(main): update LoginPage to Together AI visual style

- Background: #17171c → #010120 midnight blue gradient
- Title: weight 700 → 500, letter-spacing -0.02em
- PIN numpad: border-radius 12px → 4px

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 4：RegisterPage.vue + JoinFamilyPage.vue — 访客页视觉迁移（P1）

**Files:**
- Modify: `frontend/apps/main/src/pages/RegisterPage.vue`
- Modify: `frontend/apps/main/src/pages/JoinFamilyPage.vue`

两个页面样式改动相同：背景渐变 + 标题排版。

- [ ] **Step 1：更新 RegisterPage.vue 背景和标题**

在 `<style scoped>` 中：

```css
/* 替换 .register-page */
.register-page {
  min-height: 100vh;
  background: linear-gradient(160deg, #010120 0%, #000010 100%);
  display: flex;
  flex-direction: column;
  align-items: center;
  padding-top: 10vh;
}

/* 替换 .app-title */
.app-title {
  font-size: 28px;
  font-weight: 500;
  color: #fff;
  margin: 0;
  letter-spacing: -0.02em;
}
```

- [ ] **Step 2：更新 JoinFamilyPage.vue 背景和标题**

读取 `src/pages/JoinFamilyPage.vue` 的 `<style scoped>` 部分，找到 `.join-page` 和 `.app-title`，应用相同改动：

```css
/* .join-page 的 background 改为 */
background: linear-gradient(160deg, #010120 0%, #000010 100%);

/* .app-title 改为 */
.app-title {
  font-size: 28px;
  font-weight: 500;
  color: #fff;
  margin: 0;
  letter-spacing: -0.02em;
}
```

- [ ] **Step 3：验证**

```bash
cd frontend/apps/main && npm run typecheck && npm run lint
```

预期：0 errors。

- [ ] **Step 4：提交**

```bash
git add frontend/apps/main/src/pages/RegisterPage.vue frontend/apps/main/src/pages/JoinFamilyPage.vue
git commit -m "feat(main): update Register and JoinFamily pages to Together AI visual style

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 5：NetWorthCard.vue — 深色模式背景迁移（P1）

**Files:**
- Modify: `frontend/apps/main/src/components/dashboard/NetWorthCard.vue`

深色模式背景从 `#0d0d10` 改为 `#010120`，数字排版加负字距，日均成本 badge 圆角从 pill 改为 4px。

- [ ] **Step 1：更新深色模式背景**

找到：
```css
[data-theme='dark'] .overview-card {
  background: #0d0d10;
}
```
改为：
```css
[data-theme='dark'] .overview-card {
  background: #010120;
}
```

- [ ] **Step 2：更新主金额排版**

找到 `.ov-amount :deep(.money-display)`，加入负字距：

```css
.ov-amount :deep(.money-display) {
  color: #fff;
  font-size: 36px;
  font-weight: 500;
  letter-spacing: -0.03em;
}
```

- [ ] **Step 3：更新日均成本 badge 圆角**

找到 `.ov-daily`，将 `border-radius: var(--radius-pill)` 改为 `border-radius: 4px`：

```css
.ov-daily {
  background: rgba(255, 119, 89, 0.25);
  color: var(--color-coral-soft);
  padding: 3px 10px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 500;
}
```

- [ ] **Step 4：验证**

```bash
cd frontend/apps/main && npm run typecheck && npm run lint
```

预期：0 errors。

- [ ] **Step 5：提交**

```bash
git add frontend/apps/main/src/components/dashboard/NetWorthCard.vue
git commit -m "feat(main): update NetWorthCard to Together AI style

- Dark mode bg: #0d0d10 → #010120
- Amount letter-spacing: -0.03em, weight 500
- Daily cost badge: pill → 4px radius

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 6：AssetCard.vue — 选中态颜色迁移（P1）

**Files:**
- Modify: `frontend/apps/main/src/components/asset/AssetCard.vue`

深色模式选中态从 coral 改为 lavender，与新深色主色一致。

- [ ] **Step 1：更新深色模式选中态**

找到：
```css
[data-theme='dark'] .asset-card.selection-mode.selected {
  border-color: var(--color-coral);
  background: rgba(255, 119, 89, 0.08);
}
```
改为：
```css
[data-theme='dark'] .asset-card.selection-mode.selected {
  border-color: var(--color-lavender);
  background: rgba(189, 187, 255, 0.08);
}
```

- [ ] **Step 2：更新 card-days badge 圆角**

找到 `.card-days`，将 `border-radius: var(--radius-pill)` 改为 `border-radius: 4px`：

```css
.card-days {
  font-size: 11px;
  color: var(--color-body-muted);
  background: var(--bg-secondary);
  padding: 2px 8px;
  border-radius: 4px;
  line-height: 1.4;
}
```

- [ ] **Step 3：验证**

```bash
cd frontend/apps/main && npm run typecheck && npm run lint
```

预期：0 errors。

- [ ] **Step 4：提交**

```bash
git add frontend/apps/main/src/components/asset/AssetCard.vue
git commit -m "feat(main): update AssetCard dark mode selection color to lavender

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 7：StatusSummaryGrid.vue — 激活态颜色迁移（P2）

**Files:**
- Modify: `frontend/apps/main/src/components/dashboard/StatusSummaryGrid.vue`

深色模式激活态从 coral 改为 lavender，tab 圆角从 pill 改为 8px。

- [ ] **Step 1：更新深色模式激活态**

找到：
```css
[data-theme='dark'] .status-tab.active {
  background: var(--color-coral);
  border-color: var(--color-coral);
}
```
改为：
```css
[data-theme='dark'] .status-tab.active {
  background: rgba(189, 187, 255, 0.15);
  border-color: var(--color-lavender);
  color: var(--color-lavender);
}
```

- [ ] **Step 2：更新 tab 圆角**

找到 `.status-tab`，将 `border-radius: var(--radius-pill)` 改为 `border-radius: 8px`：

```css
.status-tab {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 8px 14px;
  border-radius: 8px;
  background: var(--bg-secondary);
  border: 1px solid transparent;
  cursor: pointer;
  transition: background 0.18s, color 0.18s, border-color 0.18s;
  white-space: nowrap;
  flex-shrink: 0;
  min-height: 36px;
}
```

- [ ] **Step 3：验证**

```bash
cd frontend/apps/main && npm run typecheck && npm run lint
```

预期：0 errors。

- [ ] **Step 4：提交**

```bash
git add frontend/apps/main/src/components/dashboard/StatusSummaryGrid.vue
git commit -m "feat(main): update StatusSummaryGrid dark mode active color to lavender

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 8：DashboardPage.vue — FAB 深色模式颜色（P2）

**Files:**
- Modify: `frontend/apps/main/src/pages/DashboardPage.vue`

深色模式 FAB 从 coral 改为 lavender，图标文字色改为深色以保证对比度。

- [ ] **Step 1：更新 FAB 深色模式样式**

找到：
```css
[data-theme='dark'] .fab {
  background: var(--color-coral);
  box-shadow: 0 4px 20px rgba(255, 119, 89, 0.4);
}
```
改为：
```css
[data-theme='dark'] .fab {
  background: var(--color-lavender);
  color: #010120;
  box-shadow: 0 4px 20px rgba(189, 187, 255, 0.3);
}
```

同时更新浅色模式 FAB 阴影使用新 token：

找到：
```css
.fab {
  ...
  box-shadow: 0 4px 20px rgba(23, 23, 28, 0.35);
  ...
}
```
将 `box-shadow` 改为：
```css
box-shadow: var(--shadow-elevated);
```

- [ ] **Step 2：验证**

```bash
cd frontend/apps/main && npm run typecheck && npm run lint
```

预期：0 errors。

- [ ] **Step 3：提交**

```bash
git add frontend/apps/main/src/pages/DashboardPage.vue
git commit -m "feat(main): update Dashboard FAB dark mode color to lavender

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 9：AI 页面视觉迁移（P2）

**Files:**
- Modify: `frontend/apps/main/src/pages/AIHubPage.vue`
- Modify: `frontend/apps/main/src/pages/AIChatPage.vue`

AI 页面对应 Together AI "研究区"深色风格。

- [ ] **Step 1：读取 AIHubPage.vue 的 style 块**

读取 `src/pages/AIHubPage.vue` 找到 `.hub-header` 和 `.hub-header-bg` 的背景色定义。

- [ ] **Step 2：更新 AIHubPage.vue header 背景**

找到 `.hub-header-bg` 或 `.hub-header` 中的背景渐变（通常是 `#17171c` 或 `#1a1a2e` 系列），改为：

```css
/* .hub-header 背景 */
background: #010120;

/* .hub-header-bg（如有渐变装饰层）*/
background: linear-gradient(180deg, rgba(189,187,255,0.08) 0%, transparent 100%);
```

- [ ] **Step 3：读取 AIChatPage.vue 的 style 块**

读取 `src/pages/AIChatPage.vue` 找到聊天气泡相关 CSS（`.message-bubble`、`.user-bubble`、`.ai-bubble` 或类似命名）。

- [ ] **Step 4：更新 AIChatPage.vue 气泡颜色**

找到用户气泡和 AI 气泡的背景色，更新为：

```css
/* 用户气泡 */
.user-bubble, .message--user .bubble {
  background: #010120;
  color: #ffffff;
}

/* AI 气泡 */
.ai-bubble, .message--ai .bubble, .message--assistant .bubble {
  background: rgba(189, 187, 255, 0.12);
  border: 1px solid rgba(189, 187, 255, 0.2);
  color: var(--text-primary);
}

/* 深色模式 AI 气泡 */
[data-theme='dark'] .ai-bubble,
[data-theme='dark'] .message--ai .bubble,
[data-theme='dark'] .message--assistant .bubble {
  background: rgba(189, 187, 255, 0.08);
  border-color: rgba(255, 255, 255, 0.08);
}
```

> **注意：** Step 3 读取文件后，根据实际 class 名称调整 Step 4 的选择器。如果气泡 class 名称不同，以实际代码为准。

- [ ] **Step 5：验证**

```bash
cd frontend/apps/main && npm run typecheck && npm run lint
```

预期：0 errors。

- [ ] **Step 6：提交**

```bash
git add frontend/apps/main/src/pages/AIHubPage.vue frontend/apps/main/src/pages/AIChatPage.vue
git commit -m "feat(main): update AI pages to Together AI research-zone dark style

- AIHubPage header: midnight blue #010120 with lavender gradient overlay
- AIChatPage bubbles: user=#010120, AI=lavender tint

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 10：最终验收

- [ ] **Step 1：全量类型检查**

```bash
cd frontend/apps/main && npm run typecheck
```

预期：0 errors。

- [ ] **Step 2：全量 lint**

```bash
cd frontend/apps/main && npm run lint
```

预期：0 errors（或仅有预存警告）。

- [ ] **Step 3：对照验收标准逐项确认**

- [ ] 浅色模式：主色为 `#010120`，按钮圆角 8px（主 CTA）/ 4px（小按钮）
- [ ] 深色模式：背景 `#010120`，强调色 `#bdbbff`，主按钮文字 `#010120`
- [ ] 登录页：星空动画保留，粒子色为薰衣草紫，背景为午夜蓝
- [ ] FAB：浅色 `#010120`，深色 `#bdbbff` + 深色图标
- [ ] NetWorthCard：深色模式背景 `#010120`，金额负字距
- [ ] StatusSummaryGrid：深色激活态为薰衣草紫，tab 圆角 8px
- [ ] AssetCard：深色选中态为薰衣草紫
- [ ] AI 页面：header 和气泡使用新配色

- [ ] **Step 4：最终提交（如有未提交改动）**

```bash
cd frontend/apps/main && git status
# 确认无遗漏文件后提交
```
