---
title: Numina 安全防护最佳实践
date: 2026-04-02
category: best-practices
module: security
problem_type: best_practice
component: authentication
severity: high
tags: [security, rate-limiting, cache, dos-protection, brute-force]
---

# Numina 安全防护最佳实践

## Context

Numina 即将部署到生产环境，安全审计发现多个防护隐患需要修复：
- 登录存在时间攻击漏洞（响应耗时暴露用户名是否存在）
- 速率限制使用内存存储，服务重启后失效
- 缺乏全局 API 限流，仅登录端点有保护

这些防护措施必须在生产部署前实施，以防止暴力破解和资源耗尽攻击。

## Guidance

### 1. 登录端点速率限制

必须对登录端点实施速率限制：同一用户名连续失败 5 次后锁定 15 分钟。

**输入验证要求：**
- 用户名长度限制：3-50 个字符
- 用户名字符白名单：字母、数字、下划线、中划线、邮箱格式
- 密码长度限制：8-72 个字符（bcrypt 最大处理 72 字符，防止过长密码 DoS）
- 密码复杂度：必须包含大写字母、小写字母、数字
- 所有验证失败返回统一错误信息，防止用户名枚举

**时间攻击防护要求：**
- 无论用户名是否存在，都必须执行相同耗时的 bcrypt 验证，确保响应时间一致
- 对不存在的用户，使用预生成的 dummy hash 执行 bcrypt 验证

**示例场景：**
- 登录失败锁定：同一用户名连续 5 次登录失败后，第 6 次返回 429 状态码，提示"登录失败次数过多，请 X 分钟后重试"
- 锁定时间计算：被锁定后尝试登录，错误信息显示剩余锁定分钟数
- 登录成功清除锁定：被锁定后使用正确密码登录成功，锁定记录和失败计数器均清除，后续登录正常
- 输入验证失败：用户名格式不正确，返回 400 错误，不计入限流计数

### 2. 登录速率限制使用缓存层

必须使用 `CacheBackend` 存储登录失败计数，替代内存字典。

**示例场景：**
- 使用缓存存储失败计数：登录失败时调用 `cache.increment("login_attempts:{username}")` 递增计数
- 服务重启后锁定记录保留：服务重启后用户尝试登录，检查缓存中的锁定记录（使用内存实现时重启后清空）

### 3. 全局 API 速率限制

必须对所有 API 端点实施全局速率限制：每个客户端 100 次/分钟。

**存储策略：**
- 使用中间件内存存储（`RateLimitMiddleware._rate_store`）
- 多 worker 部署时每个 worker 维护独立状态，实际限流阈值 = worker 数量 × 配置阈值
- 生产环境多 worker 部署建议：实现 Redis 缓存后端或在前端 Nginx 层配置限流

**示例场景：**
- 全局限流触发：同一客户端 1 分钟内请求超过 100 次，返回 429 状态码，提示"请求次数过多，请稍后重试"
- 限流计数重置：限流窗口（1 分钟）过期后，计数器重置，客户端可继续请求

### 4. 全局限流跳过特定端点

必须对以下端点跳过全局限流（硬编码在中间件中）：
- `/api/health` - 健康检查
- `/api/v1/auth/login` - 登录（有专用限流，见 Guidance 1）
- `/api/v1/auth/register` - 注册（有专用限流，见下文 Guidance 4.1）

**示例场景：**
- 健康检查不受限流：短时间内多次请求 `/api/health` 不触发全局限流

### 4.1 注册端点专用限流

必须对注册端点实施专用速率限制：同一 IP 地址每小时最多注册 5 次。

**示例场景：**
- 注册限流触发：同一 IP 地址 1 小时内尝试注册超过 5 次，返回 429 状态码，提示"注册请求过于频繁，请稍后重试"

### 5. 限流按客户端标识

必须按以下方式标识客户端：
- 已认证请求：使用 JWT 中的 `user_id`（从 token 解码获取，确保同一用户始终使用相同的限流标识）
- 未认证请求：使用真实 IP 地址（从 `X-Forwarded-For` 或 `X-Real-IP` header 获取）

**反向代理配置要求：**
- Nginx 必须配置 `proxy_set_header X-Real-IP $remote_addr;` 和 `proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;`
- 应用层必须验证 header 来源，仅接受来自可信代理 IP 的 X-Forwarded-For header

**可信代理验证逻辑：**
1. 检查请求来源 IP 是否在 `TRUSTED_PROXY_IPS` 列表中（支持 CIDR 格式，如 `172.16.0.0/12`）
2. 如果来自可信代理：解析 `X-Forwarded-For`，从右向左找到第一个不在可信代理列表中的 IP
3. 如果不来自可信代理：直接使用 `request.client.host`，忽略所有 header
4. 如果无法解析真实 IP：使用 socket 远程地址作为回退

