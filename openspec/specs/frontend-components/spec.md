# frontend-components Specification

## Purpose
TBD - created by archiving change init-architecture-doc. Update Purpose after archive.
## Requirements
### Requirement: 前端文档必须包含页面路由映射

文档 SHALL 列出所有页面路由及其对应的组件，说明路由参数和导航方式。

#### Scenario: 开发者查找页面组件

- **WHEN** 开发者需要修改某个页面
- **THEN** 可以通过路由找到对应的组件文件

### Requirement: 前端文档必须说明核心组件职责

文档 SHALL 列出核心组件（如 AssetForm、CategoryGrid、UsageFreqSelector）的职责和 Props。

#### Scenario: 开发者复用组件

- **WHEN** 开发者需要使用某个组件
- **THEN** 可以了解组件的接口和使用方式

### Requirement: 前端文档必须说明 Store 结构

文档 SHALL 列出 Pinia Store 的结构，包括 state、actions 和使用场景。

#### Scenario: 开发者理解状态管理

- **WHEN** 开发者需要访问或修改全局状态
- **THEN** 可以找到对应的 Store 和方法

### Requirement: 前端文档必须说明 API 调用约定

文档 SHALL 说明前端如何调用后端 API，包括 axios 配置、错误处理、响应拦截等。

#### Scenario: 开发者实现 API 调用

- **WHEN** 开发者需要新增 API 调用
- **THEN** 可以遵循文档中的约定和模式

