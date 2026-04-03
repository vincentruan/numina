---
date: 2026-04-02
topic: altcha-captcha
---

# ALTCHA 验证码集成

## Problem Frame

Numina 作为自托管家庭资产管理系统，部署到生产服务器后面临公开端点的流量攻击风险：

- **注册端点** (`POST /auth/register`) — 恶意账号批量注册
- **登录端点** (`POST /auth/login`) — 凭证填充攻击
- **加入家庭端点** (`POST /auth/family/join`) — 邀请码滥用

现有防护措施（rate limiting: 5 attempts / 15 min lockout）在攻击者发起请求后才生效，缺乏前置屏障。ALTCHA 通过 proof-of-work 机制要求客户端完成计算任务，显著提高自动化攻击成本，同时保持无障碍体验（无外部调用、无 Cookie、无追踪）。

## Requirements

**端点保护**
- R1. 注册端点 `POST /auth/register` 需要 ALTCHA 验证
- R2. 登录端点 `POST /auth/login` 需要 ALTCHA 验证
- R3. 加入家庭端点 `POST /auth/family/join` 需要 ALTCHA 验证

**后端实现**
- R4. 新增 `GET /api/v1/captcha/challenge` 端点返回 ALTCHA challenge
- R5. 受保护端点验证请求中的 `altcha` payload 字段
- R6. ~~验证失败返回 HTTP 400，错误消息 `"验证码验证失败"`~~（已由 R21 替代）
- R7. 使用 `altcha` Python 库进行 challenge 生成和 solution 验证

**前端实现**
- R8. 创建 `AltchaWidget.vue` 组件封装 web component
- R9. LoginPage、RegisterPage、JoinFamilyPage 集成 AltchaWidget
- R10. 组件通过 v-model 或事件将 `altcha` payload 暴露给父组件，父组件在表单提交时包含在请求中

**环境控制**
- R11. 仅在 `ENVIRONMENT=production` 时启用 ALTCHA 验证
- R12. 非生产环境时后端跳过验证，前端 widget 显示 test 模式

**配置参数**
- R13. `ALTCHA_HMAC_KEY` 环境变量配置签名密钥（生产环境必填，启动时验证）
- R14. PoW 难度 `max_number=50000`（低难度，移动端友好；注：前端 widget 使用 camelCase `maxnumber`，Python 库使用 snake_case `max_number`）
- R15. Challenge 有效期默认 1 小时（库默认）

**用户体验**
- R16. Widget 使用标准模式（非浮动），作为表单底部固定元素（submit 按钮上方）
- R17. `auto=onsubmit`，提交表单时自动触发验证
- R18. 验证完成后自动提交表单

**Widget 状态与交互**
- R19. Widget 状态定义：(1) Loading — 获取 challenge 中；(2) Computing — PoW 计算中（显示进度或加载动画）；(3) Verified — 验证成功（显示成功标识）；(4) Error — 验证失败（显示内联错误信息）
- R20. 错误恢复：(1) Challenge 端点失败 — Widget 显示重试按钮，保留表单数据；(2) 验证失败 — 显示内联错误，用户点击 Widget 重试；(3) Challenge 过期 — 自动刷新 challenge，用户重新验证；所有场景无需刷新页面

**错误消息区分**
- R21. 生产环境验证失败返回 HTTP 400，区分错误消息：(1) 缺少 `altcha` 字段 — `"请完成验证码验证"`；(2) `altcha` 为空字符串 — `"验证码不能为空"`；(3) 验证失败/过期 — `"验证码验证失败，请重试"`

**测试覆盖**
- R22. 创建 `backend/tests/test_captcha.py` 测试 captcha 验证逻辑：(1) 生产模式下缺少/空/无效 payload 返回 400；(2) 开发模式跳过验证；(3) 有效 payload 通过验证

## Success Criteria

