## ADDED Requirements

### Requirement: 文件上传必须验证 Magic Bytes

系统 SHALL 使用 magic bytes（文件头）验证上传图片的真实格式，拒绝伪装文件。

支持的格式和 magic bytes：
- JPEG: `FF D8 FF`
- PNG: `89 50 4E 47 0D 0A 1A 0A`
- WebP: `52 49 46 46` (RIFF) + `57 45 42 50` (WEBP at offset 8-11)

#### Scenario: 验证真实 JPEG 文件

- **WHEN** 上传文件扩展名为 `.jpg` 且 magic bytes 为 `FF D8 FF`
- **THEN** 文件上传成功

#### Scenario: 拒绝伪装 JPEG 文件

- **WHEN** 上传文件扩展名为 `.jpg` 但 magic bytes 为 PNG 格式
- **THEN** 返回 400 状态码，提示 "文件内容与声明格式不匹配，可能存在安全风险"

#### Scenario: 验证真实 WebP 文件

- **WHEN** 上传文件扩展名为 `.webp` 且 magic bytes 为 RIFF + WEBP
- **THEN** 文件上传成功

### Requirement: 文件验证必须记录安全事件

系统 SHALL 在 magic bytes 不匹配时记录安全事件日志。

#### Scenario: 记录上传异常事件

- **WHEN** 上传文件 magic bytes 不匹配
- **THEN** 日志记录 `[upload_magic_bytes_mismatch] user_id=<id> claimed_format=<ext> actual_format=<detected>`

### Requirement: 文件验证服务必须提供格式检测

系统 SHALL 提供 `detect_image_format()` 函数，从 magic bytes 检测真实格式。

#### Scenario: 检测 JPEG 格式

- **WHEN** 调用 `detect_image_format(content)` 且 content 以 `FF D8 FF` 开头
- **THEN** 返回 "jpg"

#### Scenario: 检测未知格式

- **WHEN** 调用 `detect_image_format(content)` 且 content 不匹配任何已知格式
- **THEN** 返回 None

### Requirement: 文件验证必须检查最小长度

系统 SHALL 验证文件内容长度至少 12 bytes（覆盖所有格式 magic bytes）。

#### Scenario: 拒绝过短文件

- **WHEN** 上传文件内容少于 12 bytes
- **THEN** magic bytes 验证返回 False