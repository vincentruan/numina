# 统一缓存层设计

> 日期: 2026-09-25
> 状态: 草案
> 模块: server (Backend / Agent / Scheduler Worker / Packages)

## 1. 问题背景

### 1.1 现状

系统存在两层不同性质的缓存，当前未清晰分离：

**缓存层 (Cache Layer)** — 提供用户选择灵活性（memory/redis），用于共享状态、配置热路径、数据加速：

| 服务 | 缓存位置 | 当前机制 | 数据 |
|------|---------|---------|------|
| Backend | `services/cache/` (rate_limit, captcha) | `CacheBackend` 抽象 (memory/redis) | 速率限制计数器、验证码防重放 hash |
| Backend | `middleware/rate_limit.py:_rate_store` | 内联 dict（绕过 CacheBackend） | 全局 API 速率限制 |
| Backend | `config_service:_family_setting_cache` | 内联 dict 5min TTL | FamilySetting 热路径读取 |
| Agent | `agent_registry.py` | 内存 dict + 60s TTL | Agent 属性（从 backend HTTP 获取） |
| Scheduler | `exchange_rate_adapter.py` | 内存 dict 4h TTL | 汇率查询结果 |

**本地 LRU** — 内部实现逻辑要求，与缓存层无关：

| 缓存 | 原因 |
|------|------|
| Agent `family_adapter_cache` (LRU) | DeerFlowClient 实例 + temp config 路径，含 socket 等有状态对象 |
| Agent `agent_temp_cache` (LRU) | 临时文件目录路径，依赖本地文件系统 |
| Agent `checkpointer` (Postgres/SQLite) | LangGraph 会话状态持久化 |
| Backend `finance_coach_cache` (DB) | 基于 `ai_reports` 表，已跨进程 |
| `packages/core/system_config.py` (`@lru_cache`) | 进程配置，生命周期内不变 |
| `packages/storage/github.py:_sha_cache` | GitHub SHA，实例级 |
| `packages/db/models/cached_file.py` (DB) | 文件去重 |

### 1.2 问题

- **缓存层未统一**: Backend 有 `CacheBackend` 抽象但仅服务 rate_limit 和 captcha；`middleware/_rate_store`、`config_service/_family_setting_cache`、`agent_registry`、`exchange_rate_adapter` 全部绕过抽象层直接使用内联 dict
- **数据冗余**: 同样的数据（如汇率、family setting）在多个服务进程中各自缓存一份。当启用 Redis 时，这些数据可以跨进程共享，但当前没有通过统一的 cache 层实现
- **Redis 实现从未启用**: `RedisCacheBackend` 已存在但 `CACHE_BACKEND` 默认 `memory`，从未有用户切换到 Redis
- **命名不佳**: `CacheBackend` 名字过于泛化，工厂函数 `get_rate_limit_cache()` / `get_captcha_payload_cache()` 按用途而非实例管理

### 1.3 两种缓存的本质区别

| 维度 | 缓存层 (Cache Layer) | 本地 LRU |
|------|---------------------|----------|
| 目的 | 提供用户选择灵活性 (memory/redis) | 内部实现逻辑要求 |
| 数据性质 | 共享状态、配置、数据加速 | 有状态对象、文件系统引用 |
| 用户可见 | 通过 `CACHE_BACKEND` 环境变量切换 | 用户不可感知 |
| 跨进程 | Redis 模式下可跨进程共享 | 永远进程本地 |
| 是否使用封装类 | 是，通过 `Cache` 抽象 | 否，直接使用 OrderedDict 等 |

## 2. 设计目标

1. **统一缓存层封装**: 所有属于"缓存层"的数据（共享状态、配置、数据加速）统一通过 `Cache` 抽象访问，消除内联 dict 绕过抽象的情况
2. **保留双实现**: 保留 memory/redis 双实现，用户可通过 `CACHE_BACKEND` 选择。不强制要求 Redis
3. **跨进程共享**: 当用户选择 Redis 时，同样的数据可被 Backend/Agent/Scheduler Worker 共享，避免冗余存储
4. **明确语义边界**: 本地 LRU（有状态对象、文件系统依赖）不使用 cache 封装类，两者是不同层次的东西
5. **重命名**: `CacheBackend` 及其实现类重命名，更好体现语义

