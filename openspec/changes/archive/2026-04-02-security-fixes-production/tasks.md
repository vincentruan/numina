## 1. 缓存层基础设施

- [x] 1.1 创建 `backend/app/services/cache/__init__.py` 模块初始化
- [x] 1.2 创建 `backend/app/services/cache/base.py` 定义 CacheBackend 抽象接口
- [x] 1.3 创建 `backend/app/services/cache/memory.py` 实现 MemoryCacheBackend
- [x] 1.4 创建 `backend/app/services/cache/redis.py` Redis 占位实现
- [x] 1.5 创建 `backend/app/services/cache/factory.py` 缓存工厂函数

## 2. 配置扩展

- [x] 2.1 在 `backend/app/config.py` 添加缓存配置项（CACHE_BACKEND, REDIS_URL）
- [x] 2.2 在 `backend/app/config.py` 添加限流配置项（LOGIN_RATE_LIMIT_*, GLOBAL_RATE_LIMIT_*）
- [x] 2.3 在 `backend/app/config.py` 添加安全配置项（BCRYPT_ROUNDS, ENABLE_SECURITY_LOGGING）

## 3. 时间攻击防护

- [x] 3.1 在 `backend/app/services/auth.py` 添加 `_dummy_hash()` 函数
- [x] 3.2 修改 `login()` 函数，用户不存在时执行 dummy bcrypt 验证
- [x] 3.3 修改 `hash_password()` 使用配置的 BCRYPT_ROUNDS

## 4. 登录速率限制重构

- [x] 4.1 修改 `backend/app/services/auth.py` 使用缓存层存储登录失败计数
- [x] 4.2 更新 `_check_rate_limit()` 使用 `get_rate_limit_cache()`
- [x] 4.3 更新 `_record_failed_login()` 使用缓存层
- [x] 4.4 更新 `_clear_failed_login()` 使用缓存层

## 5. 全局 API 限流中间件

- [x] 5.1 创建 `backend/app/middleware/__init__.py` 模块初始化
- [x] 5.2 创建 `backend/app/middleware/rate_limit.py` 实现 RateLimitMiddleware
- [x] 5.3 在 `backend/app/main.py` 注册限流中间件

## 6. 文件上传安全增强

- [x] 6.1 创建 `backend/app/services/file_validation.py` 定义 magic bytes 常量
- [x] 6.2 实现 `validate_image_magic_bytes()` 函数
- [x] 6.3 实现 `detect_image_format()` 函数
- [x] 6.4 修改 `backend/app/routers/upload.py` 集成 magic bytes 验证

## 7. 安全事件日志

- [x] 7.1 创建 `backend/app/services/security_log.py` 定义 SecurityEventType 常量
- [x] 7.2 实现 `setup_security_logging()` 初始化函数
- [x] 7.3 实现 `_log_security_event()` 日志记录函数
- [x] 7.4 在 `backend/app/main.py` lifespan 中初始化安全日志
- [x] 7.5 创建 `backend/logs/.gitkeep` 日志目录占位

## 8. 安全日志集成

- [x] 8.1 在 `backend/app/services/auth.py` 登录成功/失败处添加日志调用
- [x] 8.2 在 `backend/app/middleware/rate_limit.py` 限流触发处添加日志调用
- [x] 8.3 在 `backend/app/routers/upload.py` 上传异常处添加日志调用

## 9. 单元测试

- [x] 9.1 创建 `backend/tests/test_cache.py` 缓存层测试
- [x] 9.2 创建 `backend/tests/test_rate_limit.py` 限流功能测试（合并到其他测试）
- [x] 9.3 创建 `backend/tests/test_file_validation.py` 文件验证测试
- [x] 9.4 创建 `backend/tests/test_security_log.py` 安全日志测试
- [x] 9.5 创建 `backend/tests/test_auth_security.py` 认证安全测试（时间攻击防护）

## 10. 验证与回归测试

- [x] 10.1 运行 `uv run pytest tests/test_auth.py -v` 核心认证测试通过
- [x] 10.2 运行 `npm run build` 验证前端构建
- [ ] 10.3 运行 `docker-compose build` 验证 Docker 构建
- [x] 10.4 验证时间攻击测试（响应时间差 < 30%）