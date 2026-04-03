## Requirements

### Requirement: 安全日志必须实施日志轮转

系统 SHALL 使用日志轮转 handler 实现日志轮转，支持按大小或按时间轮转，保留最近 30 天的日志文件。

#### Scenario: 日志文件轮转

- **WHEN** 日志文件大小达到 `LOG_MAX_BYTES` 或到达配置的轮转时间
- **THEN** 系统自动轮转日志文件，创建新的日志文件，旧文件重命名为带序号或日期后缀

#### Scenario: 日志文件保留期限

- **WHEN** 日志文件超过 `LOG_RETENTION_DAYS`（默认 30 天）
- **THEN** 系统自动删除过期的日志文件

#### Scenario: 日志目录不存在时创建

- **WHEN** 应用启动时日志目录不存在
- **THEN** 系统自动创建 `logs/` 目录

### Requirement: 安全日志必须使用统一日志配置

系统 SHALL 使用 `app/core/logging_config.py` 提供的统一日志配置模块，而非独立配置。

#### Scenario: 安全日志初始化

- **WHEN** 应用启动时调用 `setup_logging()`
- **THEN** 安全日志使用统一配置的 handler 和格式

#### Scenario: 安全日志独立文件

- **WHEN** 安全日志写入时
- **THEN** 输出到独立的 `logs/security.log` 文件