## 3. 命名与结构

### 3.1 类命名重构

| 旧名 | 新名 | 说明 |
|------|------|------|
| `CacheBackend(ABC)` | `Cache` | 抽象基类，接口不变 |
| `MemoryCacheBackend` | `MemoryCache` | 内存实现 |
| `RedisCacheBackend` | `RedisCache` | Redis 实现 |
| `cache/factory.py` | 简化 | 工厂函数简化（见 3.3） |

### 3.2 模块结构

```
server/packages/core/cache/
├── __init__.py          # 导出 Cache, MemoryCache, RedisCache + 工厂函数
├── base.py              # Cache 抽象基类（原 CacheBackend）
├── memory.py            # MemoryCache（原 MemoryCacheBackend）
├── redis.py             # RedisCache（原 RedisCacheBackend）
├── factory.py           # 工厂函数 + 初始化
└── keys.py              # Key 前缀常量与构造器
```

**Backend 私有缓存模块清理:**
- 删除 `server/apps/backend/app/services/cache/` 整个目录
- 所有消费方改为从 `packages/core/cache/` 导入

### 3.3 工厂简化

当前工厂按用途创建多个实例（`get_rate_limit_cache()`、`get_captcha_payload_cache()`），改为单一 cache 实例 + key 前缀约定：

```python
# factory.py
_instance: Cache | None = None

def init_cache(backend: str = "memory", *, redis_url: str = "", **kwargs) -> Cache
    """根据 CACHE_BACKEND 创建 Cache 实例。"""

def get_cache() -> Cache
    """获取全局 Cache 单例。未初始化时抛 RuntimeError。"""

def reset_cache() -> None
    """测试用，重置单例。"""
```

调用方通过 key 前缀区分用途，不再需要按用途创建多个 cache 实例。

### 3.4 Key 命名规范

通过 `keys.py` 定义前缀常量，防止硬编码散落：

```python
# keys.py
RATE_LIMIT = "ratelimit"      # 速率限制
CAPTCHA = "captcha"           # 验证码防重放
FAM_SETTING = "famsetting"    # FamilySetting 热路径
AGENT_REG = "agentreg"        # Agent 属性注册
FX_RATE = "fxrate"            # 汇率
```

调用方使用 `f"{RATE_LIMIT}:{scope}:{key}"` 构造 key。

### 3.5 Key 前缀变化对 Memory 模式的影响评估

**结论：无影响。**

- Memory 模式的 key 是 dict 的字符串键，前缀变化仅影响 key 字符串本身
- Memory 模式是进程重启即清空的临时缓存，不存在持久化数据迁移问题
- Redis 模式下 key 前缀变化意味着旧 key 不再被命中，但缓存数据本身可从源头重建（DB、HTTP API），不造成数据丢失
- **迁移策略**: 服务重启时自动使用新前缀，旧 Redis key 通过 TTL 自然过期，无需手动清理

## 4. Cache 抽象设计

### 4.1 接口

```python
class Cache(ABC):
    """缓存抽象基类。

    提供用户选择灵活性：memory 模式（进程本地）或 redis 模式（跨进程共享）。
    用于共享状态、配置热路径、数据加速。
    """

    @abstractmethod
    async def get(self, key: str) -> Any | None: ...

    @abstractmethod
    async def set(self, key: str, value: Any, *, ttl: int | None = None) -> None: ...

    @abstractmethod
    async def delete(self, key: str) -> None: ...

    @abstractmethod
    async def get_ttl(self, key: str) -> int | None: ...

    @abstractmethod
    async def increment(self, key: str, amount: int = 1) -> int: ...

    @abstractmethod
    async def clear(self) -> None: ...
```

### 4.2 MemoryCache

- 与当前 `MemoryCacheBackend` 逻辑一致，仅重命名
- 内部 dict + TTL 时间戳
- 需注意：async 接口下 `MemoryCache` 的 async 方法是轻量包装（直接返回结果，无 IO）

### 4.3 RedisCache

- 与当前 `RedisCacheBackend` 逻辑一致，仅重命名
- 使用 `redis.asyncio.Redis`
- JSON 序列化（`json.dumps` / `json.loads`）
- `SETEX` 实现 TTL

### 4.4 异步接口说明

