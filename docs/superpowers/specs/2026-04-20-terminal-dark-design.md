---
name: terminal-dark-developer-page
description: Numina开发者页面Terminal Dark美学重设计规范
type: design
---

# Terminal Dark 开发者页面重设计规范

## 设计目标

**重设计目的：** 多用途优化 — 品牌差异化、技术可信度、转化优化
**目标受众：** 独立开发者 / 自托管用户（隐私意识强，部署在个人服务器或家庭实验室）
**美学定位：** 平衡现代复古 — JetBrains Mono + CSS网格背景提供结构感，现代间距、精炼排版、微妙发光效果

## 核心设计决策

### 设计方法选择：混合终端现代风格

**方案B（推荐）：** 终端美学聚焦核心区块（hero、deploy、代码块），现代深色UI用于内容区块

**为什么不用其他方案：**
- 方案A（全终端）会牺牲长内容可读性，过于激进
- 方案C（终端点缀）终端感不够强烈，会模糊成通用深色模式

**关键权衡：** 保留终端身份感，同时尊重内容层级和配置表格的可读性

---

## 技术规范

### 1. 字体策略

**JetBrains Mono应用范围：**
- 主要：所有导航链接、区块标题、部署终端块、代码片段
- 强调：特性卡片标题、Trust Badge摘要、表格表头
- 不使用：正文段落、特性描述、表格单元格内容（保持system font以提高可读性）

**字体栈定义：**
```css
:root {
  --font-mono: 'JetBrains Mono', 'SF Mono', 'Menlo', 'Monaco', 'Courier New', monospace;
  --font-body: -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Hiragino Sans GB', sans-serif;
}
```

**字重与尺寸策略：**
- 导航/标题：JetBrains Mono 500, 14-18px
- 终端块：JetBrains Mono 400, 16-18px（保持代码可读性）
- 正文：System font 400, 14-16px（舒适阅读）

**设计原理：** JetBrains Mono针对代码可读性优化，但设计上可在较小尺寸工作。用于标题建立终端身份感，不在长解释文本上强制monospace（会损害可读性）。

---

### 2. 颜色系统

**核心颜色定义：**
```css
:root {
  --bg-primary: #0d0d0d;      /* 近黑终端背景 */
  --bg-secondary: #1a1a1a;    /* 提升卡片/区块 */
  --bg-tertiary: #2a2a2a;     /* 交互元素hover */
  --neon-green: #00ff41;      /* 主要强调色（经典终端绿） */
  --neon-green-dim: #00cc33;  /* Hover状态，更温和 */
  --neon-green-glow: rgba(0, 255, 65, 0.15); /* 背景发光效果 */
  --text-primary: #f0f0f0;    /* 灰白减少眼疲劳 */
  --text-secondary: #888888;  /* 柔化描述 */
  --text-tertiary: #666666;   /* 极微妙时间戳、元数据 */
  --border-subtle: #333333;   /* 网格线、卡片边框 */
  --border-bright: #444444;   /* Focus状态、活跃元素 */
}
```

**强调色使用规则：**
- **霓虹绿（#00ff41）：** 交互文字（导航链接、按钮、部署命令）、代码高亮、focus边框
- **霓虹绿发光：** 终端块背后背景模糊，卡片hover发光（15px radius, 0.15 alpha）
- **温和绿色（dim/glow变体）：** Hover状态减少视觉侵略性，次要高亮

**避免"AI Slop"反模式：**
- 无紫色渐变（遵循 design-reference.md）
- 无激进渐变背景 — 仅用实色深色 + 微妙发光
- 霓虹绿作为有目的的强调，而非全屏饱和

**设计原理：** 经典 #00ff41 终端绿在开发者中有文化共鸣。灰白文字（#f0f0f0）减少相对纯白在黑上的眼疲劳。分层深色背景创造深度而无需渐变。

---

### 3. CSS网格背景模式

**响应式密度策略：**

