# Terminal Dark 开发者页面实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 site/project/index.html 从 Apple 风格转换为 Terminal Dark 美学（JetBrains Mono + 霓虹绿 + CSS网格背景）

**Architecture:** 纯静态CSS/HTML改造，无功能性代码，技术优先布局重组，响应式网格密度策略

**Tech Stack:** HTML5, CSS3 (无框架), JetBrains Mono字体, CSS Grid背景模式

---

## 文件结构

**创建文件：**
- 无新文件创建（纯改造）

**修改文件：**
- `site/style.css` — 全局样式系统（颜色变量、字体栈、网格背景类）
- `site/project/index.html` — 页面结构调整 + 组件样式改造

**验证方式：**
- 浏览器视觉检查（file:// 或本地服务器）
- 移动端响应式测试（Chrome DevTools 375px）
- Reduced motion测试（系统偏好设置）

---

## Phase 1: 基础样式系统改造

### Task 1: 颜色系统与字体栈定义

**Files:**
- Modify: `site/style.css:35-45` (替换现有颜色变量)
- Modify: `site/style.css:48-63` (替换body字体声明)

- [ ] **Step 1: 更新颜色变量系统**

在 `site/style.css` 第35-45行，替换 `:root` 颜色变量：

```css
:root {
  --bp-mobile: 375px;
  --bp-tablet: 768px;
  --bp-desktop: 1024px;
  --bp-wide: 1440px;

  /* Terminal Dark 颜色系统 */
  --bg-primary: #0d0d0d;
  --bg-secondary: #1a1a1a;
  --bg-tertiary: #2a2a2a;
  --neon-green: #00ff41;
  --neon-green-dim: #00cc33;
  --neon-green-glow: rgba(0, 255, 65, 0.15);
  --text-primary: #f0f0f0;
  --text-secondary: #888888;
  --text-tertiary: #666666;
  --border-subtle: #333333;
  --border-bright: #444444;

  /* 保留原有变量名以便渐进迁移 */
  --color-primary: #00ff41;
  --color-bg: #1a1a1a;
  --color-text: #f0f0f0;
  --color-text-secondary: #888888;
}
```

- [ ] **Step 2: 添加字体栈变量**

在同一个 `:root` 块追加字体栈：

```css
  /* Terminal Dark 字体系统 */
  --font-mono: 'JetBrains Mono', 'SF Mono', 'Menlo', 'Monaco', 'Courier New', monospace;
  --font-body: -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Hiragino Sans GB', sans-serif;
```

- [ ] **Step 3: 更新body基础样式**

在 `site/style.css` 第52-63行，修改body样式：

```css
body {
  margin: 0;
  padding: 0;
  font-family: var(--font-body);
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  background: var(--bg-primary);
  color: var(--text-primary);
  font-size: 16px;
  line-height: 1.5;
}
```

- [ ] **Step 4: 添加JetBrains Mono字体链接**

在 `site/project/index.html` 第9行后，添加字体CDN链接：

```html
<link rel="stylesheet" href="/site/style.css">
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet">
<link rel="icon" type="image/svg+xml" href="/site/assets/favicon.svg">
```

- [ ] **Step 5: 视觉验证 — 颜色基础**

在浏览器打开 `site/project/index.html`，检查：
- 页面背景应为深色（#0d0d0d）
- 文字应为灰白色（#f0f0f0）
- 现有元素可能看起来奇怪（白色卡片在深色背景）— 这是预期中间状态

- [ ] **Step 6: Commit**

```bash
git add site/style.css site/project/index.html
git commit -m "feat(site): Terminal Dark 颜色系统 + JetBrains Mono 字体栈"
```

---

### Task 2: CSS网格背景类定义

**Files:**
- Modify: `site/style.css` (追加网格背景类)

- [ ] **Step 1: 添加密集网格背景类**

在 `site/style.css` 文件末尾追加：

```css
/* Terminal Dark 网格背景模式 */

/* 密集网格（hero、deploy区块） */
.terminal-grid-dense {
  background-image:
    linear-gradient(rgba(0, 255, 65, 0.03) 1px, transparent 1px),
    linear-gradient(90deg, rgba(0, 255, 65, 0.03) 1px, transparent 1px);
  background-size: 20px 20px;
}

/* 稀疏网格（stack、features区块） */
.terminal-grid-sparse {
  background-image:
    linear-gradient(rgba(51, 51, 51, 0.5) 1px, transparent 1px),
    linear-gradient(90deg, rgba(51, 51, 51, 0.5) 1px, transparent 1px);
  background-size: 80px 80px;
}

/* 无网格（config、comparison表格） */
.terminal-grid-none {
  background: var(--bg-secondary);
}
```

