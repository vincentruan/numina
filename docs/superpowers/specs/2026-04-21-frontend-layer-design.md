# Frontend Layer Design

**Date:** 2026-04-21
**Status:** Approved
**Scope:** 前端页面路由、核心组件、状态管理、国际化、主题系统

---

## Problem

1. 前端缺乏统一文档，页面路由、组件职责不清晰
2. 系统仅支持中文界面，非中文用户难以使用
3. 心愿系统缺乏文档
4. Terminal Dark 主题设计分散
5. 管理员切换孩子视角功能位置不当

---

## Goals

1. 定义清晰的页面路由映射
2. 规范核心组件职责和接口
3. 支持多语言界面（zh-CN、en-US）
4. 定义 Terminal Dark 主题规范
5. 将管理员孩子视角切换移至 FamilyPage

---

## Architecture

### 页面组织结构

```
frontend/src/
├── pages/          # 路由级别页面组件
│   ├── LoginPage.vue
│   ├── DashboardPage.vue
│   ├── AssetListPage.vue
│   ├── WishListPage.vue
│   └── ...
├── components/     # 可复用组件
│   ├── common/     # 通用组件（MoneyDisplay、EmptyState）
│   ├── asset/      # 资产相关组件
│   ├── charts/     # 图表组件（ECharts 封装）
│   └── family/     # 家庭相关组件
├── stores/         # Pinia 状态管理
├── composables/    # 组合式函数
├── api/            # Axios HTTP 客户端
├── i18n/           # 国际化配置
└── types/          # TypeScript 接口定义
```

### i18n 架构

```
frontend/src/i18n/
├── index.ts           # i18n 实例配置
└── locales/
    ├── zh-CN.ts       # 简体中文翻译
    └── en-US.ts       # 英文翻译
```

使用 vue-i18n 提供翻译服务，语言选择存储在 localStorage。

### Terminal Dark 主题架构

**核心颜色系统**：
```css
--bg-primary: #0d0d0d;      /* 近黑终端背景 */
--bg-secondary: #1a1a1a;    /* 提升卡片/区块 */
--neon-green: #00ff41;      /* 主要强调色 */
--text-primary: #f0f0f0;    /* 灰白文字 */
--border-subtle: #333333;   /* 网格线、边框 */
```

**字体策略**：
```css
--font-mono: 'JetBrains Mono', 'SF Mono', monospace;  /* 标题、代码 */
--font-body: -apple-system, BlinkMacSystemFont, sans-serif;  /* 正文 */
```

**CSS 网格背景**：
- 密集网格（20px）：hero、deploy 区块
- 稀疏网格（80px）：features、stack 区块
- 无网格：表格、配置区块

---

## Implementation Details

### 页面路由映射

| 路由 | 页面组件 | 说明 |
|------|----------|------|
| `/login` | LoginPage.vue | 登录页面 |
| `/register` | RegisterPage.vue | 注册页面 |
| `/dashboard` | DashboardPage.vue | 仪表盘首页 |
| `/assets` | AssetListPage.vue | 资产列表 |
| `/assets/:id` | AssetDetailPage.vue | 资产详情 |
| `/assets/new` | AssetFormPage.vue | 创建资产 |
| `/liabilities` | LiabilityListPage.vue | 负债列表 |
| `/wishes` | WishListPage.vue | 心愿列表 |
| `/wishes/:id` | WishDetailPage.vue | 心愿详情 |
| `/family` | FamilyPage.vue | 家庭管理 |
| `/settings` | SettingsPage.vue | 用户设置 |

### 核心组件

| 组件 | Props | 说明 |
|------|-------|------|
| MoneyDisplay | amount, sourceCurrency?, originalValue? | 金额显示 + 汇率信息弹窗 |
| EmptyState | icon, title, description? | 空数据状态提示 |
| CurrencyPicker | modelValue | 币种选择器 |
| AssetCard | asset | 资产卡片 |
| TrendLineChart | points | 净资产趋势图 |
| AllocationPieChart | items | 资产分布饼图 |

### Pinia Store 结构

| Store | 文件 | State |
|-------|------|-------|
| authStore | stores/auth.ts | user, token |
| assetStore | stores/asset.ts | assets, categories |
| wishStore | stores/wish.ts | wishes |
| currencyStore | stores/currency.ts | currencies, symbolMap |

### 翻译 Key 命名规范

层级格式：`模块.功能.具体文本`

示例：
```typescript
{
  asset: {
    title: '资产',
    status: { in_use: '服役中', idle: '闲置' }
  },
  common: { save: '保存', cancel: '取消' }
}
```

### 心愿系统流程

```
用户点击"实现心愿"
→ 前端打开资产表单（预填心愿信息）
→ 用户补充资产详细字段
→ POST /wishes/{id}/realize
→ 后端创建资产 + 更新心愿状态 + 关联 asset_id
→ 前端跳转到资产详情页
```

### 管理员孩子视角切换

**FamilyPage.vue** 添加按钮：
```vue
<van-button size="mini" plain @click="switchToChildView(child)">
  切换视角
</van-button>
```

**切换逻辑**：
```typescript
async function switchToChildView(child: ChildUser) {
  const response = await adminSwitchToChild(child.id)
  setTokens(response.access_token, response.refresh_token)
  localStorage.setItem('admin_child_view', child.id)
  setUser({ id: child.id, display_name: child.display_name, role: 'child' })
  router.push('/child/home')
}
```

**退出逻辑**（ChildLayout.vue）：
- 检测到 `admin_child_view` 时直接返回，无需密码验证
- 真实孩子登录需要密码验证

### API 调用约定

```typescript
const api = axios.create({
  baseURL: '/api/v1',
  timeout: 10000,
})

// 请求拦截：自动添加 Authorization header
api.interceptors.request.use((config) => {
  const token = storage.getToken()
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// 响应拦截：自动刷新过期 token
api.interceptors.response.use(
  (response) => response.data,
  async (error) => {
    if (error.response?.status === 401) {
      const newToken = await AuthApi.refreshToken()
      storage.setToken(newToken)
      return api.request(error.config)
    }
    return Promise.reject(error)
  }
)
```

---

## Code Pointers

| 功能 | 文件路径 |
|------|----------|
| 路由配置 | `frontend/src/router/index.ts` |
| API 客户端 | `frontend/src/api/index.ts` |
| i18n 配置 | `frontend/src/i18n/index.ts` |
| 中文翻译 | `frontend/src/i18n/locales/zh-CN.ts` |
| 通用组件 | `frontend/src/components/common/` |
| 图表组件 | `frontend/src/components/charts/` |
| 心愿列表页 | `frontend/src/pages/WishListPage.vue` |
| 家庭管理页 | `frontend/src/pages/FamilyPage.vue` |

---

## Related Specs

- **API层设计**：`2026-04-21-api-layer-design.md` — 前端 API 调用
- **多币种设计**：`2026-03-24-multi-currency-design.md` — CurrencyPicker（独立文档）