```css
/* 高聚焦区块的密集网格（hero、deploy） */
.terminal-grid-dense {
  background-image:
    linear-gradient(rgba(0, 255, 65, 0.03) 1px, transparent 1px),
    linear-gradient(90deg, rgba(0, 255, 65, 0.03) 1px, transparent 1px);
  background-size: 20px 20px;
}

/* 内容区块的稀疏网格（features、stack、config） */
.terminal-grid-sparse {
  background-image:
    linear-gradient(rgba(51, 51, 51, 0.5) 1px, transparent 1px),
    linear-gradient(90deg, rgba(51, 51, 51, 0.5) 1px, transparent 1px);
  background-size: 80px 80px;
}

/* 可读性区块无网格（对比表、部署步骤） */
.terminal-grid-none {
  background: var(--bg-secondary);
}
```

**密度映射规则：**
- **Hero + Deploy区块：** 密集20px网格，微妙霓虹绿线条（高视觉能量）
- **Tech Stack + Features：** 稀疏80px网格，柔和灰线条（结构性背景）
- **Comparison + Config表格：** 无网格，实色深色背景（最大表格可读性）
- **导航栏：** 密集网格延续，无缝过渡

**网格颜色细微差别：**
- 密集网格用霓虹绿（#00ff41）3%透明度 — 可见但不分心
- 稀疏网格用border-subtle（#333333）50%透明度 — 结构性，非终端编码

**设计原理：** 响应式密度尊重内容层级。密集网格在焦点区域创造终端氛围，不会在配置表格上压倒用户需要阅读小文字的地方。灰色稀疏网格维持结构而不与内容竞争。

---

## 页面结构重组

### 技术优先布局顺序

**原布局：**
```
[粘性导航栏]
  ↓
[功能特性] — 优先展示
  ↓
[技术架构] — 次要位置
  ↓
[功能对比]
  ↓
[快速部署]
  ↓
[配置参考]
```

**新布局：**
```
[粘性导航栏] — 密集网格背景 + 霓虹绿边框
  ↓
[技术架构] — 优先展示，稀疏网格背景
  ↓
[快速部署] — 终端风格核心，密集网格 + 发光效果
  ↓
[配置参考] — 环境变量表格，无网格深色
  ↓
[功能特性] — 降级展示，稀疏网格
  ↓
[功能对比] — 比较表格，无网格
  ↓
[页脚] — 最深色背景，无网格
```

**导航锚点重构：**
```html
<nav class="dev-nav-links">
  <a href="#stack">技术架构</a>   <!-- 第一锚点 -->
  <a href="#deploy">快速部署</a>
  <a href="#config">配置参考</a>
  <a href="#features">功能特性</a>
</nav>
```

**设计原理：** 自托管用户首先关心"我要部署什么技术栈"，而非"有什么功能"。将技术架构移到最前，立即建立技术可信度。部署和配置紧随其后，形成完整"上手路径"。功能特性降级到后半部分，作为补充信息而非吸引点。

---

## 核心组件设计

### 4. 快速部署区块 — 终端风格核心

**终端命令块结构：**
```html
<div class="deploy-terminal">
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
```

**终端命令块样式：**
- **外框：** 深色背景（#1a1a1a）+ 霓虹绿边框（1px #00ff41）+ 发光效果
- **发光效果：** `box-shadow: 0 0 15px rgba(0, 255, 65, 0.15)` — 微妙霓虹绿外发光
- **终端头部：** 圆点装饰 + "terminal" 标题，模拟真实终端窗口
- **命令文字：** JetBrains Mono 16px，霓虹绿色
- **输出文字：** JetBrains Mono 14px，灰白色（#888888），成功行用绿色 ✓

**部署步骤列表改造：**
```html
<ol class="deploy-steps">
  <li>
    <span class="step-number">01</span>
    <div class="step-content">
      <strong class="step-title">克隆仓库</strong>
      <code class="step-command">git clone https://github.com/vincentruan/numina.git</code>
    </div>
  </li>
  <!-- ... -->
</ol>
```

**步骤样式：**
- **步骤编号：** JetBrains Mono 14px，霓虹绿色，方形边框而非圆形（终端感）
- **命令块：** 深色背景 + 霓虹绿代码高亮，内联显示
- **背景：** 密集网格（20px）延续到整个部署区块

