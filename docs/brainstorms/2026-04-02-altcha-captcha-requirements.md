---
date: 2026-04-02
topic: altcha-captcha
updated: 2026-04-03
---

# ALTCHA 验证码集成

## Problem Frame

Numina 作为自托管家庭资产管理系统，部署到生产服务器后面临公开端点的流量攻击风险：

- **注册端点** (`POST /auth/register`) — 恶意账号批量注册
- **登录端点** (`POST /auth/login`) — 凭证填充攻击
- **加入家庭端点** (`POST /auth/family/join`) — 邀请码滥用

现有防护措施（rate limiting: 5 attempts / 15 min lockout）在攻击者发起请求后才生效，缺乏前置屏障。ALTCHA 通过 proof-of-work 机制要求客户端完成计算任务，显著提高自动化攻击成本，同时保持无障碍体验（无外部调用、无 Cookie、无追踪）。

**Updated scope (2026-04-03):** 基于已实现的基础集成，探索手机端 H5 访问（兼顾 PC 端）的最佳实践，覆盖安全加固、移动性能优化、用户体验增强三个维度。

## Requirements

**端点保护**
- R1. 注册端点 `POST /auth/register` 需要 ALTCHA 验证
- R2. 登录端点 `POST /auth/login` 需要 ALTCHA 验证
- R3. 加入家庭端点 `POST /auth/family/join` 需要 ALTCHA 验证

**后端实现**
- R4. 新增 `GET /api/v1/captcha/challenge` 端点返回 ALTCHA challenge
- R5. 受保护端点验证请求中的 `altcha` payload 字段
- R6. ~~验证失败返回 HTTP 400，错误消息 `"验证码验证失败"`~~（已由 R21 完全替代：HTTP 400 状态码保持，错误消息细分化）
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
- R14. ~~PoW 难度 `max_number=50000`（低难度，移动端友好）~~（已由端点差异化难度替代，见 Best Practices Extensions：login=30000, register/join=100000）
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

---

### Best Practices Extensions (2026-04-03)

**安全加固：防重放攻击**
- R23. 实现 payload registry 防止同一 solved challenge 在有效期内被重复使用
  - 使用 Redis 或内存缓存存储已验证 payload 的 SHA-256 hash
  - TTL 与 challenge 有效期一致（默认 1 小时）
  - 验证流程：`verify_solution()` 成功后，检查 payload hash 是否已在 registry；若存在则拒绝，否则添加到 registry 并继续
  - 存储键格式：`altcha:used:<payload_hash>`
  - 注：当前实现仅有 `check_expires=True`，缺少 payload 唯一性检查

**移动性能：端点差异化难度**
- R24. 根据端点风险等级配置不同的 PoW 难度
  - **高风险端点**（register, join-family）：`max_number=100000` — 防止批量滥用，牺牲部分移动端速度
  - **高频端点**（login）：`max_number=30000` — 优化移动端 UX，用户多次登录场景更流畅
  - 实现方式：Challenge 端点接收 `endpoint` 参数，返回对应难度的 challenge
  - 前端传递 `endpoint` 参数：`challengeurl="/api/v1/captcha/challenge?endpoint=login"`

**用户体验增强**
- R25. 重试流程优化
  - 后端验证失败时，前端自动重置 widget 并提示用户重新验证
  - 错误类型区分：网络错误（challenge 端点不可达）显示"网络异常，请稍后重试"；验证失败显示"验证失败，请重新完成验证"
  - 保留表单已填数据，仅重置 captcha 状态

- R26. 视觉集成优化
  - 深色模式支持：widget 在深色主题下使用 `dark` 属性或 CSS 变量适配
  - Vant UI 风格统一：调整 widget 边框、圆角、间距与 Vant 组件一致
  - 响应式布局：widget 宽度适配不同屏幕尺寸（max-width: 300px 移动端，max-width: 400px PC 端）

- R27. 无障碍访问（a11y）
  - Widget 状态通过 ARIA 属性通知屏幕阅读器：`aria-busy`（计算中）、`aria-live="polite"`（状态变化通知）
  - 错误消息使用 `role="alert"` 确保即时通知
  - 键盘导航支持：Tab 键聚焦 widget，Enter 键触发验证（如支持）

- R28. 加载状态反馈
  - 计算中显示进度指示器（spinner 或进度条）
  - 低端设备预估等待时间提示："正在验证，预计需 3-5 秒"
  - 验证成功后短暂显示成功图标，然后自动提交

**跨平台一致性**
- R29. 移动端优先响应式设计，PC 端无特殊处理
  - Widget 视觉和交互逻辑在所有设备上一致
  - 仅通过 CSS 响应式调整尺寸，不检测设备类型动态改变行为

**安全日志增强**
- R30. 扩展 `SecurityEventType` 包含 captcha 相关事件
  - `CAPTCHA_VERIFICATION_FAILED` — 支持三种错误类型区分：missing（缺少 altcha 字段）、empty（altcha 为空）、invalid（验证失败/过期）
  - `CAPTCHA_REPLAY_ATTACK` — payload registry 检测到重复使用（待实现）
  - `CAPTCHA_CHALLENGE_FETCH_FAILED` — 前端获取 challenge 失败（前端日志，待实现）

## Success Criteria

