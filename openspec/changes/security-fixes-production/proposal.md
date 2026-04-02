## Why

Numina 即将部署到生产环境，安全审计发现多个安全隐患需要修复：
1. 登录存在时间攻击漏洞（响应耗时暴露用户名是否存在）
2. 速率限制使用内存存储，服务重启后失效
3. 缺乏全局 API 限流，仅登录端点有保护
4. 文件上传仅验证扩展名，可被伪装文件绕过
5. 无安全事件日志，无法审计攻击行为

这些问题必须在生产部署前修复，以防止暴力破解、资源耗尽攻击和恶意文件上传。

## What Changes

- **时间攻击防护**: 登录失败时对不存在用户也执行 bcrypt 验证，确保响应时间一致
- **缓存抽象层**: 创建可扩展的缓存接口，内存实现 + Redis 预留，用于速率限制
- **bcrypt 配置**: 显式配置 bcrypt rounds（默认 12），提升密码哈希健壮性
- **全局 API 限流**: 添加中间件对所有 API 端点实施速率限制（100 次/分钟）
- **文件上传安全**: 使用 magic bytes 验证文件真实格式，拒绝伪装文件
- **安全事件日志**: 结构化日志服务，记录登录失败、限流触发、上传异常等安全事件

## Capabilities

### New Capabilities

- `cache-layer`: 可扩展的缓存抽象层（CacheBackend 接口 + MemoryCache 实现 + Redis 占位），用于速率限制和未来分布式部署
- `rate-limiting`: 全局 API 速率限制系统（登录端点专用限流 + 全局中间件），防范暴力破解和 DDoS
- `security-logging`: 安全事件日志服务，记录认证失败、限流触发、文件上传异常等安全事件
- `file-upload-security`: 文件上传安全增强，使用 magic bytes 验证真实文件格式

### Modified Capabilities

- `api-spec`: 修改认证端点行为（登录响应时间恒定、bcrypt rounds 配置）
- `architecture`: 新增缓存层和中间件层模块

## Impact

**新增文件 (9 个)**:
- `backend/app/services/cache/__init__.py`
- `backend/app/services/cache/base.py`
- `backend/app/services/cache/memory.py`
- `backend/app/services/cache/redis.py`
- `backend/app/services/cache/factory.py`
- `backend/app/middleware/__init__.py`
- `backend/app/middleware/rate_limit.py`
- `backend/app/services/file_validation.py`
- `backend/app/services/security_log.py`

**修改文件 (4 个)**:
- `backend/app/config.py` - 新增安全配置项（BCRYPT_ROUNDS, CACHE_BACKEND, 限流参数）
- `backend/app/services/auth.py` - 时间攻击防护、缓存层集成、bcrypt 配置
- `backend/app/routers/upload.py` - Magic bytes 验证集成
- `backend/app/main.py` - 注册限流中间件、初始化安全日志

**测试文件 (5 个)**:
- `backend/tests/test_cache.py`
- `backend/tests/test_rate_limit.py`
- `backend/tests/test_file_validation.py`
- `backend/tests/test_security_log.py`
- `backend/tests/test_auth_security.py`

**配置影响**:
新增可选环境变量（均有默认值，向后兼容）：
- `CACHE_BACKEND=memory`
- `REDIS_URL=redis://localhost:6379/0`
- `LOGIN_RATE_LIMIT_MAX_ATTEMPTS=5`
- `LOGIN_RATE_LIMIT_LOCKOUT_SECONDS=900`
- `GLOBAL_RATE_LIMIT_PER_MINUTE=100`
- `BCRYPT_ROUNDS=12`
- `ENABLE_SECURITY_LOGGING=true`