当前 `CacheBackend` 是同步接口。迁移为 async 的原因：
- `RedisCache` 基于 `redis.asyncio`，同步调用会阻塞事件循环
- 三个服务的调用方均在 FastAPI 异步上下文中，改造成本低
- `MemoryCache` 的 async 方法是零开销包装，不受影响

**需要同步改造的调用方:**
- `middleware/rate_limit.py` — 改为 async middleware
- `services/auth.py` — 认证函数改为 async（多数已经是）
- `auth/captcha.py` — 验证码验证改为 async

### 4.5 连接管理

- `RedisCache` 使用 `redis.asyncio.Redis` 异步连接池，`max_connections=10`
- 三个服务共用同一个 Redis 实例（`REDIS_URL`），各自维护独立连接池
- **与 StreamBridge 的关系**: 共用同一个 Redis 实例，但各自独立连接池（StreamBridge 用于 Streams，Cache 用于 KV）。不合并，使用模式和生命周期不同

### 4.6 初始化与生命周期

每个服务在 FastAPI lifespan 中初始化：

```python
# backend lifespan
cache = init_cache(backend=settings.CACHE_BACKEND, redis_url=settings.REDIS_URL)
app.state.cache = cache
# 关闭时调用 await cache.clear() 或其他清理逻辑（如有需要）
```

## 5. 各服务迁移计划

### 5.1 Backend

| 迁移项 | 当前 | 迁移后 | 备注 |
|-------|------|--------|------|
| `services/cache/` (rate_limit) | 私有 `CacheBackend` memory/redis | `packages/core/cache` 的 `get_cache()` | 移除 Backend 私有缓存模块 |
| `services/cache/` (captcha) | 同上 | 同上 | 同上 |
| `middleware/rate_limit.py:_rate_store` | 内联 dict | `get_cache()` | 消除绕过抽象；中间件改 async |
| `config_service:_family_setting_cache` | 内联 dict 5min TTL | `get_cache()` 5min TTL | Redis 模式下 agent 也可直接读取 |

**文件变更清单:**
- 删除 `server/apps/backend/app/services/cache/` 整个目录
- 修改 `server/apps/backend/app/services/auth.py` — 使用 `get_cache()` 替代 `get_rate_limit_cache()`
- 修改 `server/apps/backend/app/middleware/rate_limit.py` — 使用 `get_cache()` 替代 `_rate_store` dict；中间件改 async
- 修改 `server/apps/backend/app/services/config_service.py` — 使用 `get_cache()` 替代 `_family_setting_cache`
- 修改 `server/apps/backend/app/auth/captcha.py` — 使用 `get_cache()` 替代 `get_captcha_payload_cache()`
- 修改 `server/apps/backend/app/routers/device.py` — 同上
- 修改 `server/apps/backend/app/routers/shared.py` — 同上
- 修改 backend lifespan — 调用 `init_cache()` 初始化

### 5.2 Agent

| 迁移项 | 当前 | 迁移后 | 备注 |
|-------|------|--------|------|
| `agent_registry.py` | 内存 dict + HTTP fetch | `get_cache()` | Redis 模式下 backend/scheduler 可直接读取 |
| `family_adapter_cache` | 本地 LRU | **不变** | 本地 LRU，不属于缓存层 |
| `agent_temp_cache` | 本地 LRU | **不变** | 本地 LRU，不属于缓存层 |

**关于 `agent_registry` 的迁移:**

- **Memory 模式**: 行为与当前基本一致（进程本地 dict），但通过统一 `Cache` 接口访问。各进程独立缓存，仍需 HTTP invalidation 通知 agent 清除本地缓存
- **Redis 模式**: agent 写入 cache，backend/scheduler 直接读取 Redis，无需 HTTP invalidation

后续可考虑：当确认所有生产部署都使用 Redis 模式时，再移除 HTTP invalidation 端点作为简化。

### 5.3 Scheduler Worker

| 迁移项 | 当前 | 迁移后 | 备注 |
|-------|------|--------|------|
| `exchange_rate_adapter.py` | 内存 dict 4h TTL | `get_cache()` 4h TTL | Redis 模式下 backend 也可命中 |