- 生产环境注册/登录/加入家庭请求无有效 `altcha` payload 时被拒绝
- 开发环境可正常完成注册/登录流程（无验证障碍）
- 移动端用户验证延迟：<2 秒（login）、<4 秒（register/join-family）
- 同一 payload 无法在有效期内重复使用（防重放）
- 无外部验证 API 调用（前端 widget 脚本通过 CDN 加载），核心验证逻辑完全自托管
- 深色模式下 widget 视觉正常
- 屏幕阅读器用户可理解验证状态和错误提示

## Scope Boundaries

- **不实现 Sentinel spam filter** — 仅使用基础 PoW 验证，不集成 Sentinel 服务端的 spam 分类和字段哈希验证
- **不扩展到其他端点** — 仅限公开 auth 端点，已认证用户的 CRUD 操作不增加验证
- ~~不持久化 challenge~~ — **已变更**：实现 payload registry（仅存储 payload hash，非完整 challenge）作为防重放措施（见 R23）
- **不实现设备检测动态难度** — 端点固定难度，不根据设备类型动态调整
- **不实现请求签名完整性验证** — 当前 captcha + rate limiting + security logging 足够；请求签名作为未来增强选项记录，不在本次实现

## Key Decisions

| 决策 | 选择 | 理由 |
|------|------|------|
| 保护端点 | register + login + family/join | 公开端点最高风险，已认证用户 CRUD 操作不需要额外验证 |
| 环境激活 | 仅 ENVIRONMENT=production | 开发体验友好，生产安全严格 |
| 前端集成 | Vue 组件封装 | 统一配置，多处复用一致 |
| 显示模式 | 标准模式 | 用户明确知道验证需求，实现简单 |
| ~~PoW 难度~~ | ~~max_number=50000（低）~~ | ~~移动端友好，<1s 延迟~~ — 已由端点差异化替代 |
| 端点难度 | login=30000, register/join=100000 | 平衡高频操作的 UX 和高风险操作的滥用防护 |
| 防重放机制 | payload registry + TTL | 防止已解决 challenge 在有效期内重复使用 |
| 跨平台策略 | 移动优先响应式 | PC 端无特殊处理，降低复杂度 |
| 请求完整性 | 记录未来选项，不实现 | 当前防护足够，避免过度工程 |

## Dependencies / Assumptions

- [已完成] `altcha` Python 库（`pip install altcha`）需添加到 backend 依赖
- [已完成] 前端通过 CDN 加载 ALTCHA web component script
- [已完成] `ALTCHA_HMAC_KEY` 在生产部署时通过环境变量配置
- [待实现] Payload registry 需要 Redis 或内存缓存支持（`CACHE_BACKEND` 配置已存在，需扩展用于 captcha）
- [待实现] 前端 axios 需传递 `endpoint` 参数到 challenge URL（R24 实现）

## Future Considerations

以下选项不在本次实现范围，记录供未来增强参考：

**请求完整性验证**
- 请求签名：客户端对请求 body + timestamp + nonce 签名，后端验证签名防止请求篡改
- Timestamp 验证：请求携带时间戳，后端拒绝超出时间窗口（如 ±5 分钟）的请求
- Nonce challenge-response：登录前先获取 nonce，请求必须包含该 nonce 的签名响应

适用场景：需要更高安全等级时（如金融操作、敏感数据修改），可与 captcha 组合使用。

## Outstanding Questions

### Resolve Before Planning

- ~~[Affects R23][Technical] Payload registry 存储选型：Redis（生产推荐）vs 内存缓存（简单实现）~~ — 已决定使用现有 `CACHE_BACKEND` 配置（Redis 生产，内存开发）

### Deferred to Planning

- [Affects R8][Technical] Vue 组件如何处理 web component 的 `statechange` 事件和表单提交时机 — **已实现**
- [Affects R4][Technical] Challenge 端点需要在 axios interceptor 中标记为不需要 Authorization header — **已实现**
- [Affects R24][Technical] Challenge 端点如何接收和处理 `endpoint` 参数，返回不同难度的 challenge
- [Affects R4][Technical] Challenge 端点需添加到 `RateLimitMiddleware.SKIP_PATHS`
- [Affects R23][Technical] Payload registry 与 `verify_solution()` 的集成顺序：先验证签名再查 registry，还是先查 registry
- [Affects R26][Technical] 深色模式下 widget 样式适配的具体 CSS 方案
- [Affects R27][Technical] ARIA 属性如何在 Vue 组件中正确设置和更新
- [Affects R28][Technical] 计算进度如何从 web component 获取并显示（ALTCHA widget 是否暴露进度事件）

## Integration Flow

```mermaid
flow TB
    subgraph Frontend["Vue 3 + AltchaWidget"]
        F1[LoginPage<br/>RegisterPage<br/>JoinFamilyPage]
        F2[AltchaWidget.vue]
        F3[altcha-widget<br/>challengeurl=/api/v1/captcha/challenge?endpoint={type}<br/>auto=onsubmit]
    end

    subgraph Backend["FastAPI + altcha-lib"]
        B1["GET /captcha/challenge<br/>?endpoint=<type><br/>create_challenge(max_number)"]
        B2["POST /auth/*<br/>1. verify_solution()<br/>2. check_payload_registry()<br/>3. add_to_registry()"]
        B3["Payload Registry<br/>Redis/Memory Cache<br/>TTL=1h"]
    end

    F1 --> F2 --> F3
    F3 -->|fetch challenge with endpoint param| B1
    B1 -->|Challenge JSON (difficulty by endpoint)| F3
    F3 -->|submit altcha payload| B2
    B2 -->|check/add| B3
    B2 -->|验证通过 or 400| F1
```

## Next Steps

→ `/ce:plan` for structured implementation planning