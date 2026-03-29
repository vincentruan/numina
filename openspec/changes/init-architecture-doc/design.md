## Context

Numina 是一个家庭资产可视化管理系统的全栈项目：
- **前端**：Vue 3 + Vant UI + Pinia + Vue Router + ECharts
- **后端**：FastAPI + SQLAlchemy + MySQL/PostgreSQL
- **部署**：Docker Compose + Nginx

当前状态：核心功能已实现，包括资产管理、负债管理、心愿单、家庭管理、仪表盘统计等。但缺乏系统性文档，导致：
1. 新开发者上手成本高
2. Claude Code 缺乏项目上下文
3. 代码风格可能逐渐分化

## Goals / Non-Goals

**Goals:**
- 建立完整的项目文档体系
- 定义清晰的架构和模块边界
- 为 AI 辅助开发提供上下文
- 建立编码和协作规范

**Non-Goals:**
- 不涉及代码重构
- 不改变现有 API 竾名
- 不引入新的技术栈

## Decisions

### 1. 文档组织方式

**决策**：所有文档放在 `docs/` 目录下，使用 Markdown 格式。

**理由**：
- Markdown 可直接在 GitHub 渲染
- 与现有 docs/ 目录结构一致
- 便于 Claude Code 读取

**替代方案**：
- 使用 OpenAPI/Swagger → 过于重量级，适合 API 文档
- 使用 Wiki → 与代码仓库分离，维护成本高

### 2. 架构图格式

**决策**：使用 Mermaid 格式绘制架构图。

**理由**：
- 可在 Markdown 中直接渲染
- 版本可控
- 与 GitHub 原生支持

### 3. 数据模型文档

**决策**：手动维护 ER 图和字段说明，不依赖代码自动生成。

**理由**：
- 更清晰的业务语义说明
- 可包含设计决策和约束
- 自动生成工具（如 SQLAlchemy 插件）通常输出过于技术化

### 4. 文档更新机制

**决策**：在 PR 中要求更新相关文档，由 code review 检查。

**理由**：
- 文档与代码同步更新
- 避免"文档过时"问题
- 依赖开发者自觉 + Reviewer 检查

## Risks / Trade-offs

| 风险 | 缓解措施 |
|------|----------|
| 文档可能过时 | 在 PR checklist 中要求检查文档 |
| 文档维护成本 | 保持文档精简，只记录关键信息 |
| Mermaid 兼容性 | 使用 GitHub 原生支持的语法 |