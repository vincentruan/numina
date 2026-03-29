## Context

基于深度审查发现的问题，需要系统性补全 OpenSpec 文档。当前代码已实现 90% 的功能，但 spec 只覆盖了 30%。核心问题是 spec 文件只是 archive 时自动生成的骨架，没有实际内容。

## Goals / Non-Goals

**Goals:**
- 补全 6 个缺失的 spec（wish-system, multi-currency, data-lifecycle, data-portability, observability, i18n）
- 完善 3 个现有 spec 的内容（data-models, api-spec, architecture）
- 所有 spec 填写 Purpose 字段

**Non-Goals:**
- 不修改现有代码
- 不改变 API 竾名
- 不引入新功能

## Decisions

### 1. Spec 组织方式

**决策**：每个 spec 文件聚焦单一能力域，包含 Purpose + Requirements + Scenarios。

**理由**：
- 便于独立查阅和维护
- 符合 OpenSpec 规范
- 便于后续增量更新

### 2. 内容来源

**决策**：从现有代码反向抽取 spec 内容，确保与实现一致。

**来源**：
- 数据模型：`backend/app/models/*.py`
- API 端点：`backend/app/routers/*.py`
- 前端组件：`frontend/src/pages/*.vue`, `frontend/src/components/*.vue`
- 业务逻辑：`backend/app/services/*.py`

### 3. 优先级排序

| 优先级 | Spec | 理由 |
|--------|------|------|
| P0 | wish-system | 核心功能，完全缺失 |
| P0 | multi-currency | 横切关注点，影响所有金额 |
| P1 | data-lifecycle | 核心业务逻辑 |
| P1 | data-portability | 用户高频需求 |
| P2 | observability | 运维支持 |
| P2 | i18n | 可选功能 |

## Risks / Trade-offs

| 风险 | 缓解措施 |
|------|----------|
| Spec 内容可能与代码不同步 | 从代码反向抽取，确保一致 |
| 内容量较大，可能遗漏 | 按模块逐一审查，使用 checklist |
| Purpose 字段描述不准确 | 参考现有文档和代码注释 |