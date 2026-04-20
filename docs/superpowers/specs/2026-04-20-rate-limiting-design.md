# Rate Limiting Design

**Date:** 2026-04-20
**Status:** Approved
**Scope:** API 速率限制，防止滥用和攻击

---

## Problem

API 缺乏速率限制保护，容易遭受暴力破解和滥用攻击。恶意用户可以无限尝试登录或高频请求 API，消耗系统资源并威胁账户安全。

---

## Goals

1. 防止登录暴力破解攻击
2. 保护 API 端点免受滥用
3. 提供公平的服务访问
4. 支持限流配置灵活调整

---

## Architecture

### 双层限流策略

**登录专用限流**：
- 策略：按用户名限流（防止针对特定账户攻击）
- 触发条件：同一用户名连续失败 5 次
- 惩罚：锁定 15 分钟
- 存储位置：缓存层（内存或 Redis）

**全局 API 限流**：
- 策略：按客户端标识限流
- 限制：每个客户端 100 次/分钟
- 跳过端点：健康检查、登录、注册
- 客户端标识：已认证用 token 前缀，未认证用 IP

### 限流组件位置

```
backend/app/middleware/rate_limit.py
├── LoginRateLimiter      # 登录专用限流器
├── GlobalRateLimiter     # 全局 API 限流器
└── RateLimitMiddleware   # FastAPI 中间件
```

依赖缓存层：`backend/app/services/cache/`

---

## Implementation Details

### 登录限流逻辑

```python
class LoginRateLimiter:
    MAX_ATTEMPTS = 5  # 最大失败次数
    LOCKOUT_SECONDS = 900  # 锁定时间（15分钟）
    
    def check_lockout(self, username: str, cache: CacheBackend) -> int | None:
        """检查是否被锁定，返回剩余锁定分钟数"""
        key = f"login_lockout:{username}"
        ttl = cache.get_ttl(key)
        if ttl and ttl > 0:
            return int(ttl / 60)
        return None
    
    def record_failure(self, username: str, cache: CacheBackend) -> None:
        """记录登录失败"""
        key = f"login_attempts:{username}"
        count = cache.increment(key)
        
        if count >= self.MAX_ATTEMPTS:
            # 锁定账户
            lockout_key = f"login_lockout:{username}"
            cache.set(lockout_key, True, ttl_seconds=self.LOCKOUT_SECONDS)
            # 清除失败计数
            cache.delete(key)
    
    def clear_lockout(self, username: str, cache: CacheBackend) -> None:
        """登录成功后清除锁定"""
        cache.delete(f"login_attempts:{username}")
        cache.delete(f"login_lockout:{username}")
```

### 全局 API 限流逻辑

```python
class GlobalRateLimiter:
    LIMIT_PER_MINUTE = 100
    
    SKIP_PATHS = [
        "/api/health",
        "/api/v1/auth/login",
        "/api/v1/auth/register",
    ]
    
    def get_client_id(self, request: Request) -> str:
        """获取客户端标识"""
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            # 使用 token 前缀（前8字符）作为标识
            return f"token:{auth_header[7:15]}"
        else:
            # 使用 IP 地址
            return f"ip:{request.client.host}"
    
    def check_limit(self, client_id: str, cache: CacheBackend) -> bool:
        """检查是否超限，返回 True 表示允许"""
        key = f"global_rate:{client_id}"
        count = cache.get(key) or 0
        
        if count >= self.LIMIT_PER_MINUTE:
            return False
        
        # 递增计数（1分钟 TTL）
        ttl = cache.get_ttl(key)
        if ttl is None:
            cache.set(key, 1, ttl_seconds=60)
        else:
            cache.increment(key)
        
        return True
```

### 中间件集成

```python
class RateLimitMiddleware:
    async def dispatch(self, request: Request, call_next):
        # 跳过不需要限流的端点
        if request.url.path in self.global_limiter.SKIP_PATHS:
            return await call_next(request)
        
        # 全局限流检查
        client_id = self.global_limiter.get_client_id(request)
        if not self.global_limiter.check_limit(client_id, self.cache):
            return JSONResponse(
                status_code=429,
                content={"detail": "请求次数过多，请稍后重试"}
            )
        
        return await call_next(request)
```

### 登录端点集成

在 `backend/app/routers/auth.py` 的 `login()` 函数中：

```python
@router.post("/login")
def login(form: LoginForm, cache: CacheBackend = Depends(get_cache_backend)):
    limiter = LoginRateLimiter()
    
    # 1. 检查锁定状态
    lockout_minutes = limiter.check_lockout(form.username, cache)
    if lockout_minutes:
        SecurityLogService.log("login_rate_limited", username=form.username)
        raise HTTPException(429, f"登录失败次数过多，请 {lockout_minutes} 分钟后重试")
    
    # 2. 验证用户
    user = authenticate_user(form.username, form.password)
    
    if not user:
        # 记录失败
        limiter.record_failure(form.username, cache)
        SecurityLogService.log("login_failed_wrong_password", username=form.username)
        raise HTTPException(401, "用户名或密码错误")
    
    # 3. 登录成功，清除锁定
    limiter.clear_lockout(form.username, cache)
    SecurityLogService.log("login_success", username=form.username, user_id=user.id)
    
    return create_tokens(user)
```

### 配置项

```python
class Settings(BaseSettings):
    LOGIN_RATE_LIMIT_MAX_ATTEMPTS: int = 5
    LOGIN_RATE_LIMIT_LOCKOUT_SECONDS: int = 900
    GLOBAL_RATE_LIMIT_PER_MINUTE: int = 100
```

---

## Design Trade-offs

| 决策 | 优势 | 局限性 | 缓解措施 |
|------|------|----------|----------|
| 用户名限流 | 防止针对特定账户的暴力破解 | 攻击者可尝试不同用户名绕过 | 全局 API 限流仍按 IP 标识 |
| 内存存储 | 简单、无外部依赖 | 单 worker 正常，多 worker 时实际阈值 = worker数 × 配置阈值 | 提供 Redis 后端选项；或使用 Nginx 限流 |
| Token 前缀标识 | 精确区分不同用户 | Token 刷新后前缀变化 | 1分钟窗口内影响很小 |

---

## Verification

**测试场景**（`tests/test_rate_limit.py`）：
- 健康检查端点不受限流（跳过列表验证）
- 同一用户连续 5 次登录失败后被锁定
- 锁定后登录返回 429 + 剩余分钟数
- 登录成功后清除锁定状态
- 同一客户端 1 分钟内请求超过 100 次返回 429
- 不同客户端独立计数（token vs IP）

---

## Code Pointers

| 功能 | 文件路径 |
|------|----------|
| 登录限流器 | `backend/app/middleware/rate_limit.py` |
| 全局限流器 | `backend/app/middleware/rate_limit.py` |
| 中间件 | `backend/app/middleware/rate_limit.py` |
| 登录集成 | `backend/app/routers/auth.py` |
| 缓存层 | `backend/app/services/cache/` |
| 配置项 | `backend/app/config.py` |

---

## Related Specs

- **缓存层设计**：`2026-04-20-cache-layer-design.md` — 限流状态存储
- **安全日志设计**：`2026-04-20-security-logging-design.md` — 限流事件日志
- **API规范设计**：`2026-04-20-api-spec-design.md` — 429 响应格式