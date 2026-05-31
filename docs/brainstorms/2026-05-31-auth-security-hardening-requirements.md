---
date: 2026-05-31
topic: auth-security-hardening
source: 2026-04-16-auth-security-ideation.md (Ideas #1–#5)
status: implemented (baseline complete, hardening gaps identified below)
---

# 鉴权安全加固

## Summary

本文档记录 Numina 鉴权安全加固的 5 项核心需求（R1–R5），均已实现并部署。在验证实现完整性后，识别出 6 项残余安全加固点（R6–R11），作为下一轮迭代目标。

---

## Problem Frame

Numina 鉴权体系曾存在以下已知缺口（均已在本轮加固中解决）：

- **Refresh Token 无法吊销** — 7 天有效期内泄露即可持续获取 access token
- **无密码修改接口** — 用户无法主动应对密码泄露
- **family_id 过滤分散** — 约 18 处手动过滤，遗漏一处即横向越权
- **敏感操作无独立限流** — refresh/password/invite 共享全局 100 req/min 限制
- **安全事件仅写文件日志** — 不可查询、可被删除、无法事后取证

这些不是"锦上添花"，而是自托管家庭应用的安全底线。

---

## User Flow

```
攻击者获取 refresh token（XSS / 设备丢失）
        │
        ▼
   已解决：JTI 轮换 → 旧 token 立即失效，攻击窗口 < 分钟级
        │
        ▼
   用户发现异常 → 修改密码 → 全量 token 吊销 → 强制重新登录
        │
        ▼
   审计日志记录完整事件链，支持事后取证
```

---

## Requirements（已实现基线）

### R1. JTI-Based Token Rotation（刷新时 JTI 轮换）✅

实现位置：`server/packages/security/revoke_jti.py`、`server/apps/backend/app/auth/deps.py`

- R1.1 JWT payload 携带 `jti` 字段（UUID4），access / refresh / temp token 均包含
- R1.2 `/auth/refresh` 签发新 token 时，将旧 refresh token 的 JTI 写入 `revoked_tokens` 表（数据库持久化，非内存）
- R1.3 吊销记录使用 `expires_at` 字段实现 TTL 自动清理（scheduler_worker 定期执行 `cleanup_expired_revoked_tokens`）
- R1.4 `_verify_token()` 中检查 JTI 是否已吊销，命中则返回 None → 401
- R1.5 吊销存储使用 SQLite `revoked_tokens` 表（`packages/db/models/revoked_token.py`），跨重启持久化
- R1.6 `revoke_all_user_tokens(user_id)` 方法实现基于 `iat` 的批量吊销（所有 iat <= revoked_at 的 token 均失效）

### R2. Password Change Endpoint（密码修改接口）✅

实现位置：`server/apps/backend/app/routers/auth.py`、`server/apps/backend/app/services/auth.py`

- R2.1 `POST /auth/me/password`，请求体：`{ old_password: str, new_password: str }`
- R2.2 验证 old_password 正确后更新密码哈希（bcrypt，rounds 可配置）
- R2.3 成功后调用 `revoke_all_user_tokens(user_id)` 吊销所有现存 token
- R2.4 返回 `{"message": "密码已修改，请重新登录"}`（当前实现要求重新登录，不返回新 token pair）
- R2.5 记录安全审计事件：`write_audit_log("password_change", "success", ...)`
- R2.6 独立限流：3 次/小时/用户（`_check_password_change_rate_limit`）

### R3. Middleware-Enforced Family ID Validation（中间件层 family_id 强制校验）✅

实现位置：`server/apps/backend/app/middleware/family_context.py`、`server/apps/backend/app/auth/deps.py`

- R3.1 `FamilyContextMiddleware` 从 JWT `fid` claim 提取 family_id，注入 `request.state.family_id`
- R3.2 豁免路由：`/api/v1/ai/internal/`、`/api/v1/auth/`、`/api/v1/captcha/`、`/api/health`、`/uploads/`、`/static/`
- R3.3 `get_current_user()` 中验证 JWT payload `fid` 与数据库 `User.family_id` 一致，不一致则 401
- R3.4 现有 router 仍保留手动 `family_id` 过滤（defense-in-depth），中间件提供第一层保护
- R3.5 Agent 请求通过 `ai_deps.py` 中的 `verify_agent_token()` + `X-Family-Id` header 校验
- R3.6 新增 endpoint 默认受 `get_current_user` 依赖保护（fail-closed）

### R4. Rate Limiting on Sensitive Operations（敏感操作独立限流）✅

实现位置：`server/apps/backend/app/services/auth.py`、`server/apps/backend/app/middleware/rate_limit.py`

- R4.1 `/auth/refresh` — 10 次/分钟/用户（`_check_refresh_rate_limit`）
- R4.2 `/auth/me/password` — 3 次/小时/用户（`_check_password_change_rate_limit`）
- R4.3 登录 — 5 次失败后锁定 15 分钟/用户名（`_check_rate_limit`）
- R4.4 注册 — 5 次/小时/IP（`_check_register_rate_limit`）
- R4.5 超限返回 `AppError(ErrorCode.AUTH_RATE_LIMITED)`
- R4.6 限流事件写入 security log：`SecurityEventType.LOGIN_RATE_LIMITED` 等

### R5. Immutable Audit Log Table（不可变安全审计日志）✅

实现位置：`server/packages/db/models/security_audit_log.py`、`server/packages/domain/audit/service.py`

- R5.1 `security_audit_logs` 表，字段：`id, event_type, user_id, family_id, ip_address, user_agent, outcome, detail, created_at`
- R5.2 应用层仅提供 INSERT（`write_audit_log`），无 UPDATE/DELETE 接口
- R5.3 记录事件：login_success, login_failed (wrong_password), token_refresh, password_change
- R5.4 保留策略：90 天，`purge_old_audit_logs(retention_days=90)` 由 scheduler_worker 调用
- R5.5 **缺失**：尚无 `GET /admin/audit-logs` 查询接口
- R5.6 表包含 `event_type`、`user_id`、`family_id`、`created_at` 索引

---

## 残余安全加固需求（下一轮迭代）

以下为代码审查中发现的未覆盖安全边界，按优先级排列：

### R6. Concurrent Refresh Race Condition（并发刷新竞态）

**问题**：两个客户端同时使用同一 refresh token 调用 `/auth/refresh`，若第一个请求尚未完成 JTI 吊销写入，第二个请求可能通过 `_is_jti_revoked` 检查。

**决策：方案 A — INSERT OR IGNORE + rowcount，先吊销再签发**

- R6.1 确保 `revoked_tokens.jti` 列有 UNIQUE 约束
- R6.2 `refresh_token()` 流程调整为：验证旧 token → `INSERT OR IGNORE INTO revoked_tokens` → 检查 affected_rows == 1 → 签发新 token pair
- R6.3 若 affected_rows == 0（已被其他请求消费），立即返回 401，不签发新 token
- R6.4 此方案利用 SQLite UNIQUE 约束的原子性，无需额外锁机制

### R7. Password Strength Validation（密码强度校验）

**问题**：当前 `change_password` 和 `register` 均无密码强度校验，允许弱密码。

- R7.1 最少 8 字符
- R7.2 不与当前密码相同（change_password 场景）
- R7.3 可选：禁止常见弱密码（top 1000 列表）
- R7.4 注册和密码修改共用同一校验逻辑

### R8. Audit Log Query Endpoint（审计日志查询接口）

**问题**：R5.5 尚未实现，owner 无法通过 API 查询安全事件。

- R8.1 `GET /admin/audit-logs`，仅 owner 角色可访问
- R8.2 支持过滤：`event_type`、`user_id`、`date_from`、`date_to`
- R8.3 分页：`page` + `page_size`，默认 20 条/页
- R8.4 响应中 `user_id` 序列化为 string（SnowflakeBase）

### R9. Rate Limit Response Headers（限流响应头）

**问题**：当前超限返回 `AppError` 但不包含 `Retry-After` header，客户端无法智能重试。

- R9.1 超限响应包含 `Retry-After` header（秒数）
- R9.2 HTTP 状态码使用 429（当前通过 AppError 映射，需确认实际返回码）

### R10. Invite Code Rate Limiting（邀请码操作限流）

**问题**：`POST /family/invite-code` 无独立限流，可被滥用生成大量邀请码。

- R10.1 `/family/invite-code` — 5 次/小时/用户
- R10.2 限流事件写入审计日志

### R11. Audit Log Tamper Detection（审计日志防篡改）

**问题**：SQLite 文件可被有物理访问权限的攻击者直接修改或删除。自托管场景下这是现实威胁。

- R11.1 可选：每条日志记录包含前一条的哈希（链式完整性）
- R11.2 可选：定期将审计日志摘要导出到外部存储（如 webhook 推送）
- R11.3 最低限度：记录 `purge_old_audit_logs` 执行事件本身，防止静默清除

---

## Implementation Status

| Requirement | Status | 实现位置 |
|-------------|--------|----------|
| R1 JTI Rotation | ✅ 完成 | `packages/security/revoke_jti.py` |
| R2 Password Change | ✅ 完成 | `services/auth.py` + `routers/auth.py` |
| R3 Family Middleware | ✅ 完成 | `middleware/family_context.py` + `auth/deps.py` |
| R4 Rate Limiting | ✅ 完成 | `services/auth.py` + `middleware/rate_limit.py` |
| R5 Audit Log | ✅ 基本完成 | `packages/domain/audit/service.py` |
| R6 Concurrent Refresh | ⬜ 待实现 | — |
| R7 Password Strength | ⬜ 待实现 | — |
| R8 Audit Query API | ⬜ 待实现 | — |
| R9 Retry-After Header | ⬜ 待实现 | — |
| R10 Invite Code Limit | ⬜ 待实现 | — |
| R11 Tamper Detection | ⬜ 待评估 | — |

---

## Key Decisions

- **数据库持久化 vs 内存吊销**：选择 SQLite `revoked_tokens` 表而非内存缓存，确保服务重启后吊销状态不丢失
- **iat-based 批量吊销**：`revoke_all_user_tokens` 记录吊销时间戳，所有 `iat <= revoked_at` 的 token 均失效，无需逐一记录每个 JTI
- **Defense-in-depth family_id**：中间件注入 + `get_current_user` DB 验证 + router 层手动过滤三层防护
- **密码修改后强制重新登录**：不返回新 token pair，要求用户重新认证，降低被劫持会话继续使用的风险
- **限流 fail-open**：缓存不可用时允许请求通过（`except Exception: pass`），优先可用性

---

## Acceptance Criteria

- [x] Refresh token 使用后旧 token 立即失效（测试：`test_jti_revocation.py`）
- [x] 密码修改后所有其他 session 失效（测试：`test_auth_security.py`）
- [x] 新增 endpoint 默认受 family_id 保护（通过 `get_current_user` 依赖）
- [x] 超限请求被拒绝（测试：`test_rate_limit.py`）
- [x] 审计日志可写入（测试：通过 `write_audit_log` 调用验证）
- [ ] 弱密码被拒绝（测试：少于 8 字符的密码返回 400）（R7 待实现）
- [ ] 审计日志可通过 API 查询（R8 待实现）
- [ ] 并发 refresh 不会导致 token 复用（R6 待实现）

---

## Out of Scope

- Agent JWT 改造（Idea #6）— 依赖本轮 R1 基础设施，作为后续迭代
- Agent 身份审计（Idea #7）— 依赖 #6，作为后续迭代
- Redis 分布式限流 — 当前单实例部署，SQLite + 内存限流足够
- TOTP/WebAuthn 二因素 — 已有 numeric_pin 和 WebAuthn（儿童），成人 TOTP 作为独立需求
- 密码历史记录 — 自托管家庭场景下 ROI 不高，暂不实现
