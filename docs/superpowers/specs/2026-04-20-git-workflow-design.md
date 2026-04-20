# Git Workflow Design

**Date:** 2026-04-20
**Status:** Approved
**Scope:** Git 工作流程，分支策略，提交规范

---

## Problem

Git 工作流程缺乏规范，分支命名混乱、commit message 不统一、PR 流程不清晰。团队协作效率低，代码历史难以追溯，合并冲突频繁。

---

## Goals

1. 规范分支命名策略
2. 统一 commit message 格式
3. 定义清晰的 PR 流程
4. 提供代码审查检查清单

---

## Architecture

### 分支策略

采用简化的 GitHub Flow：

```
main (稳定版本)
  ├── feature/* (功能开发)
  ├── fix/* (问题修复)
  └── hotfix/* (紧急修复)
```

分支生命周期：
- 功能分支 → 开发 → 测试 → PR → 合并 → 删除
- 无长期存在的 develop 分支，main 为唯一稳定分支

---

## Implementation Details

### 分支命名规范

| 分支类型 | 命名格式 | 示例 |
|----------|----------|------|
| 功能开发 | `feature/<description>` | `feature/multi-currency` |
| 问题修复 | `fix/<issue-number>-<description>` | `fix/123-login-validation` |
| 紧急修复 | `hotfix/<description>` | `hotfix/security-patch` |

命名要求：
- 使用小写字母和连字符
- 描述简洁明确（不超过 50 字符）
- 避免使用特殊字符

### Commit Message 格式

采用约定式提交（Conventional Commits）：

```
<type>: <subject>

<body>

<footer>
```

**类型前缀**

| 类型 | 说明 | 示例 |
|------|------|------|
| feat | 新功能 | `feat: add wish management module` |
| fix | 修复问题 | `fix: resolve login rate limit bug` |
| docs | 文档更新 | `docs: update API specification` |
| refactor | 重构代码 | `refactor: extract cache layer` |
| test | 测试相关 | `test: add rate limit integration tests` |
| chore | 其他修改 | `chore: update dependencies` |

**Subject 要求**
- 使用中文（与项目 UI 语言一致）
- 不超过 50 字符
- 不以句号结尾
- 首字母大写

**Body 格式**
- 详细说明修改内容和原因
- 使用 `-` 列表项

**Footer（可选）**
- 关联 Issue：`Refs: #123`
- 关闭 Issue：`Closes: #123`

**完整示例**

```
feat: 添加心愿管理模块

- 新增 Wish 数据模型
- 实现 CRUD API 端点
- 添加心愿列表页面和详情页面
- 支持心愿实现为资产

Refs: #45
```

### PR 流程

**创建 PR**

1. 确保功能分支已推送到远程
2. 在 GitHub 创建 Pull Request
3. 填写 PR 描述模板：

```markdown
## 功能说明
简要描述本次修改的功能或解决的问题

## 修改内容
- 新增文件：xxx
- 修改文件：xxx
- 删除文件：xxx

## 测试情况
- 单元测试：新增 X 个测试
- E2E 测试：覆盖 X 个场景
- 手动验证：xxx

## 相关 Issue
Refs: #xxx
```

**代码审查**

Reviewer 检查清单：
- [ ] 功能正确性：核心逻辑是否符合需求
- [ ] 代码风格：遵循编码规范
- [ ] 测试覆盖：关键路径有测试
- [ ] 文档更新：API 变更有文档
- [ ] 安全考虑：无明显安全隐患

**合并要求**
- 至少 1 个 Reviewer 批准
- 所有 CI 检查通过
- 无未解决的冲突
- Squash merge（保持历史整洁）

### 工作流示例

**功能开发完整流程**

```bash
# 1. 创建功能分支
git checkout -b feature/wish-module

# 2. 开发并提交
git add .
git commit -m "feat: 添加心愿数据模型"

# 3. 推送到远程
git push origin feature/wish-module

# 4. 在 GitHub 创建 PR

# 5. 合并后删除本地分支
git checkout main
git pull
git branch -d feature/wish-module
```

---

## Code Pointers

| 文件 | 路径 | 说明 |
|------|------|------|
| PR 模板 | `.github/PULL_REQUEST_TEMPLATE.md` | PR 描述模板 |
| Issue 模板 | `.github/ISSUE_TEMPLATE/` | Issue 分类模板 |
| CI 配置 | `.github/workflows/` | 自动检查配置 |

---

## Related Specs

- **编码规范设计**：`2026-04-20-coding-standards-design.md` — 代码风格要求
- **测试设计**：`2026-04-20-testing-design.md` — 测试覆盖要求