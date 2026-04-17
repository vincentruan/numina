---
date: 2026-04-16
topic: auth-security
focus: 人-前端-后端-agent端鉴权方式优化，防盗号、越权、横向越权
---

# Ideation: 鉴权安全全链路优化

## Codebase Context

**项目形态：** 自托管家庭资产管理系统，FastAPI + SQLAlchemy + SQLite，Vue 3 移动端，内部 Agent 微服务层。每个实例 2-10 用户。

**当前鉴权实现：**
- 人→前端→后端：httpOnly Cookie（主）+ Bearer Token（备），JWT 15分钟 access / 7天 refresh
- 登录保护：5次失败锁定15分钟，ALTCHA CAPTCHA，timing attack 防护（dummy bcrypt）
- 全局限流：100 req/min per client（内存存储）
- 后端→Agent：单一共享 `AGENT_INTERNAL_TOKEN` + `X-Family-Id` header
- family_id 隔离：各 router 手动过滤（约18处）

**已记录的已知问题：**
- 单一共享 Agent Token，无轮换，无吊销
- 内存限流在多 worker 部署下失效（有效阈值 = workers × 配置值）
- family_id 过滤分散在各 router，遗漏即数据泄露
- 无 token 吊销机制（logout 仅清 cookie，token 本身仍有效）
- 无密码修改接口
- 无 token refresh 的限流保护

**已有最佳实践文档：**
- `docs/solutions/best-practices/security-protection.md` — 登录暴力破解防护、timing attack、限流客户端识别
- `docs/solutions/best-practices/security-audit.md` — 安全事件日志规范
- `docs/solutions/best-practices/redis-fail-fast-strategy.md` — Redis 缓存后端 fail-fast 策略
- `docs/solutions/best-practices/altcha-captcha-best-practices-2026-04-03.md` — CAPTCHA 重放攻击防护

---

## Ranked Ideas

### 1. JTI-Based Token Rotation on Refresh（刷新时 JTI 轮换）

**Description:** 在 JWT payload 中加入 `jti`（JWT ID）字段。每次调用 `/auth/refresh` 时，签发带新 JTI 的新 token，并将旧 JTI 加入内存吊销集合（带 TTL，过期后自动清理）。任何请求携带已吊销 JTI 时立即拒绝。

**Rationale:** 当前 refresh token 7天有效且无法吊销。一旦泄露，攻击者可持续刷新 access token 长达7天。JTI 轮换将 refresh token 变为一次性凭证——每次刷新后旧 token 立即失效，将攻击窗口从7天压缩到刷新间隔（通常数分钟）。同时为密码修改（Idea #2）提供基础设施。

**Downsides:** JTI 吊销集合需要内存存储（TTL 清理可控）；多 worker 部署下内存集合不共享（但 refresh 操作频率低，影响有限；若需严格一致性可接入 Redis）。

**Confidence:** 95%
**Complexity:** Medium
**Security Impact:** High
**Status:** Unexplored

---

### 2. Password Change Endpoint（密码修改接口）

**Description:** 新增 `POST /auth/me/password`，要求提供旧密码验证。成功后：① 更新密码哈希；② 通过 JTI 机制吊销该用户所有现存 token；③ 记录安全审计事件。

**Rationale:** 当前无密码修改接口，用户无法主动应对密码泄露。这是最基础的账号安全能力缺失。与 Idea #1 组合后形成完整的 token 生命周期管理：密码修改 → 吊销所有 token → 强制重新登录。

**Downsides:** 依赖 Idea #1 的 JTI 基础设施才能实现"吊销所有 token"；单独实现时只能吊销当前 session。

**Confidence:** 98%
**Complexity:** Low
**Security Impact:** High
**Status:** Unexplored

---

### 3. Middleware-Enforced Family ID Validation（中间件层 family_id 强制校验）

**Description:** 将 family_id 过滤从各 router 提升到全局中间件。中间件从 JWT 提取 `family_id`，注入 request context；各 router 从 context 读取，不再手动过滤。对于 Agent 请求，中间件同时校验 `X-Family-Id` header 与 JWT 中的 family_id 一致性。任何不匹配立即 403。

**Rationale:** 当前约18处手动 `Model.family_id == current_user.family_id` 过滤，遗漏一处即横向越权（访问其他家庭数据）。中间件方案 fail-closed：新增 endpoint 默认受保护，无需开发者记住过滤。

**Downsides:** 需要仔细处理豁免路由（注册、登录、公开接口）；Agent 内部路由需要特殊处理逻辑。

**Confidence:** 92%
**Complexity:** Medium
**Security Impact:** High
**Status:** Unexplored

---

### 4. Rate Limiting on Refresh + Sensitive Ops（刷新及敏感操作限流）

**Description:** 在现有限流基础上，为以下接口单独配置限流：`/auth/refresh`（如 10次/分钟/用户）、`/auth/me/password`（3次/小时/用户）、`/family/invite-code`（5次/小时/用户）。

**Rationale:** 当前限流仅覆盖登录/注册。攻击者持有 refresh token 后可无限刷新 access token，绕过 access token 的15分钟有效期限制。对 refresh 接口限流可检测 token 滥用行为，并与 Idea #1 的 JTI 轮换形成双重防护。