**CTA按钮改造：**
- **主按钮：** 霓虹绿边框 + 透明背景，hover时填充霓虹绿 + 黑色文字
- **文字：** JetBrains Mono 14px，"查看完整部署指南 →"

---

### 5. 特性卡片与内容区块

**技术架构卡片改造：**
```html
<div class="stack-grid">
  <div class="stack-card">
    <h3 class="stack-title">后端</h3>
    <ul class="stack-list">
      <li>FastAPI (Python)</li>
      <li>SQLAlchemy ORM</li>
      <li>SQLite / MySQL / PostgreSQL</li>
    </ul>
  </div>
  <!-- 前端 / 基础设施卡片 -->
</div>
```

**卡片样式：**
- **背景：** 深色（#1a1a1a），霓虹绿边框（1px #00ff41）
- **标题：** JetBrains Mono 16px 500，霓虹绿色，上边距0
- **列表项：** System font 14px，灰白色（#888888），bullet用霓虹绿色小方块
- **Hover效果：** 边框发光增强，背景轻微提升（#2a2a2a）
- **网格背景：** 稀疏80px网格，灰色线条

**功能特性卡片网格：**
```html
<div class="feature-grid">
  <div class="feature-card">
    <span class="feature-icon">📦</span>
    <h3 class="feature-title">资产管理</h3>
    <p class="feature-desc">实物资产追踪（房产、车辆、数码等13个分类）</p>
  </div>
  <!-- 5张特性卡片 -->
</div>
```

**特性卡片样式：**
- **视觉降级：** 无霓虹绿边框，仅用深色边框（#333333）
- **标题：** JetBrains Mono 14px，白色（#f0f0f0）
- **描述：** System font 14px，灰色（#888888）
- **图标：** 保留现有emoji或替换为简单ASCII符号（如📦→[+]）
- **Hover：** 背景提升 + 边框变亮（#444444），无发光

**Trust Badges改造：**
- **展开按钮：** JetBrains Mono，霓虹绿色 ✓ 符号
- **展开内容：** 深色背景 + 霓虹绿文字链接
- **保持 `<details>` 单开行为**

---

### 6. 表格样式

**配置参考表格：**
```html
<table class="config-table">
  <thead>
    <tr>
      <th>变量名</th>
      <th>默认值</th>
      <th>说明</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><code>SECRET_KEY</code></td>
      <td><span class="config-warning">⚠️ 必填</span></td>
      <td>JWT 签名密钥，生产环境必须设置</td>
    </tr>
  </tbody>
</table>
```

**表格样式：**
- **背景：** 深色（#1a1a1a），无网格背景（最大可读性）
- **表头：** JetBrains Mono 14px，霓虹绿色，背景稍深（#2a2a2a）
- **代码单元格：** JetBrains Mono 13px，霓虹绿高亮 + 深色背景块
- **警告标记：** 霓虹绿色 ⚠️ 符号 + 文字
- **边框：** 细线（#333333），分隔行而非包围整个表格
- **Hover：** 行背景轻微提升（#2a2a2a）

**功能对比表格：**
```html
<table class="comparison-table">
  <thead>
    <tr>
      <th>功能</th>
      <th class="numina-column">Numina</th>
      <th>传统预算应用</th>
      <th>电子表格</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>隐私保护</td>
      <td class="numina-column">自托管，数据完全本地</td>
      <td>云端存储</td>
      <td>本地文件</td>
    </tr>
  </tbody>
</table>
```

**对比表格样式：**
- **Numina列高亮：** 霓虹绿左边框（2px），背景稍亮（#2a2a2a）
- **表头：** JetBrains Mono 14px
- **单元格：** System font 14px，保持可读性
- **背景：** 深色无网格
- **响应式：** 保留移动端横向滚动

**数据库选项区块：**
- **每个选项：** 深色卡片 + 霓虹绿标题
- **代码块：** JetBrains Mono 12px，终端风格代码显示

---

### 7. 导航栏与页脚

