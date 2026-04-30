# UI 重构设计文档：Together AI 视觉语言迁移

**日期：** 2026-05-01  
**范围：** `frontend/apps/main`  
**目标：** 将现有 Cohere 设计系统迁移至 Together AI 视觉语言，手机端优先，支持日间/夜间双主题  
**约束：** 不修改交互逻辑，仅重构视觉层

---

## 1. 背景与目标

`DESIGN.md` 已更新为 Together AI 风格设计系统。本次重构将 `style.css` 及相关组件的视觉 token 从 Cohere 体系迁移至 Together AI 体系，核心变化：

- 主色从近黑 `#17171c` 改为午夜蓝 `#010120`
- 深色模式强调色从 coral `#ff7759` 改为薰衣草紫 `#bdbbff`
- 按钮圆角从 pill（32px）改为折中方案（主 CTA 8px，小按钮 4px）
- 阴影从通用黑色改为带蓝调的 `rgba(1,1,32,0.1)`
- 排版加入负字距，heading 更紧凑

---

## 2. 设计决策记录

| 决策点 | 选择 | 理由 |
|---|---|---|
| 访客页背景 | 保留星空动画，更新为 `#010120` 配色 | 保留现有视觉特色，只迁移颜色 |
| 按钮圆角 | 主 CTA 8px，小按钮 4px | 折中：比 pill 克制，比 4px 亲和，适合家庭 app |
| 深色模式主色 | 薰衣草紫 `#bdbbff` | 区别于浅色模式，冷静优雅，符合 Together AI 气质 |
| FAB 形状 | 保持圆形，更新颜色 | 圆形 FAB 在手机端辨识度高，不必要的改动 |

---

## 3. 设计 Token 迁移规范

### 3.1 浅色模式 `:root`

```css
/* 主色 */
--color-primary: #010120;           /* 旧: #17171c */
--color-on-primary: #ffffff;

/* 表面 */
--color-canvas: #ffffff;            /* 不变 */
--color-soft-stone: #f5f5ff;        /* 旧: #eeece7，改为极淡薰衣草 */

/* 新增 Together AI token */
--color-lavender: #bdbbff;
--color-magenta: #ef2cc1;           /* 插图专用，不用于 UI chrome */
--color-brand-orange: #fc4c02;      /* 插图专用，不用于 UI chrome */

/* 分隔线 */
--color-hairline: rgba(1,1,32,0.08);  /* 旧: #d9d9dd，带蓝调 */
--color-border-light: rgba(1,1,32,0.08);

/* 阴影 */
--shadow-elevated: rgba(1,1,32,0.1) 0px 4px 10px;  /* 新增 */

/* 保留 */
--color-coral: #ff7759;             /* 保留用于警告/错误语义 */
--color-action-blue: #1863dc;       /* 保留用于链接 */
--color-error: #b30000;
```

### 3.2 深色模式 `[data-theme='dark']`

```css
--bg-primary: #010120;
--bg-secondary: #0a0a1a;
--bg-tertiary: #12122a;
--card-bg: #12122a;
--separator: rgba(255,255,255,0.08);
--color-canvas: #0a0a1a;
--color-soft-stone: #12122a;
--color-card-border: rgba(255,255,255,0.08);
--color-hairline: rgba(255,255,255,0.08);

/* 强调色改为薰衣草紫 */
--van-primary-color: #bdbbff;
--van-button-primary-background: #bdbbff;
--van-button-primary-border-color: #bdbbff;
--van-button-primary-color: #010120;   /* 深色文字在浅色按钮上 */
--van-tabs-bottom-bar-color: #bdbbff;
--van-tab-active-text-color: #bdbbff;
--van-checkbox-checked-icon-color: #bdbbff;
--van-switch-on-background: #bdbbff;
```

### 3.3 按钮圆角覆盖

```css
.van-button--primary  { border-radius: 8px !important; }   /* 主 CTA */
.van-button--normal   { border-radius: 4px !important; }   /* 普通 */
.van-button--small    { border-radius: 4px !important; }   /* 小按钮 */
```

### 3.4 排版

```css
--font-display: 'Space Grotesk', 'Inter', ui-sans-serif, system-ui, sans-serif;
--font-body: 'Inter', 'Arial', ui-sans-serif, system-ui, sans-serif;

/* heading 统一负字距 */
h1, h2, h3, .display-text { letter-spacing: -0.02em; }
```

---

## 4. 页面级变更规范

### 4.1 访客页面（LoginPage / RegisterPage / JoinFamilyPage）

**背景**
```css
background: linear-gradient(160deg, #010120 0%, #000010 100%);
```

