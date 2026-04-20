# Cache Layer Design

**Date:** 2026-04-20
**Status:** Approved
**Scope:** 缓存抽象层，支持内存和 Redis 后端

---

## Problem

限流和缓存功能直接使用内存字典，缺乏抽象层。未来切换到 Redis 需要大量代码修改，且服务重启后限流状态丢失。

---

## Goals

1. 提供统一的缓存抽象接口
2. 支持多种后端实现（内存、Redis）
3. 便于未来扩展分布式缓存
4. 保持当前内存实现的简单性

---

## Architecture

### 缓存后端抽象

定义 `CacheBackend` 抽象基类，提供统一接口：

```
backend/app/services/cache/
├── base.py        # CacheBackend 抽象接口
├── memory.py      # MemoryCacheBackend 实现
├── redis.py       # RedisCacheBackend 占位
└── factory.py     # get_cache_backend() 工厂函数
```

依赖方向：调用方 → factory → 具体后端实现

### 后端选择策略

通过 `CACHE_BACKEND` 配置项选择后端：
- `memory`（默认）：单机部署、开发环境
- `redis`（未来）：多 worker、分布式部署

工厂函数返回单例实例，全局复用。

---

## Implementation Details

### CacheBackend 接口

```python
class CacheBackend(ABC):
    @abstractmethod
    def get(self, key: str) -> Any | None:
        """获取缓存值"""
    
    @abstractmethod
    def set(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        """设置缓存值（可选 TTL）"""
    
    @abstractmethod
    def delete(self, key: str) -> None:
        """删除缓存值"""
    
    @abstractmethod
    def increment(self, key: str, delta: int = 1) -> int:
        """递增计数器，返回新值"""
    
    @abstractmethod
    def get_ttl(self, key: str) -> int | None:
        """获取剩余 TTL 秒数"""
    
    @abstractmethod
    def clear(self) -> None:
        """清空所有缓存"""
```

### MemoryCacheBackend 实现

使用内存字典 + TTL 过期机制：

```python
class MemoryCacheBackend(CacheBackend):
    _store: dict[str, tuple[Any, float | None]]  # {key: (value, expire_at)}
    
    def get(self, key: str) -> Any | None:
        value, expire_at = self._store.get(key, (None, None))
        if expire_at and time.time() > expire_at:
            self.delete(key)
            return None
        return value
    
    def set(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        expire_at = time.time() + ttl_seconds if ttl_seconds else None
        self._store[key] = (value, expire_at)
    
    def increment(self, key: str, delta: int = 1) -> int:
        current = self.get(key) or 0
        new_value = current + delta
        # 保留原有 TTL
        _, expire_at = self._store.get(key, (None, None))
        self.set(key, new_value, expire_at and int(expire_at - time.time()))
        return new_value
```

### RedisCacheBackend 占位

接口定义完整，方法抛出 `NotImplementedError`：

```python
class RedisCacheBackend(CacheBackend):
    def __init__(self, redis_url: str):
        raise NotImplementedError("Redis backend not yet implemented")
    
    def get(self, key: str) -> Any | None:
        raise NotImplementedError
    # ... 其他方法同上
```

### 工厂函数

```python
_cache_instance: CacheBackend | None = None

def get_cache_backend() -> CacheBackend:
    global _cache_instance
    if _cache_instance:
        return _cache_instance
    
    backend_type = settings.CACHE_BACKEND
    if backend_type == "memory":
        _cache_instance = MemoryCacheBackend()
    elif backend_type == "redis":
        _cache_instance = RedisCacheBackend(settings.REDIS_URL)
    else:
        raise ValueError(f"Unknown cache backend: {backend_type}")
    
    return _cache_instance
```

### 配置项

在 `backend/app/config.py` 中添加：

```python
class Settings(BaseSettings):
    CACHE_BACKEND: str = "memory"
    REDIS_URL: str = "redis://localhost:6379/0"
```

---

## Design Trade-offs

| 决策 | 优势 | 局限性 | 缓解措施 |
|------|------|----------|----------|
| 用户名限流 | 防止针对特定账户的暴力破解 | 攻击者可尝试不同用户名绕过 | 全局 API 限流仍按 IP 标识 |
| 内存存储 | 简单、无外部依赖 | 单 worker 正常，多 worker 时每个 worker 独立状态 | 提供 Redis 后端选项，或使用 Nginx 限流 |
| TTL 过期检查 | 在 get 时检查，避免定时器开销 | 极端情况下内存占用可能增长 | 可添加后台清理线程（可选） |

---

## Verification

- `cache.set("key", "value", ttl_seconds=1)` 后等待 1.1 秒，`cache.get("key")` 返回 None
- `cache.increment("counter")` 递增计数器，返回新值
- `get_cache_backend()` 多次调用返回同一实例
- 配置 `CACHE_BACKEND=redis` 时抛出 `NotImplementedError`

---

## Code Pointers

| 功能 | 文件路径 |
|------|----------|
| 缓存接口 | `backend/app/services/cache/base.py` |
| 内存实现 | `backend/app/services/cache/memory.py` |
| Redis 占位 | `backend/app/services/cache/redis.py` |
| 工厂函数 | `backend/app/services/cache/factory.py` |
| 配置项 | `backend/app/config.py` |

---

## Related Specs

- **速率限制设计**：`2026-04-20-rate-limiting-design.md` — 缓存层使用方式
- **架构设计**：`2026-04-20-architecture-design.md` — 缓存层模块位置