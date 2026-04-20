# Wish System Design

**Date:** 2026-04-20
**Status:** Approved
**Scope:** 心愿单系统，支持用户记录购买意愿并转化为资产

---

## Problem

用户想要购买的物品往往缺乏规划，容易冲动消费。需要一个系统来记录购买意愿，并支持将心愿转化为实际资产，形成完整的消费闭环。

---

## Core Goal

心愿系统帮助用户规划消费计划，核心价值：
- 记录购买意愿，避免冲动消费
- 优先级排序，明确消费优先次序
- 心愿实现时自动创建资产，实现"愿望→资产"的闭环

---

## Design Decisions

### 状态设计

采用三状态模型：
- **pending**：规划中（默认状态）
- **realized**：已实现（转化为资产）
- **cancelled**：已取消

**理由**：简单的三状态足够表达心愿生命周期，避免过度复杂。

### 优先级设计

采用三级优先级：high、medium、low

**理由**：
- 三级优先级足够区分重要性，避免5级或7级的决策负担
- 按优先级排序显示，突出重要心愿

### 心愿实现机制

实现心愿时自动创建资产，而不是手动创建后再关联。

**理由**：
- 自动化减少用户操作步骤
- 确保心愿和资产的一致性
- 用户只需补充资产详细信息，系统自动关联

---

## Architecture

### 数据模型

```python
class Wish(Base):
    __tablename__ = "wishes"
    
    id: Mapped[str]        # 主键
    family_id: Mapped[str] # 家庭ID
    user_id: Mapped[str]   # 创建者ID
    name: Mapped[str]      # 心愿名称
    description: Mapped[str | None]  # 描述
    expected_price: Mapped[float]    # 期望价格
    priority: Mapped[str]  # high/medium/low
    status: Mapped[str]    # pending/realized/cancelled
    category_id: Mapped[str | None]  # 分类ID
    currency: Mapped[str]  # 币种
    realized_asset_id: Mapped[str | None]  # 实现后的资产ID
```

### API 端点

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | /wishes | 获取心愿列表（按优先级排序） |
| POST | /wishes | 创建心愿 |
| GET | /wishes/{id} | 获取心愿详情 |
| PUT | /wishes/{id} | 更新心愿 |
| DELETE | /wishes/{id} | 删除心愿 |
| POST | /wishes/{id}/realize | 实现心愿（创建资产） |

### 实现流程

```
用户点击"实现心愿"
→ 前端打开资产表单（预填心愿信息）
→ 用户补充资产详细字段
→ POST /wishes/{id}/realize
→ 后端创建资产 + 更新心愿状态 + 关联 asset_id
→ 前端跳转到资产详情页
```

---

## Implementation Details

### 后端实现

**路由层** (`backend/app/routers/wishes.py`):
```python
@router.post("/{wish_id}/realize", status_code=201)
def realize_wish(
    wish_id: str,
    asset_data: AssetCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # 1. 验证心愿存在且状态为 pending
    # 2. 创建资产（使用 asset_data + 心愿基础信息）
    # 3. 更新心愿：status=realized, realized_asset_id=新资产ID
    # 4. 返回资产详情
```

**服务层** (`backend/app/services/wish.py`):
- `get_wishes_by_priority()`：按优先级排序查询
- `realize_wish()`：实现心愿的完整业务逻辑

### 前端实现

**心愿列表页** (`frontend/src/pages/WishListPage.vue`):
- 显示心愿卡片（名称、价格、优先级、状态）
- 优先级排序：high（红色） > medium（黄色） > low（灰色）
- 操作按钮：实现、编辑、删除

**心愿表单页** (`frontend/src/pages/WishFormPage.vue`):
- 基本信息：名称、描述、期望价格
- 优先级选择：high/medium/low
- 分类选择（可选）
- 币种选择（使用 CurrencySelector）

**心愿详情页** (`frontend/src/pages/WishDetailPage.vue`):
- 显示心愿完整信息
- 已实现心愿显示资产链接
- 实现按钮（pending 状态）

---

## Code Pointers

| 功能 | 入口文件 | 关键函数/组件 |
|------|----------|--------------|
| 心愿 CRUD API | `backend/app/routers/wishes.py` | `create_wish`, `list_wishes`, `realize_wish` |
| 心愿数据模型 | `backend/app/models/wish.py` | `class Wish` |
| 心愿服务逻辑 | `backend/app/services/wish.py` | `realize_wish_service` |
| 心愿列表页 | `frontend/src/pages/WishListPage.vue` | `WishCard` 组件 |
| 心愿表单页 | `frontend/src/pages/WishFormPage.vue` | 表单提交逻辑 |
| 心愿详情页 | `frontend/src/pages/WishDetailPage.vue` | 实现按钮处理 |

---

## Verification

### 实现验证

创建心愿 → 设置优先级 → 点击实现 → 填写资产信息 → 确认创建：
- 心愿状态变为 `realized`
- 新资产创建成功
- 心愿详情页显示资产链接
- 资产详情页可追溯到心愿来源

### 优先级验证

创建三个心愿（high、medium、low）：
- 列表按优先级降序排列
- 高优先级心愿突出显示（颜色标识）

---

## Related Specs

- **数据模型设计**：`2026-04-20-data-models-design.md` — Wish 实体定义
- **API 规格设计**：`2026-04-20-api-spec-design.md` — /wishes 端点
- **前端组件设计**：`2026-04-20-frontend-components-design.md` — 心愿页面组件