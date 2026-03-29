## ADDED Requirements

### Requirement: 数据模型文档必须包含实体关系图

文档 SHALL 使用 ER 图展示核心实体之间的关系，包括 User、Family、Asset、Category、Liability、Wish 等。

#### Scenario: 开发者理解实体关系

- **WHEN** 开发者查看数据模型文档
- **THEN** 可以清楚识别各实体之间的关系（一对多、多对多等）

### Requirement: 数据模型文档必须包含核心字段说明

文档 SHALL 列出每个核心实体的字段定义，包括字段名、类型、约束、默认值等。

#### Scenario: 开发者查询字段定义

- **WHEN** 开发者需要了解某个实体的字段
- **THEN** 可以在文档中找到完整的字段列表和说明

### Requirement: 数据模型文档必须说明资产分类体系

文档 SHALL 详细说明 21 个资产分类，包括 13 个实物分类和 8 个金融分类。

#### Scenario: 开发者理解分类结构

- **WHEN** 开发者查看分类说明
- **THEN** 可以看到每个分类的名称、图标、asset_type 和说明

### Requirement: 数据模型文档必须说明计算字段

文档 SHALL 说明系统中的计算字段，如 daily_cost（日均成本）、return_rate（收益率）。

#### Scenario: 开发者理解计算逻辑

- **WHEN** 开发者查看计算字段说明
- **THEN** 可以理解计算公式和数据来源