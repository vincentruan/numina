# Frontend Components Design

**Date:** 2026-04-20
**Status:** Approved
**Scope:** 前端页面路由、核心组件、状态管理

---

## Problem

前端缺乏统一文档，页面路由、组件职责、状态管理结构不清晰。开发者难以定位组件位置、理解组件接口，导致重复开发和维护困难。

---

## Goals

1. 定义清晰的页面路由映射
2. 规范核心组件职责和接口
3. 说明 Pinia Store 结构
4. 提供前后端协作参考

---

## Architecture

### 页面组织结构

```
frontend/src/
├── pages/          # 路由级别页面组件
│   ├── LoginPage.vue
│   ├── DashboardPage.vue
│   ├── AssetListPage.vue
│   └── ...
├── components/     # 可复用组件
│   ├── common/     # 通用组件（MoneyDisplay、EmptyState）
│   ├── asset/      # 资产相关组件
│   ├── liability/  # 负债相关组件
│   ├── charts/     # 图表组件（ECharts 封装）
│   └── family/     # 家庭相关组件
├── stores/         # Pinia 状态管理
├── composables/    # 组合式函数
├── api/            # Axios HTTP 客户端
└── types/          # TypeScript 接口定义
```

---

## Implementation Details

### 页面路由映射

| 路由 | 页面组件 | 说明 |
|------|----------|------|
| `/login` | LoginPage.vue | 登录页面 |
| `/register` | RegisterPage.vue | 注册页面 |
| `/join-family` | JoinFamilyPage.vue | 加入家庭页面 |
| `/dashboard` | DashboardPage.vue | 仪表盘首页 |
| `/assets` | AssetListPage.vue | 资产列表 |
| `/assets/:id` | AssetDetailPage.vue | 资产详情 |
| `/assets/new` | AssetFormPage.vue | 创建资产 |
| `/assets/:id/edit` | AssetFormPage.vue | 编辑资产 |
| `/assets/:id/sell` | AssetSellPage.vue | 出售资产 |
| `/liabilities` | LiabilityListPage.vue | 负债列表 |
| `/liabilities/:id` | LiabilityDetailPage.vue | 负债详情 |
| `/liabilities/new` | LiabilityFormPage.vue | 创建负债 |
| `/wishes` | WishListPage.vue | 心愿列表 |
| `/wishes/:id` | WishDetailPage.vue | 心愿详情 |
| `/wishes/new` | WishFormPage.vue | 创建心愿 |
| `/family` | FamilyPage.vue | 家庭管理 |
| `/settings` | SettingsPage.vue | 用户设置 |
| `/categories` | CategoryManagePage.vue | 分类管理 |
| `/tags` | TagManagePage.vue | 标签管理 |

### 核心组件

**通用组件**

| 组件 | Props | 说明 |
|------|-------|------|
| MoneyDisplay | amount, sourceCurrency?, originalValue? | 金额显示 + 汇率信息弹窗 |
| EmptyState | icon, title, description? | 空数据状态提示 |
| PageHeader | title, showBack? | 页面标题栏 |
| AppTabBar | — | 底部导航栏（固定 5 个 tab） |

**币种相关组件**

| 组件 | Props | 说明 |
|------|-------|------|
| CurrencyPicker | modelValue | 币种选择器（底部弹出） |
| CurrencySelector | modelValue: {amount, currency} | 币种 + 金额输入 |

**资产相关组件**

| 组件 | Props | 说明 |
|------|-------|------|
| AssetCard | asset | 资产卡片（列表项） |
| AssetForm | modelValue | 资产表单（动态字段） |

**负债相关组件**

| 组件 | Props | 说明 |
|------|-------|------|
| LiabilityCard | liability | 负债卡片 |
| LiabilityForm | modelValue | 负债表单 |

**图表组件**

| 组件 | Props | 说明 |
|------|-------|------|
| TrendLineChart | points | 净资产趋势图 |
| AllocationPieChart | items | 资产分布饼图 |

### Pinia Store 结构

| Store | 文件 | State | 说明 |
|-------|------|-------|------|
| authStore | stores/auth.ts | user, token | 用户认证状态 |
| assetStore | stores/asset.ts | assets, categories | 资产数据管理 |
| liabilityStore | stores/liability.ts | liabilities | 负债数据管理 |
| wishStore | stores/wish.ts | wishes | 心愿数据管理 |
| categoryStore | stores/category.ts | categories | 分类数据管理 |
| tagStore | stores/tag.ts | tags | 标签数据管理 |
| familyStore | stores/family.ts | family, members | 家庭数据管理 |
| currencyStore | stores/currency.ts | currencies, symbolMap, flagMap | 币种数据管理 |

**Store 使用模式**

```typescript
// stores/asset.ts
export const useAssetStore = defineStore('asset', () => {
  const assets = ref<Asset[]>([])
  const loading = ref(false)
  
  async function fetchAssets() {
    loading.value = true
    assets.value = await AssetApi.list()
    loading.value = false
  }
  
  return { assets, loading, fetchAssets }
})

// 页面中使用
const assetStore = useAssetStore()
onMounted(() => assetStore.fetchAssets())
```

### API 调用约定

**Axios 配置**

```typescript
// api/index.ts
const api = axios.create({
  baseURL: '/api/v1',
  timeout: 10000,
})

// 请求拦截：自动添加 Authorization header
api.interceptors.request.use((config) => {
  const token = storage.getToken()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// 响应拦截：自动刷新过期 token
api.interceptors.response.use(
  (response) => response.data,
  async (error) => {
    if (error.response?.status === 401) {
      // Token 过期，尝试刷新
      const newToken = await AuthApi.refreshToken()
      storage.setToken(newToken)
      // 重试原请求
      return api.request(error.config)
    }
    return Promise.reject(error)
  }
)
```

**错误处理**

```typescript
// 组件中的错误处理
async function handleSubmit() {
  try {
    await AssetApi.create(form)
    showToast('创建成功')
    router.push('/assets')
  } catch (error) {
    if (error.response?.status === 400) {
      showToast(error.response.data.detail)
    } else {
      showToast('网络错误，请稍后重试')
    }
  }
}
```

---

## Code Pointers

| 入口 | 文件路径 |
|------|----------|
| 应用入口 | `frontend/src/main.ts` |
| 路由配置 | `frontend/src/router/index.ts` |
| API 客户端 | `frontend/src/api/index.ts` |
| 类型定义 | `frontend/src/types/index.ts` |
| 通用组件 | `frontend/src/components/common/` |
| 图表组件 | `frontend/src/components/charts/` |

---

## Related Specs

- **编码规范设计**：`2026-04-20-coding-standards-design.md` — Vue 组件规范
- **API规范设计**：`2026-04-20-api-spec-design.md` — 前端 API 调用
- **多币种设计**：`2026-03-24-multi-currency-design.md` — CurrencyPicker、CurrencySelector