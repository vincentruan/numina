# Security Logging Design

**Date:** 2026-04-20
**Status:** Approved
**Scope:** 安全事件日志记录和审计

---

## Problem

安全事件缺乏统一日志记录，审计追溯困难。登录失败、限流触发、文件上传异常等关键事件没有结构化日志，无法发现异常行为和支持安全分析。

---

## Goals

1. 记录关键安全事件到独立日志文件
2. 使用结构化格式便于分析和查询
3. 实现日志轮转避免文件过大
4. 提供配置开关控制日志记录

---

## Architecture

### 安全日志服务设计

独立日志文件：`logs/security.log`
独立日志 Handler：`TimedRotatingFileHandler`
独立 Logger：`security_logger`

日志服务位于 `backend/app/services/security_log.py`，提供统一的日志记录接口。

### 日志事件类型

| 事件类型 | 级别 | 触发时机 |
|----------|------|----------|
| login_success | INFO | 登录成功 |
| login_failed_wrong_password | WARNING | 密码错误 |
| login_failed_user_not_found | WARNING | 用户不存在 |
| login_rate_limited | WARNING | 登录限流触发 |
| global_rate_limited | WARNING | 全局限流触发 |
| upload_magic_bytes_mismatch | WARNING | 文件格式不匹配 |
| token_refresh_success | INFO | Token 刷新成功 |
| token_refresh_failed | WARNING | Token 刷新失败 |

---

## Implementation Details

### 日志格式

结构化格式：`<timestamp> - <level> - [<event_type>] <key=value> | <key=value>`

示例：
```
2026-04-20 10:30:00 - INFO - [login_success] username=testuser | user_id=1
2026-04-20 10:31:00 - WARNING - [login_failed_wrong_password] username=testuser
2026-04-20 10:32:00 - WARNING - [login_rate_limited] username=testuser | lockout_minutes=15
```

### SecurityLogService 实现

```python
import logging
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

class SecurityLogService:
    _logger: logging.Logger | None = None
    
    @classmethod
    def init(cls, log_dir: str = "logs") -> None:
        Path(log_dir).mkdir(exist_ok=True)
        
        handler = TimedRotatingFileHandler(
            filename=f"{log_dir}/security.log",
            when="midnight",
            interval=1,
            backupCount=7,
            encoding="utf-8"
        )
        handler.suffix = "%Y-%m-%d"
        
        cls._logger = logging.getLogger("security")
        cls._logger.setLevel(logging.INFO)
        cls._logger.addHandler(handler)
    
    @classmethod
    def log(cls, event_type: str, level: str = "INFO", **kwargs) -> None:
        if not cls._logger or not settings.ENABLE_SECURITY_LOGGING:
            return
        
        key_value_pairs = " | ".join(f"{k}={v}" for k, v in kwargs.items())
        message = f"[{event_type}] {key_value_pairs}"
        
        log_level = logging.WARNING if level == "WARNING" else logging.INFO
        cls._logger.log(log_level, message)
```

### 初始化时机

在 `main.py` 的 lifespan 中初始化：

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时初始化安全日志
    SecurityLogService.init()
    
    yield
    
    # 关闭时清理
    SecurityLogService.shutdown()
```

### 日志轮转配置

| 配置项 | 值 | 说明 |
|--------|-----|------|
| when | midnight | 每天午夜轮转 |
| interval | 1 | 每天 |
| backupCount | 7 | 保留 7 天 |
| suffix | %Y-%m-%d | 文件后缀格式 |

轮转后文件命名：`security.log.2026-04-19`

### 配置开关

```python
class Settings(BaseSettings):
    ENABLE_SECURITY_LOGGING: bool = True
```

---

## Examples

### 记录登录成功

```python
SecurityLogService.log(
    event_type="login_success",
    level="INFO",
    username="testuser",
    user_id="1"
)
```

### 记录登录限流

```python
SecurityLogService.log(
    event_type="login_rate_limited",
    level="WARNING",
    username="testuser",
    lockout_minutes=15
)
```

### 记录文件上传异常

```python
SecurityLogService.log(
    event_type="upload_magic_bytes_mismatch",
    level="WARNING",
    user_id="1",
    claimed_format="jpg",
    actual_format="png"
)
```

---

## Verification

- 登录成功后，`logs/security.log` 包含 `[login_success]` 记录
- 登录失败后，日志级别为 WARNING
- 日志文件到达午夜后自动轮转
- 配置 `ENABLE_SECURITY_LOGGING=false` 后不记录日志
- 日志文件超过 7 天后自动删除

---

## Code Pointers

| 功能 | 文件路径 |
|------|----------|
| 安全日志服务 | `backend/app/services/security_log.py` |
| 初始化 | `backend/app/main.py` lifespan |
| 配置项 | `backend/app/config.py` |
| 登录日志调用 | `backend/app/routers/auth.py` |
| 限流日志调用 | `backend/app/middleware/rate_limit.py` |

---

## Related Specs

- **速率限制设计**：`2026-04-20-rate-limiting-design.md` — 限流事件日志
- **文件上传安全**：`2026-04-20-file-upload-security-design.md` — 上传异常日志