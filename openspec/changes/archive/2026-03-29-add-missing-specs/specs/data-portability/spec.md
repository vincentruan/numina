# data-portability Specification

## Purpose

数据导入导出功能允许用户以标准格式备份和迁移数据，支持 CSV 格式的资产/负债导出，以及 JSON 格式的全量数据备份。

## ADDED Requirements

### Requirement: 系统必须支持 CSV 格式导出

系统 SHALL 提供资产和负债的 CSV 格式导出功能。

#### Scenario: 导出资产 CSV

- **WHEN** 用户点击"导出资产 CSV"
- **THEN** 系统生成包含所有资产字段的 CSV 文件并下载

#### Scenario: CSV 包含关联数据

- **WHEN** 导出资产 CSV
- **THEN** CSV 包含分类名称、标签名称等关联字段

### Requirement: 系统必须支持 JSON 全量导出

系统 SHALL 提供全量数据的 JSON 格式导出，包含 export_version 字段用于版本管理。

#### Scenario: 全量数据备份

- **WHEN** 用户点击"导出全部数据"
- **THEN** 系统生成包含资产、负债、心愿、分类、标签的 JSON 文件

### Requirement: 系统必须支持 CSV 导入

系统 SHALL 提供 CSV 导入功能，支持校验和错误提示。

#### Scenario: 导入资产 CSV

- **WHEN** 用户上传 CSV 文件
- **THEN** 系统校验字段格式，创建资产记录

#### Scenario: 导入错误处理

- **WHEN** CSV 包含无效数据
- **THEN** 系统返回具体行号和错误信息

### Requirement: 系统必须支持图片上传

系统 SHALL 提供图片上传功能，用于资产图片存储。

#### Scenario: 上传资产图片

- **WHEN** 用户在资产表单中上传图片
- **THEN** 系统存储图片并返回 URL

## API Endpoints

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | /export/assets/csv | 导出资产 CSV |
| GET | /export/liabilities/csv | 导出负债 CSV |
| GET | /export/all/json | 导出全量 JSON |
| POST | /import/assets/csv | 导入资产 CSV |
| POST | /upload/image | 上传图片 |

## CSV Format

### 资产 CSV 字段

```
name,category,asset_type,purchase_price,current_value,currency,purchase_date,status,usage_frequency,expected_lifespan_years,annual_maintenance_cost,location,notes,tags
```

### 负债 CSV 字段

```
name,category,original_amount,remaining_amount,currency,interest_rate,start_date,end_date,institution,notes,is_active
```

## JSON Export Format

```json
{
  "export_version": "1.0",
  "exported_at": "2026-03-29T00:00:00Z",
  "family": { ... },
  "assets": [ ... ],
  "liabilities": [ ... ],
  "wishes": [ ... ],
  "categories": [ ... ],
  "tags": [ ... ]
}
```

## Frontend

- 设置页面提供导出入口
- 导入页面提供文件上传和校验反馈