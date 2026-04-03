---
date: 2026-04-02
topic: openspec-to-ce-migration
---

# OpenSpec to CE Compound Migration

## Problem Frame

Numina 项目使用 OpenSpec 进行 spec coding，现有 17 个已归档的 spec 文档。团队决定迁移到 compound-engineering (CE) 工作流，需要将 OpenSpec spec 转换为 CE compound 格式，以便：
- 利用 CE 的 knowledge track 存储最佳实践
- 通过 `learnings-researcher` agent 自动发现相关文档
- 统一知识管理流程

## Requirements

**迁移策略**
- R1. 将 OpenSpec spec 转换为 CE compound knowledge track 格式
- R2. 按业务领域合并相关 spec，减少文档碎片化
- R3. 保留原始 spec 的语义完整性，转换但不丢失信息

**转换规则**
- R4. Requirement 标题映射为 Guidance 子标题
- R5. SHALL 描述转换为指导性陈述（去掉 SHALL）
- R6. Scenario WHEN/THEN 合并为 Examples 描述性列表
- R7. 多个 Scenario 合并到同一 Requirement 下的 Examples

**输出格式**
- R8. 使用 CE knowledge track 模板（`problem_type: best_practice`）
- R9. 文档路径：`docs/solutions/best-practices/`
- R10. YAML frontmatter 包含：module, problem_type, component, severity, tags

## Success Criteria

- 安全领域的 4 个 spec 成功转换为 2 个 CE compound 文档
- 文档可通过 `learnings-researcher` agent 搜索发现
- 原始 spec 的所有 Requirements 和 Scenarios 被保留
- AGENTS.md 或 CLAUDE.md 更新以指向新的知识库位置

## Scope Boundaries

- 仅迁移安全领域作为 PoC
- 不删除原始 openspec 目录（保留作为参考）
- 不修改 CE schema 或创建新的 problem_type

## Key Decisions

- **合并粒度**：分为 2 个文档（防护类 + 审计类）
  - 文档 1：`security-protection.md`（rate-limiting + cache-layer）
  - 文档 2：`security-audit.md`（security-logging + file-upload-security）
- **格式转换**：将 Gherkin WHEN/THEN 转换为描述性 Examples
- **Why**: 减少 CE knowledge track 不支持的 Gherkin 语法，同时保持语义

## Dependencies / Assumptions

- CE compound knowledge track 已支持 `best_practice` problem_type
- `docs/solutions/best-practices/` 目录结构符合 CE 规范
- 用户已安装 compound-engineering-plugin

## Outstanding Questions

### Resolve Before Planning
- 无

### Deferred to Planning
- [Affects R10][Technical] 是否需要扩展 CE component 枚举以包含 Numina 特定模块？

## Next Steps

→ `/ce:plan` for structured implementation planning