**星空粒子色**（`useStarField` composable）
- 粒子颜色：`rgba(189,187,255,0.6)`（薰衣草色，替代纯白）
- 背景色参数：`#010120`

**标题排版**
```css
.app-title {
  font-size: 36px;
  font-weight: 500;          /* 旧: 700 */
  letter-spacing: -0.02em;   /* 旧: 2px 正字距 */
  color: #ffffff;
}
```

**表单卡片**（van-cell-group inset）
```css
background: rgba(255,255,255,0.06);
border: 1px solid rgba(255,255,255,0.12);
border-radius: 8px;
```

**PIN 数字键盘**
```css
.numpad-btn {
  border-radius: 4px;        /* 旧: 12px */
  background: rgba(255,255,255,0.12);
}
```

**主按钮**：通过全局 token 自动继承 `#010120` 背景 + `8px` 圆角。

### 4.2 主应用 Shell

**MainLayout.vue**：无需改动，`--bg-secondary` 通过 token 自动更新。

**AppTabBar.vue**：颜色通过 Vant token 自动继承，无需改动。

**FAB（DashboardPage）**
```css
.fab {
  background: var(--color-primary);  /* 浅色: #010120 */
  box-shadow: var(--shadow-elevated);
}
[data-theme='dark'] .fab {
  background: var(--color-lavender); /* 深色: #bdbbff */
  color: #010120;                    /* 深色文字 */
  box-shadow: 0 4px 20px rgba(189,187,255,0.3);
}
```

### 4.3 核心组件

**NetWorthCard.vue**
- 浅色模式：背景改为 `#010120`（深色卡片，形成双世界对比），文字白色
- 深色模式：背景 `#12122a`，强调数字用 `#bdbbff`
- 数字排版：`letter-spacing: -0.03em`，`font-weight: 500`
- 阴影：`var(--shadow-elevated)`

**AssetCard.vue**
- 边框：`1px solid rgba(0,0,0,0.08)`（浅色）/ `1px solid rgba(255,255,255,0.08)`（深色）
- 圆角：`8px`（通过 `--radius-sm` token）
- 阴影：`var(--shadow-elevated)`

**StatusSummaryGrid.vue**
- 激活态：背景 `#010120`，文字白色（浅色模式）
- 深色模式激活态：背景 `rgba(189,187,255,0.15)`，文字 `#bdbbff`

**EmptyState.vue**
- 图标/插图色：`var(--color-lavender)`（`#bdbbff`）

### 4.4 AI 页面

**AIHubPage / AIChatPage**
- 页面背景：`#010120`（对应 Together AI "研究区"深色风格）
- 聊天气泡：
  - 用户侧：`#010120` 背景，白色文字
  - AI 侧：`rgba(189,187,255,0.12)` 背景，`var(--text-primary)` 文字
- 深色模式：背景 `#0a0a1a`，气泡边框 `rgba(255,255,255,0.08)`

---

## 5. 变更文件清单

| 文件 | 变更类型 | 优先级 |
|---|---|---|
| `src/style.css` | Token 全量迁移 | P0（核心，影响全局） |
| `src/pages/LoginPage.vue` | 背景色、粒子色、排版、PIN 键盘 | P1 |
| `src/pages/RegisterPage.vue` | 背景色、排版 | P1 |
| `src/pages/JoinFamilyPage.vue` | 背景色、排版 | P1 |
| `src/components/dashboard/NetWorthCard.vue` | 卡片背景、排版、阴影 | P1 |
| `src/components/asset/AssetCard.vue` | 边框、阴影、圆角 | P1 |
| `src/pages/DashboardPage.vue` | FAB 颜色（深色模式） | P2 |
| `src/components/dashboard/StatusSummaryGrid.vue` | 激活态颜色 | P2 |
| `src/components/common/EmptyState.vue` | 图标色 | P2 |
| `src/pages/AIHubPage.vue` | 页面背景 | P2 |
| `src/pages/AIChatPage.vue` | 气泡颜色 | P2 |
| `src/composables/useStarField.ts` | 粒子颜色参数化 | P1 |

`frontend/packages/auth`：无 UI 文件，**不需要改动**。

---

## 6. 验收标准

- [ ] 浅色模式：主色为 `#010120`，按钮圆角 8px/4px，阴影带蓝调
- [ ] 深色模式：背景 `#010120`，强调色 `#bdbbff`，按钮文字 `#010120`
- [ ] 登录页：星空动画保留，粒子色为薰衣草紫，背景为午夜蓝
- [ ] FAB：浅色 `#010120`，深色 `#bdbbff`
- [ ] NetWorthCard：浅色模式下为深色卡片
- [ ] 所有页面在 375px 宽度下无布局溢出
- [ ] `npm run typecheck` 通过
- [ ] `npm run lint` 通过