**Downsides:** 内存限流在多 worker 下仍有同样的计数分散问题（但 refresh 频率远低于普通请求，实际影响小）。

**Confidence:** 88%
**Complexity:** Low
**Security Impact:** Medium
**Status:** Unexplored

---

### 5. Immutable Audit Log Table（不可变审计日志表）

**Description:** 新增 `security_audit_logs` 数据库表，append-only（无 UPDATE/DELETE 权限约束）。记录：登录成功/失败、token 刷新、密码修改、角色变更、邀请码重置、疑似异常操作。字段：`id, event_type, user_id, family_id, ip_address, user_agent, outcome, detail, created_at`。设置90天保留策略。

**Rationale:** 当前安全日志写入文件，可被删除，不可查询。DB 审计表支持事后取证（"哪些账号在什么时间从哪里被访问"），与 Idea #4 的限流日志形成完整的安全可观测性。

**Downsides:** 表会持续增长，需要保留策略；不能替代文件日志（文件日志在 DB 不可用时仍有价值）。

**Confidence:** 85%
**Complexity:** Medium
**Security Impact:** Medium
**Status:** Unexplored

---

### 6. Embed Family ID in Agent JWT（Agent JWT 中绑定 family_id）

**Description:** 将 Agent→Backend 的鉴权从"静态 HMAC token + 独立 X-Family-Id header"改为"短期 JWT，payload 中包含 family_id + agent_instance_id + exp"。Backend 验证 JWT 签名，从 payload 提取 family_id，无需信任独立 header。

**Rationale:** 当前 `X-Family-Id` header 与 `AGENT_INTERNAL_TOKEN` 解耦，理论上可伪造 header（若 token 泄露）。JWT 将 family_id 与签名绑定，使伪造在密码学上不可行。同时为 Agent 身份审计（Idea #7）提供 `agent_instance_id` 字段。

**Downsides:** 需要 Agent 侧改造（生成/刷新短期 JWT）；增加 Agent 启动复杂度。

**Confidence:** 82%
**Complexity:** Low-Medium
**Security Impact:** Medium
**Status:** Unexplored

---

### 7. Agent Identity in Audit Logs（Agent 身份审计）

**Description:** Agent 请求中携带 `X-Agent-Instance-Id` header（或通过 Idea #6 的 JWT payload）。Backend 在审计日志中记录 `agent_instance_id`，区分哪个 Agent 实例发起了哪些操作。

**Rationale:** 当前 Agent 调用在日志中无法区分来源。若 Agent 实例被攻陷，无法通过日志定位是哪个实例。与 Idea #5 组合后，审计日志具备完整的请求溯源能力。

**Downsides:** 单独实现价值有限；强依赖 Idea #5（审计日志表）和 Idea #6（Agent JWT）。

**Confidence:** 65%
**Complexity:** Low
**Security Impact:** Low
**Status:** Unexplored

---

## Rejection Summary

| # | Idea | Reason Rejected |
|---|------|-----------------|
| 1 | Token Revocation Blacklist (Redis) | 需要 Redis 依赖；JTI 轮换（Idea #1）以更低成本解决同一问题 |
| 2 | Concurrent Session Limits + Device Fingerprinting | 设备指纹可伪造；2-10用户的家庭应用过度工程化 |
| 3 | Suspicious Login Detection / Anomaly Scoring | 需要 ML/启发式基础设施；小用户量下误报率高 |
| 4 | Distributed Rate Limiting (Redis) | 项目基础配置无 Redis；单实例自托管场景内存限流足够 |
| 5 | Granular RBAC Beyond Owner/Member | 2-10用户场景 owner/member 二元角色已足够；细粒度权限增加复杂度无实质收益 |
| 6 | JWT Token Version Field | 与 JTI 方案重复；JTI 更标准、更精细 |
| 7 | Step-Up Authentication (TOTP/Email) | 需要 TOTP/邮件验证基础设施；现有 CAPTCHA + 限流已覆盖高风险操作 |
| 8 | Behavioral Signals + Risk-Based CAPTCHA | 需要 IP/设备历史追踪；小用户量下常驻 CAPTCHA 更简单有效 |
| 9 | Session Table in DB | 每次请求增加 DB 查询；家庭应用场景收益不足以覆盖开销 |
| 10 | Per-Endpoint Rate Limit Configuration | 配置复杂度增加；全局100 req/min 对家庭应用已足够 |
| 11 | Per-Instance Agent Token Rotation (scheduled) | 定时轮换增加运维负担；Idea #6 的短期 JWT 以更优雅的方式解决同一问题 |

---

## Cross-Cutting Combinations

- **Idea #1 + #2** → 完整 token 生命周期管理：JTI 轮换提供吊销基础设施，密码修改触发全量吊销
- **Idea #3 + #6** → 家庭隔离双重防护：中间件防止 router 遗漏，JWT 绑定防止 Agent header 伪造
- **Idea #4 + #5** → 安全可观测性：限流阻断攻击，审计日志记录证据
- **Idea #5 + #6 + #7** → Agent 完整审计链：JWT 携带身份，日志记录溯源

---

## Session Log
- 2026-04-16: Initial ideation — 30 raw candidates generated (4 frames × ~8 ideas), 7 survivors after adversarial filtering + cross-cutting synthesis