- [ ] **Step 2: 添加网格发光增强类**

继续追加发光效果类：

```css
/* 终端发光效果 */
.terminal-glow {
  box-shadow: 0 0 15px rgba(0, 255, 65, 0.15);
}

.terminal-glow-strong {
  box-shadow: 0 0 20px rgba(0, 255, 65, 0.25);
}

/* 文字发光 */
.text-glow {
  text-shadow: 0 0 8px rgba(0, 255, 65, 0.4);
}
```

- [ ] **Step 3: Commit**

```bash
git add site/style.css
git commit -m "feat(site): CSS网格背景类 + 终端发光效果"
```

---

## Phase 2: 导航栏与页面结构重组

### Task 3: 粘性导航栏改造

**Files:**
- Modify: `site/project/index.html:260-274` (导航栏HTML结构)
- Modify: `site/project/index.html:10-258` (导航栏内联样式)

- [ ] **Step 1: 重构导航栏HTML结构**

在 `site/project/index.html` 第262-274行，替换导航栏：

```html
<!-- Terminal Dark 粘性导航栏 -->
<header class="dev-nav terminal-grid-dense">
  <div class="dev-nav-inner">
    <a href="#" class="dev-nav-logo">Numina</a>
    <span class="nav-separator">/</span>
    <span class="nav-label">开发者文档</span>
    <nav class="dev-nav-links">
      <a href="#stack">技术架构</a>
      <a href="#deploy">快速部署</a>
      <a href="#config">配置参考</a>
      <a href="#features">功能特性</a>
    </nav>
    <a href="../overview/" class="nav-cross-link">产品介绍 →</a>
  </div>
</header>
```

- [ ] **Step 2: 更新导航栏内联样式**

在 `<style>` 块（第10-258行内），替换导航栏样式：

```css
/* Terminal Dark Sticky Nav */
.dev-nav {
  position: sticky;
  top: 0;
  z-index: 100;
  background: var(--bg-primary);
  border-bottom: 1px solid var(--neon-green);
  padding: 0 16px;
}

.dev-nav-inner {
  max-width: 1440px;
  margin: 0 auto;
  display: flex;
  align-items: center;
  gap: 16px;
  height: var(--nav-height);
  flex-wrap: wrap;
}

.dev-nav-logo {
  font-family: var(--font-mono);
  font-size: 18px;
  font-weight: 700;
  color: var(--neon-green);
  text-decoration: none;
  margin-right: 8px;
}

.nav-separator {
  color: var(--text-tertiary);
  font-size: 14px;
}

.nav-label {
  color: var(--text-secondary);
  font-size: 14px;
  font-family: var(--font-mono);
}

.dev-nav-links {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
  flex: 1;
}

.dev-nav-links a {
  font-family: var(--font-mono);
  color: var(--neon-green);
  text-decoration: none;
  font-size: 14px;
  white-space: nowrap;
  transition: text-shadow 150ms ease;
}

.dev-nav-links a:hover {
  text-shadow: 0 0 8px rgba(0, 255, 65, 0.4);
}

.nav-cross-link {
  font-family: var(--font-mono);
  color: var(--neon-green);
  text-decoration: none;
  font-size: 14px;
  white-space: nowrap;
}

.nav-cross-link:hover {
  text-shadow: 0 0 8px rgba(0, 255, 65, 0.4);
}
```

- [ ] **Step 3: 视觉验证 — 导航栏**

刷新浏览器，检查导航栏：
- 背景应为深色 + 密集网格可见
- 底部应有霓虹绿细线边框
- Logo应为霓虹绿色，JetBrains Mono字体
- 链接hover应有发光效果

- [ ] **Step 4: Commit**

```bash
git add site/project/index.html
git commit -m "feat(site): Terminal Dark 导航栏 + 技术优先锚点顺序"
```

---

### Task 4: 页面区块顺序重组