**粘性导航栏改造：**
```html
<header class="dev-nav">
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

**导航样式：**
- **背景：** 深色（#0d0d0d），密集网格背景延续
- **Logo：** JetBrains Mono 18px 700，霓虹绿色
- **分隔符：** 灰色 "/"，增强路径感（如 `Numina / docs`）
- **链接：** JetBrains Mono 14px，霓虹绿色，hover发光效果
- **边框：** 底部霓虹绿细线（1px），分隔导航与内容

**页脚改造：**
```html
<footer class="dev-footer">
  <nav class="footer-links">
    <a href="https://github.com/vincentruan/numina">GitHub</a>
    <span class="footer-separator">·</span>
    <a href="https://github.com/vincentruan/numina/issues">Issues</a>
    <span class="footer-separator">·</span>
    <a href="https://github.com/vincentruan/numina/blob/main/LICENSE">LICENSE</a>
  </nav>
  <p class="footer-meta">Last updated: 2026-04-20</p>
</footer>
```

**页脚样式：**
- **背景：** 最深色（#0d0d0d），无网格
- **链接：** JetBrains Mono 14px，霓虹绿色
- **分隔符：** 灰色 "·"，终端路径风格
- **元数据：** JetBrains Mono 12px，灰色（#666666）

---

### 8. 动画与过渡

**光标闪烁动画：**
```css
.cursor {
  display: inline-block;
  width: 8px;
  height: 18px;
  background: #00ff41; /* 霓虹绿 */
  margin-left: 4px;
  animation: blink 1s infinite;
}

@keyframes blink {
  0%, 50% { opacity: 1; }
  51%, 100% { opacity: 0; }
}
```

**卡片Hover过渡：**
```css
.stack-card,
.feature-card {
  transition: box-shadow 150ms ease, background 150ms ease;
}

.stack-card:hover {
  box-shadow: 0 0 20px rgba(0, 255, 65, 0.25); /* 发光增强 */
  background: var(--bg-tertiary);
}

.feature-card:hover {
  background: var(--bg-tertiary);
  border-color: var(--border-bright);
}
```

**链接Hover发光：**
```css
.dev-nav-links a:hover,
.footer-links a:hover {
  text-shadow: 0 0 8px rgba(0, 255, 65, 0.4);
}
```

**Reduced Motion支持：**
```css
@media (prefers-reduced-motion: reduce) {
  .cursor {
    animation: none;
    opacity: 1;
  }

  * {
    transition: none !important;
  }
}
```

---

## 实现优先级

### Phase 1：基础样式改造
1. 更新 `site/style.css` — 颜色系统、网格背景类、字体栈
2. 改造粘性导航栏 — 密集网格 + 霓虹绿边框
3. 页面结构调整 — 技术架构优先顺序

### Phase 2：核心组件改造
1. 快速部署区块 — 终端命令块 + 发光效果
2. 技术架构卡片 — 霓虹绿边框 + hover发光
3. 配置参考表格 — 深色背景 + 代码高亮

### Phase 3：次要组件改造
1. 功能特性卡片 — 视觉降级样式
2. 功能对比表格 — Numina列高亮
3. Trust Badges + 页脚

### Phase 4：细节打磨
1. 动画过渡优化
2. Reduced motion测试
3. 移动端响应式验证

---

## 验收标准

**必须达成：**
- ✓ 页面完整转换为深色背景（无白色区块）
- ✓ 所有标题/导航使用JetBrains Mono
- ✓ 霓虹绿（#00ff41）一致应用于交互元素
- ✓ CSS网格背景在至少3个区块可见（hero/deploy/stack）
- ✓ 技术架构区块位于页面最前（锚点#stack）
- ✓ 终端命令块显示发光效果
- ✓ 移动端（375px）所有交互元素 ≥44px触摸目标

**应该达成：**
- ✓ 配置表格代码单元格可读（≥13px）
- ✓ 对比表格横向滚动流畅（移动端）
- ✓ Trust Badge单开行为保持
- ✓ 光标动画在reduced motion下禁用

**可优化：**
- 终端输出动画（逐行显示）
- 部署步骤编号方形边框vs圆形
- ASCII符号替换emoji图标

---

## 相关文档

- `site/CLAUDE.md` — 站点模块规范（避免AI Slop反模式）
- `site/design-reference.md` — 深度设计模式参考
- `docs/plans/2026-04-18-004-feat-frontend-promotional-pages-plan.md` — Vue前端宣传页面（不同scope）