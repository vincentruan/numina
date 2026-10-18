# About 页面子页面架构 + 法务文档设计

**日期**: 2026-10-18
**状态**: 待审批

## 1. 背景与目标

### 现状

`AboutPage.vue` 是 `/settings/about` 下的独立页面，包含 5 个菜单项：

| 菜单项 | 当前行为 |
|--------|---------|
| 更新日志 | `van-popup` 底部浮窗 |
| 服务条款 | `window.open` 跳转 GitHub |
| 隐私政策 | `window.open` 跳转 GitHub |
| 开源组件声明 | `van-popup` 底部浮窗 |
| 项目主页 | `window.open` 跳转 GitHub |

### 目标

1. **更新日志、开源组件声明** — 从底部浮窗改为独立路由页面，支持完整阅读体验
2. **服务条款、隐私政策** — 不再跳转 GitHub，改为前端内嵌独立页面，内容由法务视角撰写
3. **项目主页** — 保留跳转 GitHub（开发者相关，合理）
4. **可扩展性** — 未来新增内容页（FAQ、免责声明等）只需加路由 + 数据，不重复造轮子

### 非目标

- 不改动 AboutPage 的菜单结构（5 项保持不变）
- 不引入新的 UI 库（继续使用 Vant 4）
- 不改动后端 API
- 不改子应用 (child app)

## 2. 前端架构设计

### 2.1 内容页基础组件 `ContentPage`

所有子页面共享一个基础布局组件，避免重复样式和结构：

```
src/components/common/ContentPage.vue
```

**职责**：
- `PageHeader` 标题 + 返回按钮
- 可滚动内容区域
- 统一的内边距、排版样式（标题层级、段落、列表）
- 深色模式适配（CSS variables）
- 底部安全区

**Props**:
```ts
interface ContentPageProps {
  title: string              // 页面标题（i18n key）
  lastUpdated?: string       // 可选，最后更新日期
}
```

**Slots**:
- `default` — 页面正文内容

### 2.2 路由结构

```ts
// router/index.ts 新增子路由
{
  path: 'settings/about/changelog',
  name: 'AboutChangelog',
  component: () => import('@/pages/about/ChangelogPage.vue'),
},
{
  path: 'settings/about/terms',
  name: 'AboutTerms',
  component: () => import('@/pages/about/TermsPage.vue'),
},
{
  path: 'settings/about/privacy',
  name: 'AboutPrivacy',
  component: () => import('@/pages/about/PrivacyPage.vue'),
},
{
  path: 'settings/about/licenses',
  name: 'AboutLicenses',
  component: () => import('@/pages/about/LicensesPage.vue'),
},
```

使用 `settings/about/*` 子路径，语义清晰，未来加页面只需加路由。

### 2.3 文件结构

```
src/pages/about/
├── ChangelogPage.vue       # 更新日志
├── TermsPage.vue           # 服务条款
├── PrivacyPage.vue         # 隐私政策
├── LicensesPage.vue        # 开源组件声明
└── data/
    ├── changelog.ts        # 版本数据（从 AboutPage.vue 迁移）
    └── licenses.ts         # 组件数据（从 AboutPage.vue 迁移）
```

### 2.4 AboutPage.vue 改造

- 删除 `showChangelog`、`showOpenSource` 两个 ref 和两个 `van-popup`
- 删除 changelog、ossComponents 数据（迁移到 `data/` 目录）
- 菜单项改为 `<van-cell :to="...">` 路由跳转
- "项目主页" 保留 `@click="openProjectUrl"`

### 2.5 各页面设计

#### ChangelogPage（更新日志）

- 复用现有 changelog 数据和样式
- 使用 `ContentPage` 包裹
- 版本时间线样式：版本号 + 日期 + 变更列表
- 数据从 `data/changelog.ts` 导入

#### TermsPage（服务条款）

- 法务长文，使用 `ContentPage` 包裹
- 内容结构：章节标题 + 段落 + 有序/无序列表
- 使用 `<section>` 分章节，锚点导航（可选，首期不做）
- 内容通过 i18n 管理（中英双语）
- 顶部显示"最后更新日期"

#### PrivacyPage（隐私政策）

- 同 TermsPage 结构
- 需覆盖：数据收集、AI 数据处理、行为分析、自部署 vs 未来 SaaS

#### LicensesPage（开源组件声明）

- 复用现有 ossComponents 数据
- 使用 `ContentPage` 包裹
- 列表样式：组件名 + 许可证类型 + 链接
- 顶部显示 Numina 自身的 AGPL-3.0 声明摘要

## 3. 法务文档内容大纲

### 3.1 服务条款 (Terms of Service)

以 AGPL-3.0 开源项目为基础，预留未来 SaaS 商用条款接口。