**Files:**
- Modify: `site/project/index.html` (移动区块位置)

- [ ] **Step 1: 移动技术架构区块到第一位**

将第363-397行的 Tech Stack 区块移动到导航栏之后（第275行之后）：

```html
<!-- Section 1: Tech Stack (技术优先) -->
<section id="stack" class="dev-section terminal-grid-sparse">
  <h2>技术架构</h2>
  <div class="stack-grid">
    <div class="stack-card">
      <h3 class="stack-title">后端</h3>
      <ul class="stack-list">
        <li>FastAPI (Python)</li>
        <li>SQLAlchemy ORM</li>
        <li>SQLite / MySQL / PostgreSQL</li>
        <li>JWT 认证（bcrypt + access/refresh tokens）</li>
        <li>Alembic 数据库迁移</li>
      </ul>
    </div>
    <div class="stack-card">
      <h3 class="stack-title">前端</h3>
      <ul class="stack-list">
        <li>Vue 3 + TypeScript</li>
        <li>Vite 构建工具</li>
        <li>Vant 4（移动端 UI）</li>
        <li>ECharts（图表）</li>
        <li>Pinia 状态管理</li>
      </ul>
    </div>
    <div class="stack-card">
      <h3 class="stack-title">基础设施</h3>
      <ul class="stack-list">
        <li>Docker Compose</li>
        <li>Nginx 反向代理</li>
        <li>GitHub Actions CI/CD</li>
        <li>Playwright E2E 测试</li>
      </ul>
    </div>
  </div>
</section>
```

删除原位置的第363-397行区块。

- [ ] **Step 2: 移动快速部署区块到第二位**

将第454-491行的 Deploy 区块移动到 Tech Stack 之后，修改类名为：

```html
<!-- Section 2: Quick Deploy (终端核心) -->
<section id="deploy" class="terminal-grid-dense">
```

- [ ] **Step 3: 移动配置参考区块到第三位**

将第493-530行的 Config 区块移动到 Deploy 之后，添加类名：

```html
<!-- Section 3: Config Reference -->
<section id="config" class="dev-section terminal-grid-none">
```

- [ ] **Step 4: 移动功能特性区块到第四位**

将第276-361行的 Features 区块移动到 Config 之后，修改类名：

```html
<!-- Section 4: Feature Overview -->
<section id="features" class="dev-section terminal-grid-sparse">
```

- [ ] **Step 5: 移动功能对比区块到第五位**

将第399-452行的 Comparison 区块保持位置，添加类名：

```html
<!-- Section 5: Comparison Grid -->
<section class="dev-section terminal-grid-none">
```

- [ ] **Step 6: 移动数据库选项区块到第六位**

将第533-549行的 Database Options 区块移动到 Comparison 之后。

- [ ] **Step 7: 视觉验证 — 页面结构**

刷新浏览器，滚动检查：
- 第一区块应为"技术架构"（稀疏网格背景）
- 第二区块应为"快速部署"（密集网格背景）
- 导航链接锚点跳转应正确工作

- [ ] **Step 8: Commit**

```bash
git add site/project/index.html
git commit -m "feat(site): 技术优先布局重组 — stack/deploy/config/features顺序"
```

---

## Phase 3: 核心组件样式改造

### Task 5: 快速部署区块 — 终端命令块

**Files:**
- Modify: `site/project/index.html` (deploy区块HTML + 样式)

- [ ] **Step 1: 替换部署区块HTML结构**

在 `<section id="deploy">` 内，替换终端块：

```html
<div class="deploy-content">
  <div class="deploy-terminal terminal-glow">
    <div class="terminal-header">
      <span class="terminal-dot"></span>
      <span class="terminal-title">terminal</span>
    </div>
    <div class="terminal-body">
      <code class="terminal-command">$ docker-compose up -d<span class="cursor"></span></code>
      <div class="terminal-output">
        <span class="output-line">✓ Backend started on port 8000</span>
        <span class="output-line">✓ Frontend built successfully</span>
        <span class="output-line">✓ Nginx proxy configured</span>
        <span class="output-success">→ Ready at http://localhost:8080</span>
      </div>
    </div>
  </div>
  <p class="deploy-tagline">一键启动</p>
  <a href="https://github.com/vincentruan/numina#快速开始" class="deploy-link" target="_blank" rel="noopener noreferrer">查看完整部署指南 →</a>
</div>
```

