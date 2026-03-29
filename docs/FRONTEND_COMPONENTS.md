# Numina 前端组件索引

## 页面路由映射

| 路由 | 组件 | 说明 |
|------|------|------|
| `/login` | LoginPage.vue | 登录页面 |
| `/register` | RegisterPage.vue | 注册页面 |
| `/join-family` | JoinFamilyPage.vue | 加入家庭页面 |
| `/` | DashboardPage.vue | 首页仪表盘 |
| `/assets` | AssetListPage.vue | 资产列表 |
| `/assets/new` | AssetFormPage.vue | 新建资产 |
| `/assets/:id` | AssetDetailPage.vue | 资产详情 |
| `/assets/:id/edit` | AssetFormPage.vue | 编辑资产 |
| `/liabilities` | LiabilityListPage.vue | 负债列表 |
| `/liabilities/new` | LiabilityFormPage.vue | 新建负债 |
| `/liabilities/:id` | LiabilityDetailPage.vue | 负债详情 |
| `/wishes` | WishListPage.vue | 心愿列表 |
| `/wishes/new` | WishFormPage.vue | 新建心愿 |
| `/stats` | DataStatsPage.vue | 数据统计 |
| `/family` | FamilyPage.vue | 家庭管理 |
| `/settings` | SettingsPage.vue | 设置页面 |
| `/settings/categories` | CategoryManagePage.vue | 分类管理 |
| `/settings/tags` | TagManagePage.vue | 标签管理 |

---

## 核心组件

### 资产组件 (`components/asset/`)

| 组件 | 职责 | Props |
|------|------|-------|
| AssetForm.vue | 资产录入/编辑表单 | `assetId?: string`, `isEdit?: boolean` |
| AssetCard.vue | 资产卡片展示 | `asset: Asset` |
| AssetListItem.vue | 资产列表项 | `asset: Asset` |
| CategoryGrid.vue | 分类图标网格 | `selected?: string`, `assetType?: string` |
| UsageFreqSelector.vue | 使用频率选择器 | `modelValue: string` |
| TagSelector.vue | 标签多选器 | `modelValue: string[]` |

### 仪表盘组件 (`components/dashboard/`)

| 组件 | 职责 | Props |
|------|------|-------|
| NetWorthCard.vue | 净资产卡片 | `overview: DashboardOverview` |
| StatusSummaryGrid.vue | 状态汇总网格 | `summary: StatesSummary`, `activeStatus?: string` |
| AlertCards.vue | 预警卡片组 | `idleAssets: LowUsageItem[]`, `expiringAssets: ExpiringSoonItem[]` |
| AllocationPieChart.vue | 资产分布饼图 | `data: AllocationItem[]` |
| TrendLineChart.vue | 趋势折线图 | `data: TrendPoint[]` |

### 表单组件 (`components/common/`)

| 组件 | 职责 | Props |
|------|------|-------|
| CurrencyInput.vue | 货币输入框 | `modelValue: number`, `currency?: string` |
| DatePicker.vue | 日期选择器 | `modelValue: string` |
| SearchBar.vue | 搜索栏 | `placeholder?: string` |

---

## Store 结构

### 资产 Store (`stores/asset.ts`)

```typescript
interface AssetState {
  assets: Asset[]
  currentAsset: Asset | null
  loading: boolean
  filters: AssetFilters
}

interface AssetFilters {
  status?: string
  asset_type?: string
  category_id?: string
  search?: string
}

// Actions
- fetchAssets()
- fetchAsset(id)
- createAsset(data)
- updateAsset(id, data)
- deleteAsset(id)
- setFilters(filters)
```

### 仪表盘 Store (`stores/dashboard.ts`)

