# 统一 Redis 共享缓存设计

> 日期: 2026-09-25
> 状态: 草案
> 模块: server (Backend / Agent / Scheduler Worker / Packages)

## 1. 问题背景

### 1.1 现状

在 DeerFlow SSE 会话重构中，AI 对话功能的续作机制已完全依赖 Redis（移除了此前的 cache 层封装本地缓存和 Redis 的架构，复用 DeerFlow 的 Redis 方案）。这意味着启用 AI 助手功能时 Redis 是硬性依赖。

然而 Backend、Agent、Scheduler Worker 三个服务中仍有大量缓存使用本地内存：

| 服务 | 缓存位置 | 当前机制 | 数据 |
|------|---------|---------|------|
| Backend | `services/cache/` (rate_limit, captcha) | `CacheBackend` 抽象 (memory/redis 可选) | 速率限制计数器、验证码防重放 hash |
| Backend | `middleware/rate_limit.py:_rate_store` | 内联 dict | 全局 API 速率限制（绕过 CacheBackend） |
| Backend | `config_service:_family_setting_cache` | 内联 dict 5min TTL | FamilySetting 热路径读取 |
| Agent | `agent_registry.py` | 内存 dict + 60s TTL | Agent 属性（从 backend HTTP 获取） |
| Scheduler | `exchange_rate_adapter.py` | 内存 dict 4h TTL | 汇率查询结果 |

### 1.2 问题

- **数据冗余**: 同样的数据（如汇率、family setting）在多个服务进程中各自缓存一份，不一致风险高
- **多实例不兼容**: 内存缓存无法跨进程共享，水平扩展时速率限制等安全功能失效
- **抽象过时**: `CacheBackend` 抽象层同时支持 memory 和 redis 两种后端，但 memory 后端在多实例场景下不可靠，而 Redis 已是 AI 功能的硬性依赖
- **命名误导**: `CacheBackend` 名字过于泛化，不能体现"跨进程共享"的核心语义

### 1.3 不在范围内

以下缓存明确保留本地，不属于统一缓存的范畴：

| 缓存 | 原因 |
|------|------|
| Agent `family_adapter_cache` (LRU) | 存储 DeerFlowClient 实例 + temp config 路径，包含 socket 等有状态对象，不可序列化 |
| Agent `agent_temp_cache` (LRU) | 存储临时文件目录路径，依赖本地文件系统 |
| Agent `checkpointer` (Postgres/SQLite) | LangGraph 会话状态持久化，非缓存语义 |
| Backend `finance_coach_cache` (DB) | 基于 `ai_reports` 表的 DB 缓存，已跨进程，非内存缓存 |
| `packages/core/system_config.py` (`@lru_cache`) | 进程配置，生命周期内不变，适合本地 |
| `packages/storage/github.py:_sha_cache` | GitHub SHA 缓存，实例级 |
| `packages/db/models/cached_file.py` (DB) | 文件去重，DB 表 |

这些场景使用本地 LRU 或 DB，不需要 `SharedCache` 封装。

## 2. 设计目标

1. **统一共享缓存**: 三个服务通过同一个 Redis 实例访问共享缓存数据
2. **消除冗余**: 同样的数据（汇率、family setting 等）只存一份，任何服务写入后其他服务可立即读取
3. **简化架构**: 移除 memory 回退，Redis 成为系统级必需（与 AI 功能对齐）
4. **明确语义边界**: "共享缓存"用于共享状态、配置、数据加速；本地 LRU 用于有状态对象和文件系统依赖

## 3. 命名与结构

### 3.1 类命名重构

| 旧名 | 新名 | 位置 |
|------|------|------|
| `CacheBackend(ABC)` | 删除 | — |
| `MemoryCacheBackend` | 删除 | — |
| `RedisCacheBackend` | `SharedCache` | `packages/core/shared_cache/` |
| `cache/factory.py` | 合并到 `__init__.py` | `packages/core/shared_cache/` |
| `services/cache/` (Backend 私有) | 删除 | — |

### 3.2 模块结构

```
server/packages/core/shared_cache/
├── __init__.py          # 导出 SharedCache + 工厂函数
├── shared_cache.py      # SharedCache 类（唯一实现）
└── keys.py              # Redis key 前缀常量与构造器
```

### 3.3 Redis Key 命名规范

