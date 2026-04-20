# Architecture Design

**Date:** 2026-04-20
**Status:** Approved
**Scope:** 系统整体架构、模块划分、技术选型

---

## Problem

系统缺乏整体架构文档，新成员难以理解技术选型理由和模块边界。代码组织分散，职责划分不清，导致维护困难和架构腐化。

---

## Goals

1. 明确技术栈和选型理由
2. 定义模块边界和职责
3. 规范分层架构模式
4. 支持多数据库后端扩展

---

## Architecture

### 技术栈

| 层级 | 技术 | 版本 | 选型理由 |
|------|------|------|----------|
| 前端框架 | Vue 3 Composition API | 3.x | 更好的逻辑复用和类型支持 |
| 前端语言 | TypeScript | 5.x | 类型安全，IDE支持完善 |
| 前端构建 | Vite | 8.x | 快速开发服务器，HMR体验好 |
| 前端UI | Vant 4 | 4.x | 成熟移动端组件库，中文友好 |
| 前端图表 | ECharts | 5.x | 强大的可视化能力 |
| 前端状态 | Pinia | 2.x | Vue 3 官方状态管理 |
| 后端框架 | FastAPI | 0.100+ | 高性能、自动文档、类型安全 |
| 后端语言 | Python | 3.11 | 开发效率高，生态丰富 |
| 后端ORM | SQLAlchemy | 2.x | Mapped类型注解，现代API |
| 数据库 | SQLite | 默认 | 轻量级、零配置、适合家庭场景 |
| 数据库 | MySQL | 可选 | 支持多用户、高性能场景 |
| 数据库 | PostgreSQL | 可选 | 企业级、扩展性强 |
| 认证 | JWT | bcrypt | 标准认证方案、密码哈希安全 |
| 部署 | Docker Compose | — | 容器化部署、环境一致性 |
| 反向代理 | Nginx | — | SSL、静态资源、负载均衡 |

### 三层架构

系统采用严格的三层架构：

**API 层（routers）**：
- 处理 HTTP 请求和响应
- 参数验证（Pydantic schemas）
- 调用服务层
- 不包含业务逻辑

**服务层（services）**：
- 业务逻辑实现
- 数据聚合和计算
- 跨模块协调
- 不直接操作数据库

**数据层（models）**：
- SQLAlchemy ORM 模型
- 数据持久化
- 基础 CRUD 操作

依赖方向：routers → services → models（单向依赖）

### 模块划分

| 模块 | 目录 | 职责 |
|------|------|------|
| auth | `backend/app/auth/` | JWT生成、验证、用户认证依赖 |
| models | `backend/app/models/` | 数据实体定义 |
| routers | `backend/app/routers/` | API端点处理 |
| services | `backend/app/services/` | 业务逻辑实现 |
| schemas | `backend/app/schemas/` | 请求/响应数据结构 |
| seed | `backend/app/seed/` | 系统数据初始化（分类、币种） |
| middleware | `backend/app/middleware/` | 请求中间件（速率限制） |
| cache | `backend/app/services/cache/` | 缓存抽象层 |

---

## Implementation Details

### 多数据库后端支持

通过 `DATABASE_URL` 配置切换数据库：

| 配置 | 格式 |
|------|------|
| SQLite | `sqlite:///./data/numina.db` |
| MySQL | `mysql+pymysql://user:pass@host:3306/db` |
| PostgreSQL | `postgresql+psycopg2://user:pass@host:5432/db` |

数据库工厂位于 `backend/app/db/factory.py`：
```python
def get_engine(database_url: str) -> Engine:
    if database_url.startswith("sqlite"):
        return create_sqlite_engine(database_url)
    elif database_url.startswith("mysql"):
        return create_mysql_engine(database_url)
    elif database_url.startswith("postgresql"):
        return create_postgres_engine(database_url)
```

连接池配置（MySQL/PostgreSQL）：
- pool_size: 10
- max_overflow: 20
- pool_recycle: 3600

### 定时任务调度

使用 APScheduler 实现定时任务：