- [ ] **Step 2: 更新部署区块内联样式**

在 `<style>` 块内替换 `#deploy` 和相关样式：

```css
/* Terminal Dark Deploy Section */
#deploy {
  padding: 32px 16px;
  background: var(--bg-primary);
  text-align: center;
}

.deploy-content {
  max-width: var(--bp-wide);
  margin: 0 auto;
}

.deploy-terminal {
  display: inline-block;
  background: var(--bg-secondary);
  border: 1px solid var(--neon-green);
  border-radius: 8px;
  padding: 0;
  margin-bottom: 16px;
  min-width: 300px;
}

.terminal-header {
  background: var(--bg-tertiary);
  padding: 8px 16px;
  border-bottom: 1px solid var(--border-subtle);
  display: flex;
  align-items: center;
  gap: 8px;
}

.terminal-dot {
  width: 12px;
  height: 12px;
  background: var(--neon-green);
  border-radius: 50%;
}

.terminal-title {
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--text-secondary);
}

.terminal-body {
  padding: 16px 24px;
}

.terminal-command {
  font-family: var(--font-mono);
  font-size: 16px;
  color: var(--neon-green);
  display: block;
}

.terminal-output {
  margin-top: 12px;
  display: block;
}

.output-line {
  font-family: var(--font-mono);
  font-size: 14px;
  color: var(--text-secondary);
  display: block;
  margin-top: 4px;
}

.output-success {
  font-family: var(--font-mono);
  font-size: 14px;
  color: var(--neon-green);
  display: block;
  margin-top: 4px;
}

.deploy-tagline {
  font-family: var(--font-mono);
  font-size: 20px;
  color: var(--text-primary);
  margin: 0 0 12px;
}

.deploy-link {
  font-family: var(--font-mono);
  color: var(--neon-green);
  font-size: 14px;
  text-decoration: none;
}

.deploy-link:hover {
  text-shadow: 0 0 8px rgba(0, 255, 65, 0.4);
}

/* 光标闪烁动画 */
.cursor {
  display: inline-block;
  width: 8px;
  height: 18px;
  background: var(--neon-green);
  margin-left: 4px;
  animation: blink 1s infinite;
}

@keyframes blink {
  0%, 50% { opacity: 1; }
  51%, 100% { opacity: 0; }
}

@media (prefers-reduced-motion: reduce) {
  .cursor {
    animation: none;
    opacity: 1;
  }
}
```

- [ ] **Step 3: 更新部署步骤列表样式**

替换 `.deploy-steps` 相关样式：

```css
.deploy-steps {
  list-style: none;
  padding: 0;
  margin: 24px 0;
  counter-reset: step;
}

.deploy-steps li {
  counter-increment: step;
  display: flex;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 16px;
  color: var(--text-primary);
}

.deploy-steps li::before {
  content: counter(step, decimal-leading-zero);
  display: flex;
  align-items: center;
  justify-content: center;
  min-width: 40px;
  height: 28px;
  background: transparent;
  border: 1px solid var(--neon-green);
  color: var(--neon-green);
  font-family: var(--font-mono);
  font-size: 14px;
  font-weight: 500;
  border-radius: 4px; /* 方形而非圆形 */
}

.deploy-steps code {
  font-family: var(--font-mono);
  font-size: 13px;
  background: var(--bg-tertiary);
  color: var(--neon-green);
  padding: 2px 6px;
  border-radius: 4px;
}

.deploy-steps strong {
  color: var(--text-primary);
  font-family: var(--font-mono);
}
```

- [ ] **Step 4: 视觉验证 — 终端块**

刷新浏览器，检查部署区块：
- 终端块应有霓虹绿边框 + 发光效果
- 命令文字应为霓虹绿色
- 光标应闪烁（或reduced motion下静止）
- 步骤编号应为方形边框，JetBrains Mono字体

- [ ] **Step 5: Commit**

```bash
git add site/project/index.html
git commit -m "feat(site): Terminal Dark 部署区块 — 终端命令块 + 发光效果"
```

---

### Task 6: 技术架构卡片样式

**Files:**
- Modify: `site/project/index.html` (stack区块样式)

- [ ] **Step 1: 更新技术架构区块基础样式**

