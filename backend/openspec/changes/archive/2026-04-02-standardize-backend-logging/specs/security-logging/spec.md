## MODIFIED Requirements

### Requirement: 安全日志必须使用统一日志配置

系统 SHALL 使用 `app/core/logging_config.py` 提供的统一日志配置模块，而非独立配置。

#### Scenario: 安全日志初始化

- **WHEN** 应用启动时调用 `setup_logging()`
- **THEN** 安全日志使用统一配置的 handler 和格式

#### Scenario: 安全日志独立文件

- **WHEN** 安全日志写入时
- **THEN** 输出到独立的 `logs/security.log` 文件