统一前缀 `numina:` 加服务名，避免 key 冲突：

```
numina:ratelimit:{scope}:{key}          # 速率限制
numina:captcha:{sha256_hash}            # 验证码防重放
numina:famsetting:{family_id}:{key}     # FamilySetting 热路径
numina:agentreg:{family_id}:{agent}     # Agent 属性注册
numina:fxrate:{currency}                # 汇率
```

`keys.py` 提供常量与构造函数，防止硬编码 key 字符串散落各处。

## 4. SharedCache 类设计

### 4.1 接口

```python
class SharedCache:
    """跨进程共享的 Redis 缓存。

    用于共享状态、配置热路径、数据加速。
    不适合存储有状态对象或本地文件系统引用。
    """

    def __init__(self, redis_url: str, *, key_prefix: str = "numina")
    async def get(self, key: str) -> Any | None
    async def set(self, key: str, value: Any, *, ttl: int | None = None) -> None
    async def delete(self, key: str) -> None
    async def exists(self, key: str) -> bool
    async def clear(self, pattern: str) -> int  # 按通配符删除，返回删除数量
```

### 4.2 序列化

- 值统一使用 JSON 序列化（`json.dumps` / `json.loads`）
- 支持基本类型：`str`, `int`, `float`, `bool`, `dict`, `list`, `None`
- 不支持自定义对象的自动序列化（调用方负责转为 dict）

### 4.3 连接管理

- 使用 `redis.asyncio.Redis` 异步连接池
- 三个服务共用同一个 Redis 实例（`REDIS_URL`），各自维护独立的连接池
- **与 StreamBridge 的连接关系**: StreamBridge 已使用 `redis.asyncio`，且 `SharedCache` 也使用 `redis.asyncio`。两者共用同一个 Redis 实例，但各自维护独立的 `Redis` 连接池（StreamBridge 用于 Streams 操作，SharedCache 用于 KV 操作）。不合并连接池，因为两者的使用模式和生命周期不同
- 连接池大小通过 `SharedCache` 构造参数控制，默认 `max_connections=10`
- 不在业务代码中直接使用 `redis-py`，所有访问通过 `SharedCache` 封装

### 4.4 初始化与生命周期

每个服务在启动时（FastAPI lifespan）创建 `SharedCache` 单例：

```python
# 示例：backend lifespan
cache = SharedCache(settings.REDIS_URL)
app.state.shared_cache = cache
# 关闭时 await cache.close()
```

工厂函数提供便捷访问：

```python
# __init__.py
_instance: SharedCache | None = None

def init_shared_cache(redis_url: str, **kwargs) -> SharedCache
def get_shared_cache() -> SharedCache  # 未初始化时抛 RuntimeError
def reset_shared_cache() -> None       # 测试用
```

## 5. 各服务迁移计划

### 5.1 Backend

| 迁移项 | 当前 | 迁移后 | 备注 |
|-------|------|--------|------|
| `services/cache/` (rate_limit) | `CacheBackend` memory/redis | `SharedCache` | 移除旧模块 |
| `services/cache/` (captcha) | `CacheBackend` memory/redis | `SharedCache` | 同上 |
| `middleware/rate_limit.py:_rate_store` | 内联 dict | `SharedCache` | 消除绕过抽象的直接 dict |
| `config_service:_family_setting_cache` | 内联 dict 5min TTL | `SharedCache` 5min TTL | agent 也可直接读取 |

**文件变更清单:**
- 删除 `server/apps/backend/app/services/cache/` 整个目录
- 修改 `server/apps/backend/app/services/auth.py` — 使用 `get_shared_cache()` 替代 `get_rate_limit_cache()`
- 修改 `server/apps/backend/app/middleware/rate_limit.py` — 使用 `SharedCache` 替代 `_rate_store` dict；中间件需从同步改为 async（`SharedCache` 基于 `redis.asyncio`，FastAPI 支持 async middleware）
- 修改 `server/apps/backend/app/services/config_service.py` — 使用 `SharedCache` 替代 `_family_setting_cache`
- 修改 `server/apps/backend/app/auth/captcha.py` — 使用 `SharedCache` 替代 `get_captcha_payload_cache()`
- 修改 `server/apps/backend/app/routers/device.py` — 同上
- 修改 `server/apps/backend/app/routers/shared.py` — 同上
- 修改 backend lifespan — 初始化 `SharedCache`