在 `<style>` 块内，替换 `.dev-section` 和区块样式：

```css
/* Terminal Dark Content Sections */
.dev-section {
  padding: 48px 16px;
  max-width: 1440px;
  margin: 0 auto;
}

.dev-section h2 {
  font-family: var(--font-mono);
  font-size: 24px;
  font-weight: 600;
  margin: 0 0 24px;
  color: var(--neon-green);
}

.dev-section h3 {
  font-family: var(--font-mono);
  font-size: 18px;
  font-weight: 600;
  margin: 16px 0 8px;
  color: var(--text-primary);
}
```

- [ ] **Step 2: 更新stack卡片样式**

替换 `.stack-grid` 和 `.stack-column` 样式：

```css
.stack-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 24px;
  margin-top: 16px;
}

@media (min-width: 768px) {
  .stack-grid {
    grid-template-columns: repeat(3, 1fr);
  }
}

.stack-card {
  background: var(--bg-secondary);
  border: 1px solid var(--neon-green);
  border-radius: 12px;
  padding: 24px;
  transition: box-shadow 150ms ease, background 150ms ease;
}

.stack-card:hover {
  box-shadow: 0 0 20px rgba(0, 255, 65, 0.25);
  background: var(--bg-tertiary);
}

.stack-title {
  margin-top: 0;
  color: var(--neon-green);
  font-family: var(--font-mono);
  font-size: 16px;
  font-weight: 500;
}

.stack-list {
  margin: 0;
  padding-left: 20px;
}

.stack-list li {
  font-size: 14px;
  color: var(--text-secondary);
  margin-bottom: 6px;
  list-style-type: none;
  position: relative;
  padding-left: 16px;
}

.stack-list li::before {
  content: '';
  position: absolute;
  left: 0;
  top: 6px;
  width: 6px;
  height: 6px;
  background: var(--neon-green);
}
```

- [ ] **Step 3: 视觉验证 — Stack卡片**

刷新浏览器，检查技术架构区块：
- 卡片应有霓虹绿边框
- 标题应为霓虹绿色，JetBrains Mono字体
- Hover应有发光增强效果
- 列表bullet应为霓虹绿色小方块

- [ ] **Step 4: Commit**

```bash
git add site/project/index.html
git commit -m "feat(site): Terminal Dark 技术架构卡片 — 霓虹绿边框 + hover发光"
```

---

### Task 7: 配置参考表格样式

**Files:**
- Modify: `site/project/index.html` (config表格样式)

- [ ] **Step 1: 更新配置表格样式**

替换 `.config-table` 相关样式：

```css
.config-table {
  width: 100%;
  border-collapse: collapse;
  background: var(--bg-secondary);
  border-radius: 8px;
  overflow: hidden;
  margin-top: 16px;
}

.config-table th,
.config-table td {
  padding: 12px 16px;
  text-align: left;
  border-bottom: 1px solid var(--border-subtle);
  font-size: 14px;
}

.config-table th {
  background: var(--bg-tertiary);
  font-family: var(--font-mono);
  font-weight: 600;
  color: var(--neon-green);
}

.config-table td {
  color: var(--text-secondary);
}

.config-table tr:hover {
  background: var(--bg-tertiary);
}

.config-table code {
  font-family: var(--font-mono);
  font-size: 13px;
  background: var(--bg-tertiary);
  color: var(--neon-green);
  padding: 4px 8px;
  border-radius: 4px;
}

.config-warning {
  color: var(--neon-green);
  font-family: var(--font-mono);
  font-weight: 600;
}
```

- [ ] **Step 2: 视觉验证 — Config表格**

刷新浏览器，检查配置区块：
- 表格背景应为深色（无网格）
- 表头应为霓虹绿色
- 代码单元格应为霓虹绿高亮

- [ ] **Step 3: Commit**

```bash
git add site/project/index.html
git commit -m "feat(site): Terminal Dark 配置表格 — 深色背景 + 代码高亮"
```

---

## Phase 4: 次要组件改造

### Task 8: 功能特性卡片样式

**Files:**
- Modify: `site/project/index.html` (features区块样式)

- [ ] **Step 1: 更新特性卡片样式**

替换 `.feature-category` 相关样式：

