# architecture MODIFIED Specification

## ADDED Requirements

### Requirement: 架构必须支持多数据库后端

系统 SHALL 支持 SQLite、MySQL、PostgreSQL 三种数据库，通过配置切换。

#### Scenario: 配置 MySQL 数据库

- **WHEN** 用户配置 DATABASE_URL=mysql://...
- **THEN** 系统使用 MySQL 作为数据库后端

### Requirement: 架构必须支持定时任务调度

系统 SHALL 使用 APScheduler 实现定时任务，支持汇率自动更新等周期性任务。

#### Scenario: 汇率定时更新

- **WHEN** 定时任务触发
- **THEN** 系统调用汇率 API 更新数据

### Requirement: 架构必须支持文件上传服务

系统 SHALL 提供文件上传功能，支持资产图片存储。

#### Scenario: 图片上传处理

- **WHEN** 用户上传图片
- **THEN** 系统存储到指定目录，返回访问 URL

### Requirement: 架构必须定义分层结构

系统 SHALL 采用三层架构：API 层（routers）→ 服务层（services）→ 数据层（models）。

#### Scenario: 新增业务逻辑

- **WHEN** 开发者新增功能
- **THEN** 遵循 routers → services → models 的分层结构

### Requirement: 架构必须定义错误处理机制

系统 SHALL 统一使用 `{"detail": "错误信息"}` 格式返回错误响应。

#### Scenario: 返回错误信息

- **WHEN** API 发生错误
- **THEN** 返回 HTTP 状态码和中文错误信息