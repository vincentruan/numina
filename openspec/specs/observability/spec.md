# observability Specification

## Purpose
TBD - created by archiving change add-missing-specs. Update Purpose after archive.
## Requirements
### Requirement: 系统必须记录操作日志

系统 SHALL 为关键操作创建 Activity 日志记录。

#### Scenario: 记录资产创建

- **WHEN** 用户创建资产
- **THEN** 系统创建 type=create 的 Activity 记录

#### Scenario: 记录资产更新

- **WHEN** 用户更新资产价值
- **THEN** 系统创建 type=update 的 Activity 记录

#### Scenario: 记录负债还款

- **WHEN** 用户记录负债还款
- **THEN** 系统创建 type=payment 的 Activity 记录

### Requirement: 操作日志必须包含关键信息

Activity SHALL 记录 family_id、user_id、type、entity_type、entity_id、title、amount 字段。

#### Scenario: 查看操作日志

- **WHEN** 用户查看活动历史
- **THEN** 显示操作时间、类型、关联实体、金额变化

### Requirement: 系统必须支持资产快照

系统 SHALL 提供快照功能，定期或手动记录家庭资产总额状态。

#### Scenario: 手动创建快照

- **WHEN** 用户点击"生成快照"
- **THEN** 系统记录当前所有资产总额

#### Scenario: 查看历史快照

- **WHEN** 用户访问快照列表
- **THEN** 显示历史快照的时间和净资产总额