```
1. 接受条款
2. 服务描述 — Numina 家庭资产管理平台
3. 开源许可 — AGPL-3.0 声明
4. 自部署模式 — 用户自行部署、数据自控
5. 账户与家庭组 — 注册、角色、邀请机制
6. 用户内容 — 资产数据归用户所有
7. AI 功能 — 第三方数据处理、脱敏说明、风险提示
8. 行为分析 — 数据收集范围、用途
9. 免责声明 — "按原样"提供，无担保
10. 责任限制
11. 未来服务变更 — 保留 SaaS 化条款空间
12. 条款修改
13. 联系方式
```

### 3.2 隐私政策 (Privacy Policy)

```
1. 概述
2. 信息收集
   2.1 用户提供的信息（注册、资产数据）
   2.2 自动收集的信息（行为分析、错误日志）
   2.3 不收集的信息
3. 信息使用
   3.1 核心功能
   3.2 AI 功能数据处理
   3.3 行为分析
   3.4 错误上报
4. 数据存储与安全
   4.1 自部署场景 — 数据完全本地
   4.2 加密措施
5. 第三方数据共享
   5.1 AI 服务（发送前脱敏）
   5.2 错误上报服务
6. 数据保留与删除
7. 用户权利 — 访问、更正、删除
8. 儿童隐私
9. Cookie 与本地存储
10. 政策更新
11. 联系方式
```

### 3.3 撰写原则

- **严谨但可读**：避免纯法律八股，让普通用户能读懂关键条款
- **中英双语**：与项目 i18n 对齐，zh-CN 和 en-US 各一份
- **技术准确**：基于实际技术栈（FastAPI、PostgreSQL/SQLite、LangChain、Tavily 等）
- **前瞻性**：为未来 SaaS 模式预留条款空间，措辞不锁死自部署
- **AGPL-3.0 合规**：明确开源义务

### 3.4 i18n 策略

法务文档内容较长，不适合逐句拆成 i18n key（维护成本高）。采用以下方案：

- 每个法务页面组件内，根据 `locale` 从对应数据文件导入全文内容
- `data/terms-zh.ts` / `data/terms-en.ts` 导出结构化章节数组
- `data/privacy-zh.ts` / `data/privacy-en.ts` 同理
- 页面组件根据当前 locale 选择对应版本渲染

```ts
// data/terms-zh.ts
export const termsContent = [
  {
    heading: '1. 接受条款',
    paragraphs: [
      '欢迎使用 Numina...',
      '通过使用本软件，您同意...',
    ],
  },
  // ...
]
```

```ts
// TermsPage.vue
import { termsContent as termsZh } from './data/terms-zh'
import { termsContent as termsEn } from './data/terms-en'
const content = computed(() => locale.value.startsWith('zh') ? termsZh : termsEn)
```

## 4. 扩展性设计

未来新增内容页只需：

1. 在 `src/pages/about/` 下新建 `XxxPage.vue`
2. 在 `router/index.ts` 加一条路由
3. 在 `AboutPage.vue` 加一个 `<van-cell :to="...">`
4. 如需 i18n key，加到 locales 文件

`ContentPage` 组件确保所有页面视觉一致，新页面零样式成本。

## 5. 实现顺序

| 步骤 | 内容 | 说明 |
|------|------|------|
| 1 | 创建 `ContentPage.vue` 基础组件 | 布局 + 样式 + 深色模式 |
| 2 | 迁移数据到 `data/` 目录 | changelog.ts + licenses.ts |
| 3 | 创建 4 个子页面 | Changelog/Terms/Privacy/Licenses |
| 4 | 撰写法务文档 | terms (zh+en) + privacy (zh+en) |
| 5 | 改造 AboutPage.vue | popup → router-link |
| 6 | 添加路由 | 4 条新路由 |
| 7 | 添加 i18n keys | 菜单项标题等 |
| 8 | 验证 | typecheck + lint + 视觉确认 |

## 6. Builder Check 决议

| 问题 | 决议 |
|------|------|
| 法务文档谁写？ | 由实现者（我）以法务资深律师视角撰写，作为本次实现范围的一部分。用户审阅最终版本。 |
| changelog 数据迁移后 i18n 处理 | 数据文件只存 i18n key 字符串，不存解析后的文本。页面组件在渲染时调用 `t()` 解析。数据文件形状：`{ version, date, changes: string[] }` 其中 `changes` 是 i18n key 数组。 |

## 7. 待确认项（已清零）

- ~~法务文档内容方向~~ ✅ 已确认
- ~~页面架构~~ ✅ 已确认
- ~~i18n 法务文档策略~~ ✅ 整段文本按章节组织，不做逐句 i18n
- ~~TermsPage/PrivacyPage 是否需要锚点导航~~ ✅ 首期不做
- ~~法务文档作者~~ ✅ 实现者撰写，用户审阅
- ~~changelog 数据 i18n 迁移~~ ✅ 数据文件存 key，组件调 `t()`
