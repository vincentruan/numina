---
title: Numina 安全审计最佳实践
date: 2026-04-02
category: best-practices
module: security
problem_type: best_practice
component: documentation
severity: high
tags: [security, logging, audit, file-upload, magic-bytes]
---

# Numina 安全审计最佳实践

## Context

Numina 生产环境需要完善的安全审计能力，包括：
- 缺乏安全事件日志，无法审计攻击行为
- 文件上传仅验证扩展名，可被伪装文件绕过

这些审计措施帮助发现和追溯安全事件，是生产环境必备的安全基础设施。

## Guidance

### 安全日志

#### 1. 记录安全事件日志

必须记录以下安全事件到 `logs/security.log`：
- 登录成功
- 登录失败（用户不存在、密码错误）
- 登录限流触发
- 全局限流触发
- 文件上传格式不匹配
- Token 刷新成功/失败

**示例场景：**
- 记录登录成功事件：用户登录成功，日志记录 `[login_success] username=<name> user_id=<id>`
- 记录登录失败事件：用户登录失败（密码错误），日志记录 `[login_failed_wrong_password] username=<name> user_id=<id>`
- 记录限流触发事件：登录限流触发，日志记录 `[login_rate_limited] username=<name>`

#### 2. 安全日志使用结构化格式

必须使用以下日志格式：
`<timestamp> - <level> - [<event_type>] <key=value> | <key=value>`

**示例场景：**
- 日志格式示例：记录安全事件时，日志格式为 `2026-04-02 10:30:00 - INFO - [login_success] username=testuser | user_id=1`

#### 3. 安全日志区分事件级别

必须按事件类型设置日志级别：
- 成功事件：INFO
- 失败/阻断事件：WARNING

**示例场景：**
- 成功事件 INFO 级别：记录 `login_success` 事件，日志级别为 INFO
- 失败事件 WARNING 级别：记录 `login_failed_wrong_password` 事件，日志级别为 WARNING

#### 4. 安全日志服务可配置开关

必须提供 `ENABLE_SECURITY_LOGGING` 配置项（默认 true）。

**示例场景：**
- 关闭安全日志：配置 `ENABLE_SECURITY_LOGGING=false`，不记录安全事件日志

#### 5. 安全日志在应用启动时初始化

必须在 `main.py` 的 lifespan 中初始化安全日志服务。

**示例场景：**
- 日志初始化：应用启动时，创建 `logs/` 目录，初始化日志 handler

#### 6. 安全日志实施日志轮转

必须使用 `TimedRotatingFileHandler` 实现日志轮转，每天午夜轮转，保留最近 7 天的日志文件。

**示例场景：**
- 日志文件轮转：日志文件到达午夜，系统自动轮转日志文件，创建新的日志文件，旧文件重命名为带日期后缀
- 日志文件保留期限：日志文件超过 7 天，系统自动删除过期的日志文件
- 日志目录不存在时创建：应用启动时日志目录不存在，系统自动创建 `logs/` 目录

### 文件上传安全

#### 7. 文件上传验证 Magic Bytes

必须使用 magic bytes（文件头）验证上传图片的真实格式，拒绝伪装文件。

支持的格式和 magic bytes：
- JPEG: `FF D8 FF`
- PNG: `89 50 4E 47 0D 0A 1A 0A`
- WebP: `52 49 46 46` (RIFF) + `57 45 42 50` (WEBP at offset 8-11)

**示例场景：**
- 验证真实 JPEG 文件：上传文件扩展名为 `.jpg` 且 magic bytes 为 `FF D8 FF`，文件上传成功
- 拒绝伪装 JPEG 文件：上传文件扩展名为 `.jpg` 但 magic bytes 为 PNG 格式，返回 400 状态码，提示"文件内容与声明格式不匹配，可能存在安全风险"
- 验证真实 WebP 文件：上传文件扩展名为 `.webp` 且 magic bytes 为 RIFF + WEBP，文件上传成功

#### 8. 文件验证记录安全事件

必须在 magic bytes 不匹配时记录安全事件日志。

**示例场景：**
- 记录上传异常事件：上传文件 magic bytes 不匹配，日志记录 `[upload_magic_bytes_mismatch] user_id=<id> claimed_format=<ext> actual_format=<detected>`

#### 9. 文件验证服务提供格式检测

必须提供 `detect_image_format()` 函数，从 magic bytes 检测真实格式。

**示例场景：**
- 检测 JPEG 格式：调用 `detect_image_format(content)` 且 content 以 `FF D8 FF` 开头，返回 "jpg"
- 检测未知格式：调用 `detect_image_format(content)` 且 content 不匹配任何已知格式，返回 None

#### 10. 文件验证检查最小长度

必须验证文件内容长度至少 12 bytes（覆盖所有格式 magic bytes）。

**示例场景：**
- 拒绝过短文件：上传文件内容少于 12 bytes，magic bytes 验证返回 False

## Why This Matters

安全审计是发现和追溯安全事件的关键：
- **攻击行为追溯**：安全日志记录所有认证失败、限流触发、上传异常等事件，帮助发现攻击模式
- **合规要求**：生产环境通常需要安全审计日志以满足合规要求
- **文件上传防护**：Magic bytes 验证防止攻击者上传伪装文件（如将 PHP 脚本伪装成图片）

## When to Apply

- 部署到生产环境前必须实施
- 处理用户上传文件时必须验证 magic bytes
- 新增认证相关端点时需评估日志记录需求
- 安全事件调查时查询 `logs/security.log`

## Examples

### 安全日志配置

```python
# backend/app/config.py
class Settings(BaseSettings):
    ENABLE_SECURITY_LOGGING: bool = True
```

### 安全日志服务使用

```python
from app.services.security_log import security_log

# 登录成功
security_log.login_success(username="testuser", user_id=1)

# 登录失败
security_log.login_failed_wrong_password(username="testuser", user_id=1)

# 限流触发
security_log.login_rate_limited(username="testuser")

# 文件上传异常
security_log.upload_magic_bytes_mismatch(
    user_id=1,
    claimed_format="jpg",
    actual_format="png"
)
```

### 文件上传验证

```python
from app.services.file_validation import validate_image_magic_bytes, detect_image_format

# 验证上传文件
async def validate_upload(file: UploadFile) -> bool:
    content = await file.read()
    await file.seek(0)  # 重置指针

    if len(content) < 12:
        raise HTTPException(status_code=400, detail="文件内容过短")

    detected = detect_image_format(content)
    expected = file.filename.split(".")[-1].lower()

    if detected != expected:
        security_log.upload_magic_bytes_mismatch(
            user_id=current_user.id,
            claimed_format=expected,
            actual_format=detected or "unknown"
        )
        raise HTTPException(status_code=400, detail="文件内容与声明格式不匹配")

    return True
```

### 日志文件示例

```
# logs/security.log
2026-04-02 10:30:00 - INFO - [login_success] username=testuser | user_id=1
2026-04-02 10:31:15 - WARNING - [login_failed_wrong_password] username=admin | user_id=None
2026-04-02 10:31:45 - WARNING - [login_rate_limited] username=admin
2026-04-02 11:00:00 - WARNING - [upload_magic_bytes_mismatch] user_id=1 | claimed_format=jpg | actual_format=png
```

## Related

- [安全防护最佳实践](./security-protection.md) - 速率限制和缓存层
- `openspec/specs/security-logging/spec.md` - 原始需求规范
- `openspec/specs/file-upload-security/spec.md` - 原始需求规范