**CIDR 格式要求：**
- `TRUSTED_PROXY_IPS` 必须支持 CIDR 格式（如 `10.0.0.0/8`, `172.16.0.0/12`）
- 应用启动时使用 `ipaddress` 模块验证每个配置项格式正确性
- 无效 CIDR 格式应阻止应用启动并输出明确错误

**防欺骗要求：**
- 禁止接受来自非可信 IP 的 `X-Forwarded-For` 或 `X-Real-IP` header
- 应用启动时应验证 `TRUSTED_PROXY_IPS` 配置是否正确
- 记录 IP 解析异常到安全日志

**示例场景：**
- 按用户标识限流：已认证用户短时间内请求超过 100 次，返回 429 状态码
- 按 IP 标识限流：未认证请求（无 token）短时间内超过 100 次，返回 429 状态码
- 反向代理后正确获取 IP：请求经过 Nginx 后，从 `X-Forwarded-For` 解析出客户端真实 IP
- 拒绝欺骗请求：来自非可信 IP 的请求携带伪造的 `X-Forwarded-For` header，应用忽略该 header 使用 socket 地址

### 6. 速率限制配置可调整

必须在 `config.py` 中定义以下配置项：
- `LOGIN_RATE_LIMIT_MAX_ATTEMPTS` - 登录最大失败次数（默认 5）
- `LOGIN_RATE_LIMIT_LOCKOUT_SECONDS` - 登录锁定时间（默认 900）
- `GLOBAL_RATE_LIMIT_PER_MINUTE` - 全局限流阈值（默认 100）
- `REGISTER_RATE_LIMIT_PER_HOUR` - 注册限流阈值（默认 5）
- `TRUSTED_PROXY_IPS` - 可信代理 IP 列表（用于解析 X-Forwarded-For）

**启动验证要求：**
- 应用启动时验证 `TRUSTED_PROXY_IPS` 中每个条目格式正确（CIDR 或单 IP）
- 若配置 `CACHE_BACKEND=redis`，应用启动时验证 Redis 连接可用性
- 无效配置应阻止启动并输出明确错误信息

**示例场景：**
- 调整登录锁定时间：配置 `LOGIN_RATE_LIMIT_LOCKOUT_SECONDS=1800`，登录锁定时间为 30 分钟
- 配置可信代理：设置 `TRUSTED_PROXY_IPS=["10.0.0.1", "172.16.0.0/12"]`，应用将信任来自这些 IP 的 X-Forwarded-For header

### 7. 缓存后端抽象接口

必须定义 `CacheBackend` 抽象基类，提供以下方法：
- `get(key)` - 获取缓存值
- `set(key, value, ttl_seconds)` - 设置缓存值（可选 TTL）
- `delete(key)` - 删除缓存值
- `increment(key, delta)` - 递增计数器
- `get_ttl(key)` - 获取剩余 TTL（返回秒数，整数）
- `clear()` - 清空缓存

**示例场景：**
- 使用缓存接口存储计数器：调用 `cache.set("login_attempts:{username}", 3, ttl_seconds=900)`，缓存存储值为 3，900 秒后自动过期
- 递增计数器：调用 `cache.increment("login_attempts:{username}")`，返回新值 4，保留原有 TTL

### 8. 缓存后端内存实现

必须提供 `MemoryCacheBackend` 实现，使用内存字典存储数据，支持 TTL 过期。

**示例场景：**
- 内存缓存基本操作：调用 `cache.set("key", "value")` 后调用 `cache.get("key")`，返回 "value"
- 内存缓存 TTL 过期：调用 `cache.set("key", "value", ttl_seconds=1)` 后等待 1.1 秒，`cache.get("key")` 返回 None

### 9. 缓存后端 Redis 预留

必须提供 `RedisCacheBackend` 占位实现，已定义完整接口但所有方法抛出 `NotImplementedError`。

**快速失败要求：**
- 当 `CACHE_BACKEND=redis` 且 Redis 后端不可用时，工厂函数应抛出 `NotImplementedError`，禁止静默回退到 `MemoryCacheBackend`
- 集群部署场景下，不同节点使用不同缓存后端会导致行为不一致（部分节点限流生效，部分节点限流失效）
- 应用启动时应立即失败，而非运行时才发现配置错误

**示例场景：**
- Redis 后端未实现时快速失败：配置 `CACHE_BACKEND=redis`，应用启动时抛出 `NotImplementedError`，明确提示需要实现 Redis 后端或切换到 memory
- 开发环境提示：开发环境应使用 `CACHE_BACKEND=memory`，生产环境集群部署前必须实现 Redis 后端

### 10. 缓存后端工厂创建

