---
title: Numina 日志配置最佳实践
date: 2026-05-14
category: best-practices
module: backend
problem_type: best_practice
component: logging
severity: medium
tags: [logging, log-rotation, log-config, log-archival, log-cleanup, log-retention]
last_refreshed: 2026-07-31
---

# Numina 日志配置最佳实践

## Context

Numina 后端需要统一、可配置的日志基础设施，涵盖：
- 应用日志与安全事件日志的统一管理
- 日志文件轮转，防止单文件无限增长
- 旧日志归档压缩，节省磁盘空间
- 过期日志自动清理，控制保留周期

这些能力由 `server/packages/core/logging.py` 统一实现，是生产环境稳定运行的基础。

## Guidance

### 1. 统一日志配置模块

日志配置的实际实现位于 `server/packages/core/logging.py`，后端通过 `server/apps/backend/app/core/logging_config.py` 作为再导出（re-export）入口对外暴露。

对外公开的两个入口函数：

- `setup_logging()` — 应用启动时调用，初始化所有 handler、格式和级别，并自动执行一次日志清理
- `get_logger(name)` — 获取配置好的 logger 实例，供各模块使用

**示例场景：**
- 应用启动时调用 `setup_logging()`，系统初始化控制台 handler、文件 handler 和安全日志 handler，并完成一次过期日志清理
- 各模块调用 `get_logger(__name__)` 获取 logger，返回已配置格式和级别的 logger 实例

> 注意：`packages/core/CLAUDE.md` 规定，项目内所有模块必须通过 `get_logger(__name__)` 获取 logger，禁止直接调用 `logging.getLogger()`。

### 2. 日志目录结构

`setup_logging()` 在启动时自动创建日志目录（如不存在）。标准目录结构如下：

```
logs/
├── app.log              # 应用主日志
├── app.log.1            # 轮转备份文件（按大小模式）
├── app.log.1.gz         # 压缩归档（手动调用 archive_old_logs() 后生成，与原文件同目录）
├── security.log         # 安全事件日志
└── security.log.1       # 安全日志轮转备份
```

> 注意：`archive_old_logs()` 将压缩文件写入与原轮转备份**相同的目录**（如 `logs/app.log.1.gz`），不会创建 `archive/` 子目录。

**示例场景：**
- 应用首次启动时 `logs/` 目录不存在，系统自动创建该目录

### 3. 日志轮转

系统支持两种轮转模式，由 `LOG_ROTATION_MODE` 配置项控制：

- **按大小轮转（默认）**：使用 `RotatingFileHandler`，单文件达到 `LOG_MAX_BYTES`（默认 10MB）时轮转，旧文件重命名为带序号后缀（如 `app.log.1`）
- **按时间轮转**：配置 `LOG_ROTATION_MODE=time` 后使用 `TimedRotatingFileHandler`，每天午夜轮转，旧文件重命名为带日期后缀

安全日志（`security.log`）由 `_setup_security_logger()` 内部配置，使用与应用日志相同的轮转模式和 `backup_count`，无需单独配置。

**示例场景：**
- 按大小轮转：日志文件大小达到 10MB，系统自动轮转，创建新的 `app.log`，旧文件重命名为 `app.log.1`
- 按时间轮转：配置 `LOG_ROTATION_MODE=time`，到达午夜时系统自动轮转，旧文件重命名为带日期后缀
- 安全日志轮转：安全日志与应用日志使用相同的轮转模式，无需额外配置

### 4. 日志归档

`archive_old_logs(log_dir, compress_after_days=7)` 将 `logs/` 目录下修改时间超过 `compress_after_days`（默认 7 天）的轮转备份文件（匹配 `*.log.[0-9]*` 模式）压缩为 `.gz` 格式，并删除原文件。

**重要：`archive_old_logs()` 是独立工具函数，不会被 `setup_logging()` 自动调用。** 需要归档能力时，必须在应用代码或定时任务中显式调用。

**示例场景：**
- 显式调用归档：在定时任务中调用 `archive_old_logs(Path("logs"), compress_after_days=7)`，将超过 7 天的轮转备份压缩为 `.gz` 文件
- 已压缩文件不重复处理：若 `.gz` 文件已存在，`archive_old_logs()` 跳过该文件，不重复压缩

### 5. 日志自动清理

`cleanup_old_logs(log_dir, retention_days)` 删除 `logs/` 目录下（含子目录）修改时间超过 `retention_days` 的 `.log`、`.gz` 及轮转备份文件。

**`cleanup_old_logs()` 由 `setup_logging()` 在每次应用启动时自动调用**，无需手动触发。默认保留天数为 30 天（`LOG_RETENTION_DAYS` 默认值）。

**示例场景：**
- 启动时自动清理：应用启动，`setup_logging()` 调用 `cleanup_old_logs()`，删除修改时间超过 30 天的日志文件
- 自定义保留期：配置 `LOG_RETENTION_DAYS=90`，日志文件保留 90 天后才被清理

### 6. 配置项

