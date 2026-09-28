# Agent 安全规则

> `server/apps/agent/` 安全约束完整清单。

## 基本规则

1. 所有用户输入不可信 — 过滤 + 长度限制 + XML 包裹
2. PII redaction 强制 (`pii_redactor.redact()`)
3. 新 AI 路径须更新安全规则 + sim-test Area 11 对抗用例
4. 自定义 agent `allowed-tools` 强制声明
5. 系统 prompt 须有不可覆盖的安全前缀

## 认证 & 信任模型

三层信任边界：

| 层 | 端点类型 | 认证方式 | 授权范围 |
|----|----------|----------|----------|
| 外部 | 前端直连 | JWT cookie (`verify_family_token`) | 认证 + family 级授权 |
| 内部 | backend→agent | `X-Agent-Token` | 仅认证调用方服务身份，**不做 family scope 校验** |
| 信任链 | — | — | agent 信任 backend 已做 family authz，backend 信任 JWT 已做 user auth |

**关键**: 内部端点的 family 级授权由调用方 backend 在执行前完成（owner/admin 检查）。

## Credential 两层 Fernet 加密

| Key | 用途 | 回退 |
|-----|------|------|
| `AI_ENCRYPTION_KEY` | 加密 `ai_providers` 表中的 API key（encrypt-at-rest） | — |
| `STORAGE_ENCRYPTION_KEY` | 加密 per-family 临时 config.yaml / extensions_config.json | `SECRET_KEY` SHA256 派生（有 warning） |

新增敏感字段时必须确认使用正确的 key 层级。

## R1 Allowlist 安全边界

| 模式 | 触发方 | R1 校验 | 前置条件 |
|------|--------|---------|----------|
| 前端直连 | 浏览器 | 强制校验 | worker 分支 + sse_gateway start_run 锁步对同步注册 |
| 内部触发 (`internal=True`) | backend | **绕过** R1 app 检查 | 后端触发端点已执行 owner/ai_enabled/concurrency 门控 |

新增 app 时必须明确选择:
- **(A)** 仅 `internal=True` 触发（R1 绕过, 后端门控）
- **(B)** 允许前端直连（R1 强制校验）