必须提供 `get_rate_limit_cache()` 工厂函数，根据配置创建缓存实例。

**示例场景：**
- 创建内存缓存：配置 `CACHE_BACKEND=memory`，`get_rate_limit_cache()` 返回 `MemoryCacheBackend` 实例
- 缓存实例全局复用：多次调用 `get_rate_limit_cache()`，返回同一缓存实例（单例模式）

### 11. 缓存配置可扩展

必须在 `config.py` 中定义以下配置项：
- `CACHE_BACKEND` - 缓存后端类型（默认 "memory"）
- `REDIS_HOST` - Redis 主机地址（默认 "localhost"）
- `REDIS_PORT` - Redis 端口（默认 6379）
- `REDIS_DB` - Redis 数据库编号（默认 0）
- `REDIS_PASSWORD` - Redis 密码（生产环境必须设置，从环境变量读取）
- `REDIS_USE_TLS` - 是否启用 TLS（默认 False）

**生产环境 Redis 安全要求：**
- 必须设置 `REDIS_PASSWORD` 环境变量，禁止硬编码密码
- 建议启用 TLS：设置 `REDIS_USE_TLS=true`
- Redis 服务器应部署在隔离的内网中，禁止外网直接访问
- 定期轮换 Redis 密码

**示例场景：**
- 配置内存缓存：未配置 `CACHE_BACKEND`，使用默认值 "memory"
- 配置 Redis 缓存：配置 `CACHE_BACKEND=redis` 和 `REDIS_URL`，系统预留 Redis 连接配置（当前未实现）

## Why This Matters

速率限制和缓存层是防御暴力破解和 DDoS 攻击的基础设施：
- **时间攻击防护**：登录失败时对不存在用户也执行 bcrypt 验证，确保响应时间一致（见 Guidance 1）
- **持久化限流**：登录限流使用缓存层存储状态（见 Guidance 2）；全局限流使用中间件内存存储（见 Guidance 3，多 worker 部署时应切换到 Redis 缓存层）
- **分布式准备**：缓存抽象层为未来切换到 Redis 实现分布式限流预留接口

### 设计权衡说明

- **用户名 vs IP 限流**：登录限流使用用户名作为键，防止针对特定账户的暴力破解；局限性是攻击者可尝试不同用户名绕过限制；缓解措施是全局 API 限流仍按 IP 标识
- **内存存储局限**：当前使用内存字典存储限流状态，单 worker 部署正常工作；多 worker 部署时每个 worker 维护独立状态，实际限流阈值 = worker 数量 × 配置阈值
- **未来扩展路径**：已提供 `CacheBackend` 抽象层，未来可切换到 Redis 实现分布式限流

## When to Apply

- 部署到生产环境前必须实施
- 新增 API 端点时需评估限流需求
- 处理认证相关功能时必须遵循登录限流规则
- 多 worker 部署时需评估缓存后端选择（内存 vs Redis）

## Examples

### 速率限制中间件配置

```python
# backend/app/config.py
class Settings(BaseSettings):
    # 速率限制配置
    LOGIN_RATE_LIMIT_MAX_ATTEMPTS: int = 5
    LOGIN_RATE_LIMIT_LOCKOUT_SECONDS: int = 900
    GLOBAL_RATE_LIMIT_PER_MINUTE: int = 100
    REGISTER_RATE_LIMIT_PER_HOUR: int = 5  # 注册专用限流

    # 可信代理配置（用于正确获取客户端 IP）
    TRUSTED_PROXY_IPS: list[str] = []  # 例如: ["10.0.0.1", "172.16.0.0/12"]

    # 缓存配置
    CACHE_BACKEND: str = "memory"
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: str | None = None  # 生产环境必须设置
    REDIS_USE_TLS: bool = False
```

### 缓存层使用示例

```python
# 获取缓存实例
cache = get_rate_limit_cache()

# 登录失败时递增计数
attempts = cache.increment(f"login_attempts:{username}")
if attempts >= config.LOGIN_RATE_LIMIT_MAX_ATTEMPTS:
    cache.set(f"login_locked:{username}", "1", ttl_seconds=config.LOGIN_RATE_LIMIT_LOCKOUT_SECONDS)

# 检查锁定状态
if cache.get(f"login_locked:{username}"):
    remaining_seconds = cache.get_ttl(f"login_locked:{username}")
    remaining_minutes = remaining_seconds // 60  # 转换为分钟
    raise AppError(ErrorCode.AUTH_RATE_LIMITED, details={"reset_at": remaining_minutes})
```

## Related

- [安全审计最佳实践](./security-audit.md) - 安全日志和文件上传验证
- `openspec/specs/rate-limiting/spec.md` - 原始需求规范
- `openspec/specs/cache-layer/spec.md` - 原始需求规范