所有日志配置项在 `config.py` 的 `Settings` 类中定义，通过环境变量覆盖：

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `LOG_LEVEL` | `"INFO"` | 日志级别（DEBUG / INFO / WARNING / ERROR） |
| `LOG_DIR` | `"logs/"` | 日志文件目录 |
| `LOG_MAX_BYTES` | `10485760`（10MB） | 按大小轮转时单文件最大字节数 |
| `LOG_BACKUP_COUNT` | `10` | 保留的轮转备份文件数量 |
| `LOG_ROTATION_MODE` | `"size"` | 轮转模式：`"size"` 或 `"time"` |
| `LOG_FORMAT` | `str | None = None` | 日志格式字符串。为 `None` 时使用内置默认格式 |
| `LOG_RETENTION_DAYS` | `30` | 日志文件保留天数 |

**示例场景：**
- 调整日志级别：配置 `LOG_LEVEL=DEBUG`，系统输出 DEBUG 及以上级别的日志
- 自定义日志目录：配置 `LOG_DIR=/var/log/numina`，日志文件写入该目录
- 切换轮转模式：配置 `LOG_ROTATION_MODE=time`，启用按时间轮转

### 7. 安全日志集成

安全日志通过 `setup_logging()` 内部调用 `_setup_security_logger()` 统一初始化，写入独立的 `logs/security.log` 文件。安全日志使用与应用日志相同的轮转模式和 `backup_count`，无需单独配置轮转参数。

安全事件的记录方式、事件类型和日志格式，参见 [安全审计最佳实践](./security-audit.md)。

**示例场景：**
- 统一初始化：调用 `setup_logging()` 后，安全日志自动使用统一配置的 handler 和格式，无需额外初始化
- 独立日志文件：安全事件写入 `logs/security.log`，与应用日志 `logs/app.log` 分离

## Why This Matters

- **防止磁盘耗尽**：日志轮转限制单文件大小，`backup_count` 控制备份数量，`retention_days` 控制总保留周期，三层机制共同防止日志无限增长
- **可观测性**：统一的日志格式和级别配置，使应用日志与安全日志风格一致，便于日志聚合工具（如 ELK、Loki）解析
- **安全审计**：安全日志独立文件，保留 30 天，满足生产环境安全审计的基本要求
- **零配置启动**：所有配置项均有合理默认值，开发环境无需任何额外配置即可运行

## When to Apply

- 新增后端服务模块时，使用 `get_logger(__name__)` 获取 logger，不要直接调用 `logging.getLogger()`
- 部署到生产环境前，确认 `LOG_DIR` 路径可写，并根据磁盘容量调整 `LOG_RETENTION_DAYS` 和 `LOG_BACKUP_COUNT`
- 需要日志归档压缩时，在定时任务（如 cron）中显式调用 `archive_old_logs()`
- 调查安全事件时，查询 `logs/security.log`；调查应用异常时，查询 `logs/app.log`

## Examples

### 应用启动时初始化日志

```python
# server/apps/backend/app/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from packages.core.logging import setup_logging
from packages.core.settings import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging(
        log_level=settings.LOG_LEVEL,
        log_dir=settings.LOG_DIR,
        max_bytes=settings.LOG_MAX_BYTES,
        backup_count=settings.LOG_BACKUP_COUNT,
        rotation_mode=settings.LOG_ROTATION_MODE,
        retention_days=settings.LOG_RETENTION_DAYS,
        log_format=settings.LOG_FORMAT,
    )
    yield


app = FastAPI(lifespan=lifespan)
```

### 各模块获取 logger

```python
# 任意后端模块
from packages.core.logging import get_logger

logger = get_logger(__name__)

logger.info("资产创建成功 asset_id=%s", asset_id)
logger.warning("查询超时 duration=%.2fs", duration)
logger.error("数据库连接失败: %s", str(exc))
```

### 手动触发日志归档（定时任务）

```python
from pathlib import Path
from packages.core.logging import archive_old_logs

# 在定时任务或管理脚本中显式调用
compressed = archive_old_logs(Path("logs"), compress_after_days=7)
print(f"已归档 {compressed} 个日志文件")
```

### 生产环境配置示例（.env）

```dotenv
LOG_LEVEL=INFO
LOG_DIR=/var/log/numina
LOG_MAX_BYTES=10485760
LOG_BACKUP_COUNT=10
LOG_ROTATION_MODE=size
LOG_RETENTION_DAYS=30
```

### 日志输出格式示例

```
# logs/app.log
2026-05-14 10:00:01 - app.routers.assets - INFO - 资产创建成功 asset_id=123456789012345
2026-05-14 10:01:30 - app.routers.auth - WARNING - 登录失败次数过多 username=testuser

# logs/security.log
2026-05-14 10:00:00 - INFO - [login_success] username=testuser | user_id=1
2026-05-14 10:01:30 - WARNING - [login_rate_limited] username=testuser
```

## Related

- [安全审计最佳实践](./security-audit.md) — 安全事件日志和文件上传安全
- [安全防护最佳实践](./security-protection.md) — 速率限制和缓存层
- 注：原始 OpenSpec 规范已保存在 git 历史中，路径为 `server/apps/backend/openspec/`
