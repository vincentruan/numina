# api-spec MODIFIED Specification

## ADDED Requirements

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