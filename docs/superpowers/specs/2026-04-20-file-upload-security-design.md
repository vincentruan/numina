# File Upload Security Design

**Date:** 2026-04-20
**Status:** Approved
**Scope:** 文件上传安全验证，防止恶意文件

---

## Problem

文件上传仅依赖扩展名验证，攻击者可上传伪装文件（如将 `.exe` 改名为 `.jpg`）。缺乏文件内容验证导致安全隐患，可能上传恶意脚本或病毒文件。

---

## Goals

1. 使用 magic bytes 验证文件真实格式
2. 拒绝伪装文件上传
3. 记录上传异常安全事件
4. 支持常见图片格式（JPEG、PNG、WebP）

---

## Architecture

### Magic Bytes 验证流程

```
用户上传文件 → 检查文件长度（>=12 bytes） → 读取头部 magic bytes → 
验证与声明格式匹配 → 匹配则存储 → 不匹配则拒绝并记录日志
```

验证服务位于 `backend/app/services/file_validation.py`，在路由层调用验证函数。

### 支持的图片格式

| 格式 | Magic Bytes | 长度 |
|------|-------------|------|
| JPEG | `FF D8 FF` | 3 bytes |
| PNG | `89 50 4E 47 0D 0A 1A 0A` | 8 bytes |
| WebP | `52 49 46 46` + `57 45 42 50` (offset 8-11) | 12 bytes |

---

## Implementation Details

### FileValidationService 实现

```python
class FileValidationService:
    MAGIC_BYTES = {
        "jpg": bytes([0xFF, 0xD8, 0xFF]),
        "png": bytes([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A]),
        "webp": bytes([0x52, 0x49, 0x46, 0x46]),  # RIFF
    }
    WEBP_SIGNATURE = bytes([0x57, 0x45, 0x42, 0x50])  # WEBP at offset 8-11
    
    @classmethod
    def detect_image_format(cls, content: bytes) -> str | None:
        """从 magic bytes 检测真实格式"""
        if len(content) < 12:
            return None
        
        if content[:3] == cls.MAGIC_BYTES["jpg"]:
            return "jpg"
        
        if content[:8] == cls.MAGIC_BYTES["png"]:
            return "png"
        
        if content[:4] == cls.MAGIC_BYTES["webp"]:
            if content[8:12] == cls.WEBP_SIGNATURE:
                return "webp"
        
        return None
    
    @classmethod
    def validate_image(cls, content: bytes, claimed_format: str) -> bool:
        """验证文件内容与声明格式匹配"""
        detected = cls.detect_image_format(content)
        
        if detected != claimed_format.lower():
            SecurityLogService.log(
                event_type="upload_magic_bytes_mismatch",
                level="WARNING",
                claimed_format=claimed_format,
                actual_format=detected or "unknown"
            )
            return False
        
        return True
```

### 上传路由集成

```python
@router.post("/upload/image")
def upload_image(
    file: UploadFile,
    user: User = Depends(get_current_user)
):
    # 1. 检查文件扩展名
    allowed_extensions = {"jpg", "jpeg", "png", "webp"}
    ext = file.filename.split(".")[-1].lower()
    if ext not in allowed_extensions:
        raise HTTPException(400, "不支持的图片格式")
    
    # 2. 读取文件内容
    content = file.file.read()
    
    # 3. 验证 magic bytes
    if not FileValidationService.validate_image(content, ext):
        raise HTTPException(400, "文件内容与声明格式不匹配，可能存在安全风险")
    
    # 4. 检查文件大小
    if len(content) > 5 * 1024 * 1024:  # 5MB
        raise HTTPException(400, "文件大小超过限制")
    
    # 5. 存储文件
    filename = f"{uuid.uuid4()}.{ext}"
    filepath = Path("uploads") / filename
    filepath.write_bytes(content)
    
    return {"url": f"/uploads/{filename}"}
```

### 最小长度验证

文件内容必须至少 12 bytes（覆盖 WebP 的完整 magic bytes 验证）：

```python
if len(content) < 12:
    raise HTTPException(400, "文件内容过短")
```

---

## Examples

### 验证真实 JPEG

```
上传文件: test.jpg
扩展名: jpg
Magic bytes: FF D8 FF
验证结果: 匹配 → 上传成功
返回: {"url": "/uploads/abc123.jpg"}
```

### 拒绝伪装 JPEG

```
上传文件: malware.jpg
扩展名: jpg
Magic bytes: 89 50 4E 47 (PNG)
验证结果: 不匹配 → 拒绝上传
返回: 400 "文件内容与声明格式不匹配，可能存在安全风险"
日志: [upload_magic_bytes_mismatch] claimed_format=jpg | actual_format=png
```

---

## Verification

- 真实 JPEG 文件上传成功
- 伪装 JPEG（PNG 内容）返回 400 错误
- WebP 文件需要 RIFF + WEBP 双重验证
- 文件小于 12 bytes 返回错误
- 不匹配时日志记录 `[upload_magic_bytes_mismatch]`

---

## Code Pointers

| 功能 | 文件路径 |
|------|----------|
| 文件验证服务 | `backend/app/services/file_validation.py` |
| 上传路由 | `backend/app/routers/upload.py` |
| 安全日志 | `backend/app/services/security_log.py` |

---

## Related Specs

- **安全日志设计**：`2026-04-20-security-logging-design.md` — 上传异常日志
- **API规范设计**：`2026-04-20-api-spec-design.md` — /upload/image 端点