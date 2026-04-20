# Coding Standards Design

**Date:** 2026-04-20
**Status:** Approved
**Scope:** 编码规范，确保代码质量和一致性

---

## Problem

代码风格不一致，缺乏统一编码规范文档。开发者各自遵循不同习惯，导致代码可读性差、维护成本高，新成员难以快速融入项目。

---

## Goals

1. 确保代码风格一致性
2. 提高代码可读性和可维护性
3. 降低新成员上手成本
4. 规范注释和命名约定

---

## Architecture

### 双栈编码规范

项目包含两个独立技术栈，各自有独立的编码规范：

**前端栈**：Vue 3 + TypeScript + Vite + Vant 4
**后端栈**：FastAPI + SQLAlchemy + Python 3.11

规范文档位于 `backend/CLAUDE.md` 和 `frontend/CLAUDE.md`，根 `CLAUDE.md` 提供全局约定。

---

## Implementation Details

### 前端编码规范

**Vue 3 Composition API**

```vue
<!-- 使用 <script setup lang="ts"> -->
<script setup lang="ts">
import { ref, computed } from 'vue'
import type { Asset } from '@/types'

const assets = ref<Asset[]>([])

const totalValue = computed(() => 
  assets.value.reduce((sum, a) => sum + a.current_value, 0)
)
</script>
```

**TypeScript 规范**

```typescript
// 启用严格模式（tsconfig.json: strict: true）
// 使用接口定义类型，避免 type alias
interface Asset {
  id: string
  name: string
  current_value: number
}

// 避免 as any、@ts-ignore、@ts-expect-error
// 使用类型收窄替代类型断言
function getAssetValue(asset: Asset | undefined): number {
  return asset?.current_value ?? 0
}
```

**命名约定**

| 元素 | 命名规则 | 示例 |
|------|----------|------|
| 页面组件 | PascalCase + Page | `AssetListPage.vue` |
| 业务组件 | PascalCase | `AssetCard.vue` |
| 通用组件 | PascalCase | `MoneyDisplay.vue` |
| 组合式函数 | camelCase + use | `useExchangeRate.ts` |
| Pinia Store | camelCase + use + Store | `useAssetStore.ts` |
| 变量/函数 | camelCase | `assets`, `fetchAssets` |
| 接口/类型 | PascalCase | `Asset`, `AssetResponse` |
| 文件名（模块） | camelCase | `format.ts`, `storage.ts` |

**导入顺序**

```typescript
// 1. 第三方库
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'

// 2. 本地别名导入（使用 @/）
import { useAssetStore } from '@/stores'
import type { Asset } from '@/types'
```

### 后端编码规范

**FastAPI + SQLAlchemy**

```python
# Mapped 类型注解
from sqlalchemy.orm import Mapped, mapped_column

class Asset(Base):
    __tablename__ = "assets"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    current_value: Mapped[float] = mapped_column(Float, nullable=False)
```

**路由组织**

```python
from fastapi import APIRouter, Depends

router = APIRouter(prefix="/assets", tags=["assets"])

@router.get("/")
def list_assets(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # 调用服务层，不在路由中实现业务逻辑
    return AssetService.list_assets(user.family_id, db)
```

**Python 规范**

```python
# 导入顺序：stdlib → third-party → local（空行分隔）
import os
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.asset import Asset
from app.services.asset_service import AssetService

# 文件/函数：snake_case
def calculate_daily_cost(asset: Asset) -> float:
    ...

# 类：PascalCase
class AssetService:
    ...

# 私有函数：前缀下划线
def _to_response(asset: Asset) -> AssetResponse:
    ...

# 类型注解：使用 3.10+ 语法
def get_asset(asset_id: str) -> Asset | None:
    ...
```

### 代码注释要求

**必须注释的场景**

```python
# 复杂业务逻辑
def calculate_return_rate(asset: Asset) -> float:
    """
    计算投资收益率。
    
    公式：(current_value - purchase_price) / purchase_price * 100
    仅适用于金融资产，实物资产返回 None。
    """
    if asset.asset_type != "financial":
        return None
    return (asset.current_value - asset.purchase_price) / asset.purchase_price * 100

# 非显而易见的算法决策
# 使用 dummy bcrypt 验证以防止用户名枚举攻击
bcrypt.checkpw("dummy_password", bcrypt.hashpw("dummy", bcrypt.gensalt()))
```

**避免冗余注释**

```python
# 不好的示例
assets = []  # 创建空列表
total = 0    # 初始化为 0

# 好的示例（代码自解释）
assets: list[Asset] = []
total: float = 0.0
```

---

## Code Pointers

| 规范文档 | 文件路径 |
|----------|----------|
| 全局约定 | `CLAUDE.md` |
| 前端规范 | `frontend/CLAUDE.md` |
| 后端规范 | `backend/CLAUDE.md` |
| ESLint 配置 | `frontend/eslint.config.js` |
| Prettier 配置 | `frontend/.prettierrc` |
| Ruff 配置 | `backend/pyproject.toml` |

---

## Related Specs

- **模块工具设计**：`2026-04-11-module-tooling-design.md` — linter/formatter 配置
- **Git 工作流设计**：`2026-04-20-git-workflow-design.md` — commit message 格式