```css
.feature-category {
  margin-bottom: 24px;
}

.feature-category h3 {
  font-family: var(--font-mono);
  color: var(--text-primary);
  font-size: 18px;
  margin: 0 0 12px;
}

.feature-category ul {
  margin: 8px 0;
  padding-left: 20px;
}

.feature-category li {
  font-size: 14px;
  color: var(--text-secondary);
  margin-bottom: 4px;
}
```

- [ ] **Step 2: 更新Trust Badges样式**

替换 `.trust-badges` 相关样式（保留details行为）：

```css
.trust-badges {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin-top: 32px;
}

.trust-badge {
  background: var(--bg-secondary);
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
  padding: 12px 16px;
  cursor: pointer;
}

.trust-badge summary {
  display: flex;
  align-items: center;
  gap: 8px;
  font-family: var(--font-mono);
  font-size: 16px;
  font-weight: 500;
  color: var(--neon-green);
  list-style: none;
  min-height: 44px;
}

.trust-badge summary::-webkit-details-marker {
  display: none;
}

.badge-icon {
  color: var(--neon-green);
}

.badge-tooltip {
  padding: 8px 12px;
  background: var(--bg-tertiary);
  border-radius: 8px;
  margin-top: 4px;
}

.badge-tooltip p {
  font-size: 14px;
  color: var(--text-secondary);
  margin: 0 0 8px;
}

.badge-tooltip a {
  font-family: var(--font-mono);
  font-size: 14px;
  color: var(--neon-green);
}
```

- [ ] **Step 3: Commit**

```bash
git add site/project/index.html
git commit -m "feat(site): Terminal Dark 功能特性卡片 + Trust Badges"
```

---

### Task 9: 功能对比表格样式

**Files:**
- Modify: `site/project/index.html` (comparison表格样式)

- [ ] **Step 1: 更新对比表格样式**

替换 `.comparison-table` 样式：

```css
.comparison-table {
  width: 100%;
  border-collapse: collapse;
  background: var(--bg-secondary);
  border-radius: 8px;
  overflow: hidden;
}

.comparison-table th,
.comparison-table td {
  padding: 12px 16px;
  text-align: left;
  border-bottom: 1px solid var(--border-subtle);
  font-size: 14px;
}

.comparison-table th {
  background: var(--bg-tertiary);
  font-family: var(--font-mono);
  font-weight: 600;
  color: var(--text-primary);
}

.comparison-table td {
  color: var(--text-secondary);
}

.numina-column {
  border-left: 2px solid var(--neon-green);
  background: var(--bg-tertiary);
  color: var(--text-primary);
}

.table-footer {
  font-size: 12px;
  color: var(--text-tertiary);
  text-align: right;
  padding: 8px 16px;
  font-family: var(--font-mono);
}
```

- [ ] **Step 2: Commit**

```bash
git add site/project/index.html
git commit -m "feat(site): Terminal Dark 对比表格 — Numina列高亮"
```

---

### Task 10: 页脚样式改造

**Files:**
- Modify: `site/project/index.html:551-563` (页脚HTML + 样式)

- [ ] **Step 1: 更新页脚HTML结构**

替换第551-563行页脚：

```html
<!-- Terminal Dark Footer -->
<footer class="dev-footer">
  <nav class="footer-links">
    <a href="https://github.com/vincentruan/numina" target="_blank" rel="noopener noreferrer">GitHub</a>
    <span class="footer-separator">·</span>
    <a href="https://github.com/vincentruan/numina/issues" target="_blank" rel="noopener noreferrer">Issues</a>
    <span class="footer-separator">·</span>
    <a href="https://github.com/vincentruan/numina/blob/main/LICENSE" target="_blank" rel="noopener noreferrer">LICENSE</a>
    <span class="footer-separator">·</span>
    <a href="https://github.com/vincentruan/numina/actions" target="_blank" rel="noopener noreferrer">CI</a>
  </nav>
  <p class="footer-meta">Last updated: 2026-04-20</p>
</footer>
```

- [ ] **Step 2: 更新页脚样式**

替换footer相关样式：