```typescript
interface DashboardState {
  overview: DashboardOverview | null
  allocation: AllocationItem[]
  trend: TrendPoint[]
  topAssets: TopAssetItem[]
  lowUsageAssets: LowUsageItem[]
  expiringSoonAssets: ExpiringSoonItem[]
  statesSummary: StatesSummaryResponse | null
  homeAssets: Record<string, Asset[]>
  loading: boolean
}

// Actions
- fetchOverview()
- fetchAllocation()
- fetchTrend(period)
- fetchTopAssets()
- fetchLowUsageAssets()
- fetchExpiringSoonAssets()
- fetchStatesSummary()
- fetchHomeAssets()
- fetchAll()
```

### 用户 Store (`stores/user.ts`)

```typescript
interface UserState {
  user: User | null
  token: string | null
  refreshToken: string | null
}

// Actions
- login(username, password)
- register(data)
- logout()
- refreshAuth()
```

### 分类 Store (`stores/category.ts`)

```typescript
interface CategoryState {
  categories: Category[]
  loading: boolean
}

// Actions
- fetchCategories()
- createCategory(data)
- updateCategory(id, data)
- deleteCategory(id)
```

---

## API 调用约定

### 请求配置

```typescript
// src/api/index.ts
const http = axios.create({
  baseURL: '/api/v1',
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json'
  }
})

// 请求拦截器：添加 Token
http.interceptors.request.use(config => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// 响应拦截器：处理错误
http.interceptors.response.use(
  response => response,
  error => {
    if (error.response?.status === 401) {
      // Token 过期，跳转登录
      router.push('/login')
    }
    return Promise.reject(error)
  }
)
```

### 类型定义

```typescript
// src/types/index.ts
interface Asset {
  id: string
  name: string
  asset_type: 'physical' | 'financial'
  category_id: string
  category?: Category
  purchase_price: number
  current_value: number
  currency: string
  purchase_date: string | null
  status: AssetStatus
  usage_frequency: UsageFrequency | null
  expected_lifespan_days: number | null
  daily_cost?: number
  return_rate?: number
  tags?: Tag[]
  notes?: string
  created_at: string
  updated_at: string
}

type AssetStatus = 'in_use' | 'idle' | 'sold' | 'retired'
type UsageFrequency = 'daily' | 'weekly' | 'monthly' | 'rarely' | 'idle'
```

### API 模块组织

```typescript
// src/api/asset.ts
export function getAssets(params?: AssetQueryParams) {
  return http.get<AssetListResponse>('/assets', { params })
}

export function getAsset(id: string) {
  return http.get<Asset>(`/assets/${id}`)
}

export function createAsset(data: CreateAssetRequest) {
  return http.post<Asset>('/assets', data)
}

export function updateAsset(id: string, data: UpdateAssetRequest) {
  return http.put<Asset>(`/assets/${id}`, data)
}

export function deleteAsset(id: string) {
  return http.delete(`/assets/${id}`)
}
```

---

## 国际化

### 语言文件 (`i18n/locales/`)

```
i18n/
├── locales/
│   ├── zh-CN.ts    # 简体中文
│   └── en-US.ts    # 英文
└── index.ts
```

### 使用方式

```vue
<template>
  <h1>{{ $t('asset.title') }}</h1>
  <p>{{ $t('asset.status.in_use') }}</p>
</template>
```

```typescript
// 切换语言
import { useI18n } from 'vue-i18n'
const { locale } = useI18n()
locale.value = 'en-US'
```

---

## 样式约定

### CSS 变量

```css
/* 使用 Vant 主题变量 */
:root {
  --van-primary-color: #1989fa;
  --van-success-color: #07c160;
  --van-warning-color: #ff976a;
  --van-danger-color: #ee0a24;
}

/* 自定义变量 */
:root {
  --app-background: #f7f8fa;
  --app-text-color: #323233;
  --app-border-color: #ebedf0;
}
```

### 响应式断点

```css
/* 移动优先 */
.container {
  padding: 16px;
}

/* 平板 */
@media (min-width: 768px) {
  .container {
    padding: 24px;
  }
}
```