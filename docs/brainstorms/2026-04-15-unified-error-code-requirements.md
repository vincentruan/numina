---
date: 2026-04-15
topic: unified-error-code-i18n
---

# 统一错误码系统 + 集中异常处理 + i18n 桥接

## Problem Frame

当前 14 个 router 中散落着 `raise HTTPException(status_code=..., detail="中文字符串")` 调用，前端 axios interceptor 硬编码中文错误提示，vue-i18n 已安装但完全绕过。这导致：

- 错误处理逻辑分散在 14 个文件，无法统一维护
- 前端无法程序化区分不同错误类型（只能靠 HTTP status + 字符串匹配）
- 添加新语言需要同时修改后端和前端多处代码
- 错误响应格式不一致（有些返回 `detail: string`，有些返回 `detail: array`）

## 架构流程

```mermaid
flowchart TB
    A[Router / Service] -->|raise AppError| B[ErrorCode Enum]
    B --> C[Global Exception Handler]
    C --> D[加载语言文件\nbackend/app/errors/locales/]
    D --> E[统一 Envelope 响应\n{ code, message, data }]
    E --> F[前端 axios interceptor]
    F -->|直接用 data.message| G[showToast]
    F -->|data.code 用于程序化处理| H[特殊逻辑\n如 401 刷新]
```

## Requirements

**后端：错误码体系**

- R1. 新建 `backend/app/errors/codes.py`，定义 `ErrorCode(str, Enum)`，每个枚举值携带 HTTP status 元数据。覆盖所有现有 router 中出现的错误场景。
- R2. 新建 `backend/app/errors/exceptions.py`，定义 `AppError(Exception)` 异常类，接受 `ErrorCode` 和可选的 `details` 参数。
- R3. 新建 `backend/app/errors/locales/zh-CN.json` 和 `en-US.json`，key 为 ErrorCode 枚举值，value 为对应语言的错误消息。
- R4. 在 `main.py` 注册全局异常处理器，捕获 `AppError`，根据请求头 `Accept-Language` 加载对应语言文件，返回统一 envelope：`{ "code": str, "message": str, "data": null }`。
- R5. 全局异常处理器同时捕获原生 `HTTPException`，将其转换为 envelope 格式。422 Pydantic 校验错误特殊处理：`message` 为固定文本（如"输入校验失败"），`details` 字段携带字段级错误数组 `[{ field: string, msg: string }]`，`code` 为 `"VALIDATION_ERROR"`。

**后端：Router 迁移**

- R6. 一次性将 `backend/app/routers/` 下所有 router 文件中的 `raise HTTPException(status_code=..., detail="...")` 替换为 `raise AppError(ErrorCode.XXX)`。Agent 模块（`backend/agent/`）不在范围内。迁移完成后 `backend/app/routers/` 目录内不再有裸 `HTTPException` 调用（FastAPI 内部行为及 `RequestValidationError` 除外）。
- R7. 成功响应保持现有结构不变，统一包装为 `{ "code": "OK", "message": "", "data": <原有响应体> }`。

**前端：axios interceptor 更新**

- R8. 更新 `frontend/src/api/index.ts`，错误处理统一读取 `error.response.data.message` 显示 toast，不再有硬编码中文字符串。对于 422 错误，读取 `error.response.data.details` 数组，将各字段的 `msg` 拼接后显示。
- R9. 401 触发 token 刷新的判断保留基于 `error.response?.status === 401`（HTTP status），不切换到 `data.code`，以兼容 FastAPI 内部抛出的 401（如 oauth2_scheme）。403 等其他程序化逻辑同样保留 HTTP status 判断。`data.code` 仅用于业务层面的细粒度区分（如未来扩展）。
- R10. 成功响应拦截器自动解包 `response.data.data`，但 `/auth/` 前缀的端点（`/auth/login`、`/auth/register`、`/auth/refresh`、`/auth/family/join`、`/auth/me`）不做解包，保持现有认证逻辑不变。其余业务 API 模块（`assets.ts`、`liabilities.ts` 等）无需修改。

**语言支持**

- R11. 初始支持 `zh-CN`（默认）和 `en-US` 两种语言。后端根据请求头 `Accept-Language` 匹配，无匹配时 fallback 到 `zh-CN`。
- R12. 前端发送请求时在请求头中携带当前 vue-i18n locale 作为 `Accept-Language`。

## Success Criteria

- 所有后端 router 中不再有 `raise HTTPException(detail="中文字符串")` 调用
- 前端 axios interceptor 中不再有硬编码中文字符串
- 切换前端语言后，后续 API 错误提示自动以对应语言显示
- 现有 36 个后端单元测试全部通过
- `npm run build` 无类型错误

## Scope Boundaries

- 不修改成功响应的业务逻辑，只做 envelope 包装
- 不引入前端 i18n 错误消息文件（错误消息由后端统一维护）
- 不处理 WebSocket 错误（AI chat 的 WS 连接保持现状）
- 不修改 422 Pydantic 校验错误的字段级结构（R5 只做格式统一，不做字段级 code 化——这是独立的想法 #4）
- Agent 模块不在本次范围内

## Key Decisions

- **统一 envelope 包装所有响应**（含成功）：前端解包逻辑集中在 axios interceptor，各 API 模块无感知
- **后端负责翻译**（Accept-Language 驱动）：前端 vue-i18n 只管 UI 文本，错误消息由后端语言文件维护
- **语言文件仅在后端维护**：`backend/app/errors/locales/`，单一来源
- **Python Enum 定义错误码**：类型安全，IDE 自动补全，重构友好
- **一次性全量迁移**：不留混合状态，PR 集中，便于 review

## Dependencies / Assumptions

- FastAPI 的 `@app.exception_handler` 支持同时注册 `AppError` 和 `HTTPException` 两个处理器
- 前端 axios 响应拦截器解包 `data.data` 不会破坏现有 API 模块的类型推断（需在 planning 阶段验证）
- 现有 36 个后端单元测试需同步更新断言：成功响应从 `response.json()["field"]` 改为 `response.json()["data"]["field"]`；错误响应从 `response.json()["detail"]` 改为 `response.json()["code"]` / `response.json()["message"]`。测试迁移是本次 PR 的一部分，不是后续工作。
- `Accept-Language` 解析取第一个语言标签（逗号分隔后取 `[0]`，再去掉 `;q=...` 权重部分），无匹配时 fallback 到 `zh-CN`。不引入 `langcodes` 等外部依赖。

## Outstanding Questions

### Resolve Before Planning

- 无

### Deferred to Planning

- [影响 R10][技术] axios 响应拦截器对非认证端点自动解包 `data.data` 后，`api/*.ts` 中的 TypeScript 返回类型声明是否需要调整（如 `Promise<ApiResponse<Asset>>` → `Promise<Asset>`）？

## Next Steps

→ `/ce:plan` 进行结构化实现规划
