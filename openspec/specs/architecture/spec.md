# architecture Specification

## Purpose
TBD - created by archiving change init-architecture-doc. Update Purpose after archive.
## Requirements
### Requirement: 架构文档必须包含技术栈说明

文档 SHALL 明确定义项目的技术栈，包括前端、后端、数据库和部署方案。

#### Scenario: 开发者查阅技术栈

- **WHEN** 开发者打开架构文档
- **THEN** 可以看到完整的技术栈列表和版本要求

### Requirement: 架构文档必须包含模块划分

文档 SHALL 使用图表展示系统的模块划分，包括认证、资产、负债、心愿、家庭、仪表盘等核心模块。

#### Scenario: 开发者理解模块边界

- **WHEN** 开发者查看架构图
- **THEN** 可以清楚识别各模块的职责和边界

### Requirement: 架构文档必须包含数据流向

文档 SHALL 使用流程图展示核心业务的数据流向，如资产录入、资产更新、统计计算等。

#### Scenario: 开发者理解数据流转

- **WHEN** 开发者查看数据流图
- **THEN** 可以理解从前端请求到后端处理再到数据库存储的完整流程

### Requirement: 架构文档必须说明技术选型理由

文档 SHALL 解释关键技术选型的理由，如为什么选择 FastAPI、Vue 3、ECharts 等。

#### Scenario: 新成员理解技术决策

- **WHEN** 新团队成员阅读架构文档
- **THEN** 可以理解每项技术选型的背景和考量

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

### Requirement: 架构必须包含缓存层模块

系统 SHALL 在 `backend/app/services/cache/` 目录下定义缓存层，包含以下文件：
- `base.py` - CacheBackend 抽象接口
- `memory.py` - MemoryCacheBackend 实现
- `redis.py` - RedisCacheBackend 占位
- `factory.py` - 缓存工厂

#### Scenario: 缓存层模块结构

- **WHEN** 开发者查看缓存层代码
- **THEN** 可以看到清晰的接口定义和实现分离

### Requirement: 架构必须包含中间件层模块

系统 SHALL 在 `backend/app/middleware/` 目录下定义中间件层，包含 `rate_limit.py`。

#### Scenario: 中间件层模块结构

- **WHEN** 开发者查看中间件层代码
- **THEN** 可以看到 RateLimitMiddleware 实现

### Requirement: 架构必须包含安全服务模块

系统 SHALL 在 `backend/app/services/` 目录下添加以下安全相关文件：
- `file_validation.py` - 文件上传验证
- `security_log.py` - 安全日志服务

#### Scenario: 安全服务模块结构

- **WHEN** 开发者查看安全服务代码
- **THEN** 可以看到文件验证和安全日志的实现

### Requirement: 架构必须支持三层扩展

系统 SHALL 保持现有三层架构（routers → services → models），并扩展 services 层包含缓存、安全等基础设施。

#### Scenario: 新增安全功能遵循分层

- **WHEN** 开发者新增安全功能
- **THEN** 遵循 routers → services → models 分层，services 层包含基础设施模块

