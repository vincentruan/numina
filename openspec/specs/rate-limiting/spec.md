## ADDED Requirements

### Requirement: 登录端点必须实施速率限制

系统 SHALL 对登录端点实施速率限制：同一用户名连续失败 5 次后锁定 15 分钟。

#### Scenario: 登录失败锁定

- **WHEN** 同一用户名连续 5 次登录失败
- **THEN** 第 6 次登录返回 429 状态码，提示 "登录失败次数过多，请 X 分钟后重试"

#### Scenario: 锁定时间计算

- **WHEN** 用户被锁定后尝试登录
- **THEN** 错误信息显示剩余锁定分钟数

#### Scenario: 登录成功清除锁定

- **WHEN** 用户被锁定后使用正确密码登录成功
- **THEN** 锁定记录清除，后续登录正常

### Requirement: 登录速率限制必须使用缓存层

系统 SHALL 使用 `CacheBackend` 存储登录失败计数，替代内存字典。

#### Scenario: 使用缓存存储失败计数

- **WHEN** 登录失败
- **THEN** 调用 `cache.increment("login_attempts:{username}")` 递增计数

#### Scenario: 服务重启后锁定记录保留

- **WHEN** 服务重启后用户尝试登录
- **THEN** 检查缓存中的锁定记录（使用内存实现时重启后清空）

### Requirement: 全局 API 必须实施速率限制

系统 SHALL 对所有 API 端点实施全局速率限制：每个客户端 100 次/分钟。

#### Scenario: 全局限流触发

- **WHEN** 同一客户端 1 分钟内请求超过 100 次
- **THEN** 返回 429 状态码，提示 "请求次数过多，请稍后重试"

#### Scenario: 限流计数重置

- **WHEN** 限流窗口（1 分钟）过期
- **THEN** 计数器重置，客户端可继续请求

### Requirement: 全局限流必须跳过特定端点

系统 SHALL 对以下端点跳过全局限流：
- `/api/health` - 健康检查
- `/api/v1/auth/login` - 登录（有专用限流）
- `/api/v1/auth/register` - 注册

#### Scenario: 健康检查不受限流

- **WHEN** 短时间内多次请求 `/api/health`
- **THEN** 不触发全局限流

### Requirement: 限流必须按客户端标识

系统 SHALL 按以下方式标识客户端：
- 已认证请求：使用 Authorization header 的 token 前缀
- 未认证请求：使用 IP 地址

#### Scenario: 按用户标识限流

- **WHEN** 已认证用户短时间内请求超过 100 次
- **THEN** 返回 429 状态码

#### Scenario: 按 IP 标识限流

- **WHEN** 未认证请求（无 token）短时间内超过 100 次
- **THEN** 返回 429 状态码

### Requirement: 速率限制配置必须可调整

系统 SHALL 在 `config.py` 中定义以下配置项：
- `LOGIN_RATE_LIMIT_MAX_ATTEMPTS` - 登录最大失败次数（默认 5）
- `LOGIN_RATE_LIMIT_LOCKOUT_SECONDS` - 登录锁定时间（默认 900）
- `GLOBAL_RATE_LIMIT_PER_MINUTE` - 全局限流阈值（默认 100）

#### Scenario: 调整登录锁定时间

- **WHEN** 配置 `LOGIN_RATE_LIMIT_LOCKOUT_SECONDS=1800`
- **THEN** 登录锁定时间为 30 分钟

### Requirement: 速率限制设计必须记录权衡说明

系统文档 SHALL 记录速率限制的设计权衡，包括：
- **用户名 vs IP 限流**：登录限流使用用户名作为键，防止针对特定账户的暴力破解；局限性是攻击者可尝试不同用户名绕过限制；缓解措施是全局 API 限流仍按 IP 标识
- **内存存储局限**：当前使用内存字典存储限流状态，单 worker 部署正常工作；多 worker 部署时每个 worker 维护独立状态，实际限流阈值 = worker 数量 × 配置阈值
- **未来扩展路径**：已提供 `CacheBackend` 抽象层，未来可切换到 Redis 实现分布式限流

#### Scenario: 开发者理解用户名限流权衡

- **WHEN** 开发者阅读速率限制文档
- **THEN** 可以理解为什么选择用户名而非 IP 作为登录限流的键

#### Scenario: 开发者理解内存存储局限

- **WHEN** 开发者部署多 worker 环境
- **THEN** 可以从文档中了解内存存储的局限性，选择使用 Redis 后端或 Nginx 限流

### Requirement: 速率限制必须提供测试覆盖

系统 SHALL 提供速率限制中间件的集成测试，覆盖以下场景：
- 健康检查端点不受限流
- 限流阈值执行
- 不同客户端独立限流
- 限流窗口重置
- 客户端标识逻辑（token vs IP）

#### Scenario: 测试覆盖限流逻辑

- **WHEN** 运行 `tests/test_rate_limit.py`
- **THEN** 所有 10 个测试通过，验证限流中间件行为正确