# git-workflow Specification

## Purpose
TBD - created by archiving change init-architecture-doc. Update Purpose after archive.
## Requirements
### Requirement: Git 工作流必须定义分支策略

文档 SHALL 定义分支命名和用途，包括 main、feature/*、fix/* 等分支的使用场景。

#### Scenario: 开发者创建新功能分支

- **WHEN** 开发者开始新功能开发
- **THEN** 可以按照规范创建正确命名的分支

### Requirement: Git 工作流必须定义 Commit 格式

文档 SHALL 定义 Commit message 格式，包括类型前缀、描述格式等。

#### Scenario: 开发者提交代码

- **WHEN** 开发者完成代码修改并提交
- **THEN** 可以使用正确的 commit 格式

### Requirement: Git 工作流必须定义 PR 流程

文档 SHALL 定义 Pull Request 的创建、审查、合并流程，包括必要信息填写和审查要点。

#### Scenario: 开发者创建 PR

- **WHEN** 开发者完成功能开发
- **THEN** 可以按照流程创建完整的 PR

### Requirement: Git 工作流必须定义代码审查要求

文档 SHALL 说明代码审查的重点，包括功能正确性、代码风格、测试覆盖等。

#### Scenario: Reviewer 审查 PR

- **WHEN** Reviewer 审查 PR
- **THEN** 可以按照检查清单进行审查