- 生产环境注册/登录/加入家庭请求无有效 `altcha` payload 时被拒绝
- 开发环境可正常完成注册/登录流程（无验证障碍）
- 移动端用户验证延迟 <1 秒
- 无外部验证 API 调用（前端 widget 脚本通过 CDN 加载），核心验证逻辑完全自托管

## Scope Boundaries

- **不实现 Sentinel spam filter** — 仅使用基础 PoW 验证，不集成 Sentinel 服务端的 spam 分类和字段哈希验证
- **不扩展到其他端点** — 仅限公开 auth 端点，已认证用户的 CRUD 操作不增加验证
- **不持久化 challenge** — challenge 单次使用，验证后立即失效。altcha 库通过 challenge 内嵌签名和 nonce 实现防重放，服务端无需额外存储；库的 1 小时有效期仅限制 challenge 的初始生成时间窗口

## Key Decisions

| 决策 | 选择 | 理由 |
|------|------|------|
| 保护端点 | register + login + family/join | 公开端点最高风险，已认证用户 CRUD 操作不需要额外验证 |
| 环境激活 | 仅 ENVIRONMENT=production | 开发体验友好，生产安全严格 |
| 前端集成 | Vue 组件封装 | 统一配置，多处复用一致 |
| 显示模式 | 标准模式 | 用户明确知道验证需求，实现简单 |
| PoW 难度 | max_number=50000（低） | 移动端友好，<1s 延迟 |

## Dependencies / Assumptions

- `altcha` Python 库（`pip install altcha`）需添加到 backend 依赖
- 前端通过 CDN 加载 ALTCHA web component script，需添加 SRI 完整性校验：
  ```html
  <script src="https://cdn.jsdelivr.net/gh/altcha-org/altcha@main/dist/altcha.min.js"
          integrity="sha384-<hash>"
          crossorigin="anonymous"></script>
  ```
  （SRI hash 需在实现时从发布的脚本计算获取）
- `ALTCHA_HMAC_KEY` 在生产部署时通过环境变量配置，需在生产环境启动时验证是否已设置（类似 `SECRET_KEY` 检查）

## Outstanding Questions

### Deferred to Planning

- [Affects R8][Technical] Vue 组件如何处理 web component 的 `statechange` 事件和表单提交时机
- [Affects R4][Technical] Challenge 端点需要在 axios interceptor 中标记为不需要 Authorization header（public endpoint），或创建无 interceptor 的独立 axios 实例
- [Affects R4][Technical] Challenge 端点需添加到 `RateLimitMiddleware.SKIP_PATHS`，避免用户被限流后无法获取 challenge
- [Affects R5][Technical] Schema 修改：在 LoginRequest、RegisterRequest、JoinFamilyRequest 中添加可选的 `altcha: str | None` 字段，验证逻辑检查 `settings.ENVIRONMENT == 'production'` 时启用验证
- [Affects R13][Technical] 在 `config.py` 中添加 `ALTCHA_HMAC_KEY` 验证：生产环境启动时检查是否为空，为空则抛出 RuntimeError

## Integration Flow

```mermaid
flow TB
    subgraph Frontend["Vue 3 + AltchaWidget"]
        F1[LoginPage<br/>RegisterPage<br/>JoinFamilyPage]
        F2[AltchaWidget.vue]
        F3[altcha-widget<br/>challengeurl=/api/v1/captcha/challenge<br/>auto=onsubmit]
    end

    subgraph Backend["FastAPI + altcha-lib"]
        B1["GET /captcha/challenge<br/>create_challenge()"]
        B2["POST /auth/*<br/>verify_solution()"]
        B3["settings.ENVIRONMENT<br/>== 'production'"]
    end

    F1 --> F2 --> F3
    F3 -->|fetch challenge| B1
    F3 -->|submit altcha payload| B2
    B1 -->|Challenge JSON| F3
    B2 -->|验证通过 or 400| F1
    B3 -->|enabled| B2
    B3 -->|disabled| B2
```

## Next Steps

→ `/ce:plan` for structured implementation planning