**文件变更清单:**
- 修改 `server/packages/db/exchange_rate_adapter.py` — 使用 `get_cache()` 替代内存 dict
- scheduler_worker lifespan 调用 `init_cache()` 初始化

### 5.4 跨服务共享（Redis 模式下）

| 数据 | 写入方 | 读取方 | 收益 |
|------|--------|--------|------|
| 速率限制计数器 | Backend | Backend | 多实例部署时一致 |
| 验证码防重放 | Backend | Backend | 多实例部署时一致 |
| FamilySetting | Backend | Backend + Agent | Agent 无需通过 HTTP 获取 |
| Agent 属性 | Agent | Backend + Agent | 消除 HTTP invalidation 调用 |
| 汇率 | Scheduler | Backend + Scheduler | 避免重复查询外部 API |

Memory 模式下行为与当前一致（各进程独立），不丢失功能。

## 6. 环境变量与配置

### 6.1 保留

- `CACHE_BACKEND` — 保留，`"memory"` (默认) 或 `"redis"`
- `REDIS_URL` — 当 `CACHE_BACKEND=redis` 时使用
- `REDIS_HOST`, `REDIS_PORT`, `REDIS_DB`, `REDIS_PASSWORD`, `REDIS_USE_TLS` — 保留，用于构造 `REDIS_URL`

### 6.2 不启用 Redis 时的行为

| 场景 | 行为 |
|------|------|
| `CACHE_BACKEND=memory` (默认) | 各服务进程独立缓存，与当前行为完全一致 |
| `CACHE_BACKEND=redis` 但 Redis 不可达 | 服务启动失败（既然选择了 Redis 就必须可用） |
| 不配置 Redis | 正常工作，使用 memory 模式 |

### 6.3 启动检查

仅在 `CACHE_BACKEND=redis` 时检测 Redis 连通性：

```python
async def _check_redis_connection(redis_url: str) -> None:
    """Redis 模式下启动时检测连通性。"""
    try:
        r = redis.asyncio.from_url(redis_url)
        await r.ping()
        await r.aclose()
    except Exception as e:
        raise RuntimeError(f"Redis connection failed: {e}") from e
```

## 7. 测试策略

- **Cache 抽象层测试**: 对 `MemoryCache` 和 `RedisCache` 分别测试 `get/set/delete/increment/clear` + TTL
- **Redis 集成测试**: 使用 `fakeredis` 或测试 Redis 容器验证序列化、TTL、key 前缀
- **Memory 模式回归**: 确保 `CACHE_BACKEND=memory` 下所有现有测试通过
- **各服务测试**:
  - Backend: `pytest server/tests/backend/`
  - Agent: `pytest server/tests/agent/`
  - Scheduler: `pytest server/tests/scheduler/`

## 8. 风险与缓解

| 风险 | 影响 | 缓解 |
|------|------|------|
| 同步改 async 影响面 | auth/middleware/captcha 等需改 async | 逐个迁移，先改接口再改调用方 |
| Key 前缀变化（Redis 模式） | 旧 key 不再命中 | 缓存数据可从源头重建，TTL 自然过期 |
| 连接池耗尽 | 缓存操作阻塞 | `max_connections=10`，可配置调大 |
| Agent HTTP invalidation 删除 | 仅 Redis 模式下不再需要 | Memory 模式下保留（进程隔离，仍需 HTTP 通知） |
| 工厂函数 API 变更 | 消费方 import 路径变化 | 迁移时统一替换，无渐进过渡 |

## 9. 明确不迁移的项

以下使用场景**不属于缓存层**，不使用 `Cache` 封装类，保持现状：

| 缓存 | 性质 | 保留原因 |
|------|------|---------|
| Agent `family_adapter_cache` | 本地 LRU | 有状态对象 (DeerFlowClient + socket + temp 路径) |
| Agent `agent_temp_cache` | 本地 LRU | 本地文件系统目录引用 |
| Agent `checkpointer` | DB 持久化 | LangGraph 会话状态，非缓存语义 |
| Backend `finance_coach_cache` | DB 缓存 | 已跨进程，基于 `ai_reports` 表 |
| `system_config.py` `@lru_cache` | 进程配置 | 生命周期内不变 |
| `github.py:_sha_cache` | 实例级 dict | GitHub SHA 缓存 |
| `cached_file.py` | DB 表 | 文件去重 |