| 任务 | 触发时间 | 说明 |
|------|----------|------|
| 汇率更新 | 08:00-23:00 每2小时 | 调用汇率 API |
| 快照生成 | 每日 00:00 | 记录净资产快照 |

调度器配置（`backend/app/scheduler.py`）：
```python
from apscheduler.schedulers.background import BackgroundScheduler

scheduler = BackgroundScheduler()

def setup_scheduler():
    # 汇率更新：08:00-23:00，每2小时，随机0-15分钟偏移
    for hour in [8, 10, 12, 14, 16, 18, 20, 22]:
        offset = random.randint(0, 15)
        scheduler.add_job(fetch_rates, 'cron', hour=hour, minute=offset)
    
    # 快照生成：每日 00:00
    scheduler.add_job(generate_snapshots, 'cron', hour=0, minute=0)
    
    scheduler.start()
```

### 文件上传服务

文件存储位置：`backend/uploads/`（Docker内 `/app/uploads`）

支持的图片格式：
- JPEG（magic bytes: `FF D8 FF`）
- PNG（magic bytes: `89 50 4E 47 0D 0A 1A 0A`）
- WebP（magic bytes: `52 49 46 46` + `57 45 42 50`）

最大文件大小：5MB
访问路径：`/uploads/<filename>`

### 错误处理机制

统一错误响应格式：
```json
{
  "detail": "中文错误信息"
}
```

HTTP 状态码规范：
- 200: 成功（GET、PUT）
- 201: 创建成功（POST）
- 400: 参数错误
- 401: 认证失败
- 403: 权限不足
- 404: 资源不存在
- 409: 冲突（重复资源）
- 429: 请求过多（限流）
- 500: 服务器错误

### 缓存层结构

`backend/app/services/cache/` 目录结构：

| 文件 | 职责 |
|------|------|
| `base.py` | `CacheBackend` 抽象接口 |
| `memory.py` | `MemoryCacheBackend` 实现 |
| `redis.py` | `RedisCacheBackend` 占位（未实现） |
| `factory.py` | `get_cache_backend()` 工厂函数 |

接口方法：
- `get(key)` - 获取缓存值
- `set(key, value, ttl_seconds)` - 设置缓存（可选TTL）
- `delete(key)` - 删除缓存
- `increment(key, delta)` - 递增计数器
- `get_ttl(key)` - 获取剩余TTL
- `clear()` - 清空缓存

### 中间件层结构

`backend/app/middleware/` 目录结构：

| 文件 | 职责 |
|------|------|
| `rate_limit.py` | `RateLimitMiddleware` - 全局API限流 |

限流配置：
- `LOGIN_RATE_LIMIT_MAX_ATTEMPTS`: 5次
- `LOGIN_RATE_LIMIT_LOCKOUT_SECONDS`: 900秒（15分钟）
- `GLOBAL_RATE_LIMIT_PER_MINUTE`: 100次

### 安全服务结构

`backend/app/services/` 安全相关文件：

| 文件 | 职责 |
|------|------|
| `file_validation.py` | 文件上传验证（magic bytes） |
| `security_log.py` | 安全事件日志记录 |

---

## Code Pointers

| 入口 | 文件路径 |
|------|----------|
| 主应用 | `backend/app/main.py` |
| 配置 | `backend/app/config.py` |
| 数据库引擎 | `backend/app/database.py` |
| 数据库工厂 | `backend/app/db/factory.py` |
| 调度器 | `backend/app/scheduler.py` |
| 认证依赖 | `backend/app/auth/deps.py` |
| 缓存层 | `backend/app/services/cache/` |
| 中间件 | `backend/app/middleware/` |

---

## Related Specs

- **数据模型**：`2026-04-20-data-models-design.md` — models 目录结构
- **API规范**：`2026-04-20-api-spec-design.md` — routers 目录结构
- **缓存层设计**：`2026-04-20-cache-layer-design.md` — cache 目录详解
- **速率限制**：`2026-04-20-rate-limiting-design.md` — middleware 目录详解