## ADDED Requirements

### Requirement: API 文档必须包含端点列表

文档 SHALL 列出所有 API 端点，按模块分组（认证、资产、负债、心愿、家庭、仪表盘）。

#### Scenario: 开发者查询可用端点

- **WHEN** 开发者需要调用某个 API
- **THEN** 可以在文档中找到完整的端点列表

### Requirement: API 文档必须说明认证方式

文档 SHALL 明确说明 API 认证方式（JWT Bearer Token）和获取方法。

#### Scenario: 开发者理解认证流程

- **WHEN** 开发者需要调用需要认证的 API
- **THEN** 可以从文档中了解如何获取和使用 Token

### Requirement: API 文档必须定义请求响应格式

文档 SHALL 说明标准的请求和响应格式，包括成功响应和错误响应的结构。

#### Scenario: 开发者处理 API 响应

- **WHEN** 开发者调用 API 并收到响应
- **THEN** 可以根据文档解析响应结构

### Requirement: API 文档必须定义错误码

文档 SHALL 列出常见的 HTTP 状态码和业务错误码，说明其含义和处理方式。

#### Scenario: 开发者处理错误响应

- **WHEN** 开发者收到错误响应
- **THEN** 可以根据错误码确定问题原因