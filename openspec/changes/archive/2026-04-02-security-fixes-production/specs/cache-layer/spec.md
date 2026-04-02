## ADDED Requirements

### Requirement: 缓存后端必须提供抽象接口

系统 SHALL 定义 `CacheBackend` 抽象基类，提供以下方法：
- `get(key)` - 获取缓存值
- `set(key, value, ttl_seconds)` - 设置缓存值（可选 TTL）
- `delete(key)` - 删除缓存值
- `increment(key, delta)` - 递增计数器
- `get_ttl(key)` - 获取剩余 TTL
- `clear()` - 清空缓存

#### Scenario: 使用缓存接口存储计数器

- **WHEN** 调用 `cache.set("login_attempts:user1", 3, ttl_seconds=900)`
- **THEN** 缓存存储值为 3，900 秒后自动过期

#### Scenario: 递增计数器

- **WHEN** 调用 `cache.increment("login_attempts:user1")`
- **THEN** 返回新值 4，保留原有 TTL

### Requirement: 缓存后端必须提供内存实现

系统 SHALL 提供 `MemoryCacheBackend` 实现，使用内存字典存储数据，支持 TTL 过期。

#### Scenario: 内存缓存基本操作

- **WHEN** 调用 `cache.set("key", "value")` 后调用 `cache.get("key")`
- **THEN** 返回 "value"

#### Scenario: 内存缓存 TTL 过期

- **WHEN** 调用 `cache.set("key", "value", ttl_seconds=1)` 后等待 1.1 秒
- **THEN** `cache.get("key")` 返回 None

### Requirement: 缓存后端必须预留 Redis 实现

系统 SHALL 提供 `RedisCacheBackend` 占位实现，接口定义完整但抛出 `NotImplementedError`。

#### Scenario: Redis 后端未实现提示

- **WHEN** 配置 `CACHE_BACKEND=redis` 并尝试获取缓存
- **THEN** 抛出 `NotImplementedError("Redis backend not yet implemented")`

### Requirement: 缓存后端必须通过工厂创建

系统 SHALL 提供 `get_rate_limit_cache()` 工厂函数，根据配置创建缓存实例。

#### Scenario: 创建内存缓存

- **WHEN** 配置 `CACHE_BACKEND=memory`
- **THEN** `get_rate_limit_cache()` 返回 `MemoryCacheBackend` 实例

#### Scenario: 缓存实例全局复用

- **WHEN** 多次调用 `get_rate_limit_cache()`
- **THEN** 返回同一缓存实例（单例模式）

### Requirement: 缓存配置必须可扩展

系统 SHALL 在 `config.py` 中定义以下配置项：
- `CACHE_BACKEND` - 缓存后端类型（默认 "memory"）
- `REDIS_URL` - Redis 连接 URL（默认 "redis://localhost:6379/0"）

#### Scenario: 配置内存缓存

- **WHEN** 未配置 `CACHE_BACKEND`
- **THEN** 使用默认值 "memory"

#### Scenario: 配置 Redis 缓存

- **WHEN** 配置 `CACHE_BACKEND=redis` 和 `REDIS_URL`
- **THEN** 系统预留 Redis 连接配置（当前未实现）