### 5.2 Agent

| 迁移项 | 当前 | 迁移后 | 备注 |
|-------|------|--------|------|
| `agent_registry.py` | 内存 dict + HTTP fetch | `SharedCache` | agent 写入，backend/scheduler 读取 |
| `family_adapter_cache` | 本地 LRU | **不变** | 有状态对象，不迁移 |
| `agent_temp_cache` | 本地 LRU | **不变** | 本地文件系统，不迁移 |

**关于 `agent_registry` 的迁移:**

当前流程: backend → HTTP POST `/internal/cache/invalidate` → agent 清除本地缓存 → 下次访问时 agent HTTP GET backend 重新获取

迁移后: backend 直接写入 `SharedCache`，agent 直接读取 `SharedCache`。无需 HTTP invalidation 调用。

- 删除 `POST /internal/cache/invalidate/{family_id}` 端点
- 删除 backend 中调用该端点的代码
- agent_registry 改为从 `SharedCache` 读取，缓存 miss 时从 DB 获取并写入 `SharedCache`

### 5.3 Scheduler Worker

| 迁移项 | 当前 | 迁移后 | 备注 |
|-------|------|--------|------|
| `exchange_rate_adapter.py` | 内存 dict 4h TTL | `SharedCache` 4h TTL | backend 也可命中汇率缓存 |

**文件变更清单:**
- 修改 `server/packages/db/exchange_rate_adapter.py` — 使用 `SharedCache` 替代内存 dict
- scheduler_worker lifespan 初始化 `SharedCache`

### 5.4 跨服务共享收益

迁移后以下数据实现真正的跨进程共享：

| 数据 | 写入方 | 读取方 | 收益 |
|------|--------|--------|------|
| 速率限制计数器 | Backend | Backend | 多实例部署时一致 |
| 验证码防重放 | Backend | Backend | 多实例部署时一致 |
| FamilySetting | Backend | Backend + Agent | Agent 无需通过 HTTP 获取 |
| Agent 属性 | Agent | Backend + Agent | 消除 HTTP invalidation 调用 |
| 汇率 | Scheduler | Backend + Scheduler | 避免重复查询外部 API |

## 6. 环境变量与配置

### 6.1 移除

- `CACHE_BACKEND` — 不再有 memory/redis 切换，统一 Redis
- `MemoryCacheBackend` 相关代码全部删除

### 6.2 保留 / 复用

- `REDIS_URL` — 已有，作为 `SharedCache` 的连接地址
- `REDIS_HOST`, `REDIS_PORT`, `REDIS_DB`, `REDIS_PASSWORD`, `REDIS_USE_TLS` — 保留，用于构造 `REDIS_URL`

### 6.3 启动检查

服务启动时检测 Redis 连通性。连接失败则服务启动失败（与 AI 功能对 Redis 的硬性依赖一致）。

```python
async def check_redis_connection(redis_url: str) -> None:
    """启动时检测 Redis 连通性，失败则抛异常阻止启动。"""
    try:
        r = redis.asyncio.from_url(redis_url)
        await r.ping()
        await r.aclose()
    except Exception as e:
        raise RuntimeError(f"Redis connection failed: {e}") from e
```

## 7. 测试策略

- 单元测试: mock `SharedCache`，测试各服务使用缓存的业务逻辑
- 集成测试: 使用 `fakeredis` 或测试 Redis 容器验证 `SharedCache` 的序列化、TTL、key 前缀
- 迁移完成后确保现有测试套件通过：
  - Backend: `pytest server/tests/backend/`
  - Agent: `pytest server/tests/agent/`
  - Scheduler: `pytest server/tests/scheduler/`

## 8. 风险与缓解

| 风险 | 影响 | 缓解 |
|------|------|------|
| Redis 单点故障 | 所有缓存失效，速率限制降级 | Redis 本身已是 AI 功能的硬性依赖，额外风险有限；可后续加 Redis Sentinel |
| 序列化兼容性 | 旧缓存数据格式不兼容 | 迁移时 flush 相关 key（服务重启前 `FLUSHDB` 或 key 前缀变更） |
| 连接池耗尽 | 缓存操作阻塞 | 默认 `max_connections=10`，监控连接使用率 |
| Agent HTTP invalidation 删除 | 破坏性变更 | 确认没有其他调用方后再删除端点 |
