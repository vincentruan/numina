# api-spec Specification

## Purpose
TBD - created by archiving change init-architecture-doc. Update Purpose after archive.
## Requirements
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

### Requirement: API 必须提供心愿模块端点

系统 SHALL 提供以下心愿相关端点：

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | /wishes | 获取心愿列表 |
| POST | /wishes | 创建心愿 |
| GET | /wishes/{id} | 获取心愿详情 |
| PUT | /wishes/{id} | 更新心愿 |
| DELETE | /wishes/{id} | 删除心愿 |
| POST | /wishes/{id}/realize | 实现心愿为资产 |

#### Scenario: 实现心愿

- **WHEN** 用户调用 POST /wishes/{id}/realize
- **THEN** 系统创建资产记录，心愿状态变为 realized

### Requirement: API 必须提供活动日志端点

系统 SHALL 提供以下活动日志端点：

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | /activities | 获取活动日志列表 |

#### Scenario: 查询活动日志

- **WHEN** 用户调用 GET /activities
- **THEN** 返回按时间倒序的操作日志列表

### Requirement: API 必须提供数据导出端点

系统 SHALL 提供以下导出端点：

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | /export/assets/csv | 导出资产 CSV |
| GET | /export/liabilities/csv | 导出负债 CSV |
| GET | /export/all/json | 导出全量 JSON |

#### Scenario: 导出资产 CSV

- **WHEN** 用户调用 GET /export/assets/csv
- **THEN** 返回 CSV 文件下载流

### Requirement: API 必须提供数据导入端点

系统 SHALL 提供以下导入端点：

| 方法 | 端点 | 说明 |
|------|------|------|
| POST | /import/assets/csv | 导入资产 CSV |

#### Scenario: 导入资产 CSV

- **WHEN** 用户上传 CSV 文件
- **THEN** 系统校验并创建资产记录

### Requirement: API 必须提供文件上传端点

系统 SHALL 提供图片上传端点：

| 方法 | 端点 | 说明 |
|------|------|------|
| POST | /upload/image | 上传图片 |

#### Scenario: 上传资产图片

- **WHEN** 用户上传图片
- **THEN** 返回图片 URL

### Requirement: API 必须提供多币种相关端点

系统 SHALL 提供以下币种相关端点：

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | /currencies | 获取币种列表 |
| GET | /exchange-rates | 获取汇率列表 |

#### Scenario: 查询币种

- **WHEN** 用户调用 GET /currencies
- **THEN** 返回支持的币种列表

### Requirement: API 必须提供仪表盘扩展端点

系统 SHALL 提供以下仪表盘端点：

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | /dashboard/states-summary | 获取状态汇总 |
| GET | /dashboard/home-assets | 获取首页资产 |
| GET | /dashboard/expiring-soon | 获取即将到期资产 |

#### Scenario: 查询即将到期资产

- **WHEN** 用户调用 GET /dashboard/expiring-soon?days_threshold=90
- **THEN** 返回 90 天内到期的资产列表

### Requirement: 登录响应时间必须恒定

系统 SHALL 确保登录失败时响应时间一致，无论用户是否存在。当用户不存在时，执行 dummy bcrypt 验证以消耗相同时间。

#### Scenario: 用户不存在时响应时间

- **WHEN** 登录用户名不存在
- **THEN** 系统执行 dummy bcrypt 验证，响应时间约 200-300ms

#### Scenario: 用户存在密码错误时响应时间

- **WHEN** 登录用户名存在但密码错误
- **THEN** 系统执行 bcrypt 验证，响应时间约 200-300ms

#### Scenario: 响应时间一致性验证

- **WHEN** 多次测试用户不存在和密码错误两种情况
- **THEN** 平均响应时间差异小于 20%

### Requirement: bcrypt rounds 必须可配置

系统 SHALL 在 `config.py` 中定义 `BCRYPT_ROUNDS` 配置项（默认 12）。该配置项适用于所有密码哈希场景，包括：
- 用户注册时的密码哈希
- 用户修改密码时的密码哈希
- 时间攻击防护中的 dummy hash

#### Scenario: 配置 bcrypt rounds

- **WHEN** 配置 `BCRYPT_ROUNDS=14`
- **THEN** 所有密码哈希操作使用 14 rounds

#### Scenario: rounds 影响哈希时间

- **WHEN** 使用 higher rounds（如 14）
- **THEN** 哈希时间增加（约 250ms），安全强度提升

#### Scenario: 时间攻击防护使用配置的 rounds

- **WHEN** 登录用户名不存在时执行 dummy hash
- **THEN** dummy hash 使用 `settings.BCRYPT_ROUNDS` 配置，确保与正常验证时间一致

### Requirement: 密码哈希必须使用配置的 rounds

系统 SHALL 在 `hash_password()` 中使用 `settings.BCRYPT_ROUNDS` 生成 salt。

#### Scenario: 生成密码哈希

- **WHEN** 调用 `hash_password("password")`
- **THEN** bcrypt 哈希格式为 `$2b$XX$...`，其中 XX 为配置的 rounds

### Requirement: 登录失败必须不区分错误原因

系统 SHALL 对所有登录失败返回相同的错误信息 "用户名或密码错误"，不提示具体原因。

#### Scenario: 用户不存在错误信息

- **WHEN** 登录用户名不存在
- **THEN** 返回 401 状态码，提示 "用户名或密码错误"

#### Scenario: 密码错误信息

- **WHEN** 登录密码错误
- **THEN** 返回 401 状态码，提示 "用户名或密码错误"

