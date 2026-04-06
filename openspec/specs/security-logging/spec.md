## ADDED Requirements

### Requirement: 系统必须记录安全事件日志

系统 SHALL 记录以下安全事件到 `logs/security.log`：
- 登录成功
- 登录失败（用户不存在、密码错误）
- 登录限流触发
- 全局限流触发
- 文件上传格式不匹配
- Token 刷新成功/失败

#### Scenario: 记录登录成功事件

- **WHEN** 用户登录成功
- **THEN** 日志记录 `[login_success] username=<name> user_id=<id>`

#### Scenario: 记录登录失败事件

- **WHEN** 用户登录失败（密码错误）
- **THEN** 日志记录 `[login_failed_wrong_password] username=<name> user_id=<id>`

#### Scenario: 记录限流触发事件

- **WHEN** 登录限流触发
- **THEN** 日志记录 `[login_rate_limited] username=<name>`

### Requirement: 安全日志必须使用结构化格式

系统 SHALL 使用以下日志格式：
`<timestamp> - <level> - [<event_type>] <key=value> | <key=value>`

#### Scenario: 日志格式示例

- **WHEN** 记录安全事件
- **THEN** 日志格式为 `2026-04-02 10:30:00 - INFO - [login_success] username=testuser | user_id=1`

### Requirement: 安全日志必须区分事件级别

系统 SHALL 按事件类型设置日志级别：
- 成功事件：INFO
- 失败/阻断事件：WARNING

#### Scenario: 成功事件 INFO 级别

- **WHEN** 记录 `login_success` 事件
- **THEN** 日志级别为 INFO

#### Scenario: 失败事件 WARNING 级别

- **WHEN** 记录 `login_failed_wrong_password` 事件
- **THEN** 日志级别为 WARNING

### Requirement: 安全日志服务必须可配置开关

系统 SHALL 提供 `ENABLE_SECURITY_LOGGING` 配置项（默认 true）。

#### Scenario: 关闭安全日志

- **WHEN** 配置 `ENABLE_SECURITY_LOGGING=false`
- **THEN** 不记录安全事件日志

### Requirement: 安全日志必须在应用启动时初始化

系统 SHALL 在 `main.py` 的 lifespan 中初始化安全日志服务。

#### Scenario: 日志初始化

- **WHEN** 应用启动
- **THEN** 创建 `logs/` 目录，初始化日志 handler

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