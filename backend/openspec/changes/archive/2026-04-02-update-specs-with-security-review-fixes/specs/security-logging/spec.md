## ADDED Requirements

### Requirement: 安全日志必须实施日志轮转

系统 SHALL 使用 `TimedRotatingFileHandler` 实现日志轮转，每天午夜轮转，保留最近 7 天的日志文件。

#### Scenario: 日志文件轮转

- **WHEN** 日志文件到达午夜
- **THEN** 系统自动轮转日志文件，创建新的日志文件，旧文件重命名为带日期后缀

#### Scenario: 日志文件保留期限

- **WHEN** 日志文件超过 7 天
- **THEN** 系统自动删除过期的日志文件

#### Scenario: 日志目录不存在时创建

- **WHEN** 应用启动时日志目录不存在
- **THEN** 系统自动创建 `logs/` 目录