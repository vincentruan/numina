## Requirements

### Requirement: 系统必须提供统一的日志配置模块

系统 SHALL 在 `app/core/logging_config.py` 中提供统一的日志配置模块，包括：
- 日志格式配置
- 日志级别配置
- 日志输出位置配置
- 日志轮转配置

#### Scenario: 初始化日志配置

- **WHEN** 应用启动时调用 `setup_logging()`
- **THEN** 系统初始化所有日志 handler，配置日志格式和级别

#### Scenario: 获取日志器

- **WHEN** 调用 `get_logger(name)` 获取日志器
- **THEN** 返回配置好的 logger 实例

### Requirement: 日志必须支持轮转

系统 SHALL 支持两种日志轮转模式：
- **按大小轮转**：单个文件达到指定大小时轮转
- **按时间轮转**：到达指定时间（如午夜）时轮转

#### Scenario: 按大小轮转日志

- **WHEN** 日志文件大小达到 `LOG_MAX_BYTES`（默认 10MB）
- **THEN** 系统轮转日志文件，创建新文件，旧文件重命名带序号后缀

#### Scenario: 按时间轮转日志

- **WHEN** 配置 `LOG_ROTATION_MODE=time` 且到达午夜
- **THEN** 系统轮转日志文件，旧文件重命名带日期后缀

### Requirement: 日志必须支持归档

系统 SHALL 支持日志归档，自动压缩超过备份数量的旧日志文件。

#### Scenario: 归档旧日志

- **WHEN** 日志备份数量超过 `LOG_BACKUP_COUNT`
- **THEN** 系统自动压缩最旧的日志文件为 `.gz` 格式

### Requirement: 日志必须支持自动清理

系统 SHALL 自动删除超过保留天数的日志文件。

#### Scenario: 清理过期日志

- **WHEN** 日志文件超过 `LOG_RETENTION_DAYS`（默认 30 天）
- **THEN** 系统自动删除该日志文件

#### Scenario: 启动时清理日志

- **WHEN** 应用启动时
- **THEN** 系统执行一次日志清理任务

### Requirement: 日志配置必须可调整

系统 SHALL 在 `config.py` 中定义以下日志配置项：
- `LOG_LEVEL` - 日志级别（默认 INFO）
- `LOG_DIR` - 日志目录（默认 `logs/`）
- `LOG_MAX_BYTES` - 单文件最大大小（默认 10MB）
- `LOG_BACKUP_COUNT` - 备份文件数量（默认 10）
- `LOG_RETENTION_DAYS` - 保留天数（默认 30）
- `LOG_ROTATION_MODE` - 轮转模式（默认 size，可选 time）
- `LOG_FORMAT` - 日志格式（默认 `%(asctime)s - %(name)s - %(levelname)s - %(message)s`）

#### Scenario: 配置日志级别

- **WHEN** 配置 `LOG_LEVEL=DEBUG`
- **THEN** 系统输出 DEBUG 及以上级别的日志

#### Scenario: 配置日志目录

- **WHEN** 配置 `LOG_DIR=/var/log/numina`
- **THEN** 日志文件写入 `/var/log/numina` 目录