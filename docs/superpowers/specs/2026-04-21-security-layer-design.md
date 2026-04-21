# Security Layer Design

**Date:** 2026-04-21
**Status:** Approved
**Scope:** 安全事件日志、文件上传验证、认证安全防护

---

## Problem

1. 安全事件缺乏统一日志记录，审计追溯困难
2. 文件上传仅依赖扩展名验证，攻击者可上传伪装文件
3. 登录接口可能被用于用户名枚举攻击

---

## Goals

1. 记录关键安全事件到独立日志文件
2. 使用 magic bytes 验证文件真实格式
3. 防止用户名枚举攻击（恒定响应时间）
4. 统一登录错误信息不区分原因

---

## Architecture

### 安全日志服务设计

独立日志文件：`logs/security.log`
独立日志 Handler：`TimedRotatingFileHandler`
独立 Logger：`security_logger`

日志服务位于 `backend/app/services/security_log.py`。

### 文件验证流程

```
用户上传文件 → 检查文件长度（>=12 bytes） → 读取头部 magic bytes → 
验证与声明格式匹配 → 匹配则存储 → 不匹配则拒绝并记录日志
```

验证服务位于 `backend/app/services/file_validation.py`。

### 认证安全策略

**恒定响应时间**：用户不存在时执行 dummy bcrypt 验证，消耗与正常验证相同时间。

**统一错误信息**：登录失败不区分原因，统一返回"用户名或密码错误"。

---

## Implementation Details

### 安全日志事件类型

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

### 日志格式

结构化格式：`<timestamp> - <level> - [<event_type>] <key=value> | <key=value>`

示例：
```
2026-04-21 10:30:00 - INFO - [login_success] username=testuser | user_id=1
2026-04-21 10:31:00 - WARNING - [login_failed_wrong_password] username=testuser
2026-04-21 10:32:00 - WARNING - [login_rate_limited] username=testuser | lockout_minutes=15
```

### SecurityLogService 实现

```python
class SecurityLogService:
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
        cls._logger = logging.getLogger("security")
        cls._logger.setLevel(logging.INFO)
        cls._logger.addHandler(handler)
    
    @classmethod
    def log(cls, event_type: str, level: str = "INFO", **kwargs) -> None:
        key_value_pairs = " | ".join(f"{k}={v}" for k, v in kwargs.items())
        message = f"[{event_type}] {key_value_pairs}"
        cls._logger.log(log_level, message)
```

### Magic Bytes 定义

| 格式 | Magic Bytes | 长度 |
|------|-------------|------|
| JPEG | `FF D8 FF` | 3 bytes |
| PNG | `89 50 4E 47 0D 0A 1A 0A` | 8 bytes |
| WebP | `52 49 46 46` + `57 45 42 50` (offset 8-11) | 12 bytes |

### FileValidationService 实现

```python
class FileValidationService:
    MAGIC_BYTES = {
        "jpg": bytes([0xFF, 0xD8, 0xFF]),
        "png": bytes([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A]),
        "webp": bytes([0x52, 0x49, 0x46, 0x46]),
    }
    WEBP_SIGNATURE = bytes([0x57, 0x45, 0x42, 0x50])
    
    @classmethod
    def detect_image_format(cls, content: bytes) -> str | None:
        if len(content) < 12:
            return None
        if content[:3] == cls.MAGIC_BYTES["jpg"]:
            return "jpg"
        if content[:8] == cls.MAGIC_BYTES["png"]:
            return "png"
        if content[:4] == cls.MAGIC_BYTES["webp"] and content[8:12] == cls.WEBP_SIGNATURE:
            return "webp"
        return None
    
    @classmethod
    def validate_image(cls, content: bytes, claimed_format: str) -> bool:
        detected = cls.detect_image_format(content)
        if detected != claimed_format.lower():
            SecurityLogService.log("upload_magic_bytes_mismatch", level="WARNING", 
                claimed_format=claimed_format, actual_format=detected or "unknown")
            return False
        return True
```

### 恒定响应时间实现

```python
@router.post("/login")
def login(form: LoginForm, cache: CacheBackend = Depends(get_cache_backend)):
    user = authenticate_user(form.username, form.password)
    
    # 用户不存在时执行 dummy bcrypt，消耗相同时间
    if not user:
        bcrypt.checkpw("dummy_password", bcrypt.hashpw("dummy", bcrypt.gensalt()))
        SecurityLogService.log("login_failed_user_not_found", username=form.username)
        raise HTTPException(401, "用户名或密码错误")
    
    # 正常登录流程
    ...
```

### 统一错误信息

不提示以下具体原因：
- 用户不存在
- 密码错误
- 账户锁定

统一返回："用户名或密码错误"

---

## Code Pointers

| 功能 | 文件路径 |
|------|----------|
| 安全日志服务 | `backend/app/services/security_log.py` |
| 文件验证服务 | `backend/app/services/file_validation.py` |
| 上传路由 | `backend/app/routers/upload.py` |
| 登录路由 | `backend/app/routers/auth.py` |

---

## Related Specs

- **API层设计**：`2026-04-21-api-layer-design.md` — 限流集成、登录端点
- **数据层设计**：`2026-04-21-data-layer-design.md` — 缓存层（限流状态存储）