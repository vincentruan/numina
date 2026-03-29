# data-portability Specification

## Purpose
TBD - created by archiving change add-missing-specs. Update Purpose after archive.
## Requirements
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

