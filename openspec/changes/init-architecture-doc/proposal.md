## Why

Numina 项目已完成核心功能开发，但缺乏系统性文档沉淀。为避免架构和代码腐化，需要建立完整的项目知识库，确保未来的开发工作有清晰的上下文和规范指引。

## What Changes

- 新增项目架构文档，定义整体技术架构和模块划分
- 新增数据模型文档，说明核心实体关系和字段定义
- 新增 API 规范文档，定义端点列表和接口约定
- 新增前端组件索引，说明页面路由和组件职责
- 新增编码规范文档，定义代码风格和命名约定
- 新增 Git 工作流文档，定义分支策略和提交规范

## Capabilities

### New Capabilities

- `architecture`: 项目整体架构设计，包括技术选型、模块划分、数据流向
- `data-models`: 核心数据模型定义，包括实体关系、字段说明、枚举值
- `api-spec`: API 接口规范，包括端点列表、认证方式、请求响应格式
- `frontend-components`: 前端组件索引，包括页面路由、组件职责、Store 结构
- `coding-standards`: 编码规范，包括前端 Vue3 风格、后端 FastAPI 模式
- `git-workflow`: Git 工作流，包括分支策略、Commit 格式、PR 流程

### Modified Capabilities

无

## Impact

- 影响文档目录结构（docs/）
- 为 Claude Code 提供项目上下文
- 不影响现有代码功能
- 为未来开发提供规范指引