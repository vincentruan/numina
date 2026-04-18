---
date: 2026-04-18
topic: system-categories-constants
---

# Requirements: 系统分类编译时常量

## Problem Frame
21个系统分类（13个实物+8个金融）在启动时seed一次，永不变更。但每次资产表单加载都调用 `/api/v1/categories` 查询数据库，浪费资源。

## Requirements

**后端常量定义**
- R1. 创建 `backend/app/constants/categories.py`，包含 `SYSTEM_CATEGORIES` 列表（21项）
- R2. 结构与现有 seed 数据一致：id、name、icon、color、asset_type、sort_order、is_system
- R3. 使用确定性ID（如 `sys-cat-001` 到 `sys-cat-021`），与seed逻辑生成的ID一致

**前端常量定义**
- R4. 创建 `frontend/src/constants/categories.ts`，包含 `SYSTEM_CATEGORIES` 数组
- R5. TypeScript类型匹配现有 `Category` interface
- R6. 导出按 asset_type 分组的辅助函数：`getSystemCategoriesByType(type)`

**API兼容**
- R7. 后端 `/categories` 端点保持不变（供自定义分类查询）
- R8. 前端 AssetFormPage 优先使用常量，减少API调用

## Success Criteria
- 前端加载资产表单时，系统分类零API调用
- 后端服务函数可直接引用常量，无需查询
- 自定义分类仍通过API正常工作

## Scope Boundaries
- 不移除 `/categories` 端点
- 不修改 seed 逻辑（保持数据库持久化）
- 不影响自定义分类的CRUD

## Key Decisions
- 使用确定性ID（`sys-cat-{sort_order:03d}`）：保证常量与DB记录ID一致
- 双端常量：后端service层和前端表单都可使用

## Implementation Order
1. 后端 `constants/categories.py`
2. 前端 `constants/categories.ts`
3. 前端 `AssetFormPage.vue` 改用常量

## Next Steps
→ `/ce:plan` 或直接实现（Lightweight scope）