# Numina 编码规范

## 前端编码规范

### Vue 3 组件结构

使用 Composition API + `<script setup>` 语法：

```vue
<template>
  <div class="asset-form">
    <!-- 模板内容 -->
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import type { Asset } from '@/types'

// Props
const props = defineProps<{
  assetId?: string
  isEdit?: boolean
}>()

// Emits
const emit = defineEmits<{
  saved: [asset: Asset]
  cancelled: []
}>()

// 响应式状态
const loading = ref(false)
const formData = ref<CreateAssetRequest>({
  name: '',
  // ...
})

// 计算属性
const isSubmitDisabled = computed(() => {
  return !formData.value.name || loading.value
})

// 方法
async function handleSubmit() {
  loading.value = true
  try {
    // 提交逻辑
    emit('saved', result)
  } finally {
    loading.value = false
  }
}

// 生命周期
onMounted(() => {
  if (props.assetId) {
    loadAsset(props.assetId)
  }
})
</script>

<style scoped>
.asset-form {
  padding: 16px;
}
</style>
```

### 命名约定

| 类型 | 约定 | 示例 |
|------|------|------|
| 组件文件 | PascalCase | `AssetForm.vue` |
| 组合式函数 | camelCase + use 前缀 | `useAsset.ts` |
| Store 文件 | camelCase | `asset.ts` |
| 类型文件 | camelCase | `types/index.ts` |
| Props | camelCase | `assetId` |
| Emits | camelCase | `onSaved` 或 `saved` |
| CSS 类 | kebab-case | `.asset-form` |

### TypeScript 使用

```typescript
// ✅ 推荐：明确类型定义
interface AssetFormData {
  name: string
  purchasePrice: number
  category?: string
}

const formData = ref<AssetFormData>({
  name: '',
  purchasePrice: 0
})

// ❌ 避免：使用 any
const data: any = {} // 不要这样

// ✅ 使用类型推断
const assets = computed(() => assetStore.assets)
```

### 组合式函数 (Composables)

```typescript
// src/composables/useAsset.ts
import { ref } from 'vue'
import * as assetApi from '@/api/asset'

export function useAsset() {
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function fetchAssets() {
    loading.value = true
    error.value = null
    try {
      const res = await assetApi.getAssets()
      return res.data
    } catch (e) {
      error.value = e.message
      throw e
    } finally {
      loading.value = false
    }
  }

  return {
    loading,
    error,
    fetchAssets
  }
}
```

### 注释要求

```vue
<script setup lang="ts">
/**
 * 资产录入表单组件
 * 支持新建和编辑模式
 */
import { ref } from 'vue'

// 计算日均成本（元/天）
// 公式：(购入价 + 累计维护费) / 持有天数
function calculateDailyCost() {
  // ...
}

// 处理表单提交
async function handleSubmit() {
  // ...
}
</script>
```

---

## 后端编码规范

### FastAPI 路由组织

```python
# app/routers/asset.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.schemas.asset import AssetCreate, AssetResponse
from app.services import asset as asset_service

router = APIRouter(prefix="/assets", tags=["assets"])

@router.get("", response_model=List[AssetResponse])
def list_assets(
    offset: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """获取资产列表"""
    return asset_service.get_user_assets(db, current_user.id, offset, limit)

@router.post("", response_model=AssetResponse, status_code=201)
def create_asset(
    data: AssetCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """创建资产"""
    return asset_service.create_asset(db, current_user.family_id, data)
```

### Pydantic Schema

```python
# app/schemas/asset.py
from pydantic import BaseModel, Field
from typing import Optional
from datetime import date
from enum import Enum

class AssetType(str, Enum):
    physical = "physical"
    financial = "financial"

class AssetBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    asset_type: AssetType
    category_id: str
    purchase_price: float = Field(..., ge=0)
    current_value: float = Field(..., ge=0)
    currency: str = Field(default="CNY", min_length=3, max_length=3)
    purchase_date: Optional[date] = None
    usage_frequency: Optional[str] = None
    expected_lifespan_days: Optional[int] = Field(None, gt=0)

class AssetCreate(AssetBase):
    """创建资产请求"""
    notes: Optional[str] = None

class AssetResponse(AssetBase):
    """资产响应"""
    id: str
    status: str
    daily_cost: Optional[float] = None
    return_rate: Optional[float] = None
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True
```

### Service 层

```python
# app/services/asset.py
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date

from app.models.asset import Asset
from app.schemas.asset import AssetCreate

def get_user_assets(
    db: Session,
    user_id: str,
    offset: int = 0,
    limit: int = 20
) -> List[Asset]:
    """获取用户资产列表"""
    return db.query(Asset).filter(
        Asset.user_id == user_id
    ).offset(offset).limit(limit).all()

def create_asset(
    db: Session,
    family_id: str,
    data: AssetCreate
) -> Asset:
    """创建资产"""
    asset = Asset(
        family_id=family_id,
        **data.model_dump()
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset

def compute_daily_cost(asset: Asset) -> Optional[float]:
    """
    计算日均成本
    
    Args:
        asset: 资产对象
        
    Returns:
        日均成本（元/天），如果无法计算返回 None
    """
    if not asset.purchase_date:
        return None
    
    days_held = (date.today() - asset.purchase_date).days
    if days_held <= 0:
        return None
    
    total_cost = asset.purchase_price
    if asset.annual_maintenance_cost:
        total_cost += asset.annual_maintenance_cost * days_held / 365
    
    return round(total_cost / days_held, 2)
```

### 命名约定

| 类型 | 约定 | 示例 |
|------|------|------|
| 文件名 | snake_case | `asset_service.py` |
| 类名 | PascalCase | `AssetService` |
| 函数名 | snake_case | `get_user_assets` |
| 变量名 | snake_case | `user_assets` |
| 常量 | UPPER_SNAKE_CASE | `MAX_PAGE_SIZE` |
| 枚举 | PascalCase | `AssetType` |

### 注释要求

```python
def compute_return_rate(asset: Asset) -> float:
    """
    计算资产收益率
    
    公式：(当前价值 - 购入价格) / 购入价格 × 100%
    
    Args:
        asset: 资产对象
        
    Returns:
        收益率百分比，如 10.5 表示 10.5%
        
    Raises:
        ValueError: 当购入价格为 0 时
    """
    if asset.purchase_price == 0:
        raise ValueError("购入价格不能为 0")
    
    return round(
        (asset.current_value - asset.purchase_price) / asset.purchase_price * 100,
        2
    )
```

---

## 通用规范

### 文件头注释

```python
"""
资产服务模块

提供资产的 CRUD 操作和计算功能
"""
```

```typescript
/**
 * 资产管理 Store
 * 
 * 负责资产列表、筛选、CRUD 操作
 */
```

### 导入顺序

```typescript
// 1. Vue 相关
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'

// 2. 第三方库
import axios from 'axios'

// 3. 项目内部
import { useAssetStore } from '@/stores/asset'
import type { Asset } from '@/types'
```

```python
# 1. 标准库
from datetime import date
from typing import List, Optional

# 2. 第三方库
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

# 3. 项目内部
from app.database import get_db
from app.models.asset import Asset
```

### 错误处理

```typescript
// 前端
try {
  await assetStore.createAsset(data)
} catch (error) {
  if (error.response?.status === 422) {
    showToast('数据验证失败')
  } else {
    showToast('操作失败，请重试')
  }
}
```

```python
# 后端
from fastapi import HTTPException

if not asset:
    raise HTTPException(status_code=404, detail="资产不存在")

if asset.family_id != current_user.family_id:
    raise HTTPException(status_code=403, detail="无权操作此资产")
```