```css
.dev-footer {
  padding: 24px 16px;
  background: var(--bg-primary);
  text-align: center;
}

.footer-links {
  display: flex;
  flex-direction: column;
  gap: 16px;
  margin-bottom: 16px;
}

.footer-links a {
  font-family: var(--font-mono);
  color: var(--neon-green);
  font-size: 16px;
  text-decoration: none;
}

.footer-links a:hover {
  text-shadow: 0 0 8px rgba(0, 255, 65, 0.4);
}

.footer-separator {
  color: var(--text-tertiary);
  font-size: 14px;
}

.footer-meta {
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--text-tertiary);
  margin: 0;
}

@media (min-width: 768px) {
  .footer-links {
    flex-direction: row;
    justify-content: center;
    gap: 8px;
  }
}
```

- [ ] **Step 3: Commit**

```bash
git add site/project/index.html
git commit -m "feat(site): Terminal Dark 页脚 — JetBrains Mono + 霓虹绿链接"
```

---

### Task 11: 数据库选项区块样式

**Files:**
- Modify: `site/project/index.html` (db-option样式)

- [ ] **Step 1: 更新数据库选项样式**

替换 `.db-option` 样式：

```css
.db-option {
  background: var(--bg-secondary);
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
  padding: 16px 24px;
  margin-bottom: 12px;
}

.db-option h3 {
  margin: 0 0 8px;
  font-size: 16px;
  font-family: var(--font-mono);
  color: var(--neon-green);
}

.db-option code {
  display: block;
  font-family: var(--font-mono);
  font-size: 12px;
  background: var(--bg-tertiary);
  color: var(--text-secondary);
  padding: 8px 12px;
  border-radius: 4px;
  word-break: break-all;
}

.db-option p {
  font-size: 13px;
  color: var(--text-secondary);
  margin: 8px 0 0;
}
```

- [ ] **Step 2: Commit**

```bash
git add site/project/index.html
git commit -m "feat(site): Terminal Dark 数据库选项区块"
```

---

## Phase 5: 最终验证与响应式测试

### Task 12: 移动端响应式验证

**Files:**
- 无文件修改（仅视觉验证）

- [ ] **Step 1: Chrome DevTools 移动端测试**

打开 Chrome DevTools，切换到 375px 视口：
- 导航栏应正常显示（flex-wrap工作）
- 所有链接应有 ≥44px 触摸目标
- 终端命令块应正常宽度（min-width: 300px）
- 对比表格应横向滚动流畅

- [ ] **Step 2: Tablet 视口测试**

切换到 768px 视口：
- 技术架构卡片应为3列网格
- 页脚链接应为横向布局
- 网格背景应正常显示

- [ ] **Step 3: Desktop 视口测试**

切换到 1024px 视口：
- 所有区块应居中对齐（max-width: 1440px）
- 霓虹绿边框和发光效果应清晰可见
- 密集网格vs稀疏网格对比应明显

- [ ] **Step 4: Reduced Motion 测试**

在系统偏好设置中启用 "Reduce motion"：
- 光标动画应停止（opacity: 1）
- 所有hover过渡应禁用
- 页面仍应保持深色可读性

- [ ] **Step 5: 视觉验收清单**

确认以下验收标准达成：
- ✓ 页面完整转换为深色背景（无白色区块）
- ✓ 所有标题/导航使用JetBrains Mono
- ✓ 霓虹绿（#00ff41）一致应用于交互元素
- ✓ CSS网格背景在至少3个区块可见
- ✓ 技术架构区块位于页面最前
- ✓ 终端命令块显示发光效果

---

### Task 13: Git清理与文档更新

**Files:**
- 无文件修改（仅Git操作）

- [ ] **Step 1: 确认所有Commits**

运行 `git log --oneline --decorate -10` 检查commit历史：
- 应有12个feat(site) commits
- 每个commit应对应一个Task

- [ ] **Step 2: 最终状态确认**

运行 `git status` 确认无未提交更改：
- 应显示 "nothing to commit, working tree clean"

- [ ] **Step 3: Push准备**

如果需要push到远程，确认：
- 所有commits已正确组织
- 无冲突文件

---

## 实现完成标志

当所有13个Tasks完成，验收标准全部达成时，实现计划完成。

**交付物：**
- `site/project/index.html` — Terminal Dark风格的开发者页面
- `site/style.css` — 颜色系统、字体栈、网格背景类
- 12个清晰的git commits（每个Task一个commit）

**后续可选优化：**
- 终端输出动画（逐行显示）
- ASCII符号替换emoji图标
- 性能优化（字体加载策略）