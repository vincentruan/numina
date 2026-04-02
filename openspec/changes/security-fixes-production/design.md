## Context

Numina 家庭资产管理系统即将部署到生产环境，安全审计发现以下隐患：
- 登录存在时间攻击漏洞（响应耗时暴露用户名存在性）
- 速率限制使用内存字典，服务重启后失效
- 缺乏全局 API 限流保护
- 文件上传仅验证扩展名，可被伪装文件绕过
- 无安全事件日志，无法审计攻击

当前架构采用 FastAPI + SQLAlchemy，认证使用 JWT + bcrypt。速率限制在 `auth.py` 中使用全局内存字典实现。系统为单机部署，未来可能扩展到集群。

## Goals / Non-Goals

**Goals:**
- 修复登录时间攻击漏洞，确保响应时间恒定
- 创建可扩展的缓存抽象层，当前使用内存，预留 Redis 扩展
- 实现全局 API 速率限制（100 次/分钟）
- 增强文件上传安全，使用 magic bytes 验证真实格式
- 添加安全事件日志服务
- 显式配置 bcrypt rounds（12）

**Non-Goals:**
- 不实现 Redis 缓存后端（仅预留接口占位）
- 不实现 IP 黑名单或自动封禁
- 不修改前端代码
- 不修改现有 API 响应格式

## Decisions

### D1: 缓存抽象层设计

**Decision:** 使用 ABC 抽象基类定义 `CacheBackend` 接口，提供 `MemoryCacheBackend` 实现，预留 `RedisCacheBackend` 占位。

**Alternatives Considered:**
- 直接使用 Redis：不选，增加部署复杂度，单机部署不需要
- 继续使用内存字典：不选，不可扩展，未来集群部署需重构
- 使用第三方库（如 `cachetools`）：不选，接口不匹配速率限制需求（increment、TTL）

**Rationale:** 抽象层允许未来无缝切换到 Redis，当前内存实现满足单机需求。

### D2: 时间攻击防护方案

**Decision:** 当用户不存在时，执行 dummy bcrypt 验证，使响应时间与正常验证一致。

**Alternatives Considered:**
- 固定延时（如 `time.sleep(0.2)`）：不选，时间不精确，可能被统计分析破解
- 响应时间随机化：不选，复杂度高，效果不如恒定时间

**Rationale:** bcrypt 验证耗时约 200-300ms，dummy 验证可确保两种情况耗时一致。

### D3: 全局限流中间件

**Decision:** 使用 `BaseHTTPMiddleware` 实现全局限流，按 IP/用户标识限流，跳过登录端点（已有专用限流）。

**Alternatives Considered:**
- Nginx 层限流：不选，缺乏灵活性，无法按用户标识限流
- slowapi 库：不选，引入新依赖，且与现有缓存抽象层不一致

**Rationale:** 中间件层限流允许使用缓存抽象层，未来可无缝切换到 Redis 分布式限流。

### D4: 文件验证方案

**Decision:** 使用 magic bytes（文件头）验证图片格式，支持 JPEG/PNG/WebP。

**Alternatives Considered:**
- `imghdr` 库：不选，Python 3.11+ 已移除
- `filetype` 库：不选，引入新依赖
- 仅验证扩展名：不选，安全风险

**Rationale:** Magic bytes 是行业标准方法，无需额外依赖，实现简单可靠。

### D5: 日志存储方案

**Decision:** 使用 Python 标准 `logging` 模块，写入本地文件 `logs/security.log`。

**Alternatives Considered:**
- 结构化 JSON 日志：不选，当前需求简单，JSON 格式增加复杂度
- 日志聚合系统（如 Loki）：不选，单机部署不需要

**Rationale:** 标准日志模块足够满足审计需求，未来可接入日志聚合系统。

## Risks / Trade-offs

### Risk: 内存缓存占用过多
→ **Mitigation:** 缓存仅存储速率限制计数器（整数），每条记录约 50 bytes，限制最多 10000 条（约 500KB）

### Risk: bcrypt dummy 验证增加登录延迟
→ **Trade-off:** 每次登录增加约 200-300ms 延迟，换取时间攻击防护，安全优先

### Risk: 全局限流误杀正常用户
→ **Mitigation:** 限流阈值设为 100 次/分钟，足够正常使用；提供 429 响应和中文提示

### Risk: Magic bytes 验证不完整
→ **Mitigation:** 验证前 12 bytes，覆盖 JPEG/PNG/WebP 标准头；定期更新 magic bytes 定义

### Risk: 日志文件过大
→ **Mitigation:** 配置日志轮转（保留 7 天）；生产环境可接入日志聚合

### Trade-off: 不实现 Redis 后端
→ **Impact:** 集群部署时需实现 Redis 后端；当前预留接口，改动量小