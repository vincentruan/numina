## Why

Backend 应用日志缺乏统一管理，当前仅安全日志实现了日志轮转，应用日志无统一配置。生产环境需要：
- 统一的日志格式和输出配置
- 日志文件轮转，防止单个文件过大
- 自动归档和清理过期日志
- 按模块分离日志（应用日志、安全日志、访问日志）

## What Changes

- 创建统一的日志配置模块 `app/core/logging_config.py`
- 配置应用日志轮转（按大小或时间）
- 实现日志归档策略（压缩旧日志）
- 实现日志清理策略（自动删除过期日志）
- 更新现有日志使用方式，统一日志格式
- 添加日志配置项到 `config.py`

## Capabilities

### New Capabilities

- `logging-config`: 统一日志配置管理，包括日志格式、轮转、归档、清理

### Modified Capabilities

- `security-logging`: 扩展现有安全日志配置，与应用日志配置保持一致
- `architecture`: 新增日志配置模块和目录结构

## Impact

**新增文件**:
- `app/core/logging_config.py` - 日志配置模块
- `logs/` 目录结构（应用日志、安全日志分离）

**修改文件**:
- `app/config.py` - 新增日志配置项
- `app/main.py` - 应用启动时初始化日志配置
- `app/services/security_log.py` - 使用统一日志配置

**配置项**:
- `LOG_LEVEL` - 日志级别（默认 INFO）
- `LOG_DIR` - 日志目录（默认 `logs/`）
- `LOG_MAX_BYTES` - 单个日志文件最大大小（默认 10MB）
- `LOG_BACKUP_COUNT` - 保留日志文件数量（默认 10）
- `LOG_RETENTION_DAYS` - 日志保留天数（默认 30）